"""
Leaderboard routes — Public pool (opt-in consent gate).

  POST /leaderboard/opt_in/{game_id}     — toggle opt-in for a game
  GET  /leaderboard/top_stats/{game_id}  — top 3 stat types (pill selector)
  GET  /leaderboard/rankings/{game_id}   — top 10 by avg for a stat_type
  GET  /leaderboard/standings            — user's rank across opted-in games (max 3)
  GET  /leaderboard/sample_size/{game_id} — opted-in count (phase gating)

All tables use user_id (INTEGER) as FK — no user_email stored in child tables.
"""

import hashlib
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from api.core.deps import DynamicConn, CurrentUser

router = APIRouter()

_cache: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 300


def _cache_get(key: str) -> Any | None:
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < _CACHE_TTL:
        return entry[1]
    _cache.pop(key, None)
    return None


def _cache_set(key: str, value: Any) -> None:
    _cache[key] = (time.time(), value)


def _cache_invalidate_leaderboard(game_id: int) -> None:
    to_delete = [k for k in _cache if k.startswith(f"lb:{game_id}:")]
    for k in to_delete:
        _cache.pop(k, None)


@router.post("/leaderboard/opt_in/{game_id}")
async def toggle_opt_in(game_id: int, conn: DynamicConn, user: CurrentUser):
    uid = user["user_id"]
    existing = await conn.fetchrow("""
        SELECT is_public FROM app.leaderboard_opts_in
        WHERE user_id = $1 AND game_id = $2
    """, uid, game_id)

    if existing is None:
        await conn.execute("""
            INSERT INTO app.leaderboard_opts_in (user_id, game_id, is_public)
            VALUES ($1, $2, TRUE)
        """, uid, game_id)
        is_public = True
    else:
        is_public = not existing["is_public"]
        await conn.execute("""
            UPDATE app.leaderboard_opts_in
            SET is_public = $1
            WHERE user_id = $2 AND game_id = $3
        """, is_public, uid, game_id)

    _cache_invalidate_leaderboard(game_id)
    return {"game_id": game_id, "opted_in": is_public}


@router.get("/leaderboard/opt_in_status")
async def get_opt_in_status(conn: DynamicConn, user: CurrentUser):
    rows = await conn.fetch("""
        SELECT game_id, is_public FROM app.leaderboard_opts_in
        WHERE user_id = $1
    """, user["user_id"])
    return {"opted_in": [r["game_id"] for r in rows if r["is_public"]]}


@router.get("/leaderboard/sample_size/{game_id}")
async def get_sample_size(game_id: int, conn: DynamicConn, user: CurrentUser):
    count = await conn.fetchval("""
        SELECT COUNT(DISTINCT user_id)
        FROM app.leaderboard_opts_in
        WHERE game_id = $1 AND is_public = TRUE
    """, game_id)

    if count == 0:
        phase = "hidden"
    elif count <= 2:
        phase = "placeholder"
    elif count <= 9:
        phase = "standings_only"
    else:
        phase = "full"

    return {"game_id": game_id, "sample_size": int(count), "phase": phase}


@router.get("/leaderboard/top_stats/{game_id}")
async def get_top_stats(game_id: int, conn: DynamicConn, user: CurrentUser):
    rows = await conn.fetch("""
        SELECT f.stat_type, COUNT(*) AS cnt
        FROM fact.fact_game_stats f
        JOIN app.leaderboard_opts_in o
            ON f.player_id IN (
                SELECT p.player_id FROM dim.dim_players p
                WHERE p.user_id = o.user_id
            )
        WHERE f.game_id = $1
          AND o.game_id = $1
          AND o.is_public = TRUE
          AND f.stat_type IS NOT NULL
        GROUP BY f.stat_type
        ORDER BY cnt DESC
        LIMIT 3
    """, game_id)

    return {"game_id": game_id, "stat_types": [r["stat_type"] for r in rows]}


@router.get("/leaderboard/rankings/{game_id}")
async def get_rankings(
    game_id:   int,
    conn:      DynamicConn,
    user:      CurrentUser,
    stat_type: str = Query(...),
):
    cache_key = f"lb:{game_id}:{hashlib.md5(stat_type.encode()).hexdigest()}"
    cached = _cache_get(cache_key)
    if cached:
        top10, all_ranks = cached
    else:
        rows = await conn.fetch("""
            WITH opted AS (
                SELECT o.user_id
                FROM app.leaderboard_opts_in o
                WHERE o.game_id = $1 AND o.is_public = TRUE
            ),
            player_avgs AS (
                SELECT
                    p.user_id,
                    p.player_name,
                    AVG(f.stat_value)              AS avg_value,
                    COUNT(DISTINCT f.played_at)    AS sessions
                FROM fact.fact_game_stats f
                JOIN dim.dim_players p ON f.player_id = p.player_id
                JOIN opted           o ON p.user_id   = o.user_id
                WHERE f.game_id   = $1
                  AND f.stat_type = $2
                  AND f.stat_value IS NOT NULL
                GROUP BY p.user_id, p.player_name
                HAVING COUNT(DISTINCT f.played_at) >= 1
            ),
            ranked AS (
                SELECT *,
                    RANK() OVER (ORDER BY avg_value DESC) AS rank
                FROM player_avgs
            )
            SELECT * FROM ranked ORDER BY rank, player_name
        """, game_id, stat_type)

        all_ranks = [dict(r) for r in rows]
        top10 = all_ranks[:10]
        _cache_set(cache_key, (top10, all_ranks))

    uid = user["user_id"]
    user_rank = next((r for r in all_ranks if r["user_id"] == uid), None)

    return {
        "game_id":   game_id,
        "stat_type": stat_type,
        "top10": [
            {
                "rank":        r["rank"],
                "player_name": r["player_name"],
                "avg_value":   round(float(r["avg_value"]), 2),
                "sessions":    r["sessions"],
                "is_you":      r["user_id"] == uid,
            }
            for r in top10
        ],
        "your_rank": {
            "rank":      user_rank["rank"] if user_rank else None,
            "avg_value": round(float(user_rank["avg_value"]), 2) if user_rank else None,
            "sessions":  user_rank["sessions"] if user_rank else None,
        } if user_rank else None,
        "sample_size": len(all_ranks),
    }


@router.get("/leaderboard/standings")
async def get_standings(conn: DynamicConn, user: CurrentUser):
    uid = user["user_id"]

    opted_rows = await conn.fetch("""
        SELECT o.game_id, g.game_name, g.game_installment
        FROM app.leaderboard_opts_in o
        JOIN dim.dim_games g ON o.game_id = g.game_id
        WHERE o.user_id = $1 AND o.is_public = TRUE
        ORDER BY o.game_id
        LIMIT 3
    """, uid)

    standings = []
    for opted in opted_rows:
        game_id = opted["game_id"]

        top_stat_row = await conn.fetchrow("""
            SELECT f.stat_type
            FROM fact.fact_game_stats f
            JOIN dim.dim_players p ON f.player_id = p.player_id
            JOIN app.leaderboard_opts_in o ON p.user_id = o.user_id AND o.game_id = f.game_id
            WHERE f.game_id = $1 AND o.is_public = TRUE AND f.stat_type IS NOT NULL
            GROUP BY f.stat_type
            ORDER BY COUNT(*) DESC
            LIMIT 1
        """, game_id)

        if not top_stat_row:
            continue

        stat_type = top_stat_row["stat_type"]

        all_rows = await conn.fetch("""
            SELECT
                p.user_id,
                AVG(f.stat_value)           AS avg_value,
                COUNT(DISTINCT f.played_at) AS sessions
            FROM fact.fact_game_stats f
            JOIN dim.dim_players p ON f.player_id = p.player_id
            JOIN app.leaderboard_opts_in o ON p.user_id = o.user_id AND o.game_id = f.game_id
            WHERE f.game_id   = $1
              AND f.stat_type = $2
              AND o.is_public = TRUE
              AND f.stat_value IS NOT NULL
            GROUP BY p.user_id
        """, game_id, stat_type)

        sample_size = len(all_rows)
        if sample_size < 3:
            continue

        sorted_avgs = sorted([r["avg_value"] for r in all_rows], reverse=True)
        user_row    = next((r for r in all_rows if r["user_id"] == uid), None)

        if not user_row:
            continue

        user_avg   = float(user_row["avg_value"])
        rank       = sorted_avgs.index(user_row["avg_value"]) + 1
        percentile = round((1 - (rank - 1) / sample_size) * 100)

        title = f"{opted['game_name']}: {opted['game_installment']}" \
                if opted["game_installment"] else opted["game_name"]

        standings.append({
            "game_id":     game_id,
            "game_title":  title,
            "stat_type":   stat_type,
            "avg_value":   round(user_avg, 2),
            "rank":        rank,
            "percentile":  percentile,
            "sample_size": sample_size,
            "small_sample": sample_size < 10,
        })

    return {"standings": standings}
