import asyncio
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from api.core.deps import DynamicConn, CurrentUser

router = APIRouter()


class DownloadChartRequest(BaseModel):
    game_id: int
    player_id: int
    platform: str = "twitter"


@router.get("/get_interactive_chart/{game_id}", response_class=HTMLResponse)
async def get_interactive_chart(
    game_id: int,
    conn: DynamicConn,
    user: CurrentUser,
    player_id: int = Query(...),
    game_mode: str | None = Query(None),
    tz: str = Query(default="America/Los_Angeles"),
):
    """
    Generate and return an interactive Plotly HTML chart.
    Returns raw HTML — embed via iframe srcdoc on the frontend.
    """
    import asyncio
    from utils.chart_utils import generate_interactive_chart, get_stat_history_from_db

    # Verify ownership
    owned = await conn.fetchval(
        "SELECT 1 FROM dim.dim_players WHERE player_id = $1 AND user_id = $2",
        player_id, user["user_id"],
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Player not found.")

    game_row = await conn.fetchrow(
        "SELECT game_name, game_installment FROM dim.dim_games WHERE game_id = $1", game_id
    )
    if not game_row:
        raise HTTPException(status_code=404, detail="Game not found.")
    game_name       = game_row["game_name"]
    game_installment = game_row["game_installment"]

    player_row = await conn.fetchrow(
        "SELECT player_name FROM dim.dim_players WHERE player_id = $1", player_id
    )
    player_name = player_row["player_name"]

    games_played = await conn.fetchval("""
        SELECT COUNT(DISTINCT played_at) FROM fact.fact_game_stats
        WHERE player_id = $1 AND game_id = $2
    """, player_id, game_id)

    if not games_played:
        raise HTTPException(status_code=404, detail="No stats found for this game.")

    if games_played == 1:
        rows = await conn.fetch("""
            SELECT stat_type, stat_value FROM fact.fact_game_stats
            WHERE player_id = $1 AND game_id = $2 AND stat_type IS NOT NULL
            ORDER BY stat_value DESC NULLS LAST
            LIMIT 3
        """, player_id, game_id)
        data = {f"stat{i}": {"label": r["stat_type"], "value": r["stat_value"], "prev_value": None}
                for i, r in enumerate(rows, 1)}
        chart_type = "bar"
    else:
        top_rows = await conn.fetch("""
            SELECT stat_type FROM fact.fact_game_stats
            WHERE player_id = $1 AND game_id = $2 AND stat_type IS NOT NULL
            GROUP BY stat_type HAVING COUNT(*) >= 2
            ORDER BY AVG(stat_value) DESC, STDDEV(stat_value) DESC NULLS LAST, COUNT(*) DESC
            LIMIT 3
        """, player_id, game_id)
        top_stats = [r["stat_type"] for r in top_rows]

        # get_stat_history_from_db uses a psycopg2 cursor — run in thread
        import psycopg2
        from api.core.config import get_settings
        settings = get_settings()
        is_owner = user.get("is_owner", False)
        dsn = settings.personal_db_url if is_owner else settings.public_db_url
        def _fetch_history():
            pg = psycopg2.connect(dsn, sslmode="require")
            try:
                with pg.cursor() as cur:
                    return get_stat_history_from_db(cur, player_id, game_id, top_stats, timezone_str=tz, days_back=365)
            finally:
                pg.close()

        data = await asyncio.to_thread(_fetch_history)
        chart_type = "line"

    html_bytes = await asyncio.to_thread(
        generate_interactive_chart,
        chart_type, data, player_name, game_name,
        game_installment=game_installment, game_mode=game_mode, tz=tz,
    )
    return HTMLResponse(content=html_bytes if isinstance(html_bytes, str) else html_bytes.decode("utf-8"))


@router.post("/download_chart")
async def download_chart(body: DownloadChartRequest, conn: DynamicConn, user: CurrentUser):
    """Generate and stream a chart PNG for the given player/game/platform."""
    import asyncio
    from utils.chart_utils import generate_bar_chart, generate_line_chart, get_stat_history_from_db

    if body.platform not in ("twitter", "instagram"):
        raise HTTPException(status_code=400, detail="platform must be 'twitter' or 'instagram'.")

    # Verify ownership
    owned = await conn.fetchval(
        "SELECT 1 FROM dim.dim_players WHERE player_id = $1 AND user_id = $2",
        body.player_id, user["user_id"],
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Player not found.")

    game_row = await conn.fetchrow(
        "SELECT game_name, game_installment FROM dim.dim_games WHERE game_id = $1", body.game_id
    )
    if not game_row:
        raise HTTPException(status_code=404, detail="Game not found.")
    game_name        = game_row["game_name"]
    game_installment = game_row["game_installment"]

    player_row = await conn.fetchrow(
        "SELECT player_name FROM dim.dim_players WHERE player_id = $1", body.player_id
    )
    player_name = player_row["player_name"]

    mode_row = await conn.fetchrow("""
        SELECT game_mode FROM fact.fact_game_stats
        WHERE player_id = $1 AND game_id = $2 ORDER BY played_at DESC LIMIT 1
    """, body.player_id, body.game_id)
    game_mode = mode_row["game_mode"] if mode_row else None

    games_played = await conn.fetchval("""
        SELECT COUNT(DISTINCT played_at) FROM fact.fact_game_stats
        WHERE player_id = $1 AND game_id = $2
    """, body.player_id, body.game_id)

    if not games_played:
        raise HTTPException(status_code=404, detail="No stats found for this game.")

    if games_played == 1:
        rows = await conn.fetch("""
            SELECT stat_type, stat_value FROM fact.fact_game_stats
            WHERE player_id = $1 AND game_id = $2 AND stat_type IS NOT NULL
            ORDER BY stat_value DESC NULLS LAST
            LIMIT 3
        """, body.player_id, body.game_id)
        stat_data = {f"stat{i}": {"label": r["stat_type"], "value": r["stat_value"], "prev_value": None}
                     for i, r in enumerate(rows, 1)}
        image_buffer = await asyncio.to_thread(
            generate_bar_chart, stat_data, player_name, game_name,
            game_installment, body.platform, game_mode,
        )
    else:
        top_rows = await conn.fetch("""
            SELECT stat_type FROM fact.fact_game_stats
            WHERE player_id = $1 AND game_id = $2 AND stat_type IS NOT NULL
            GROUP BY stat_type HAVING COUNT(*) >= 2
            ORDER BY AVG(stat_value) DESC, STDDEV(stat_value) DESC NULLS LAST, COUNT(*) DESC
            LIMIT 3
        """, body.player_id, body.game_id)
        top_stats = [r["stat_type"] for r in top_rows]

        import psycopg2
        from api.core.config import get_settings
        settings = get_settings()
        is_owner = user.get("is_owner", False)
        dsn = settings.personal_db_url if is_owner else settings.public_db_url
        def _fetch_history():
            pg = psycopg2.connect(dsn, sslmode="require")
            try:
                with pg.cursor() as cur:
                    return get_stat_history_from_db(cur, body.player_id, body.game_id, top_stats, days_back=30)
            finally:
                pg.close()

        stat_history = await asyncio.to_thread(_fetch_history)
        image_buffer = await asyncio.to_thread(
            generate_line_chart, stat_history, player_name, game_name,
            game_installment, body.platform, game_mode,
        )

    image_buffer.seek(0)
    filename = f"{player_name}_{game_name}_{body.platform}.png".replace(" ", "_")
    return Response(
        content=image_buffer.read(),
        media_type="image/png",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/get_heatmap/{game_id}")
async def get_heatmap(
    game_id: int,
    conn: DynamicConn,
    user: CurrentUser,
    player_id: int = Query(...),
    tz: str = Query(default="America/Los_Angeles"),
):
    """Session frequency by day-of-week and hour-of-day, tz-adjusted."""
    owned = await conn.fetchval(
        "SELECT 1 FROM dim.dim_players WHERE player_id = $1 AND user_id = $2",
        player_id, user["user_id"],
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Player not found.")

    rows = await conn.fetch("""
        SELECT
            EXTRACT(DOW  FROM (played_at AT TIME ZONE $1))::int AS dow,
            EXTRACT(HOUR FROM (played_at AT TIME ZONE $1))::int AS hour,
            COUNT(*) AS session_count
        FROM fact.fact_game_stats
        WHERE player_id = $2 AND game_id = $3
        GROUP BY 1, 2
        ORDER BY 1, 2
    """, tz, player_id, game_id)

    cells = [{"dow": r["dow"], "hour": r["hour"], "session_count": int(r["session_count"])} for r in rows]
    max_sessions = max((c["session_count"] for c in cells), default=0)
    return {"cells": cells, "max_sessions": max_sessions}
