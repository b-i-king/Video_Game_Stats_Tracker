"""
Auth router — /api/login, /api/add_user, /api/add_trusted_user

Login flow (Google OAuth via NextAuth):
  NextAuth → POST /api/login with { email } + X-API-KEY header
  FastAPI  → upserts dim.dim_users, syncs trust status from TRUSTED_EMAILS env,
             returns JWT + is_trusted + is_owner

Both add_user and login auto-create users on first sign-in so no pre-seeding
is needed. add_trusted_user is owner-only for manual role management.
"""

import time
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status

from api.core.config import get_settings
from api.core.deps import PersonalConn, DynamicConn, OwnerUser, require_api_key
from api.models.auth import (
    AddTrustedUserRequest,
    AddUserRequest,
    LoginRequest,
    LoginResponse,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory user cache — avoids a DB round-trip on every JWT refresh
# TTL: 300 s (5 min). Keyed by email → (user_id, is_trusted, expires_at)
# ---------------------------------------------------------------------------

_user_cache: dict = {}


def _cache_get(email: str):
    entry = _user_cache.get(email)
    if entry and time.monotonic() < entry[2]:
        return entry[0], entry[1]   # user_id, is_trusted
    _user_cache.pop(email, None)
    return None


def _cache_set(email: str, user_id: int, is_trusted: bool, ttl: int = 300):
    _user_cache[email] = (user_id, is_trusted, time.monotonic() + ttl)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _make_token(email: str, user_id: int, is_trusted: bool, is_owner: bool = False, role: str = "free") -> str:
    settings = get_settings()
    payload = {
        "email": email,
        "user_id": user_id,
        "is_trusted": is_trusted or is_owner,  # owners have all trusted privileges
        "is_owner": is_owner,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def _owner_set() -> set[str]:
    return {e.strip().lower() for e in get_settings().owner_emails.split(",") if e.strip()}


def _trusted_set() -> set[str]:
    return {e.strip().lower() for e in get_settings().trusted_emails.split(",") if e.strip()}


def _resolve_role(email: str, is_trusted: bool, is_owner: bool, plan: str) -> str:
    """Derive the display role from the user's flags and subscription plan.

    Priority: owner > trusted > premium > free
    plan comes from app.subscriptions on the public DB — defaults to 'free'
    until Stripe integration is wired in Phase 3.
    """
    if is_owner:
        return "owner"
    if is_trusted:
        return "trusted"
    if plan == "premium":
        return "premium"
    return "free"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse, dependencies=[Depends(require_api_key)])
async def login(body: LoginRequest, conn: PersonalConn):
    """
    Exchange a verified Google email for a FastAPI JWT.
    Creates a new dim.dim_users row if the email is not yet registered.
    Syncs trust status from the TRUSTED_EMAILS env var on every call.
    """
    email = body.email.lower().strip()
    should_be_trusted = email in _trusted_set()
    target_role = "trusted" if should_be_trusted else "registered"

    # Fast path — skip DB if cache is warm and trust status hasn't changed
    cached = _cache_get(email)
    if cached:
        user_id, db_is_trusted = cached
        if should_be_trusted == db_is_trusted:
            is_owner = email in _owner_set()
            from api.core.database import public_pool
            plan = "free"
            if public_pool:
                async with public_pool.acquire() as pub:
                    sub = await pub.fetchval(
                        "SELECT plan FROM app.subscriptions WHERE user_id = $1", user_id
                    )
                    if sub:
                        plan = sub
            resolved_role = _resolve_role(email, db_is_trusted, is_owner, plan)
            return LoginResponse(
                token=_make_token(email, user_id, db_is_trusted, is_owner, resolved_role),
                user_id=user_id,
                is_trusted=db_is_trusted or is_owner,
                is_owner=is_owner,
                role=resolved_role,
            )

    row = await conn.fetchrow(
        "SELECT user_id, is_trusted FROM dim.dim_users WHERE user_email = $1",
        email,
    )

    if row is None:
        # New user — insert then re-fetch to get DB-generated user_id + is_trusted
        await conn.execute(
            "INSERT INTO dim.dim_users (user_email, role) VALUES ($1, $2)",
            email, target_role,
        )
        row = await conn.fetchrow(
            "SELECT user_id, is_trusted FROM dim.dim_users WHERE user_email = $1",
            email,
        )
        if row is None:
            raise HTTPException(status_code=500, detail="Failed to create user")
        print(f"[auth] New user created: {email}, role={target_role}")
    else:
        # Sync trust status if env list has changed
        if bool(row["is_trusted"]) != should_be_trusted:
            await conn.execute(
                "UPDATE dim.dim_users SET role = $1 WHERE user_id = $2",
                target_role, row["user_id"],
            )
            print(f"[auth] Trust synced for {email} → {target_role}")
            # Re-fetch to pick up the generated is_trusted column
            row = await conn.fetchrow(
                "SELECT user_id, is_trusted FROM dim.dim_users WHERE user_email = $1",
                email,
            )

    user_id = row["user_id"]
    db_is_trusted = bool(row["is_trusted"])
    is_owner = email in _owner_set()
    _cache_set(email, user_id, db_is_trusted)

    from api.core.database import public_pool
    plan = "free"
    if public_pool:
        async with public_pool.acquire() as pub:
            sub = await pub.fetchval(
                "SELECT plan FROM app.subscriptions WHERE user_id = $1", user_id
            )
            if sub:
                plan = sub
    resolved_role = _resolve_role(email, db_is_trusted, is_owner, plan)

    return LoginResponse(
        token=_make_token(email, user_id, db_is_trusted, is_owner, resolved_role),
        user_id=user_id,
        is_trusted=db_is_trusted or is_owner,
        is_owner=is_owner,
        role=resolved_role,
    )


@router.post("/add_user", status_code=201, dependencies=[Depends(require_api_key)])
async def add_user(body: AddUserRequest, conn: DynamicConn):
    """
    Register a new user as non-trusted if they don't already exist.
    Idempotent — returns 200 if the user already exists.
    """
    email = body.email.lower().strip()

    exists = await conn.fetchval(
        "SELECT 1 FROM dim.dim_users WHERE user_email = $1", email
    )
    if exists:
        return {"message": f"User {email} already exists."}

    await conn.execute(
        "INSERT INTO dim.dim_users (user_email, role) VALUES ($1, 'registered')",
        email,
    )
    print(f"[auth] Registered guest user: {email}")
    return {"message": f"User {email} registered successfully."}


@router.post("/add_trusted_user", status_code=200)
async def add_trusted_user(
    body: AddTrustedUserRequest,
    conn: DynamicConn,
    _owner: OwnerUser,
):
    """
    Owner-only: manually set a user's trust status.
    Creates the user if they don't exist.
    """
    email = body.email.lower().strip()
    role = "trusted" if body.is_trusted else "registered"

    existing = await conn.fetchrow(
        "SELECT user_id FROM dim.dim_users WHERE user_email = $1", email
    )
    if existing:
        await conn.execute(
            "UPDATE dim.dim_users SET role = $1 WHERE user_email = $2",
            role, email,
        )
        print(f"[auth] Role updated: {email} → {role}")
    else:
        await conn.execute(
            "INSERT INTO dim.dim_users (user_email, role) VALUES ($1, $2)",
            email, role,
        )
        print(f"[auth] New user added: {email}, role={role}")

    # Invalidate cache so the change is reflected on next login
    _user_cache.pop(email, None)

    return {"message": f"User {email} updated. Trusted: {body.is_trusted}."}
