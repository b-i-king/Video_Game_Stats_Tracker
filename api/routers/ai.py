from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.core.deps import PersonalConn, CurrentUser

router = APIRouter()


class AskRequest(BaseModel):
    message: str
    game_id: int | None = None
    player_id: int | None = None
    tz: str | None = None


@router.post("/ask")
async def ask(body: AskRequest, conn: PersonalConn, user: CurrentUser):
    """
    AI chat endpoint.  Uses gemini-2.0-flash for trusted users, gemini-2.0-flash-lite for free tier.
    Includes last-3-session context via build_stats_context().
    TODO: migrate from flask_app.py /api/ask — wire user["is_trusted"] into ask_agent(trusted=...)
    """
    raise HTTPException(status_code=501, detail="Not yet migrated")
