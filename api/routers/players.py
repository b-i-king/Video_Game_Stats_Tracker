from fastapi import APIRouter, HTTPException
from api.core.deps import DynamicConn, CurrentUser, TrustedUser
from api.models.games import UpdatePlayerRequest

router = APIRouter()


@router.get("/get_players")
async def get_players(conn: DynamicConn, user: CurrentUser):
    """Players belonging to the authenticated user only."""
    rows = await conn.fetch("""
        SELECT player_id, player_name
        FROM dim.dim_players
        WHERE user_id = $1
        ORDER BY player_name
    """, user["user_id"])
    return {"players": [dict(r) for r in rows]}


@router.put("/update_player/{player_id}")
async def update_player(player_id: int, body: UpdatePlayerRequest, conn: DynamicConn, user: TrustedUser):
    """Rename a player. Caller must be trusted and own the player."""
    if not body.player_name:
        raise HTTPException(status_code=400, detail="player_name is required.")

    result = await conn.execute("""
        UPDATE dim.dim_players
        SET player_name = $1
        WHERE player_id = $2 AND user_id = $3
    """, body.player_name, player_id, user["user_id"])

    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Player not found or not authorized.")

    print(f"[players] Player {player_id} renamed to '{body.player_name}' by {user['email']}")
    return {"message": "Player updated successfully."}


@router.delete("/delete_player/{player_id}")
async def delete_player(player_id: int, conn: DynamicConn, user: CurrentUser):
    """Delete a player and all their stats. Any authenticated user may delete their own player."""
    owned = await conn.fetchval("""
        SELECT 1 FROM dim.dim_players
        WHERE player_id = $1 AND user_id = $2
    """, player_id, user["user_id"])

    if not owned:
        raise HTTPException(status_code=404, detail="Player not found or permission denied.")

    # Stats cascade automatically via ON DELETE CASCADE on dim.dim_players.
    # Explicit delete kept for the log count.
    deleted_stats = await conn.execute(
        "DELETE FROM fact.fact_game_stats WHERE player_id = $1", player_id
    )
    await conn.execute(
        "DELETE FROM dim.dim_players WHERE player_id = $1", player_id
    )

    print(f"[players] Player {player_id} + stats ({deleted_stats}) deleted by {user['email']}")
    return {"message": "Player and all associated stats deleted."}
