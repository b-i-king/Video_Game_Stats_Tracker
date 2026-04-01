from fastapi import APIRouter, HTTPException, status
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt

from api.core.config import get_settings
from api.core.deps import PersonalConn
from api.models.auth import LoginRequest, LoginResponse, AddUserRequest, AddTrustedUserRequest

router = APIRouter()


def _make_token(payload: dict) -> str:
    settings = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({**payload, "exp": exp}, settings.secret_key, algorithm=settings.jwt_algorithm)


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, conn: PersonalConn):
    # TODO: migrate query from flask_app.py /api/login
    row = await conn.fetchrow(
        "SELECT player_id, password_hash, is_trusted FROM dim.dim_users WHERE username = $1",
        body.username,
    )
    if not row or not bcrypt.checkpw(body.password.encode(), row["password_hash"].encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = _make_token({"player_id": row["player_id"], "username": body.username, "is_trusted": row["is_trusted"]})
    return LoginResponse(
        token=token,
        player_id=row["player_id"],
        username=body.username,
        is_trusted=row["is_trusted"],
    )


@router.post("/add_user", status_code=201)
async def add_user(body: AddUserRequest, conn: PersonalConn):
    # TODO: migrate from flask_app.py /api/add_user
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.post("/add_trusted_user", status_code=200)
async def add_trusted_user(body: AddTrustedUserRequest, conn: PersonalConn):
    # TODO: migrate from flask_app.py /api/add_trusted_user
    raise HTTPException(status_code=501, detail="Not yet migrated")
