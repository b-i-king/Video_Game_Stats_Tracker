"""
Referral program routes.

GET  /referral/code    — return (or auto-create) the caller's referral code + stats
POST /referral/record  — record that the current user was referred by a code (idempotent)

Env vars:
  REFERRAL_COMMISSION_PCT  — integer commission percentage (default: 10)
  NEXT_PUBLIC_APP_URL      — used to build the referral link in the response
"""

import os
import secrets

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.core.deps import DynamicConn, CurrentUser
from api.core.database import public_pool

router = APIRouter()

_COMMISSION_PCT = int(os.getenv("REFERRAL_COMMISSION_PCT", "10"))


def _app_url() -> str:
    return os.getenv("NEXT_PUBLIC_APP_URL", "").rstrip("/")


def _make_code() -> str:
    """8-character URL-safe alphanumeric code, e.g. 'A3F2BC91'."""
    return secrets.token_urlsafe(6)[:8].upper()


# ── GET /referral/code ────────────────────────────────────────────────────────

@router.get("/referral/code")
async def get_referral_code(conn: DynamicConn, user: CurrentUser):
    """
    Return the authenticated user's referral code.
    Auto-creates one on first call. Returns the full shareable link + earnings.
    """
    if public_pool is None:
        raise HTTPException(status_code=503, detail="Public pool not available.")

    async with public_pool.acquire() as pconn:
        row = await pconn.fetchrow(
            "SELECT id, code, total_earned_cents FROM app.referral_codes WHERE user_id = $1",
            user["user_id"],
        )

        if not row:
            # Generate a unique code (retry on the rare collision)
            for _ in range(5):
                code = _make_code()
                exists = await pconn.fetchval(
                    "SELECT 1 FROM app.referral_codes WHERE code = $1", code
                )
                if not exists:
                    break
            else:
                raise HTTPException(status_code=500, detail="Could not generate unique code.")

            await pconn.execute(
                "INSERT INTO app.referral_codes (user_id, code) VALUES ($1, $2)",
                user["user_id"], code,
            )
            row = await pconn.fetchrow(
                "SELECT id, code, total_earned_cents FROM app.referral_codes WHERE user_id = $1",
                user["user_id"],
            )

        # Count referrals for this code
        stats = await pconn.fetchrow("""
            SELECT
                COUNT(*)                              AS total_referred,
                COUNT(converted_at)                   AS converted,
                COALESCE(SUM(total_earned_cents), 0)  AS earned_cents
            FROM app.referrals
            WHERE referral_code_id = $1
        """, row["id"])

    site = _app_url()
    link = f"{site}?ref={row['code']}" if site else f"?ref={row['code']}"

    return {
        "code":              row["code"],
        "link":              link,
        "commission_pct":    _COMMISSION_PCT,
        "total_referred":    int(stats["total_referred"]),
        "converted":         int(stats["converted"]),
        "total_earned_cents": int(stats["earned_cents"]),
        "total_earned_usd":  round(int(stats["earned_cents"]) / 100, 2),
    }


# ── POST /referral/record ─────────────────────────────────────────────────────

class RecordReferralBody(BaseModel):
    code: str


@router.post("/referral/record", status_code=201)
async def record_referral(body: RecordReferralBody, conn: DynamicConn, user: CurrentUser):
    """
    Record that the current user arrived via a referral link.
    Idempotent — safe to call multiple times; ignores self-referral.
    """
    if public_pool is None:
        raise HTTPException(status_code=503, detail="Public pool not available.")

    code = body.code.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="code is required.")

    async with public_pool.acquire() as pconn:
        # Look up the code
        code_row = await pconn.fetchrow(
            "SELECT id, user_id FROM app.referral_codes WHERE code = $1", code
        )
        if not code_row:
            # Unknown code — silently succeed (don't expose whether a code exists)
            return {"status": "ok"}

        # Prevent self-referral
        if code_row["user_id"] == user["user_id"]:
            return {"status": "ok"}

        # Idempotent upsert — do nothing if this user is already recorded
        await pconn.execute("""
            INSERT INTO app.referrals (referral_code_id, referred_user_id)
            VALUES ($1, $2)
            ON CONFLICT (referred_user_id) DO NOTHING
        """, code_row["id"], user["user_id"])

    return {"status": "ok"}
