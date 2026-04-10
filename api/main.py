from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.core.config import get_settings as _get_settings
from api.core.database import init_pools, close_pools
from api.routers import auth, players, games, stats, charts, queue, ai, obs, instagram, ml, admin, game_requests, leaderboard, dashboard

@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_pools()
    yield
    await close_pools()


_origins = [o.strip() for o in _get_settings().allowed_origins.split(",") if o.strip()]
app = FastAPI(title="Video Game Stats Tracker API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,      prefix="/api", tags=["auth"])
app.include_router(players.router,   prefix="/api", tags=["players"])
app.include_router(games.router,     prefix="/api", tags=["games"])
app.include_router(stats.router,     prefix="/api", tags=["stats"])
app.include_router(charts.router,    prefix="/api", tags=["charts"])
app.include_router(queue.router,     prefix="/api", tags=["queue"])
app.include_router(ai.router,        prefix="/api", tags=["ai"])
app.include_router(obs.router,       prefix="/api", tags=["obs"])
app.include_router(instagram.router,    prefix="/api", tags=["instagram"])
app.include_router(ml.router,           prefix="/api", tags=["ml"])
app.include_router(admin.router,        prefix="/api", tags=["admin"])
app.include_router(game_requests.router, prefix="/api", tags=["game_requests"])
app.include_router(leaderboard.router,  prefix="/api", tags=["leaderboard"])
app.include_router(dashboard.router,    prefix="/api", tags=["dashboard"])


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}


@app.get("/db_health", tags=["health"])
async def db_health():
    from api.core.database import personal_pool, public_pool
    results = {}
    for name, pool in [("personal", personal_pool), ("public", public_pool)]:
        try:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            results[name] = "ok"
        except Exception as e:
            results[name] = str(e)
    return results
