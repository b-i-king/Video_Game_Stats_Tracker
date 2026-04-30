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
from api.core.database import public_pool, personal_pool as _personal_pool
from api.routers.auth import _make_token, _resolve_role, _owner_set, _trusted_set


def _telegram_owner_id_set() -> set[int]:
    """
    Telegram user IDs that belong to owner accounts.
    Set TELEGRAM_OWNER_IDS on Render (comma-separated numeric IDs).
    Needed because Telegram logins carry no email — we can't match against OWNER_EMAILS.
    Find your Telegram ID by messaging @userinfobot.
    """
    raw = os.getenv("TELEGRAM_OWNER_IDS", "")
    return {int(i.strip()) for i in raw.split(",") if i.strip().isdigit()}

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


async def _process_telegram_auth(body: TelegramLoginBody, conn) -> dict:
    """
    Core Telegram initData verification + user upsert, shared by both auth routes.
    conn is the public-pool connection from DynamicConn (owner path uses personal_pool directly).
    """
    bot_token = os.getenv("TELEGRAM_BROADCAST_BOT_TOKEN", "")
    if not bot_token:
        raise HTTPException(status_code=503, detail="Telegram bot not configured.")

    try:
        parsed = _verify_init_data(body.init_data, bot_token)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    try:
        tg_user = json.loads(parsed.get("user", "{}"))
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed user field in initData.")

    telegram_id: int | None = tg_user.get("id")
    if not telegram_id:
        raise HTTPException(status_code=400, detail="No Telegram user ID in initData.")

    # ── Owner path: personal pool ─────────────────────────────────────────────
    if telegram_id in _telegram_owner_id_set():
        async with _personal_pool.acquire() as pconn:
            owner_row = await pconn.fetchrow(
                "SELECT user_id, user_email FROM dim.dim_users WHERE user_email = ANY($1::text[])",
                list(_owner_set()),
            )
        if not owner_row:
            raise HTTPException(status_code=404, detail="Owner account not found in personal DB.")
        user_id       = owner_row["user_id"]
        email         = owner_row["user_email"]
        resolved_role = _resolve_role(email, True, True, "premium")
        token         = _make_token(email, user_id, True, True, resolved_role)
        display_name = tg_user.get("first_name") or email.split("@")[0]
        return {
            "token":        token,
            "user_id":      user_id,
            "email":        email,
            "role":         resolved_role,
            "is_owner":     True,
            "is_trusted":   True,
            "display_name": display_name,
        }

    # ── Public user path ──────────────────────────────────────────────────────
    synthetic_email = f"tg_{telegram_id}@telegram.local"

    existing = await conn.fetchrow(
        "SELECT user_id, user_email, is_trusted FROM dim.dim_users WHERE telegram_user_id = $1",
        telegram_id,
    )

    if existing:
        user_id    = existing["user_id"]
        email      = existing["user_email"]
        is_trusted = bool(existing["is_trusted"])
    else:
        by_email = await conn.fetchrow(
            "SELECT user_id, is_trusted FROM dim.dim_users WHERE user_email = $1",
            synthetic_email,
        )
        if by_email:
            user_id    = by_email["user_id"]
            is_trusted = bool(by_email["is_trusted"])
            await conn.execute(
                "UPDATE dim.dim_users SET telegram_user_id = $1 WHERE user_id = $2",
                telegram_id, user_id,
            )
        else:
            user_id = await conn.fetchval("""
                INSERT INTO dim.dim_users (user_email, telegram_user_id, role)
                VALUES ($1, $2, 'registered')
                RETURNING user_id
            """, synthetic_email, telegram_id)
            is_trusted = False
            print(f"[telegram_auth] New Telegram user created: tg_id={telegram_id}")
        email = synthetic_email

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

    resolved_role = _resolve_role(email, is_trusted, False, plan)
    token         = _make_token(email, user_id, is_trusted, False, resolved_role)
    display_name  = tg_user.get("first_name") or f"Player {str(telegram_id)[:6]}"
    return {
        "token":        token,
        "user_id":      user_id,
        "email":        email,
        "role":         resolved_role,
        "is_owner":     False,
        "is_trusted":   is_trusted,
        "display_name": display_name,
    }


@router.post("/telegram_login", dependencies=[Depends(require_api_key)])
async def telegram_login(body: TelegramLoginBody, conn: DynamicConn):
    """
    Exchange Telegram initData for a JWT.
    Called server-side from the NextAuth CredentialsProvider — not directly from the browser.
    """
    return await _process_telegram_auth(body, conn)


@router.post("/game/auth")
async def game_auth(body: TelegramLoginBody, conn: DynamicConn):
    """
    Browser-facing auth for Telegram Mini App games.
    Same HMAC logic and upsert path as /telegram_login but no API-key gate —
    the game iframe calls this directly at load time to obtain a short-lived JWT.
    """
    return await _process_telegram_auth(body, conn)
