"""
Bolt AI endpoint — natural language stat queries via Gemini.

Usage limits enforced against app.ai_usage (monthly, public DB):
  Owner           → unlimited (personal pool — no usage table)
  Trusted         → 200 messages / month
  Premium         → 200 messages / month
  Free            → 20 messages / month
"""

import asyncio
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from api.core.deps import DynamicConn, CurrentUser
from utils.ai_utils import ask_agent, build_stats_context

router = APIRouter()

_MONTHLY_LIMITS: dict[str, int | None] = {
    "owner":   None,
    "trusted": 200,
    "premium": 200,
    "free":    20,
}

_MODELS: dict[str, str] = {
    "owner":   "gemini-2.5-flash",
    "trusted": "gemini-2.5-flash",
    "premium": "gemini-2.5-flash",
    "free":    "gemini-2.5-flash-lite",
}


class AskRequest(BaseModel):
    prompt:    str
    game_id:   int | None = None
    player_id: int | None = None
    tz:        str | None = None


@router.post("/ask")
async def ask(body: AskRequest, conn: DynamicConn, user: CurrentUser):
    from api.core.config import get_settings
    if not get_settings().gemini_api_key:
        return {"reply": "Bolt isn't configured yet — add GEMINI_API_KEY to enable AI features."}

    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="No prompt provided.")

    role     = user.get("role", "free")
    is_owner = user.get("is_owner", False)
    limit    = _MONTHLY_LIMITS.get(role, 20)
    model    = _MODELS.get(role, "gemini-2.5-flash-lite")
    uid      = user["user_id"]

    # --- Usage check (skipped for owner) ---
    if not is_owner and limit is not None:
        monthly_used = await conn.fetchval("""
            SELECT COALESCE(SUM(query_count), 0)
            FROM app.ai_usage
            WHERE user_id = $1
              AND query_date >= DATE_TRUNC('month', CURRENT_DATE)
        """, uid)

        if monthly_used >= limit:
            raise HTTPException(
                status_code=429,
                detail=f"Monthly Bolt limit reached ({limit} messages). Upgrade to Premium for more.",
            )

    # --- Build stat context from last session ---
    context = ""
    try:
        rows = await conn.fetch("""
            SELECT p.player_name, g.game_name, g.game_installment,
                   f.stat_type, f.stat_value, f.played_at
            FROM fact.fact_game_stats f
            JOIN dim.dim_players p ON f.player_id = p.player_id
            JOIN dim.dim_games   g ON f.game_id   = g.game_id
            WHERE p.user_id = $1
              AND f.played_at = (
                  SELECT MAX(f2.played_at)
                  FROM fact.fact_game_stats f2
                  JOIN dim.dim_players p2 ON f2.player_id = p2.player_id
                  WHERE p2.user_id = $1
              )
            ORDER BY f.stat_type
        """, uid)

        if rows:
            player_name = rows[0]["player_name"]
            installment = rows[0]["game_installment"]
            game_label  = f"{rows[0]['game_name']}: {installment}" if installment else rows[0]["game_name"]
            stats = [
                {
                    "stat_type":  r["stat_type"],
                    "stat_value": r["stat_value"],
                    "played_at":  r["played_at"].isoformat() if r["played_at"] else None,
                }
                for r in rows
            ]
            context = build_stats_context(player_name, game_label, stats)
    except Exception as ctx_err:
        print(f"[ai] Could not load stat context: {ctx_err}")

    # --- Call Gemini ---
    try:
        reply = await asyncio.to_thread(ask_agent, prompt, context, model, body.tz or "UTC")
    except Exception as e:
        print(f"[ai] Gemini error: {e}")
        return {"reply": "Something went wrong on my end. Try again in a moment."}

    # --- Record usage ---
    try:
        await conn.execute("""
            INSERT INTO app.ai_usage (user_id, query_date, query_count)
            VALUES ($1, CURRENT_DATE, 1)
            ON CONFLICT (user_id, query_date)
            DO UPDATE SET query_count = app.ai_usage.query_count + 1
        """, uid)
    except Exception as e:
        print(f"[ai] Usage tracking error (non-fatal): {e}")

    return {"reply": reply}


@router.get("/ai_usage")
async def get_ai_usage(
    conn:          DynamicConn,
    user:          CurrentUser,
    simulate_role: str | None = Query(default=None),
):
    from datetime import date

    role     = user.get("role", "free")
    is_owner = user.get("is_owner", False)
    is_elevated = user.get("is_trusted") or is_owner

    effective_role = role
    if is_elevated and simulate_role in ("free", "premium", "trusted"):
        effective_role = simulate_role

    limit        = _MONTHLY_LIMITS.get(effective_role, 20)
    is_unlimited = is_owner and not simulate_role

    today = date.today()
    if today.month == 12:
        reset_date = date(today.year + 1, 1, 1)
    else:
        reset_date = date(today.year, today.month + 1, 1)

    try:
        used = await conn.fetchval("""
            SELECT COALESCE(SUM(query_count), 0)
            FROM app.ai_usage
            WHERE user_id = $1
              AND query_date >= DATE_TRUNC('month', CURRENT_DATE)
        """, user["user_id"])
    except Exception:
        used = 0

    response: dict = {
        "used":         int(used),
        "limit":        limit,
        "reset_date":   reset_date.isoformat(),
        "is_unlimited": is_unlimited,
    }
    if is_elevated and simulate_role:
        response["simulating"] = simulate_role

    return response
