"""
FastAPI dependency injection helpers.
"""

from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

from api.core.config import get_settings
from api.core.database import personal_pool, public_pool
import asyncpg

bearer = HTTPBearer(auto_error=False)
Settings = Annotated[object, Depends(get_settings)]


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


async def get_personal_conn():
    """Yield a single asyncpg connection from the personal pool."""
    async with personal_pool.acquire() as conn:
        yield conn


async def get_public_conn():
    """Yield a single asyncpg connection from the public pool."""
    if public_pool is None:
        raise HTTPException(status_code=503, detail="Public pool not configured")
    async with public_pool.acquire() as conn:
        yield conn


CurrentUser = Annotated[dict, Depends(get_current_user)]
PersonalConn = Annotated[asyncpg.Connection, Depends(get_personal_conn)]
PublicConn   = Annotated[asyncpg.Connection, Depends(get_public_conn)]
