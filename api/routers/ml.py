"""
ML router — Logistic Regression win-probability predictions.

Architecture: train server-side with scikit-learn, store coefficients as JSONB,
run inference client-side in TypeScript via sigmoid. Zero extra API calls per view.

Coefficient JSONB shape stored in app.ml_model_runs.model_coefficients (model_target = 'win_probability'):
    {
        "coef":          [[float, ...]],   # shape (1, n_features)
        "intercept":     [float],
        "classes":       [0, 1],
        "feature_names": [str, ...],
        "feature_means": [float, ...],     # StandardScaler μ
        "feature_stds":  [float, ...],     # StandardScaler σ
        "accuracy":      float,
        "n_sessions":    int,
    }

Endpoints:
    GET  /ml/coefficients/{game_id}?player_id=X  — fetch latest stored model
    POST /ml/train/{game_id}?player_id=X         — train and store LR model
"""

import json

import numpy as np
from fastapi import APIRouter, HTTPException, Query

from api.core import database as _db
from api.core.deps import DynamicConn, CurrentUser

router = APIRouter()

MIN_SESSIONS_PERSONAL = 10   # owner has enough data early
MIN_SESSIONS_PUBLIC   = 50   # public users need more signal


# ── helpers ───────────────────────────────────────────────────────────────────

async def _fetch_session_matrix(conn, user_id: int, game_id: int, player_id: int):
    """
    Pivot fact_game_stats into a (sessions × stat_types) feature matrix + win labels.
    Returns (feature_names, X, y).  Returns (None, None, None) if insufficient data.
    """
    rows = await conn.fetch("""
        SELECT
            date_trunc('minute', gs.played_at) AS session_ts,
            gs.stat_type,
            gs.stat_value,
            gs.win
        FROM fact.fact_game_stats gs
        JOIN dim.dim_players p ON gs.player_id = p.player_id
        WHERE p.user_id    = $1
          AND gs.game_id   = $2
          AND gs.player_id = $3
          AND gs.win        IS NOT NULL
          AND gs.stat_value IS NOT NULL
        ORDER BY session_ts
    """, user_id, game_id, player_id)

    if not rows:
        return None, None, None

    # Build per-session dicts: {session_ts: {stat_type: value, "win": int}}
    sessions: dict[str, dict] = {}
    for r in rows:
        ts = str(r["session_ts"])
        if ts not in sessions:
            sessions[ts] = {"win": int(r["win"])}
        sessions[ts][r["stat_type"]] = float(r["stat_value"])

    feature_names = sorted({k for s in sessions.values() for k in s if k != "win"})
    if not feature_names:
        return None, None, None

    X = [[s.get(f, 0.0) for f in feature_names] for s in sessions.values()]
    y = [s["win"] for s in sessions.values()]

    return feature_names, np.array(X, dtype=float), np.array(y, dtype=int)


async def run_lr_training(
    user_id:   int,
    game_id:   int,
    player_id: int,
    is_owner:  bool,
) -> None:
    """
    Train a Logistic Regression model and persist coefficients to app.ml_model_runs.
    Called from background tasks — never raises (logs errors instead).
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    pool = _db.personal_pool if is_owner else _db.public_pool
    if not pool:
        return

    try:
        async with pool.acquire() as conn:
            feature_names, X, y = await _fetch_session_matrix(conn, user_id, game_id, player_id)

            if X is None:
                print(f"[ml] No win-labeled sessions for user={user_id} game={game_id} player={player_id}")
                return

            n_sessions   = len(y)
            min_sessions = MIN_SESSIONS_PERSONAL if is_owner else MIN_SESSIONS_PUBLIC

            if n_sessions < min_sessions:
                print(f"[ml] Skipping: {n_sessions} sessions < {min_sessions} minimum")
                return

            if len(set(y)) < 2:
                print(f"[ml] Skipping: only one outcome class in data (need both wins and losses)")
                return

            scaler   = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            model = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
            model.fit(X_scaled, y)

            accuracy = float(model.score(X_scaled, y))

            coefficients = {
                "coef":          model.coef_.tolist(),
                "intercept":     model.intercept_.tolist(),
                "classes":       model.classes_.tolist(),
                "feature_names": feature_names,
                "feature_means": scaler.mean_.tolist(),
                "feature_stds":  scaler.scale_.tolist(),
                "accuracy":      accuracy,
                "n_sessions":    n_sessions,
            }

            await conn.execute("""
                INSERT INTO app.ml_model_runs
                    (user_id, game_id, player_id, model_target, model_type,
                     r2_score, sessions_used, model_coefficients, trained_at)
                VALUES ($1, $2, $3, 'win_probability', 'logistic_regression',
                        $4, $5, $6, NOW())
                ON CONFLICT (user_id, game_id, player_id, model_type, model_target)
                DO UPDATE SET
                    r2_score           = EXCLUDED.r2_score,
                    sessions_used      = EXCLUDED.sessions_used,
                    model_coefficients = EXCLUDED.model_coefficients,
                    trained_at         = EXCLUDED.trained_at
            """,
                user_id, game_id, player_id,
                accuracy, n_sessions,
                json.dumps(coefficients),
            )

            print(
                f"[ml] LR trained: game={game_id} player={player_id} "
                f"sessions={n_sessions} accuracy={accuracy:.2f} features={feature_names}"
            )

    except Exception as exc:
        print(f"[ml] Training error (non-fatal): {exc}")


# ── routes ────────────────────────────────────────────────────────────────────

@router.get("/ml/coefficients/{game_id}")
async def get_coefficients(
    game_id:   int,
    player_id: int = Query(...),
    conn:      DynamicConn = None,
    user:      CurrentUser = None,
):
    """
    Return the latest LR coefficients for a game+player.
    The frontend uses these to run client-side sigmoid inference — no extra calls per session.
    Returns 404 if no model has been trained yet.
    """
    row = await conn.fetchrow("""
        SELECT model_coefficients, r2_score, sessions_used, trained_at
        FROM app.ml_model_runs
        WHERE user_id    = $1
          AND game_id    = $2
          AND player_id  = $3
          AND model_type   = 'logistic_regression'
          AND model_target = 'win_probability'
          AND model_coefficients IS NOT NULL
        ORDER BY trained_at DESC
        LIMIT 1
    """, user["user_id"], game_id, player_id)

    if not row:
        raise HTTPException(status_code=404, detail="No model trained yet for this game/player.")

    return {
        "game_id":       game_id,
        "player_id":     player_id,
        "model_type":    "logistic_regression",
        "accuracy":      float(row["r2_score"]) if row["r2_score"] else None,
        "sessions_used": row["sessions_used"],
        "trained_at":    row["trained_at"].isoformat() if row["trained_at"] else None,
        "coefficients":  json.loads(row["model_coefficients"]),
    }


@router.post("/ml/train/{game_id}", status_code=202)
async def trigger_training(
    game_id:   int,
    player_id: int = Query(...),
    conn:      DynamicConn = None,
    user:      CurrentUser = None,
):
    """
    Manually trigger LR training for a game+player.
    Returns 202 immediately; training runs in a background thread.
    """
    import asyncio
    is_owner = user.get("is_owner", False)
    asyncio.create_task(
        asyncio.to_thread(
            lambda: asyncio.run(
                run_lr_training(user["user_id"], game_id, player_id, is_owner)
            )
        )
    )
    return {"status": "training_queued", "game_id": game_id, "player_id": player_id}


@router.get("/ml/model_runs/{game_id}")
async def get_model_runs(
    game_id:   int,
    player_id: int = Query(...),
    conn:      DynamicConn = None,
    user:      CurrentUser = None,
):
    """Return the last 10 training runs for a game+player (history / audit)."""
    rows = await conn.fetch("""
        SELECT model_type, model_target, r2_score, sessions_used, trained_at
        FROM app.ml_model_runs
        WHERE user_id   = $1
          AND game_id   = $2
          AND player_id = $3
        ORDER BY trained_at DESC
        LIMIT 10
    """, user["user_id"], game_id, player_id)

    return [
        {
            "model_type":    r["model_type"],
            "model_target":  r["model_target"],
            "accuracy":      float(r["r2_score"]) if r["r2_score"] else None,
            "sessions_used": r["sessions_used"],
            "trained_at":    r["trained_at"].isoformat() if r["trained_at"] else None,
        }
        for r in rows
    ]
