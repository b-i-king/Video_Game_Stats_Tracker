"""
Dashboard route — All tiers (free → owner).

GET /dashboard  — aggregate stats across all games for the calling user.

Returns in a single round-trip (3 queries, one connection):
  - total_sessions    : distinct (game × day) pairs
  - total_games       : distinct games ever played
  - current_streak    : consecutive days with any session (tz-aware)
  - longest_streak    : personal best streak
  - last_played       : most recent session date
  - top_games         : top 3 by session count, each with top stat + avg
  - heatmap           : day-of-week × time-slot matrix (all games combined)
"""

from datetime import timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from api.core.deps import DynamicConn, CurrentUser

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(
    conn: DynamicConn,
    user: CurrentUser,
    tz:   str = Query(default="America/Los_Angeles"),
):
    # ── 1. Aggregate totals + session dates for streak ────────────────────────
    agg_row = await conn.fetchrow("""
        SELECT
            COUNT(DISTINCT (f.game_id, (f.played_at AT TIME ZONE $2)::date)) AS total_sessions,
            COUNT(DISTINCT f.game_id)                                          AS total_games
        FROM fact.fact_game_stats f
        JOIN dim.dim_players p ON f.player_id = p.player_id
        JOIN dim.dim_users   u ON p.user_id   = u.user_id
        WHERE u.user_email = $1
    """, user["email"], tz)

    total_sessions = int(agg_row["total_sessions"] or 0)
    total_games    = int(agg_row["total_games"]    or 0)

    # All distinct session days (any game) for streak calculation
    date_rows = await conn.fetch("""
        SELECT DISTINCT (f.played_at AT TIME ZONE $2)::date AS d
        FROM fact.fact_game_stats f
        JOIN dim.dim_players p ON f.player_id = p.player_id
        JOIN dim.dim_users   u ON p.user_id   = u.user_id
        WHERE u.user_email = $1
        ORDER BY d DESC
    """, user["email"], tz)

    dates = [r["d"] for r in date_rows]  # newest first

    current_streak = 0
    longest_streak = 0
    last_played    = None

    if dates:
        from datetime import datetime
        today = datetime.now(ZoneInfo(tz)).date()
        last_played = dates[0].isoformat()

        # Current streak — count back from today or yesterday
        if dates[0] >= today - timedelta(days=1):
            expected = dates[0]
            for d in dates:
                if d == expected:
                    current_streak += 1
                    expected -= timedelta(days=1)
                else:
                    break

        # Longest streak
        asc     = sorted(dates)
        run     = 1
        longest = 1
        for i in range(1, len(asc)):
            if (asc[i] - asc[i - 1]).days == 1:
                run    += 1
                longest = max(longest, run)
            else:
                run = 1
        longest_streak = max(current_streak, longest)

    # ── 2. Top 3 games (by session count) with top stat + avg ─────────────────
    game_rows = await conn.fetch("""
        WITH player_ids AS (
            SELECT p.player_id
            FROM dim.dim_players p
            JOIN dim.dim_users u ON p.user_id = u.user_id
            WHERE u.user_email = $1
        ),
        game_sessions AS (
            SELECT
                f.game_id,
                g.game_name,
                g.game_installment,
                COUNT(DISTINCT (f.played_at AT TIME ZONE $2)::date) AS sessions
            FROM fact.fact_game_stats f
            JOIN dim.dim_games g ON f.game_id = g.game_id
            WHERE f.player_id IN (SELECT player_id FROM player_ids)
            GROUP BY f.game_id, g.game_name, g.game_installment
            ORDER BY sessions DESC
            LIMIT 3
        ),
        top_stats AS (
            SELECT
                f.game_id,
                f.stat_type,
                COUNT(*)              AS cnt,
                ROUND(AVG(f.stat_value)::numeric, 2) AS avg_value
            FROM fact.fact_game_stats f
            WHERE f.player_id IN (SELECT player_id FROM player_ids)
              AND f.stat_type  IS NOT NULL
              AND f.stat_value IS NOT NULL
              AND f.game_id IN (SELECT game_id FROM game_sessions)
            GROUP BY f.game_id, f.stat_type
        ),
        top_stat_per_game AS (
            SELECT DISTINCT ON (game_id) game_id, stat_type, avg_value
            FROM top_stats
            ORDER BY game_id, cnt DESC
        )
        SELECT
            gs.game_id,
            gs.game_name,
            gs.game_installment,
            gs.sessions,
            ts.stat_type  AS top_stat,
            ts.avg_value  AS top_stat_avg
        FROM game_sessions gs
        LEFT JOIN top_stat_per_game ts ON gs.game_id = ts.game_id
        ORDER BY gs.sessions DESC
    """, user["email"], tz)

    top_games = [
        {
            "game_id":          r["game_id"],
            "game_name":        r["game_name"],
            "game_installment": r["game_installment"],
            "sessions":         r["sessions"],
            "top_stat":         r["top_stat"],
            "top_stat_avg":     float(r["top_stat_avg"]) if r["top_stat_avg"] else None,
        }
        for r in game_rows
    ]

    # ── 3. Heatmap (all games combined) ───────────────────────────────────────
    heatmap_rows = await conn.fetch("""
        SELECT
            EXTRACT(DOW  FROM (f.played_at AT TIME ZONE $2))::int AS dow,
            EXTRACT(HOUR FROM (f.played_at AT TIME ZONE $2))::int AS hour,
            COUNT(DISTINCT f.played_at) AS session_count
        FROM fact.fact_game_stats f
        JOIN dim.dim_players p ON f.player_id = p.player_id
        JOIN dim.dim_users   u ON p.user_id   = u.user_id
        WHERE u.user_email = $1
        GROUP BY dow, hour
    """, user["email"], tz)

    cells = [
        {"dow": r["dow"], "hour": r["hour"], "session_count": int(r["session_count"])}
        for r in heatmap_rows
    ]
    max_sessions = max((c["session_count"] for c in cells), default=0)

    return {
        "total_sessions": total_sessions,
        "total_games":    total_games,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "last_played":    last_played,
        "top_games":      top_games,
        "heatmap": {
            "cells":        cells,
            "max_sessions": max_sessions,
        },
    }
