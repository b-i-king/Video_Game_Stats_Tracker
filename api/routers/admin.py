"""
Admin routes — Owner only.

  POST /sync_game_to_public  — copy a game from personal → public dim.dim_games

IGDB-ready: accepts optional stat_types / game_modes / platforms JSONB fields
so that when IGDB integration arrives, the same endpoint fills them automatically.
"""

import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.core.deps import OwnerUser
from api.core.database import personal_pool, public_pool

router = APIRouter()


class SyncGameRequest(BaseModel):
    game_name:        str
    game_installment: str | None = None
    game_genre:       str | None = None
    game_subgenre:    str | None = None
    # IGDB nice-haves — stored as JSONB, ignored until IGDB integration lands
    stat_types:       list[str] | None = None
    game_modes:       list[str] | None = None
    platforms:        list[str] | None = None


@router.post("/sync_game_to_public", status_code=201)
async def sync_game_to_public(body: SyncGameRequest, user: OwnerUser):
    """
    Copy a game from the personal dim.dim_games catalog to the public one.
    Owner only. Idempotent — if the game already exists on public (same name +
    installment), updates the genre/subgenre fields and returns 200.

    This is the single write path for the public game catalog:
      - Called manually by owner now
      - Will be called automatically when a game_request is approved
      - Will be called with IGDB-populated fields when that integration lands
    """
    if public_pool is None:
        raise HTTPException(status_code=503, detail="Public pool not available.")

    # --- Verify the game exists on personal first ---
    async with personal_pool.acquire() as pconn:
        personal_row = await pconn.fetchrow("""
            SELECT game_id, game_name, game_installment, game_genre, game_subgenre,
                   stat_types, game_modes, platforms
            FROM dim.dim_games
            WHERE game_name = $1
              AND (game_installment = $2 OR (game_installment IS NULL AND $2 IS NULL))
        """, body.game_name, body.game_installment)

    if not personal_row:
        raise HTTPException(
            status_code=404,
            detail=f"Game '{body.game_name}' not found in personal catalog. Add it there first.",
        )

    # Prefer request body values; fall back to personal row values
    genre      = body.game_genre    or personal_row["game_genre"]
    subgenre   = body.game_subgenre or personal_row["game_subgenre"]
    stat_types = json.dumps(body.stat_types  or [])
    game_modes = json.dumps(body.game_modes  or [])
    platforms  = json.dumps(body.platforms   or [])

    async with public_pool.acquire() as qconn:
        existing = await qconn.fetchrow("""
            SELECT game_id FROM dim.dim_games
            WHERE game_name = $1
              AND (game_installment = $2 OR (game_installment IS NULL AND $2 IS NULL))
        """, body.game_name, body.game_installment)

        if existing:
            # Idempotent update — refresh metadata if changed
            await qconn.execute("""
                UPDATE dim.dim_games
                SET game_genre    = $1,
                    game_subgenre = $2,
                    stat_types    = $3::jsonb,
                    game_modes    = $4::jsonb,
                    platforms     = $5::jsonb
                WHERE game_id = $6
            """, genre, subgenre, stat_types, game_modes, platforms, existing["game_id"])

            print(f"[admin] Game '{body.game_name}' already on public — metadata updated by {user['email']}")
            return {
                "status":  "updated",
                "game_id": existing["game_id"],
                "message": f"'{body.game_name}' already exists on public — metadata refreshed.",
            }

        # Insert new game into public catalog
        new_id = await qconn.fetchval("""
            INSERT INTO dim.dim_games
                (game_name, game_installment, game_genre, game_subgenre,
                 stat_types, game_modes, platforms)
            VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb)
            RETURNING game_id
        """, body.game_name, body.game_installment, genre, subgenre,
             stat_types, game_modes, platforms)

    print(f"[admin] '{body.game_name}' synced to public (game_id={new_id}) by {user['email']}")
    return {
        "status":  "created",
        "game_id": new_id,
        "message": f"'{body.game_name}' successfully added to public catalog.",
    }
