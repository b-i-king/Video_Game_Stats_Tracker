import asyncio
from datetime import timezone, datetime

from fastapi import APIRouter, HTTPException
from api.core.deps import DynamicConn, CurrentUser, TrustedUser
from api.models.games import AddGameRequest, UpdateGameRequest, RequestGameRequest, GameScoreRequest

router = APIRouter()


@router.get("/get_games")
async def get_games(conn: DynamicConn, user: CurrentUser):
    rows = await conn.fetch(
        "SELECT game_id, game_name, game_installment, game_genre, game_subgenre "
        "FROM dim.dim_games ORDER BY game_name"
    )
    return {"games": [dict(r) for r in rows]}


@router.get("/get_game_franchises")
async def get_game_franchises(conn: DynamicConn, user: CurrentUser):
    """Games the authenticated user has stats for, grouped by franchise name."""
    rows = await conn.fetch("""
        SELECT DISTINCT g.game_name
        FROM dim.dim_games g
        JOIN fact.fact_game_stats gs ON g.game_id = gs.game_id
        JOIN dim.dim_players p ON gs.player_id = p.player_id
        WHERE p.user_id = $1 AND g.game_name IS NOT NULL
        ORDER BY g.game_name
    """, user["user_id"])
    return {"game_franchises": [r["game_name"] for r in rows]}


@router.get("/get_game_installments/{franchise_name:path}")
async def get_game_installments(franchise_name: str, conn: DynamicConn, user: CurrentUser):
    """Game IDs + installment names for a franchise, scoped to the user."""
    rows = await conn.fetch("""
        SELECT DISTINCT g.game_id, g.game_installment
        FROM dim.dim_games g
        JOIN fact.fact_game_stats gs ON g.game_id = gs.game_id
        JOIN dim.dim_players p ON gs.player_id = p.player_id
        WHERE p.user_id = $1 AND g.game_name = $2
        ORDER BY g.game_installment
    """, user["user_id"], franchise_name)
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
            WHERE gs.game_id = $1 AND gs.ranked = 1
              AND gs.pre_match_rank_value IS NOT NULL AND p.user_id = $2
            UNION
            SELECT post_match_rank_value AS rank_value FROM fact.fact_game_stats gs
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE gs.game_id = $1 AND gs.ranked = 1
              AND gs.post_match_rank_value IS NOT NULL AND p.user_id = $2
        ) AS combined_ranks
        WHERE rank_value IS NOT NULL AND rank_value != ''
        ORDER BY rank_value
    """, game_id, user["user_id"])
    return {"ranks": [r["rank_value"] for r in rows]}


@router.get("/get_game_modes/{game_id}")
async def get_game_modes(game_id: int, conn: DynamicConn, user: CurrentUser):
    """Distinct game modes for a game, scoped to the user."""
    rows = await conn.fetch("""
        SELECT DISTINCT game_mode
        FROM fact.fact_game_stats gs
        JOIN dim.dim_players p ON gs.player_id = p.player_id
        WHERE gs.game_id = $1 AND p.user_id = $2
          AND gs.game_mode IS NOT NULL AND gs.game_mode != ''
        ORDER BY game_mode
    """, game_id, user["user_id"])
    return {"game_modes": [r["game_mode"] for r in rows]}


@router.get("/get_game_stat_types/{game_id}")
async def get_game_stat_types(game_id: int, conn: DynamicConn, user: CurrentUser):
    """Distinct stat types for a game, scoped to the user."""
    rows = await conn.fetch("""
        SELECT DISTINCT gs.stat_type
        FROM fact.fact_game_stats gs
        JOIN dim.dim_players p ON gs.player_id = p.player_id
        WHERE gs.game_id = $1 AND p.user_id = $2
          AND gs.stat_type IS NOT NULL AND gs.stat_type != ''
        ORDER BY stat_type
    """, game_id, user["user_id"])
    return {"stat_types": [r["stat_type"] for r in rows]}


@router.get("/get_game_context/{game_id}")
async def get_game_context(game_id: int, conn: DynamicConn, user: CurrentUser):
    """Ranks + modes + stat types in a single round-trip."""
    uid = user["user_id"]

    ranks_rows = await conn.fetch("""
        SELECT DISTINCT rank_value FROM (
            SELECT pre_match_rank_value AS rank_value FROM fact.fact_game_stats gs
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE gs.game_id = $1 AND gs.ranked = 1
              AND gs.pre_match_rank_value IS NOT NULL AND p.user_id = $2
            UNION
            SELECT post_match_rank_value AS rank_value FROM fact.fact_game_stats gs
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE gs.game_id = $1 AND gs.ranked = 1
              AND gs.post_match_rank_value IS NOT NULL AND p.user_id = $2
        ) AS combined_ranks
        WHERE rank_value IS NOT NULL AND rank_value != ''
        ORDER BY rank_value
    """, game_id, uid)
    modes_rows = await conn.fetch("""
        SELECT DISTINCT game_mode FROM fact.fact_game_stats gs
        JOIN dim.dim_players p ON gs.player_id = p.player_id
        WHERE gs.game_id = $1 AND p.user_id = $2
          AND gs.game_mode IS NOT NULL AND gs.game_mode != ''
        ORDER BY game_mode
    """, game_id, uid)
    types_rows = await conn.fetch("""
        SELECT DISTINCT gs.stat_type FROM fact.fact_game_stats gs
        JOIN dim.dim_players p ON gs.player_id = p.player_id
        WHERE gs.game_id = $1 AND p.user_id = $2
          AND gs.stat_type IS NOT NULL AND gs.stat_type != ''
        ORDER BY stat_type
    """, game_id, uid)

    return {
        "ranks":      [r["rank_value"] for r in ranks_rows],
        "modes":      [r["game_mode"]  for r in modes_rows],
        "stat_types": [r["stat_type"]  for r in types_rows],
    }


@router.post("/add_game", status_code=201)
async def add_game(body: AddGameRequest, conn: DynamicConn, user: TrustedUser):
    """Add a new game to the catalog. Trusted/Owner only."""
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
    """Free/Premium users request a game to be added to the catalog."""
    existing = await conn.fetchval("""
        SELECT request_id FROM app.game_requests
        WHERE user_id = $1 AND game_name = $2
          AND (game_installment = $3 OR (game_installment IS NULL AND $3 IS NULL))
          AND status = 'pending'
    """, user["user_id"], body.game_name, body.game_installment)

    if existing:
        return {"request_id": existing, "message": "A pending request for this game already exists."}

    request_id = await conn.fetchval("""
        INSERT INTO app.game_requests (user_id, game_name, game_installment, status, created_at)
        VALUES ($1, $2, $3, 'pending', NOW())
        RETURNING request_id
    """, user["user_id"], body.game_name, body.game_installment)

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


@router.post("/game/score", status_code=201)
async def submit_game_score(
    body: GameScoreRequest,
    conn: DynamicConn,
    user: CurrentUser,
):
    """
    Record a single game session from a browser-hosted game (e.g. Light Climb).
    Requires a Bearer JWT obtained via /api/game/auth.
    DynamicConn routes owners to personal_pool and public users to public_pool.
    """
    _MIN_SCORE   = 10   # metres — must match MIN_SCORE_TO_RECORD in light-climb.html
    _COOLDOWN_S  = 60   # seconds — minimum gap between recorded runs per user per game

    if body.score < _MIN_SCORE:
        raise HTTPException(status_code=400, detail="Score too low to record.")

    user_id = user["user_id"]

    # 1. Game lookup — NULL installment safe (ON CONFLICT won't fire for NULLs)
    game_id = await conn.fetchval(
        "SELECT game_id FROM dim.dim_games WHERE game_name = $1 AND game_installment IS NULL",
        body.game_name,
    )
    if not game_id:
        game_id = await conn.fetchval(
            """INSERT INTO dim.dim_games (game_name, game_installment, game_genre, game_subgenre)
               VALUES ($1, NULL, 'Platformer', 'Endless Runner') RETURNING game_id""",
            body.game_name,
        )

    # 2. Player lookup / create
    player_id = await conn.fetchval(
        "SELECT player_id FROM dim.dim_players WHERE user_id = $1 ORDER BY created_at LIMIT 1",
        user_id,
    )
    if not player_id:
        player_id = await conn.fetchval(
            "INSERT INTO dim.dim_players (player_name, user_id, created_at)"
            " VALUES ($1, $2, NOW()) RETURNING player_id",
            body.player_name, user_id,
        )

    # 3. Rate limit — reject if a run was already recorded within the cooldown window
    last_run = await conn.fetchval(
        """SELECT played_at FROM fact.fact_game_stats
           WHERE player_id = $1 AND game_id = $2
           ORDER BY played_at DESC LIMIT 1""",
        player_id, game_id,
    )
    if last_run:
        elapsed = (datetime.now(timezone.utc) - last_run).total_seconds()
        if elapsed < _COOLDOWN_S:
            raise HTTPException(status_code=429, detail="Run submitted too soon — please finish a full attempt.")

    # 4. first_session_of_day
    played_today = await conn.fetchval(
        """SELECT EXISTS(
            SELECT 1 FROM fact.fact_game_stats gs
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE p.user_id = $1 AND gs.game_id = $2
              AND gs.played_at >= CURRENT_DATE
        )""",
        user_id, game_id,
    )
    first_session_of_day = 0 if played_today else 1

    # 5. Insert stat row
    played_at = await conn.fetchval("SELECT NOW()")
    await conn.execute(
        """INSERT INTO fact.fact_game_stats
           (game_id, player_id, stat_type, stat_value, game_mode, solo_mode, party_size,
            game_level, win, ranked, pre_match_rank_value, post_match_rank_value,
            overtime, difficulty, input_device, platform, first_session_of_day,
            was_streaming, source, is_editable, played_at)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)
        """,
        game_id, player_id, "Height", float(body.score),
        "Solo", 1, "1",
        body.checkpoints, None, None,
        None, None,
        0, None,
        body.input_device, body.platform,
        first_session_of_day, 0, "vgst", False,
        played_at,
    )

    # 6. Owner: fire full social pipeline (charts → GCS → Twitter/IFTTT + Telegram with photo)
    if user.get("is_owner"):
        from utils.social_pipeline import run_social_media_pipeline
        asyncio.create_task(
            asyncio.to_thread(
                run_social_media_pipeline,
                player_id=player_id,
                player_name=body.player_name,
                game_id=game_id,
                game_name=body.game_name,
                game_installment=None,
                stats=[
                    {"stat_type": "Height",      "stat_value": float(body.score),    "game_mode": "Solo"},
                    {"stat_type": "Checkpoints", "stat_value": body.checkpoints,     "game_mode": "Solo"},
                ],
                is_live=False,
                credit_style="made_by",
                queue_platforms=[],
                played_at_iso=played_at.isoformat(),
                win=None,
            )
        )

    return {"recorded": True, "first_session_of_day": bool(first_session_of_day)}
