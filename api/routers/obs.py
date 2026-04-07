"""
OBS overlay routes — Owner only.

  JWT-protected (OwnerUser):
    POST /set_live_state       — set current player/game for dashboard
    GET  /obs_status           — returns current obs_active flag
    POST /set_obs_active       — enable/disable OBS overlay polling

  Secret-key protected (OBS browser source — cannot send JWT headers):
    GET  /get_live_dashboard   — live stats for the current player/game
    GET  /get_stat_ticker      — tiered educational stat facts
"""

import time
from collections import Counter
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.core.config import get_settings
from api.core.deps import PersonalConn, DynamicConn, OwnerUser

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory OBS active flag and response cache
# ---------------------------------------------------------------------------

_obs_active: bool = False

_cache: dict = {}   # key → (data, expires_at)


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and time.monotonic() < entry[1]:
        return entry[0]
    return None


def _cache_set(key: str, data, ttl: float):
    _cache[key] = (data, time.monotonic() + ttl)


def _cache_invalidate_obs():
    """Called after new stats are saved to push fresh data on next OBS poll."""
    for k in list(_cache.keys()):
        if k.startswith(("dash_", "ticker_")):
            _cache.pop(k, None)


# ---------------------------------------------------------------------------
# Auth helper for OBS browser source endpoints
# ---------------------------------------------------------------------------

def _check_obs_key(key: str | None) -> None:
    obs_key = get_settings().obs_secret_key
    if not obs_key or key != obs_key:
        raise HTTPException(status_code=401, detail="Unauthorized. Invalid or missing key.")


# ---------------------------------------------------------------------------
# Stat fact helpers (pure — no DB calls, operate on pre-fetched value lists)
# ---------------------------------------------------------------------------

def _abbreviate(stat_name: str) -> str:
    if not stat_name:
        return "XXXX"
    clean = stat_name.replace("Total", "").replace("Average", "").strip()
    return (clean[:4].upper() + "S") if len(clean) > 8 else clean.upper()


def _basic_facts(
    stat_types: list[str],
    best_by_stat: dict,   # {stat_type: (value, date)}
    overall_high: tuple | None,  # (stat_type, value)
    player_name: str,
    game_name: str,
) -> list[str]:
    facts = []
    for st in stat_types[:3]:
        entry = best_by_stat.get(st)
        if entry:
            val, date = entry
            facts.append(
                f"{player_name}'s best {st} in {game_name} was {val} on {date.strftime('%B %d, %Y')}."
            )
    if overall_high:
        st, hi = overall_high
        facts.append(f"The highest {st} recorded for {game_name} is {hi}.")
    return facts


def _descriptive_facts(
    stat_types: list[str],
    values_by_stat: dict,   # {stat_type: sorted list[int]}
    player_name: str,
    game_name: str,
) -> list[str]:
    facts = []
    for st in stat_types[:2]:
        values = values_by_stat.get(st, [])
        if not values:
            continue
        n = len(values)
        mean_val   = round(sum(values) / n, 1)
        median_val = values[n // 2] if n % 2 == 1 \
                     else round((values[n // 2 - 1] + values[n // 2]) / 2, 1)
        min_val, max_val = values[0], values[-1]
        range_val  = max_val - min_val
        mode_val, mode_cnt = Counter(values).most_common(1)[0]

        facts.append(f"On average, {player_name} gets {mean_val} {st} per game in {game_name}.")
        facts.append(f"The median {st} for {player_name} in {game_name} is {median_val}.")
        if mode_cnt > 1:
            facts.append(f"{player_name} most frequently scores {mode_val} {st} in {game_name}.")
        facts.append(
            f"{player_name}'s {st} in {game_name} ranges from {min_val} (minimum) to {max_val} (maximum)."
        )
        facts.append(f"The range of {st} scores in {game_name} is {range_val}.")
    return facts


def _advanced_facts(
    stat_types: list[str],
    values_by_stat: dict,
    player_name: str,
    game_name: str,
) -> list[str]:
    facts = []
    for st in stat_types[:2]:
        values = values_by_stat.get(st, [])
        if len(values) < 2:
            continue
        mean_val  = sum(values) / len(values)
        variance  = sum((x - mean_val) ** 2 for x in values) / len(values)
        std_dev   = round(variance ** 0.5, 2)
        var_round = round(variance, 2)

        def _pct(p):
            n = len(values)
            k = (n - 1) * p
            f = int(k)
            c = k - f
            return values[f] + c * (values[f + 1] - values[f]) if f + 1 < n else values[f]

        p25 = round(_pct(0.25), 1)
        p50 = round(_pct(0.50), 1)
        p75 = round(_pct(0.75), 1)
        variability = "high" if std_dev > mean_val * 0.3 else "low"

        facts.append(
            f"The standard deviation of {st} in {game_name} is {std_dev}, "
            f"showing {variability} variability in performance."
        )
        facts.append(f"The variance of {player_name}'s {st} in {game_name} is {var_round}.")
        facts.append(
            f"25% of {player_name}'s games have {st} below {p25}, while 75% are below {p75}."
        )
        facts.append(f"The median (50th percentile) {st} is {p50} for {player_name} in {game_name}.")
    return facts


# ---------------------------------------------------------------------------
# JWT-protected routes (OwnerUser)
# ---------------------------------------------------------------------------

class LiveStateRequest(BaseModel):
    player_id: int
    game_id:   int


class ObsActiveRequest(BaseModel):
    active: bool


@router.post("/set_live_state")
async def set_live_state(body: LiveStateRequest, conn: DynamicConn, user: OwnerUser):
    """Set the current player/game for the OBS dashboard. Owner only."""
    await conn.execute("""
        INSERT INTO dim.dim_dashboard_state (state_id, current_player_id, current_game_id, updated_at)
        VALUES (1, $1, $2, NOW())
        ON CONFLICT (state_id) DO UPDATE
            SET current_player_id = EXCLUDED.current_player_id,
                current_game_id   = EXCLUDED.current_game_id,
                updated_at        = EXCLUDED.updated_at
    """, body.player_id, body.game_id)
    _cache_invalidate_obs()
    return {"message": "Live state updated."}


@router.get("/obs_status")
async def obs_status(user: OwnerUser):
    """Returns the current OBS active flag. Owner only."""
    return {"obs_active": _obs_active}


@router.post("/set_obs_active")
async def set_obs_active(body: ObsActiveRequest, user: OwnerUser):
    """Enable or disable OBS overlay polling. Owner only."""
    global _obs_active
    _obs_active = body.active
    status = "active" if _obs_active else "sleeping"
    print(f"[obs] OBS overlay {status} — set by {user['email']}")
    return {"obs_active": _obs_active}


# ---------------------------------------------------------------------------
# Secret-key routes (OBS browser source — no JWT possible in URL)
# ---------------------------------------------------------------------------

@router.get("/get_live_dashboard")
async def get_live_dashboard(
    conn: PersonalConn,  # browser source has no JWT — always hits personal DB
    key: str | None = Query(default=None),
    tz: str = Query(default="UTC"),
):
    """
    Live stats for the current player/game.
    Protected by ?key=OBS_SECRET_KEY — used as an OBS browser source URL.
    Returns an idle response when obs_active is False.
    """
    _check_obs_key(key)

    if not _obs_active:
        return {"obs_active": False, "message": "OBS overlay sleeping — activate to load stats."}

    cache_key = f"dash_{tz}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    # Current player/game from dashboard state
    state = await conn.fetchrow(
        "SELECT current_player_id, current_game_id FROM dim.dim_dashboard_state WHERE state_id = 1"
    )
    if not state or not state["current_player_id"] or not state["current_game_id"]:
        raise HTTPException(status_code=404, detail="No live game/player selected.")

    player_id = state["current_player_id"]
    game_id   = state["current_game_id"]

    # Does this game track wins?
    has_wins = await conn.fetchval(
        "SELECT COUNT(*) FROM fact.fact_game_stats WHERE game_id = $1 AND win IS NOT NULL LIMIT 1",
        game_id,
    ) > 0

    # Top 2 (with wins) or top 3 stat types by ascending average value
    stat_limit = 2 if has_wins else 3
    top_rows = await conn.fetch("""
        SELECT stat_type, AVG(stat_value) AS avg_value
        FROM fact.fact_game_stats
        WHERE game_id = $1 AND player_id = $2
          AND stat_type IS NOT NULL AND stat_type != ''
          AND stat_value > 0
        GROUP BY stat_type
        HAVING AVG(stat_value) > 0
        ORDER BY avg_value ASC
        LIMIT $3
    """, game_id, player_id, stat_limit)
    top_stats = [r["stat_type"] for r in top_rows]

    if not top_stats and not has_wins:
        return {
            "stat1": {"label": "STAT 1", "value": 0},
            "stat2": {"label": "STAT 2", "value": 0},
            "stat3": {"label": "STAT 3", "value": 0},
            "time_period": "NEW GAME",
        }

    # "Today" in the requested timezone
    today_row = await conn.fetchrow("SELECT (NOW() AT TIME ZONE $1)::DATE AS d", tz)
    today_date = today_row["d"]

    # Stats today?
    stats_today = await conn.fetchval("""
        SELECT 1 FROM fact.fact_game_stats
        WHERE player_id = $1 AND game_id = $2
          AND (played_at AT TIME ZONE $3)::DATE = $4
        LIMIT 1
    """, player_id, game_id, tz, today_date)

    query_date  = today_date
    time_period = "TODAY"

    if not stats_today:
        most_recent = await conn.fetchval("""
            SELECT MAX((played_at AT TIME ZONE $1)::DATE)
            FROM fact.fact_game_stats
            WHERE player_id = $2 AND game_id = $3
              AND (played_at AT TIME ZONE $1)::DATE < $4
        """, tz, player_id, game_id, today_date)

        if most_recent:
            query_date  = most_recent
            time_period = "PAST"
        else:
            # No stats at all
            results: dict = {}
            idx = 1
            if has_wins:
                results["stat1"] = {"label": "WINS", "value": "---"}
                idx = 2
            for i, st in enumerate(top_stats, idx):
                results[f"stat{i}"] = {"label": _abbreviate(st), "value": "---"}
            results["time_period"] = "N/A"
            return results

    results = {}
    idx = 1

    if has_wins:
        if stats_today:
            win_count = await conn.fetchval("""
                SELECT COUNT(DISTINCT played_at)
                FROM fact.fact_game_stats
                WHERE player_id = $1 AND game_id = $2 AND win = 1
                  AND (played_at AT TIME ZONE $3)::DATE = $4
            """, player_id, game_id, tz, query_date)
        else:
            win_count_raw = await conn.fetchval("""
                SELECT AVG(daily_wins) FROM (
                    SELECT COUNT(DISTINCT played_at) AS daily_wins
                    FROM fact.fact_game_stats
                    WHERE player_id = $1 AND game_id = $2 AND win = 1
                      AND (played_at AT TIME ZONE $3)::DATE = $4
                    GROUP BY (played_at AT TIME ZONE $3)::DATE
                ) sub
            """, player_id, game_id, tz, query_date)
            win_count = int(round(float(win_count_raw))) if win_count_raw else 0
        results["stat1"] = {"label": "WINS", "value": win_count}
        idx = 2

    if top_stats:
        agg = "SUM" if stats_today else "AVG"
        # asyncpg doesn't support dynamic IN lists with $n cleanly — use unnest
        stat_rows = await conn.fetch(f"""
            SELECT stat_type, {agg}(stat_value) AS val
            FROM fact.fact_game_stats
            WHERE player_id = $1 AND game_id = $2
              AND stat_type = ANY($3::text[])
              AND (played_at AT TIME ZONE $4)::DATE = $5
            GROUP BY stat_type
        """, player_id, game_id, top_stats, tz, query_date)
        stat_map = {r["stat_type"]: r["val"] for r in stat_rows}

        for i, st in enumerate(top_stats, idx):
            raw = stat_map.get(st)
            value = (int(raw) if stats_today else round(float(raw))) if raw is not None else 0
            results[f"stat{i}"] = {"label": _abbreviate(st), "value": value}

    results["time_period"] = time_period
    _cache_set(cache_key, results, ttl=600)  # 10 min; invalidated immediately on stat submit
    return results


@router.get("/get_stat_ticker")
async def get_stat_ticker(
    conn: PersonalConn,  # browser source has no JWT — always hits personal DB
    key: str | None = Query(default=None),
    tz: str = Query(default="UTC"),
):
    """
    Tiered educational stat facts for the OBS ticker.
    Protected by ?key=OBS_SECRET_KEY.
    Tiers: 1-2 sessions → basic | 3-30 → + descriptive | 30+ → + advanced
    """
    _check_obs_key(key)

    if not _obs_active:
        return {"obs_active": False, "message": "OBS ticker sleeping — activate to load stats."}

    cache_key = f"ticker_{tz}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    state = await conn.fetchrow(
        "SELECT current_player_id, current_game_id FROM dim.dim_dashboard_state WHERE state_id = 1"
    )
    if not state or not state["current_player_id"] or not state["current_game_id"]:
        raise HTTPException(status_code=404, detail="No live game/player selected.")

    player_id = state["current_player_id"]
    game_id   = state["current_game_id"]

    player_name = await conn.fetchval(
        "SELECT player_name FROM dim.dim_players WHERE player_id = $1", player_id
    )
    game_row = await conn.fetchrow(
        "SELECT game_name, game_installment FROM dim.dim_games WHERE game_id = $1", game_id
    )
    installment = game_row["game_installment"] or ""
    game_name   = f"{game_row['game_name']}: {installment}" if installment else game_row["game_name"]

    sessions = await conn.fetchval("""
        SELECT COUNT(DISTINCT played_at) FROM fact.fact_game_stats
        WHERE player_id = $1 AND game_id = $2
    """, player_id, game_id)

    if not sessions:
        result = {"facts": ["No stats recorded yet. Start playing to see educational stats!"], "games_played": 0}
        _cache_set(cache_key, result, ttl=300)
        return result

    stat_types = [
        r["stat_type"] for r in await conn.fetch("""
            SELECT DISTINCT stat_type FROM fact.fact_game_stats
            WHERE player_id = $1 AND game_id = $2 AND stat_type IS NOT NULL
        """, player_id, game_id)
    ]

    # Fetch values for all stat types in one query
    value_rows = await conn.fetch("""
        SELECT stat_type, stat_value FROM fact.fact_game_stats
        WHERE player_id = $1 AND game_id = $2 AND stat_type = ANY($3::text[])
        ORDER BY stat_value
    """, player_id, game_id, stat_types)

    values_by_stat: dict[str, list] = {}
    for r in value_rows:
        values_by_stat.setdefault(r["stat_type"], []).append(r["stat_value"])

    # Best per stat and overall high for basic facts
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

    result = {"facts": facts, "games_played": sessions}
    _cache_set(cache_key, result, ttl=900)  # 15 min
    return result
