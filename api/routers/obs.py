from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.core.deps import PersonalConn, CurrentUser

router = APIRouter()


class LiveStateRequest(BaseModel):
    player_id: int
    game_id: int


@router.post("/set_live_state")
async def set_live_state(body: LiveStateRequest, conn: PersonalConn, user: CurrentUser):
    """
    Upsert into dim.dim_dashboard_state.
    Uses INSERT ... ON CONFLICT DO UPDATE so it works even on empty table.
    """
    await conn.execute(
        """
        INSERT INTO dim.dim_dashboard_state (state_id, current_player_id, current_game_id, updated_at)
        VALUES (1, $1, $2, NOW())
        ON CONFLICT (state_id) DO UPDATE
            SET current_player_id = EXCLUDED.current_player_id,
                current_game_id   = EXCLUDED.current_game_id,
                updated_at        = EXCLUDED.updated_at
        """,
        body.player_id,
        body.game_id,
    )
    return {"status": "ok"}


@router.get("/obs_status")
async def obs_status(conn: PersonalConn):
    # TODO: migrate from flask_app.py /api/obs_status
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.post("/set_obs_active")
async def set_obs_active(conn: PersonalConn, user: CurrentUser):
    # TODO: migrate from flask_app.py /api/set_obs_active
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.get("/get_live_dashboard")
async def get_live_dashboard(conn: PersonalConn):
    # TODO: migrate from flask_app.py /api/get_live_dashboard
    raise HTTPException(status_code=501, detail="Not yet migrated")
