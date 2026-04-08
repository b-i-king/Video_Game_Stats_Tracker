import asyncio
from fastapi import APIRouter, HTTPException
from api.core.deps import DynamicConn, CurrentUser, TrustedUser
from api.models.games import AddGameRequest, UpdateGameRequest, RequestGameRequest

router = APIRouter()


@router.get("/get_games")
async def get_games(conn: DynamicConn, user: CurrentUser):
    rows = await conn.fetch(
        "SELECT game_id, game_name, game_installment, game_genre, game_subgenre "
        "FROM dim.dim_games ORDER BY game_name"
    )
    return [dict(r) for r in rows]


@router.get("/get_game_franchises")
async def get_game_franchises(conn: DynamicConn, user: CurrentUser):
    """Games the authenticated user has stats for, grouped by franchise name."""
    rows = await conn.fetch("""
        SELECT DISTINCT g.game_name
        FROM dim.dim_games g
        JOIN fact.fact_game_stats gs ON g.game_id = gs.game_id
        JOIN dim.dim_players p ON gs.player_id = p.player_id
        WHERE p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = $1)
        AND g.game_name IS NOT NULL
        ORDER BY g.game_name
    """, user["email"])
    return {"game_franchises": [r["game_name"] for r in rows]}


@router.get("/get_game_installments/{franchise_name:path}")
async def get_game_installments(franchise_name: str, conn: DynamicConn, user: CurrentUser):
    """Game IDs + installment names for a franchise, scoped to the user."""
    rows = await conn.fetch("""
        SELECT DISTINCT g.game_id, g.game_installment
        FROM dim.dim_games g
        JOIN fact.fact_game_stats gs ON g.game_id = gs.game_id
        JOIN dim.dim_players p ON gs.player_id = p.player_id
        WHERE p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = $1)
        AND g.game_name = $2
        ORDER BY g.game_installment
    """, user["email"], franchise_name)
    return {
        "game_installments": [
            {"game_id": r["game_id"], "installment_name": r["game_installment"] or "(Main Game)"}
            for r in rows
        ]
    }


@router.get("/get_game_ranks/{game_id}")
async def get_game_ranks(game_id: int, conn: DynamicConn, user: CurrentUser):
    """Distinct rank values seen for a game, scoped to the user."""
    rows = await conn.fetch("""
        SELECT DISTINCT rank_value FROM (
            SELECT pre_match_rank_value AS rank_value FROM fact.fact_game_stats gs
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE gs.game_id = $1 AND gs.ranked = 1 AND gs.pre_match_rank_value IS NOT NULL
            AND p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = $2)
            UNION
            SELECT post_match_rank_value AS rank_value FROM fact.fact_game_stats gs
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE gs.game_id = $1 AND gs.ranked = 1 AND gs.post_match_rank_value IS NOT NULL
            AND p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = $2)
        ) AS combined_ranks
        WHERE rank_value IS NOT NULL AND rank_value != ''
        ORDER BY rank_value
    """, game_id, user["email"])
    return {"ranks": [r["rank_value"] for r in rows]}


@router.get("/get_game_modes/{game_id}")
async def get_game_modes(game_id: int, conn: DynamicConn, user: CurrentUser):
    """Distinct game modes for a game, scoped to the user."""
    rows = await conn.fetch("""
        SELECT DISTINCT game_mode
        FROM fact.fact_game_stats gs
        JOIN dim.dim_players p ON gs.player_id = p.player_id
        WHERE gs.game_id = $1
        AND p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = $2)
        AND gs.game_mode IS NOT NULL AND gs.game_mode != ''
        ORDER BY game_mode
    """, game_id, user["email"])
    return {"game_modes": [r["game_mode"] for r in rows]}


@router.get("/get_game_stat_types/{game_id}")
async def get_game_stat_types(game_id: int, conn: DynamicConn, user: CurrentUser):
    """Distinct stat types for a game, scoped to the user."""
    rows = await conn.fetch("""
        SELECT DISTINCT gs.stat_type
        FROM fact.fact_game_stats gs
        JOIN dim.dim_players p ON gs.player_id = p.player_id
        WHERE gs.game_id = $1
        AND p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = $2)
        AND gs.stat_type IS NOT NULL AND gs.stat_type != ''
        ORDER BY stat_type
    """, game_id, user["email"])
    return {"stat_types": [r["stat_type"] for r in rows]}


@router.get("/get_game_context/{game_id}")
async def get_game_context(game_id: int, conn: DynamicConn, user: CurrentUser):
    """Ranks + modes + stat types in a single round-trip. Replaces 3 separate calls."""
    email = user["email"]

    ranks_rows, modes_rows, types_rows = await asyncio.gather(
        conn.fetch("""
            SELECT DISTINCT rank_value FROM (
                SELECT pre_match_rank_value AS rank_value FROM fact.fact_game_stats gs
                JOIN dim.dim_players p ON gs.player_id = p.player_id
                WHERE gs.game_id = $1 AND gs.ranked = 1 AND gs.pre_match_rank_value IS NOT NULL
                AND p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = $2)
                UNION
                SELECT post_match_rank_value AS rank_value FROM fact.fact_game_stats gs
                JOIN dim.dim_players p ON gs.player_id = p.player_id
                WHERE gs.game_id = $1 AND gs.ranked = 1 AND gs.post_match_rank_value IS NOT NULL
                AND p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = $2)
            ) AS combined_ranks
            WHERE rank_value IS NOT NULL AND rank_value != ''
            ORDER BY rank_value
        """, game_id, email),
        conn.fetch("""
            SELECT DISTINCT game_mode FROM fact.fact_game_stats gs
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE gs.game_id = $1
            AND p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = $2)
            AND gs.game_mode IS NOT NULL AND gs.game_mode != ''
            ORDER BY game_mode
        """, game_id, email),
        conn.fetch("""
            SELECT DISTINCT gs.stat_type FROM fact.fact_game_stats gs
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE gs.game_id = $1
            AND p.user_id = (SELECT user_id FROM dim.dim_users WHERE user_email = $2)
            AND gs.stat_type IS NOT NULL AND gs.stat_type != ''
            ORDER BY stat_type
        """, game_id, email),
    )

    return {
        "ranks":      [r["rank_value"] for r in ranks_rows],
        "modes":      [r["game_mode"]  for r in modes_rows],
        "stat_types": [r["stat_type"]  for r in types_rows],
    }


@router.post("/add_game", status_code=201)
async def add_game(body: AddGameRequest, conn: DynamicConn, user: TrustedUser):
    """
    Add a new game to the catalog. Trusted/Owner only.
    Fields are sourced from IGDB lookup or manual input.
    Returns the new game_id, or the existing one if the game already exists.
    """
    # Check for duplicate (game_name + game_installment must be unique)
    if body.game_installment:
        existing = await conn.fetchval(
            "SELECT game_id FROM dim.dim_games WHERE game_name = $1 AND game_installment = $2",
            body.game_name, body.game_installment,
        )
    else:
        existing = await conn.fetchval(
            "SELECT game_id FROM dim.dim_games WHERE game_name = $1 AND game_installment IS NULL",
            body.game_name,
        )

    if existing:
        return {"game_id": existing, "message": "Game already exists.", "created": False}

    game_id = await conn.fetchval("""
        INSERT INTO dim.dim_games (game_name, game_installment, game_genre, game_subgenre, created_at, last_played_at)
        VALUES ($1, $2, $3, $4, NOW(), NOW())
        RETURNING game_id
    """, body.game_name, body.game_installment, body.game_genre, body.game_subgenre)

    print(f"[games] Game '{body.game_name}' ('{body.game_installment}') added by {user['email']}")
    return {"game_id": game_id, "message": "Game added successfully.", "created": True}


@router.post("/request_game", status_code=201)
async def request_game(body: RequestGameRequest, conn: DynamicConn, user: CurrentUser):
    """
    Free/Premium users request a game be added to the catalog.
    Writes to app.game_requests for Trusted/Owner review.
    Returns existing request_id if already pending.
    """
    existing = await conn.fetchval("""
        SELECT request_id FROM app.game_requests
        WHERE user_email = $1 AND game_name = $2
        AND (game_installment = $3 OR (game_installment IS NULL AND $3 IS NULL))
        AND status = 'pending'
    """, user["email"], body.game_name, body.game_installment)

    if existing:
        return {"request_id": existing, "message": "A pending request for this game already exists."}

    request_id = await conn.fetchval("""
        INSERT INTO app.game_requests (user_email, game_name, game_installment, status, created_at)
        VALUES ($1, $2, $3, 'pending', NOW())
        RETURNING request_id
    """, user["email"], body.game_name, body.game_installment)

    print(f"[games] Game request '{body.game_name}' submitted by {user['email']}")
    return {"request_id": request_id, "message": "Game request submitted successfully."}


@router.put("/update_game/{game_id}")
async def update_game(game_id: int, body: UpdateGameRequest, conn: DynamicConn, user: TrustedUser):
    """Update game metadata. Trusted/Owner only."""
    result = await conn.execute("""
        UPDATE dim.dim_games SET
            game_name        = COALESCE($1, game_name),
            game_installment = COALESCE($2, game_installment),
            game_genre       = COALESCE($3, game_genre),
            game_subgenre    = COALESCE($4, game_subgenre)
        WHERE game_id = $5
    """, body.game_name, body.game_installment, body.game_genre, body.game_subgenre, game_id)

    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Game not found.")

    print(f"[games] Game {game_id} updated by {user['email']}")
    return {"message": "Game updated successfully."}


@router.delete("/delete_game/{game_id}", status_code=204)
async def delete_game(game_id: int, conn: DynamicConn, user: TrustedUser):
    raise HTTPException(status_code=501, detail="Not yet migrated")


@router.get("/get_game_details/{game_id}")
async def get_game_details(game_id: int, conn: DynamicConn, user: CurrentUser):
    raise HTTPException(status_code=501, detail="Not yet migrated")
