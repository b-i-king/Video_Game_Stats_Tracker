"""
FastAPI migration placeholder for flask_app.py
===============================================
STATUS: NOT IN USE — reference only. Flask is the active backend.

This file shows the 1-to-1 rewrite of every Flask route into FastAPI
patterns. When migrating, copy the SQL bodies from flask_app.py — only
the framework boilerplate changes.

Key differences vs Flask
─────────────────────────
1. Routes are async — use asyncpg (async Postgres driver) instead of
   psycopg2 SimpleConnectionPool.
2. Auth uses FastAPI Depends() instead of decorator wrappers.
3. Request bodies are Pydantic models — automatic validation + OpenAPI
   docs generated for free at /docs.
4. CORS and startup/shutdown handled via middleware + lifespan.
5. HTTPException replaces jsonify(...), status_code.

When to migrate
───────────────
Good trigger points:
  • Starting Riot API integration (concurrent HTTP calls → async wins)
  • Adding ML score prediction (scikit-learn / XGBoost endpoints)
  • After Supabase migration is stable (asyncpg works natively with Postgres)

New in this file vs flask_app.py
──────────────────────────────────
  • /api/predict_score/{game_id}  — ML placeholder (see bottom of file)
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import os
import time
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

import asyncpg
import jwt as pyjwt
from fastapi import Depends, FastAPI, Header, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, EmailStr

from utils.chart_utils import (
    generate_bar_chart,
    generate_line_chart,
    get_stat_history_from_db,
    generate_interactive_chart,
)
from utils.gcs_utils import upload_chart_to_gcs, upload_interactive_chart_to_gcs
from utils.ifttt_utils import trigger_ifttt_post, generate_post_caption
from utils.queue_utils import (
    ensure_post_queue_table,
    enqueue_post,
    get_oldest_pending,
    mark_status,
    get_queue_counts,
    reset_failed_to_pending,
    reset_stale_processing,
    purge_old_sent,
)

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

DB_URL           = os.environ["DB_URL"]
DB_NAME          = os.environ["DB_NAME"]
DB_USER          = os.environ["DB_USER"]
DB_PASSWORD      = os.environ["DB_PASSWORD"]
API_KEY          = os.environ["API_KEY"]
JWT_SECRET_KEY   = os.environ["JWT_SECRET_KEY"]
OBS_SECRET_KEY   = os.environ.get("OBS_SECRET_KEY")
CRON_SECRET      = os.environ.get("CRON_SECRET")
TRUSTED_EMAILS   = {
    e.strip()
    for e in os.environ.get("TRUSTED_EMAILS", "").split(",")
    if e.strip()
}

# ---------------------------------------------------------------------------
# In-memory caches (identical logic to Flask version)
# ---------------------------------------------------------------------------

_endpoint_cache: dict = {}
obs_active: bool = False
_user_cache: dict = {}


def _cache_get(key):
    entry = _endpoint_cache.get(key)
    if entry and time.monotonic() < entry[2]:
        return entry[0], entry[1]
    _endpoint_cache.pop(key, None)
    return None


def _cache_set(key, data, status_code, ttl_seconds):
    _endpoint_cache[key] = (data, status_code, time.monotonic() + ttl_seconds)


def _cache_invalidate_obs():
    for k in list(_endpoint_cache.keys()):
        if k.startswith(("dash_", "ticker_")):
            _endpoint_cache.pop(k, None)


def _user_cache_get(email: str):
    entry = _user_cache.get(email)
    if entry and time.monotonic() < entry[2]:
        return entry[0], entry[1]
    _user_cache.pop(email, None)
    return None


def _user_cache_set(email: str, user_id, is_trusted: bool, ttl: int = 300):
    _user_cache[email] = (user_id, is_trusted, time.monotonic() + ttl)


# ---------------------------------------------------------------------------
# Database pool — asyncpg (replaces psycopg2 SimpleConnectionPool)
# ---------------------------------------------------------------------------

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """FastAPI dependency — injects a pool reference into route handlers."""
    assert _pool is not None, "DB pool not initialized"
    return _pool


# asyncpg uses a context-manager to check out/return connections automatically
# so there is no manual get_db_connection() / release_db_connection() needed.

# ---------------------------------------------------------------------------
# Lifespan — replaces Flask's @app.before_first_request + atexit
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool
    print("Initializing asyncpg pool...")
    _pool = await asyncpg.create_pool(
        host=DB_URL,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=5439,
        ssl="require",
        min_size=0,
        max_size=3,
        command_timeout=30,
    )
    print("✅ asyncpg pool ready.")

    try:
        ensure_post_queue_table()
        print("✅ post_queue table ready.")
    except Exception as e:
        print(f"⚠️  post_queue init failed: {e}")

    yield  # app runs here

    print("Closing asyncpg pool...")
    await _pool.close()
    print("✅ Pool closed.")


# ---------------------------------------------------------------------------
# App init + CORS
# ---------------------------------------------------------------------------

app = FastAPI(title="Game Tracker API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://video-game-stats-tracking.streamlit.app",
        "https://video-game-stats-tracker.vercel.app",
        "http://localhost:3000",
        "http://localhost:8501",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Auth dependencies — replaces @requires_api_key / @requires_jwt_auth
# ---------------------------------------------------------------------------

async def require_api_key(x_api_key: str = Header(...)):
    """Dependency: validates X-API-KEY header."""
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


async def require_jwt(authorization: str = Header(...)) -> dict:
    """
    Dependency: validates Bearer JWT and returns the decoded payload.
    Inject as:  current_user: dict = Depends(require_jwt)
    Access email as: current_user["email"]
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="JWT is missing or malformed")
    token = authorization.split(" ", 1)[1]
    try:
        payload = pyjwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=["HS256"],
            leeway=timedelta(seconds=10),
        )
        if not payload.get("email"):
            raise HTTPException(status_code=401, detail="Invalid JWT payload")
        return payload
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="JWT has expired")
    except pyjwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid JWT: {e}")


# ---------------------------------------------------------------------------
# Pydantic models — request bodies (replaces request.json)
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr


class AddUserRequest(BaseModel):
    email: EmailStr


class StatRow(BaseModel):
    stat_type: str
    stat_value: int
    game_mode: str = "Main"
    solo_mode: int = 1
    party_size: str = "Solo"
    game_level: Optional[int] = None
    win: Optional[int] = None
    ranked: int = 0
    pre_match_rank_value: Optional[str] = None
    post_match_rank_value: Optional[str] = None
    overtime: int = 0
    difficulty: Optional[str] = None
    input_device: str = "Controller"
    platform: str = "PC"
    first_session_of_day: int = 1
    was_streaming: int = 0


class AddStatsRequest(BaseModel):
    player_name: str
    game_name: str
    game_installment: Optional[str] = None
    game_genre: Optional[str] = None
    game_subgenre: Optional[str] = None
    stats: list[StatRow]
    is_live: bool = False
    queue_platforms: Optional[list[str]] = None
    queue_mode: Optional[bool] = None  # legacy — maps to ['twitter']
    credit_style: str = "shoutout"


class UpdatePlayerRequest(BaseModel):
    player_name: str


class UpdateGameRequest(BaseModel):
    game_name: Optional[str] = None
    game_installment: Optional[str] = None
    game_genre: Optional[str] = None
    game_subgenre: Optional[str] = None


class UpdateStatRequest(BaseModel):
    stat_value: Optional[int] = None
    game_mode: Optional[str] = None
    win: Optional[int] = None
    ranked: Optional[int] = None
    played_at: Optional[str] = None


class SetLiveStateRequest(BaseModel):
    player_id: int
    game_id: int


class SetObsActiveRequest(BaseModel):
    active: bool


class DownloadChartRequest(BaseModel):
    game_id: int
    player_name: str
    platform: str  # "twitter" | "instagram"


class AskRequest(BaseModel):
    prompt: str


class ProcessQueueRequest(BaseModel):
    secret: str


# ---------------------------------------------------------------------------
# Routes — Auth / Users
# ---------------------------------------------------------------------------

@app.post("/api/login")
async def login(
    body: LoginRequest,
    _=Depends(require_api_key),
    pool: asyncpg.Pool = Depends(get_pool),
):
    # SQL body identical to flask_app.py login()
    # Replace conn/cur psycopg2 calls with:
    #   async with pool.acquire() as conn:
    #       row = await conn.fetchrow("SELECT ...", email)
    ...


@app.post("/api/add_user")
async def add_user(
    body: AddUserRequest,
    _=Depends(require_api_key),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


@app.post("/api/add_trusted_user")
async def add_trusted_user(
    body: AddUserRequest,
    _=Depends(require_api_key),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


# ---------------------------------------------------------------------------
# Routes — Stats
# ---------------------------------------------------------------------------

@app.post("/api/add_stats")
async def add_stats(
    body: AddStatsRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    # queue_platforms backward-compat (same logic as Flask)
    if body.queue_platforms is not None:
        queue_platforms = body.queue_platforms
    else:
        queue_platforms = ["twitter"] if body.queue_mode else []
    # SQL body identical to flask_app.py add_stats()
    # Fire social-media pipeline in background (replaces threading.Thread):
    #   background_tasks.add_task(_social_media_pipeline, ...)
    ...


@app.get("/api/get_recent_stats")
async def get_recent_stats(
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


@app.delete("/api/delete_stats/{stat_id}")
async def delete_stats(
    stat_id: int,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


@app.put("/api/update_stats/{stat_id}")
async def update_stats(
    stat_id: int,
    body: UpdateStatRequest,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


# ---------------------------------------------------------------------------
# Routes — Players
# ---------------------------------------------------------------------------

@app.get("/api/get_players")
async def get_players(
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


@app.put("/api/update_player/{player_id}")
async def update_player(
    player_id: int,
    body: UpdatePlayerRequest,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


@app.delete("/api/delete_player/{player_id}")
async def delete_player(
    player_id: int,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


# ---------------------------------------------------------------------------
# Routes — Games
# ---------------------------------------------------------------------------

@app.get("/api/get_games")
async def get_games(
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


@app.get("/api/get_game_details/{game_id}")
async def get_game_details(
    game_id: int,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


@app.put("/api/update_game/{game_id}")
async def update_game(
    game_id: int,
    body: UpdateGameRequest,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


@app.delete("/api/delete_game/{game_id}")
async def delete_game(
    game_id: int,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


@app.get("/api/get_game_franchises")
async def get_game_franchises(
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


@app.get("/api/get_game_installments/{franchise_name:path}")
async def get_game_installments(
    franchise_name: str,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


@app.get("/api/get_game_ranks/{game_id}")
async def get_game_ranks(
    game_id: int,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


@app.get("/api/get_game_modes/{game_id}")
async def get_game_modes(
    game_id: int,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


@app.get("/api/get_game_stat_types/{game_id}")
async def get_game_stat_types(
    game_id: int,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


@app.get("/api/get_game_context/{game_id}")
async def get_game_context(
    game_id: int,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


# ---------------------------------------------------------------------------
# Routes — OBS / Live Dashboard
# ---------------------------------------------------------------------------

@app.post("/api/set_live_state")
async def set_live_state(
    body: SetLiveStateRequest,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


@app.get("/api/obs_status")
async def obs_status(current_user: dict = Depends(require_jwt)):
    return {"obs_active": obs_active}


@app.post("/api/set_obs_active")
async def set_obs_active(
    body: SetObsActiveRequest,
    current_user: dict = Depends(require_jwt),
):
    global obs_active
    obs_active = body.active
    return {"obs_active": obs_active}


@app.get("/api/get_live_dashboard")
async def get_live_dashboard(
    obs_secret: str,
    pool: asyncpg.Pool = Depends(get_pool),
):
    # Validated with OBS_SECRET_KEY instead of JWT (OBS can't send headers)
    ...


@app.get("/api/get_stat_ticker")
async def get_stat_ticker(
    obs_secret: str,
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


# ---------------------------------------------------------------------------
# Routes — Queue
# ---------------------------------------------------------------------------

@app.post("/api/process_queue")
async def process_queue(body: ProcessQueueRequest):
    if body.secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    ...


@app.get("/api/queue_status")
async def queue_status(current_user: dict = Depends(require_jwt)):
    counts = get_queue_counts()
    return counts


@app.post("/api/retry_failed")
async def retry_failed(current_user: dict = Depends(require_jwt)):
    reset_count = reset_failed_to_pending()
    return {"reset_count": reset_count}


# ---------------------------------------------------------------------------
# Routes — Charts / Social
# ---------------------------------------------------------------------------

@app.post("/api/post_instagram")
async def post_instagram(
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


@app.get("/api/preview_instagram")
async def preview_instagram(
    player_name: str,
    game_id: int,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    ...


@app.get("/api/get_summary/{game_id}")
async def get_summary(
    game_id: int,
    player_name: str,
    game_mode: Optional[str] = None,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    # SQL body identical to flask_app.py get_summary()
    ...


@app.get("/api/get_interactive_chart/{game_id}", response_class=HTMLResponse)
async def get_interactive_chart(
    game_id: int,
    player_name: str,
    game_mode: Optional[str] = None,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    # SQL body identical to flask_app.py get_interactive_chart()
    ...


@app.post("/api/download_chart")
async def download_chart(
    body: DownloadChartRequest,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    # Returns StreamingResponse instead of send_file()
    ...


# ---------------------------------------------------------------------------
# Routes — Bolt AI
# ---------------------------------------------------------------------------

@app.post("/api/ask")
async def ask_bolt(
    body: AskRequest,
    current_user: dict = Depends(require_jwt),
):
    if not os.environ.get("GEMINI_API_KEY"):
        return {"reply": "Bolt isn't configured yet — add GEMINI_API_KEY to enable AI features."}
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="No prompt provided")
    try:
        from utils.ai_utils import ask_agent
        reply = await asyncio.to_thread(ask_agent, prompt)  # run sync Gemini call off event loop
        return {"reply": reply}
    except Exception as e:
        print(f"[Bolt] Error: {e}")
        return {"reply": "Something went wrong on my end. Try again in a moment."}


# ---------------------------------------------------------------------------
# Routes — Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/db_health")
async def db_health(pool: asyncpg.Pool = Depends(get_pool)):
    try:
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# ML — Score Prediction  (NEW — not in flask_app.py)
# ---------------------------------------------------------------------------
#
# Predicts the player's next stat value for a given game + stat_type using
# a rolling time-series model trained on their historical entries.
#
# Suggested stack:
#   pip install scikit-learn xgboost pandas numpy
#
# Model options (start simple, upgrade as data grows):
#   • Linear Regression    — good baseline, interpretable
#   • XGBoost Regressor    — handles non-linear trends and game-mode features
#   • Prophet (Meta)       — purpose-built for time-series with seasonality
#
# Features to use:
#   - Rolling 5/10/20 session average of stat_value
#   - game_mode (encoded)
#   - ranked (0/1)
#   - win (0/1)
#   - day_of_week, hour_of_day (from played_at)
#   - session count (proxy for skill over time)
#
# Training cadence: retrain on each /api/add_stats call (cheap for personal
# scale); cache model per (player_id, game_id, stat_type) in memory.
# ---------------------------------------------------------------------------

class PredictScoreRequest(BaseModel):
    player_name: str
    stat_type: str
    game_mode: Optional[str] = None


class PredictScoreResponse(BaseModel):
    stat_type: str
    predicted_value: float
    confidence_low: float
    confidence_high: float
    sessions_used: int
    model: str


@app.get("/api/predict_score/{game_id}", response_model=PredictScoreResponse)
async def predict_score(
    game_id: int,
    player_name: str,
    stat_type: str,
    game_mode: Optional[str] = None,
    current_user: dict = Depends(require_jwt),
    pool: asyncpg.Pool = Depends(get_pool),
):
    """
    Predicts the player's next stat value based on their session history.

    Implementation steps (when ready):
    1. Pull last N sessions from fact.fact_game_stats for this
       (player, game_id, stat_type, game_mode).
    2. Build feature matrix: rolling averages, encoded categoricals,
       time features.
    3. Load or train model from in-memory cache keyed by
       (player_id, game_id, stat_type).
    4. Return predicted value + 80% confidence interval.

    Returns 404 if fewer than 10 sessions exist (not enough data).
    """
    # ── placeholder ──────────────────────────────────────────────────────
    # async with pool.acquire() as conn:
    #     rows = await conn.fetch("""
    #         SELECT stat_value, game_mode, ranked, win, played_at
    #         FROM fact.fact_game_stats
    #         WHERE player_id = (SELECT player_id FROM dim.dim_players WHERE player_name = $1)
    #           AND game_id = $2
    #           AND stat_type = $3
    #         ORDER BY played_at DESC
    #         LIMIT 50
    #     """, player_name, game_id, stat_type)
    #
    # if len(rows) < 10:
    #     raise HTTPException(404, "Not enough data to predict (need ≥ 10 sessions)")
    #
    # import pandas as pd
    # from sklearn.linear_model import Ridge
    # df = pd.DataFrame(rows, columns=["stat_value","game_mode","ranked","win","played_at"])
    # ... feature engineering ...
    # model = Ridge().fit(X_train, y_train)
    # pred = model.predict(X_next)[0]
    # return PredictScoreResponse(
    #     stat_type=stat_type,
    #     predicted_value=round(pred, 1),
    #     confidence_low=round(pred * 0.85, 1),
    #     confidence_high=round(pred * 1.15, 1),
    #     sessions_used=len(rows),
    #     model="ridge",
    # )
    raise HTTPException(status_code=501, detail="ML prediction not yet implemented")
