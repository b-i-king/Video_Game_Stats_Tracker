"""
Email routes — newsletter opt-in + monthly recap trigger.

GET  /newsletter/optin         — get current user's opt-in status
POST /newsletter/optin         — set opt-in (body: {optin: bool})
POST /newsletter/send_monthly  — owner-only: gather stats from both DBs, send recap
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.core.deps import DynamicConn, CurrentUser, OwnerUser, require_api_key
from api.core.database import personal_pool, public_pool

router = APIRouter()


class OptInBody(BaseModel):
    optin: bool


# ---------------------------------------------------------------------------
# Opt-in routes
# ---------------------------------------------------------------------------

@router.get("/newsletter/optin")
async def get_newsletter_optin(conn: DynamicConn, user: CurrentUser):
    """Return whether the current user is opted in to monthly recaps."""
    row = await conn.fetchrow(
        "SELECT newsletter_optin FROM dim.dim_users WHERE user_id = $1",
        user["user_id"],
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"optin": bool(row["newsletter_optin"])}


@router.post("/newsletter/optin")
async def set_newsletter_optin(body: OptInBody, conn: DynamicConn, user: CurrentUser):
    """Opt in or out of the monthly recap email."""
    await conn.execute(
        "UPDATE dim.dim_users SET newsletter_optin = $1 WHERE user_id = $2",
        body.optin, user["user_id"],
    )
    return {"optin": body.optin}


# ---------------------------------------------------------------------------
# Owner-only: send monthly recap
# ---------------------------------------------------------------------------

async def _gather_stats() -> dict:
    """
    Pull last-month stats from both personal and public pools,
    merge them, and return a single stats dict for the email template.
    """
    from datetime import datetime, timezone

    # ── Public pool ──────────────────────────────────────────────────────────
    pub_mau = pub_sessions = pub_new_users = pub_total_users = 0
    pub_games: dict[str, int] = {}   # game_name → session count
    pub_players: dict[str, int] = {} # player_name → session count

    if public_pool:
        async with public_pool.acquire() as conn:
            pub_mau = await conn.fetchval("""
                SELECT COUNT(DISTINCT dp.user_id)
                FROM fact.fact_game_stats fgs
                JOIN dim.dim_players dp ON dp.player_id = fgs.player_id
                WHERE fgs.played_at >= date_trunc('month', NOW() - INTERVAL '1 month')
                  AND fgs.played_at  < date_trunc('month', NOW())
            """) or 0

            pub_sessions = await conn.fetchval("""
                SELECT COUNT(*)
                FROM fact.fact_game_stats
                WHERE played_at >= date_trunc('month', NOW() - INTERVAL '1 month')
                  AND played_at  < date_trunc('month', NOW())
            """) or 0

            pub_new_users = await conn.fetchval("""
                SELECT COUNT(*) FROM dim.dim_users
                WHERE created_at >= date_trunc('month', NOW() - INTERVAL '1 month')
                  AND created_at  < date_trunc('month', NOW())
            """) or 0

            pub_total_users = await conn.fetchval(
                "SELECT COUNT(*) FROM dim.dim_users"
            ) or 0

            game_rows = await conn.fetch("""
                SELECT
                    CASE WHEN dg.game_installment IS NOT NULL
                         THEN dg.game_name || ': ' || dg.game_installment
                         ELSE dg.game_name
                    END AS game_title,
                    COUNT(*) AS sessions
                FROM fact.fact_game_stats fgs
                JOIN dim.dim_games dg ON dg.game_id = fgs.game_id
                WHERE fgs.played_at >= date_trunc('month', NOW() - INTERVAL '1 month')
                  AND fgs.played_at  < date_trunc('month', NOW())
                GROUP BY game_title
            """)
            for r in game_rows:
                pub_games[r["game_title"]] = int(r["sessions"])

            player_rows = await conn.fetch("""
                SELECT dp.player_name, COUNT(*) AS sessions
                FROM fact.fact_game_stats fgs
                JOIN dim.dim_players dp ON dp.player_id = fgs.player_id
                WHERE fgs.played_at >= date_trunc('month', NOW() - INTERVAL '1 month')
                  AND fgs.played_at  < date_trunc('month', NOW())
                GROUP BY dp.player_name
            """)
            for r in player_rows:
                pub_players[r["player_name"]] = int(r["sessions"])

    # ── Personal pool (owner data) ────────────────────────────────────────────
    per_sessions = 0
    per_owner_active = False
    per_games: dict[str, int] = {}
    per_players: dict[str, int] = {}

    if personal_pool:
        async with personal_pool.acquire() as conn:
            per_sessions = await conn.fetchval("""
                SELECT COUNT(*)
                FROM fact.fact_game_stats
                WHERE played_at >= date_trunc('month', NOW() - INTERVAL '1 month')
                  AND played_at  < date_trunc('month', NOW())
            """) or 0

            per_owner_active = bool(per_sessions > 0)

            game_rows = await conn.fetch("""
                SELECT
                    CASE WHEN dg.game_installment IS NOT NULL
                         THEN dg.game_name || ': ' || dg.game_installment
                         ELSE dg.game_name
                    END AS game_title,
                    COUNT(*) AS sessions
                FROM fact.fact_game_stats fgs
                JOIN dim.dim_games dg ON dg.game_id = fgs.game_id
                WHERE fgs.played_at >= date_trunc('month', NOW() - INTERVAL '1 month')
                  AND fgs.played_at  < date_trunc('month', NOW())
                GROUP BY game_title
            """)
            for r in game_rows:
                per_games[r["game_title"]] = int(r["sessions"])

            player_rows = await conn.fetch("""
                SELECT dp.player_name, COUNT(*) AS sessions
                FROM fact.fact_game_stats fgs
                JOIN dim.dim_players dp ON dp.player_id = fgs.player_id
                WHERE fgs.played_at >= date_trunc('month', NOW() - INTERVAL '1 month')
                  AND fgs.played_at  < date_trunc('month', NOW())
                GROUP BY dp.player_name
            """)
            for r in player_rows:
                per_players[r["player_name"]] = int(r["sessions"])

    # ── Merge ─────────────────────────────────────────────────────────────────
    total_sessions = pub_sessions + per_sessions
    mau            = pub_mau + (1 if per_owner_active else 0)

    # Merge game session counts across both pools by title
    merged_games = dict(pub_games)
    for title, count in per_games.items():
        merged_games[title] = merged_games.get(title, 0) + count

    # Merge player session counts
    merged_players = dict(pub_players)
    for name, count in per_players.items():
        merged_players[name] = merged_players.get(name, 0) + count

    top_game = max(merged_games, key=merged_games.get) if merged_games else "N/A"
    top_game_sessions = merged_games.get(top_game, 0)

    player_of_month = max(merged_players, key=merged_players.get) if merged_players else "N/A"
    player_sessions = merged_players.get(player_of_month, 0)

    return {
        "mau":               mau,
        "total_sessions":    total_sessions,
        "new_users":         pub_new_users,
        "total_users":       pub_total_users + 1,  # +1 for owner
        "top_game":          top_game,
        "top_game_sessions": top_game_sessions,
        "player_of_month":   player_of_month,
        "player_sessions":   player_sessions,
    }


@router.post("/newsletter/send_monthly", dependencies=[Depends(require_api_key)])
async def send_monthly_recap():
    """
    Owner-only endpoint — gather stats from both DBs and send the monthly recap
    to all opted-in public users. Safe to call manually or via a cron trigger.
    """
    from calendar import month_name
    from datetime import datetime, timezone
    import asyncio

    from utils.resend_utils import send_monthly_recap as _send

    # Month label for the previous calendar month
    now   = datetime.now(timezone.utc)
    month = now.month - 1 if now.month > 1 else 12
    year  = now.year if now.month > 1 else now.year - 1
    month_label = f"{month_name[month]} {year}"

    # Fetch opted-in recipients from public pool
    recipients: list[str] = []
    if public_pool:
        async with public_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_email FROM dim.dim_users
                WHERE newsletter_optin = TRUE
            """)
            recipients = [r["user_email"] for r in rows]

    # Gather cross-pool stats
    stats = await _gather_stats()

    # Send (runs in thread to avoid blocking the event loop)
    result = await asyncio.to_thread(_send, recipients, stats, month_label)

    return {
        "month":      month_label,
        "recipients": len(recipients),
        **result,
        "stats":      stats,
    }
