"""
ML service — Phase 3b.

Storage strategy:
  Personal users
    - Logistic Regression  → coefficients stored as JSONB in app.ml_model_runs
    - RF / XGBoost         → pickled model in GCS bucket (gaming-stats-images-thebolgroup)

  Public users
    - Logistic Regression  → coefficients stored as JSONB in app.ml_model_runs
    - RF / XGBoost         → pickled model in Supabase Storage (100 GB Pro tier)
                             evicted after 90 days of inactivity; threshold gate at 50 sessions

Client-side inference:
  LR coefficients are returned as JSONB so the SummaryTab TypeScript sigmoid
  can render what-if sliders with zero extra backend calls.
"""

import asyncpg
from typing import Any


SESSION_THRESHOLD = 50    # minimum sessions before a model is trained
EVICTION_DAYS = 90        # public storage eviction window


async def get_prediction(
    conn: asyncpg.Connection,
    game_id: int,
    player_id: int,
    stat_inputs: dict[str, float],
) -> dict[str, Any]:
    # TODO: load latest LR coefficients from app.ml_model_runs and apply sigmoid
    raise NotImplementedError


async def enqueue_training(
    conn: asyncpg.Connection,
    game_id: int,
    player_id: int,
) -> str:
    """
    Enqueue a training job.  Rejects if session count < SESSION_THRESHOLD.
    Returns job_id.
    """
    # TODO: implement
    raise NotImplementedError


async def get_model_runs(
    conn: asyncpg.Connection,
    game_id: int,
    player_id: int,
) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT run_id, model_type, target_stat, metrics, trained_at
        FROM app.ml_model_runs
        WHERE game_id = $1 AND player_id = $2
        ORDER BY trained_at DESC
        LIMIT 20
        """,
        game_id,
        player_id,
    )
    return [dict(r) for r in rows]
