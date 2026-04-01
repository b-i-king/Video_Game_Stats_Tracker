from fastapi import APIRouter, HTTPException
from api.core.deps import PersonalConn, CurrentUser
from api.models.games import UpdatePlayerRequest

router = APIRouter()


@router.get("/get_players")
async def get_players(conn: PersonalConn):
    # TODO: migrate from flask_app.py /api/get_players
    rows = await conn.fetch(
        "SELECT player_id, player_name, display_name, is_active FROM dim.dim_players ORDER BY player_name"
    )
    return [dict(r) for r in rows]


@router.put("/update_player/{player_id}")
async def update_player(player_id: int, body: UpdatePlayerRequest, conn: PersonalConn, user: CurrentUser):
    # TODO: migrate from flask_app.py /api/update_player
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.delete("/delete_player/{player_id}", status_code=204)
async def delete_player(player_id: int, conn: PersonalConn, user: CurrentUser):
    # TODO: migrate from flask_app.py /api/delete_player
    raise HTTPException(status_code=501, detail="Not yet migrated")
