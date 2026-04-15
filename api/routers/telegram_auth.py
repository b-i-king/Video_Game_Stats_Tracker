"""
Telegram Mini App authentication.

POST /telegram_login — verifies Telegram initData HMAC, upserts dim_users row,
                       returns same JWT shape as /api/login.

Security: initData is signed by Telegram using HMAC-SHA256 with a key derived
from the bot token. Verification is MANDATORY — skipping it allows anyone to
forge a Telegram identity and impersonate any user.

Reuses _make_token / _resolve_role / _owner_set / _trusted_set from auth.py
so the JWT payload is identical regardless of login method.
"""

import hashlib
import hmac as _hmac
import json
import os
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.core.deps import DynamicConn, require_api_key
from api.core.database import public_pool
from api.routers.auth import _make_token, _resolve_role, _owner_set, _trusted_set

router = APIRouter()


# ── HMAC verification ─────────────────────────────────────────────────────────

def _verify_init_data(init_data: str, bot_token: str) -> dict:
    """
    Verify Telegram Mini App initData signature.
    Returns the parsed fields on success. Raises ValueError on failure.
    """
    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received = parsed.pop("hash", "")
    if not received:
        raise ValueError("Missing hash in initData")
    data_str = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret   = _hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = _hmac.new(secret, data_str.encode(), hashlib.sha256).hexdigest()
    if not _hmac.compare_digest(expected, received):
        raise ValueError("Invalid initData signature — possible spoofing attempt")
    return parsed


# ── Route ─────────────────────────────────────────────────────────────────────

class TelegramLoginBody(BaseModel):
    init_data: str


@router.post("/telegram_login", dependencies=[Depends(require_api_key)])
async def telegram_login(body: TelegramLoginBody, conn: DynamicConn):
    """
    Exchange Telegram initData for a FastAPI JWT.
    Called server-side from the NextAuth CredentialsProvider — never from the browser directly.
    """
    bot_token = os.getenv("TELEGRAM_BROADCAST_BOT_TOKEN", "")
    if not bot_token:
        raise HTTPException(status_code=503, detail="Telegram bot not configured.")

    # Verify signature
    try:
        parsed = _verify_init_data(body.init_data, bot_token)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    # Extract Telegram user object
    try:
        tg_user = json.loads(parsed.get("user", "{}"))
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed user field in initData.")

    telegram_id: int | None = tg_user.get("id")
    if not telegram_id:
        raise HTTPException(status_code=400, detail="No Telegram user ID in initData.")

    synthetic_email = f"tg_{telegram_id}@telegram.local"

    # ── Upsert dim_users ──────────────────────────────────────────────────────
    existing = await conn.fetchrow(
        "SELECT user_id, user_email, is_trusted FROM dim.dim_users WHERE telegram_user_id = $1",
        telegram_id,
    )

    if existing:
        user_id    = existing["user_id"]
        email      = existing["user_email"]
        is_trusted = bool(existing["is_trusted"])
    else:
        # Check for an existing row with the synthetic email (handles retries)
        by_email = await conn.fetchrow(
            "SELECT user_id, is_trusted FROM dim.dim_users WHERE user_email = $1",
            synthetic_email,
        )
        if by_email:
            user_id    = by_email["user_id"]
            is_trusted = bool(by_email["is_trusted"])
            # Back-fill telegram_user_id if it was missing
            await conn.execute(
                "UPDATE dim.dim_users SET telegram_user_id = $1 WHERE user_id = $2",
                telegram_id, user_id,
            )
        else:
            # Brand-new Telegram user
            user_id = await conn.fetchval("""
                INSERT INTO dim.dim_users (user_email, telegram_user_id, role)
                VALUES ($1, $2, 'registered')
                RETURNING user_id
            """, synthetic_email, telegram_id)
            is_trusted = False
            print(f"[telegram_auth] New Telegram user created: tg_id={telegram_id}")

        email = synthetic_email

    # ── Resolve role (same logic as /api/login) ───────────────────────────────
    is_owner = email in _owner_set()
    # Sync trust from env
    should_be_trusted = email in _trusted_set()
    if should_be_trusted != is_trusted:
        role_val = "trusted" if should_be_trusted else "registered"
        await conn.execute(
            "UPDATE dim.dim_users SET role = $1 WHERE user_id = $2", role_val, user_id
        )
        is_trusted = should_be_trusted

    plan = "free"
    if public_pool:
        async with public_pool.acquire() as pub:
            sub = await pub.fetchval(
                "SELECT plan FROM app.subscriptions WHERE user_id = $1", user_id
            )
            if sub:
                plan = sub

    resolved_role = _resolve_role(email, is_trusted, is_owner, plan)
    token         = _make_token(email, user_id, is_trusted, is_owner, resolved_role)

    return {
        "token":      token,
        "user_id":    user_id,
        "email":      email,
        "role":       resolved_role,
        "is_owner":   is_owner,
        "is_trusted": is_trusted or is_owner,
    }
