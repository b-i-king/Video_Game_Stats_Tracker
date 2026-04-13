import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from scipy import stats as scipy_stats

from api.core.deps import DynamicConn, CurrentUser, TrustedUser
from api.routers.obs import _cache_invalidate_obs
from api.models.stats import (
    AddStatsRequest, UpdateStatRequest,
    _NAME_RE, _STAT_TYPE_RE, _VALID_PARTY_SIZES,
)

_PLAYER_CAPS: dict[str, int | None] = {
    "owner":   None,   # unlimited
    "trusted": 5,
    "premium": 5,
    "free":    2,
}


def _player_cap(role: str) -> int | None:
    return _PLAYER_CAPS.get(role, 2)


def _content_check(value: str, field: str, pattern: re.Pattern) -> str | None:
    """Returns an error message string if invalid, else None."""
    if not value or not value.strip():
        return f"'{field}' cannot be empty."
    if not pattern.match(value):
        return f"'{field}' contains invalid characters."
    return None

router = APIRouter()


# ---------------------------------------------------------------------------
# Last session — most recent submission batch
# ---------------------------------------------------------------------------

@router.get("/last_session")
async def last_session(conn: DynamicConn, user: CurrentUser):
    """All stats from the user's most recent submission batch."""
    rows = await conn.fetch("""
        WITH latest_batch AS (
            SELECT gs.played_at, gs.game_id, gs.player_id
            FROM fact.fact_game_stats gs
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE p.user_id = $1
            ORDER BY gs.played_at DESC
            LIMIT 1
        )
        SELECT
            g.game_name,
            g.game_installment,
            p.player_name,
            gs.stat_type,
            gs.stat_value,
            gs.win,
            gs.game_mode,
            gs.difficulty,
            gs.platform,
            gs.played_at
        FROM fact.fact_game_stats gs
        JOIN dim.dim_games g ON gs.game_id = g.game_id
        JOIN dim.dim_players p ON gs.player_id = p.player_id
        JOIN latest_batch lb
          ON gs.played_at = lb.played_at
         AND gs.game_id   = lb.game_id
         AND gs.player_id = lb.player_id
        ORDER BY gs.stat_type
    """, user["user_id"])

    if not rows:
        return {"session": None}

    first = rows[0]
    installment = first["game_installment"]
    game_title = f"{first['game_name']}: {installment}" if installment else first["game_name"]
    win_val = first["win"]
    win_loss = "Win" if win_val == 1 else ("Loss" if win_val == 0 else None)

    return {
        "session": {
            "game_title":   game_title,
            "player_name":  first["player_name"],
            "game_mode":    first["game_mode"],
            "difficulty":   first["difficulty"],
            "platform":     first["platform"],
            "played_at":    first["played_at"].isoformat() if first["played_at"] else None,
            "win_loss":     win_loss,
            "stats": [
                {"stat_type": r["stat_type"], "stat_value": r["stat_value"]}
                for r in rows
            ],
        }
    }


# ---------------------------------------------------------------------------
# Recent stats — last 50 entries with z-score anomaly detection
# ---------------------------------------------------------------------------

@router.get("/get_recent_stats")
async def get_recent_stats(conn: DynamicConn, user: CurrentUser):
    """50 most recent stat entries with z-score anomaly detection."""
    rows = await conn.fetch("""
        WITH hist AS (
            SELECT
                gs.game_id,
                gs.stat_type,
                AVG(gs.stat_value::float)         AS hist_mean,
                STDDEV_SAMP(gs.stat_value::float) AS hist_std,
                COUNT(*)                          AS hist_count
            FROM fact.fact_game_stats gs
            JOIN dim.dim_players p ON gs.player_id = p.player_id
            WHERE p.user_id = $1
            GROUP BY gs.game_id, gs.stat_type
        )
        SELECT
            gs.stat_id,
            p.player_name,
            g.game_name,
            g.game_installment,
            g.game_id,
            gs.stat_type,
            gs.stat_value,
            gs.game_mode,
            gs.game_level,
            gs.win,
            gs.ranked,
            gs.pre_match_rank_value,
            gs.post_match_rank_value,
            gs.played_at,
            h.hist_mean,
            h.hist_std,
            h.hist_count
        FROM fact.fact_game_stats gs
        JOIN dim.dim_players p ON gs.player_id = p.player_id
        JOIN dim.dim_games g ON gs.game_id = g.game_id
        LEFT JOIN hist h ON gs.game_id = h.game_id AND gs.stat_type = h.stat_type
        WHERE p.user_id = $1
        ORDER BY gs.played_at DESC
        LIMIT 50
    """, user["user_id"])

    def _outlier_fields(value, mean, std, count):
        if count is None or count < 5 or std is None or std == 0:
            return {"is_outlier": False, "z_score": None, "percentile": None}
        z = (float(value) - float(mean)) / float(std)
        return {
            "is_outlier": abs(z) > 2.0,
            "z_score": round(z, 2),
            "percentile": int(scipy_stats.norm.cdf(z) * 100),
        }

    stats = []
    for r in rows:
        entry = {
            "stat_id":               r["stat_id"],
            "player_name":           r["player_name"],
            "game_name":             r["game_name"],
            "game_installment":      r["game_installment"],
            "game_id":               r["game_id"],
            "stat_type":             r["stat_type"],
            "stat_value":            r["stat_value"],
            "game_mode":             r["game_mode"],
            "game_level":            r["game_level"],
            "win":                   r["win"],
            "ranked":                r["ranked"],
            "pre_match_rank_value":  r["pre_match_rank_value"],
            "post_match_rank_value": r["post_match_rank_value"],
            "played_at":             r["played_at"].isoformat() if r["played_at"] else None,
        }
        entry.update(_outlier_fields(r["stat_value"], r["hist_mean"], r["hist_std"], r["hist_count"]))
        stats.append(entry)

    return {"stats": stats}


# ---------------------------------------------------------------------------
# Update stat
# ---------------------------------------------------------------------------

@router.put("/update_stats/{stat_id}")
async def update_stats(stat_id: int, body: UpdateStatRequest, conn: DynamicConn, user: TrustedUser):
    """Update a stat entry. Caller must be trusted and own the stat."""
    # Verify ownership + trust
    owned = await conn.fetchval("""
        SELECT gs.stat_id
        FROM fact.fact_game_stats gs
        JOIN dim.dim_players p ON gs.player_id = p.player_id
        JOIN dim.dim_users u ON p.user_id = u.user_id
        WHERE gs.stat_id = $1 AND u.user_id = $2 AND u.is_trusted = TRUE
    """, stat_id, user["user_id"])

    if not owned:
        raise HTTPException(status_code=404, detail="Stat not found or not authorized.")

    await conn.execute("""
        UPDATE fact.fact_game_stats SET
            stat_type             = COALESCE($1, stat_type),
            stat_value            = COALESCE($2, stat_value),
            game_mode             = COALESCE($3, game_mode),
            game_level            = $4,
            win                   = $5,
            ranked                = COALESCE($6, ranked),
            pre_match_rank_value  = $7,
            post_match_rank_value = $8
        WHERE stat_id = $9
    """,
        body.stat_type,
        body.stat_value,
        body.game_mode,
        body.game_level,
        body.win,
        body.ranked,
        body.pre_match_rank_value,
        body.post_match_rank_value,
        stat_id,
    )
    print(f"[stats] Stat {stat_id} updated by {user['email']}")
    return {"message": "Stat updated successfully."}


# ---------------------------------------------------------------------------
# Delete stat
# ---------------------------------------------------------------------------

@router.delete("/delete_stats/{stat_id}")
async def delete_stats(stat_id: int, conn: DynamicConn, user: TrustedUser):
    """
    Delete a stat entry owned by the caller.
    Returns last_stat_deleted=True if this was the final stat for that game.
    """
    # Verify ownership
    stat_info = await conn.fetchrow("""
        SELECT gs.game_id, p.user_id
        FROM fact.fact_game_stats gs
        JOIN dim.dim_players p ON gs.player_id = p.player_id
        JOIN dim.dim_users u ON p.user_id = u.user_id
        WHERE gs.stat_id = $1 AND u.user_id = $2
    """, stat_id, user["user_id"])

    if not stat_info:
        raise HTTPException(status_code=404, detail="Stat not found or permission denied.")

    game_id   = stat_info["game_id"]
    user_id   = stat_info["user_id"]

    await conn.execute("DELETE FROM fact.fact_game_stats WHERE stat_id = $1", stat_id)
    print(f"[stats] Stat {stat_id} deleted by {user['email']}")

    # Check if any stats remain for this game for this user
    other_exists = await conn.fetchval("""
        SELECT 1 FROM fact.fact_game_stats gs
        JOIN dim.dim_players p ON gs.player_id = p.player_id
        WHERE gs.game_id = $1 AND p.user_id = $2
        LIMIT 1
    """, game_id, user_id)

    response = {"message": "Entry successfully deleted."}
    if not other_exists:
        any_exists = await conn.fetchval(
            "SELECT 1 FROM fact.fact_game_stats WHERE game_id = $1 LIMIT 1", game_id
        )
        if not any_exists:
            response["last_stat_deleted"] = True
            response["game_id"] = game_id

    return response


# ---------------------------------------------------------------------------
# Stubbed routes — ported in next chunk
# ---------------------------------------------------------------------------

@router.post("/add_stats", status_code=201)
async def add_stats(body: AddStatsRequest, conn: DynamicConn, user: CurrentUser):
    """
    Submit a batch of stats for a game session.
    Any authenticated user may call this; capabilities vary by role:

      Free/Premium : game must exist in catalog; stat types must already exist
                     for that game; player auto-created up to tier cap (2/5)
      Trusted      : same player cap (5); any stat type; does NOT auto-create games
      Owner        : unlimited players; any stat type; does NOT auto-create games here
                     (use POST /add_game first); social media pipeline fires post-insert
    """
    role:       str  = user.get("role", "free")
    is_owner:   bool = user.get("is_owner", False)
    is_trusted: bool = user.get("is_trusted", False)
    elevated:   bool = is_trusted or is_owner

    # --- Batch-level validation ---
    if not body.stats:
        raise HTTPException(status_code=400, detail="stats must be a non-empty list.")
    if len(body.stats) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 stat rows per submission.")

    seen_types: set[str] = set()
    for s in body.stats:
        t = (s.stat_type or "").strip().title()
        if t in seen_types:
            raise HTTPException(status_code=400, detail=f"Duplicate stat type in submission: '{t}'")
        if t:
            seen_types.add(t)

    # --- Name content checks ---
    for val, field in [
        (body.player_name, "Player name"),
        (body.game_name,   "Game name"),
    ]:
        err = _content_check(val, field, _NAME_RE)
        if err:
            raise HTTPException(status_code=400, detail=err)

    if body.game_installment:
        err = _content_check(body.game_installment, "Game installment", _NAME_RE)
        if err:
            raise HTTPException(status_code=400, detail=err)

    # --- Per-stat validation ---
    for s in body.stats:
        s.stat_type = s.stat_type.strip().title()
        err = _content_check(s.stat_type, "Stat type", _STAT_TYPE_RE)
        if err:
            raise HTTPException(status_code=400, detail=err)

        if s.stat_value < 0 or s.stat_value > 100_000:
            raise HTTPException(status_code=400, detail=f"stat_value out of range: {s.stat_value}")

        for bool_field, v in [
            ("win",                  s.win),
            ("ranked",               s.ranked),
            ("overtime",             s.overtime),
            ("solo_mode",            s.solo_mode),
            ("was_streaming",        s.was_streaming),
            ("first_session_of_day", s.first_session_of_day),
        ]:
            if v is not None and v not in (0, 1):
                raise HTTPException(status_code=400, detail=f"'{bool_field}' must be 0, 1, or null — got: {v}")

        if s.game_level is not None and not (0 <= s.game_level <= 10_000):
            raise HTTPException(status_code=400, detail=f"game_level must be 0–10,000 — got: {s.game_level}")

        if s.party_size is not None and str(s.party_size) not in _VALID_PARTY_SIZES:
            raise HTTPException(status_code=400, detail=f"Invalid party_size: '{s.party_size}'")

        if s.ranked == 1 and not s.pre_match_rank_value:
            raise HTTPException(status_code=400, detail="ranked=1 requires pre_match_rank_value.")

    # --- Resolve queue_platforms (support legacy queue_mode bool) ---
    queue_platforms: list[str] = body.queue_platforms if body.queue_platforms is not None \
        else (["twitter"] if body.queue_mode else [])

    # --- DB: game lookup — game must already exist for ALL roles ---
    if body.game_installment:
        game_id = await conn.fetchval(
            "SELECT game_id FROM dim.dim_games WHERE game_name = $1 AND game_installment = $2",
            body.game_name, body.game_installment,
        )
    else:
        game_id = await conn.fetchval(
            "SELECT game_id FROM dim.dim_games WHERE game_name = $1 AND game_installment IS NULL",
            body.game_name,
        )

    if game_id is None:
        # For everyone: game must be added via POST /add_game (Trusted/Owner) or
        # requested via POST /request_game (Free/Premium) before submitting stats.
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Game not found. Please add it to the catalog first.",
                "request_game": not elevated,   # hint for frontend: show request form vs add form
            },
        )

    await conn.execute(
        "UPDATE dim.dim_games SET last_played_at = NOW() WHERE game_id = $1", game_id
    )

    # --- Free/Premium: stat types must already exist for this game ---
    if not elevated:
        existing_types: set[str] = set(
            r["stat_type"] for r in await conn.fetch(
                "SELECT DISTINCT stat_type FROM fact.fact_game_stats WHERE game_id = $1",
                game_id,
            )
        )
        for s in body.stats:
            if s.stat_type not in existing_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Stat type '{s.stat_type}' is not recognised for this game. "
                           "Please select an existing stat type.",
                )

    # --- DB: user lookup ---
    user_id = user["user_id"]

    # --- DB: player lookup / auto-create (all roles, capped by tier) ---
    player_id = await conn.fetchval(
        "SELECT player_id FROM dim.dim_players WHERE player_name = $1 AND user_id = $2",
        body.player_name, user_id,
    )

    if player_id is None:
        cap = _player_cap(role)
        if cap is not None:
            player_count = await conn.fetchval(
                "SELECT COUNT(*) FROM dim.dim_players WHERE user_id = $1", user_id
            )
            if player_count >= cap:
                raise HTTPException(
                    status_code=403,
                    detail=f"Your plan allows up to {cap} player profiles. "
                           "Upgrade to add more.",
                )
        print(f"[stats] Player '{body.player_name}' for user {user_id} not found — creating.")
        await conn.execute(
            "INSERT INTO dim.dim_players (player_name, user_id, created_at) VALUES ($1, $2, NOW())",
            body.player_name, user_id,
        )
        player_id = await conn.fetchval(
            "SELECT player_id FROM dim.dim_players WHERE player_name = $1 AND user_id = $2",
            body.player_name, user_id,
        )
        if player_id is None:
            raise HTTPException(status_code=500, detail="Failed to retrieve player_id after insert.")

    # --- Duplicate session guard (2-minute window) ---
    two_min_ago = datetime.now(timezone.utc) - timedelta(minutes=2)
    duplicate = await conn.fetchval("""
        SELECT 1 FROM fact.fact_game_stats
        WHERE player_id = $1 AND game_id = $2 AND played_at > $3
        LIMIT 1
    """, player_id, game_id, two_min_ago)

    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="A session was already submitted in the last 2 minutes. "
                   "Check your recent stats before resubmitting.",
        )

    # --- Stat insertion (shared batch timestamp) ---
    batch_timestamp = await conn.fetchval("SELECT NOW()")

    inserted = 0
    for s in body.stats:
        if not s.stat_type or s.stat_value is None:
            continue
        await conn.execute("""
            INSERT INTO fact.fact_game_stats
            (game_id, player_id, stat_type, stat_value, game_mode, solo_mode, party_size,
             game_level, win, ranked, pre_match_rank_value, post_match_rank_value,
             overtime, difficulty, input_device, platform, first_session_of_day, was_streaming,
             source, played_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)
        """,
            game_id, player_id, s.stat_type, s.stat_value,
            s.game_mode, s.solo_mode, s.party_size,
            s.game_level, s.win, s.ranked,
            s.pre_match_rank_value, s.post_match_rank_value,
            s.overtime, s.difficulty,
            s.input_device, s.platform,
            s.first_session_of_day, s.was_streaming,
            s.source, batch_timestamp,
        )
        inserted += 1

    if inserted == 0:
        raise HTTPException(status_code=400, detail="No valid stats provided to insert.")

    print(f"[stats] {inserted} stat(s) inserted for player {player_id} / game {game_id} by {user['email']}")

    # Invalidate OBS dashboard/ticker cache so next poll reflects new stats
    _cache_invalidate_obs()

    if is_owner:
        import asyncio
        from utils.social_pipeline import run_social_media_pipeline
        asyncio.create_task(
            asyncio.to_thread(
                run_social_media_pipeline,
                player_id=player_id,
                player_name=body.player_name,
                game_id=game_id,
                game_name=body.game_name,
                game_installment=body.game_installment,
                stats=[s.model_dump() for s in body.stats],
                is_live=body.is_live,
                credit_style=body.credit_style,
                queue_platforms=queue_platforms,
            )
        )
        post_action = "queued" if queue_platforms else "posting"
    else:
        post_action = "skipped"

    return {
        "message": f"Stats successfully added ({inserted} records)!",
        "social_media": post_action,
    }


@router.get("/get_summary/{game_id}")
async def get_summary(
    game_id:   int,
    conn:      DynamicConn,
    user:      CurrentUser,
    player_id: int = Query(...),
    game_mode: str | None = Query(default=None),
    tz:        str = Query(default="America/Los_Angeles"),
):
    """
    Today's average and all-time best KPIs for the top 3 stat types.
    Scoped to the authenticated user's player.
    """
    game_mode = game_mode.strip() if game_mode else None

    _LOWER_IS_BETTER = {"respawn", "damage taken", "loss", "missed"}

    def _lib(stat_type: str) -> bool:
        return any(kw in stat_type.lower() for kw in _LOWER_IS_BETTER)

    def _ci_and_z(values: list[float], today_val: float | None = None):
        n = len(values)
        if n < 3:
            return None, None, None, n
        arr = np.array(values, dtype=float)
        sem = float(scipy_stats.sem(arr))
        if sem == 0:
            return None, None, None, n
        ci = scipy_stats.t.interval(0.95, n - 1, loc=float(np.mean(arr)), scale=sem)
        z = None
        if today_val is not None:
            std = float(np.std(arr, ddof=1))
            z = round((today_val - float(np.mean(arr))) / std, 2) if std > 0 else 0.0
        return round(float(ci[0]), 1), round(float(ci[1]), 1), z, n

    # Verify player belongs to authenticated user
    owned = await conn.fetchval(
        "SELECT 1 FROM dim.dim_players WHERE player_id = $1 AND user_id = $2",
        player_id, user["user_id"],
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Player not found.")

    # Top 3 stat types by ascending average value
    mode_filter = "AND game_mode = $3" if game_mode else ""
    params      = [player_id, game_id] + ([game_mode] if game_mode else [])
    top_rows    = await conn.fetch(f"""
        SELECT stat_type FROM fact.fact_game_stats
        WHERE player_id = $1 AND game_id = $2 AND stat_type IS NOT NULL
        {mode_filter}
        GROUP BY stat_type
        HAVING AVG(stat_value) > 0
        ORDER BY AVG(stat_value) ASC
        LIMIT 3
    """, *params)
    top_stats = [r["stat_type"] for r in top_rows]

    if not top_stats:
        return {"today_avg": [], "all_time_best": []}

    stat_params = [player_id, game_id, top_stats] + ([game_mode] if game_mode else [])
    gm_filter   = f"AND game_mode = ${len(stat_params)}" if game_mode else ""

    # Today's average (tz-adjusted)
    today_rows = await conn.fetch(f"""
        SELECT stat_type, ROUND(AVG(stat_value)) AS avg_val
        FROM fact.fact_game_stats
        WHERE player_id = $1 AND game_id = $2
          AND stat_type = ANY($3::text[])
          AND (played_at AT TIME ZONE $4)::DATE = (NOW() AT TIME ZONE $4)::DATE
          {gm_filter}
        GROUP BY stat_type
    """, player_id, game_id, top_stats, tz, *([game_mode] if game_mode else []))
    today_map = {r["stat_type"]: int(r["avg_val"]) for r in today_rows}

    # All-time best
    best_rows = await conn.fetch(f"""
        SELECT stat_type, MAX(stat_value) AS max_val, MIN(stat_value) AS min_val
        FROM fact.fact_game_stats
        WHERE player_id = $1 AND game_id = $2
          AND stat_type = ANY($3::text[])
          {gm_filter}
        GROUP BY stat_type
    """, player_id, game_id, top_stats, *([game_mode] if game_mode else []))

    # Historical values for CI / z-score
    hist_rows = await conn.fetch(f"""
        SELECT stat_type, stat_value FROM fact.fact_game_stats
        WHERE player_id = $1 AND game_id = $2
          AND stat_type = ANY($3::text[])
          {gm_filter}
        ORDER BY stat_type
    """, player_id, game_id, top_stats, *([game_mode] if game_mode else []))
    hist: dict[str, list[float]] = {}
    for r in hist_rows:
        hist.setdefault(r["stat_type"], []).append(float(r["stat_value"]))

    today_avg_out = []
    for st in top_stats:
        val = today_map.get(st)
        if val is None:
            continue
        ci_lo, ci_hi, z, n = _ci_and_z(hist.get(st, []), val)
        today_avg_out.append({
            "stat_type": st, "value": val, "lower_is_better": _lib(st),
            "ci_low": ci_lo, "ci_high": ci_hi, "n_sessions": n, "today_z_score": z,
        })

    all_time_out = []
    for r in best_rows:
        st  = r["stat_type"]
        lib = _lib(st)
        raw = r["min_val"] if lib else r["max_val"]
        best_val = int(raw) if float(raw) == int(raw) else round(float(raw), 1)
        ci_lo, ci_hi, _, n = _ci_and_z(hist.get(st, []))
        all_time_out.append({
            "stat_type": st, "value": best_val, "lower_is_better": lib,
            "ci_low": ci_lo, "ci_high": ci_hi, "n_sessions": n,
        })

    return {"today_avg": today_avg_out, "all_time_best": all_time_out}


@router.get("/get_streaks/{game_id}")
async def get_streaks(
    game_id:   int,
    conn:      DynamicConn,
    user:      CurrentUser,
    player_id: int = Query(...),
    tz:        str = Query(default="America/Los_Angeles"),
):
    """
    Current streak, longest streak, last session date, and total session days.
    Uses the user's local timezone so the streak doesn't reset at UTC midnight.
    """
    owned = await conn.fetchval(
        "SELECT 1 FROM dim.dim_players WHERE player_id = $1 AND user_id = $2",
        player_id, user["user_id"],
    )
    if not owned:
        raise HTTPException(status_code=404, detail="Player not found.")

    rows = await conn.fetch("""
        SELECT DISTINCT (played_at AT TIME ZONE $1)::DATE AS session_date
        FROM fact.fact_game_stats
        WHERE player_id = $2 AND game_id = $3
        ORDER BY session_date DESC
    """, tz, player_id, game_id)

    dates = [r["session_date"] for r in rows]  # newest first

    if not dates:
        return {"current_streak": 0, "longest_streak": 0, "last_session": None, "total_session_days": 0}

    today = datetime.now(ZoneInfo(tz)).date()

    # Current streak — count back from today or yesterday
    current = 0
    if dates[0] >= today - timedelta(days=1):
        expected = dates[0]
        for d in dates:
            if d == expected:
                current += 1
                expected -= timedelta(days=1)
            else:
                break

    # Longest streak (ascending scan)
    asc     = sorted(dates)
    longest = run = 1
    for i in range(1, len(asc)):
        if (asc[i] - asc[i - 1]).days == 1:
            run    += 1
            longest = max(longest, run)
        else:
            run = 1

    return {
        "current_streak":    current,
        "longest_streak":    max(current, longest),
        "last_session":      dates[0].isoformat(),
        "total_session_days": len(dates),
    }


@router.get("/get_ticker_facts/{game_id}")
async def get_ticker_facts(
    game_id:   int,
    conn:      DynamicConn,
    user:      CurrentUser,
    player_id: int = Query(...),
    tz:        str = Query(default="America/Los_Angeles"),
):
    """
    Tiered educational stat facts for the Summary page ticker (JWT-authenticated).
    Tiers: 1–2 sessions → basic | 3–30 → + descriptive | 30+ → + advanced
    """
    from api.routers.obs import _basic_facts, _descriptive_facts, _advanced_facts

    game_row = await conn.fetchrow(
        "SELECT game_name, game_installment FROM dim.dim_games WHERE game_id = $1", game_id
    )
    if not game_row:
        raise HTTPException(status_code=404, detail="Game not found.")
    installment = game_row["game_installment"] or ""
    game_name   = f"{game_row['game_name']}: {installment}" if installment else game_row["game_name"]

    player_row = await conn.fetchrow(
        "SELECT player_name FROM dim.dim_players WHERE player_id = $1 AND user_id = $2",
        player_id, user["user_id"],
    )
    if not player_row:
        raise HTTPException(status_code=404, detail="Player not found.")
    player_name = player_row["player_name"]

    sessions = await conn.fetchval("""
        SELECT COUNT(DISTINCT played_at) FROM fact.fact_game_stats
        WHERE player_id = $1 AND game_id = $2
    """, player_id, game_id)

    if not sessions:
        return {"facts": [], "sessions": 0}

    stat_types = [
        r["stat_type"] for r in await conn.fetch("""
            SELECT DISTINCT stat_type FROM fact.fact_game_stats
            WHERE player_id = $1 AND game_id = $2 AND stat_type IS NOT NULL
        """, player_id, game_id)
    ]

    # Fetch all values in one query
    value_rows = await conn.fetch("""
        SELECT stat_type, stat_value FROM fact.fact_game_stats
        WHERE player_id = $1 AND game_id = $2 AND stat_type = ANY($3::text[])
        ORDER BY stat_value
    """, player_id, game_id, stat_types)
    values_by_stat: dict[str, list] = {}
    for r in value_rows:
        values_by_stat.setdefault(r["stat_type"], []).append(r["stat_value"])

    # Best per stat for basic facts
    best_by_stat = {}
    for st in stat_types[:3]:
        row = await conn.fetchrow("""
            SELECT stat_value, (played_at AT TIME ZONE $1)::DATE AS play_date
            FROM fact.fact_game_stats
            WHERE player_id = $2 AND game_id = $3 AND stat_type = $4
            ORDER BY stat_value DESC LIMIT 1
        """, tz, player_id, game_id, st)
        if row:
            best_by_stat[st] = (row["stat_value"], row["play_date"])

    overall_high_row = await conn.fetchrow("""
        SELECT stat_type, MAX(stat_value) AS high_score FROM fact.fact_game_stats
        WHERE player_id = $1 AND game_id = $2
        GROUP BY stat_type ORDER BY high_score DESC LIMIT 1
    """, player_id, game_id)
    overall_high = (overall_high_row["stat_type"], overall_high_row["high_score"]) \
        if overall_high_row else None

    facts: list[str] = []
    facts += _basic_facts(stat_types, best_by_stat, overall_high, player_name, game_name)
    if sessions >= 3:
        facts += _descriptive_facts(stat_types, values_by_stat, player_name, game_name)
    if sessions > 30:
        facts += _advanced_facts(stat_types, values_by_stat, player_name, game_name)

    return {"facts": facts, "sessions": sessions}
