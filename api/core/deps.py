"""
FastAPI dependency injection helpers.
"""

from typing import Annotated
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import asyncpg

from api.core.config import get_settings
from api.core import database

bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# API key
# ---------------------------------------------------------------------------

async def require_api_key(x_api_key: str = Header(...)):
    """Validates X-API-KEY header. Used on admin and login endpoints."""
    settings = get_settings()
    if not settings.api_key or x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def _decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return _decode_token(credentials.credentials)


# ---------------------------------------------------------------------------
# Role guards
# ---------------------------------------------------------------------------

async def require_trusted(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    """Blocks access unless the JWT carries is_trusted=True."""
    if not user.get("is_trusted"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Trusted access required")
    return user


async def require_owner(user: Annotated[dict, Depends(get_current_user)]) -> dict:
    """Blocks access unless the caller's email is in OWNER_EMAILS."""
    settings = get_settings()
    owner_set = {e.strip().lower() for e in settings.owner_emails.split(",") if e.strip()}
    if user.get("email", "").lower() not in owner_set:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner access required")
    return user


# ---------------------------------------------------------------------------
# DB connection helpers
# ---------------------------------------------------------------------------

async def get_personal_conn():
    """Yield a connection from the personal (owner) pool. Use for personal-only features."""
    async with database.personal_pool.acquire() as conn:
        yield conn


async def get_public_conn():
    """Yield a connection from the public (multi-tenant) pool."""
    if database.public_pool is None:
        raise HTTPException(status_code=503, detail="Public pool not configured")
    async with database.public_pool.acquire() as conn:
        yield conn


async def get_current_user_optional(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict | None:
    """Like get_current_user but returns None instead of raising 401 (used by DynamicConn)."""
    if not credentials:
        return None
    try:
        return _decode_token(credentials.credentials)
    except HTTPException:
        return None


async def get_dynamic_conn(
    user: Annotated[dict | None, Depends(get_current_user_optional)],
):
    """
    Route to the appropriate pool based on caller role:
      Owner  → personal_pool  (single-tenant, your data)
      Others → public_pool    (multi-tenant, all users)
    Falls back to public_pool when no valid JWT is present.
    Use PersonalConn directly for personal-only features (OBS browser source,
    post_queue, instagram) that have no JWT or must always hit the personal DB.
    """
    if user and user.get("is_owner"):
        async with database.personal_pool.acquire() as conn:
            yield conn
    elif database.public_pool is not None:
        async with database.public_pool.acquire() as conn:
            yield conn
    else:
        # PUBLIC_DB_URL not yet configured — fall back to personal during transition.
        # Once the public Supabase project is live, set PUBLIC_DB_URL on Render and
        # this branch will stop being reached.
        async with database.personal_pool.acquire() as conn:
            yield conn


# ---------------------------------------------------------------------------
# Annotated type aliases — use these in route signatures
# ---------------------------------------------------------------------------

CurrentUser   = Annotated[dict, Depends(get_current_user)]
TrustedUser   = Annotated[dict, Depends(require_trusted)]
OwnerUser     = Annotated[dict, Depends(require_owner)]
PersonalConn  = Annotated[asyncpg.Connection, Depends(get_personal_conn)]
PublicConn    = Annotated[asyncpg.Connection, Depends(get_public_conn)]
DynamicConn   = Annotated[asyncpg.Connection, Depends(get_dynamic_conn)]
