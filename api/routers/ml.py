"""
ML Insights router — Phase 3b of the migration plan.
Implements after FastAPI core routes are stable.
"""

from fastapi import APIRouter, HTTPException, Query
from api.core.deps import DynamicConn, CurrentUser
from api.models.ml import PredictionRequest, PredictionResponse

router = APIRouter()


@router.get("/ml/prediction/{game_id}", response_model=PredictionResponse)
async def get_prediction(
    game_id: int,
    player_id: int = Query(...),
    conn: DynamicConn = None,
    user: CurrentUser = None,
):
    """
    Return win-probability prediction for a game.
    - Personal users: LR coefficients served as JSONB → client-side TypeScript sigmoid
    - Public users: same pattern; model evicted after 90 days of inactivity
    TODO: implement via ml_service.get_prediction()
    """
    raise HTTPException(status_code=501, detail="ML not yet implemented")


@router.post("/ml/train/{game_id}", status_code=202)
async def trigger_training(game_id: int, conn: DynamicConn, user: CurrentUser):
    """
    Enqueue a model training job for the given game.
    Requires >= 50 sessions (session threshold gate).
    TODO: implement via ml_service.enqueue_training()
    """
    raise HTTPException(status_code=501, detail="ML not yet implemented")


@router.get("/ml/model_runs/{game_id}")
async def get_model_runs(game_id: int, player_id: int = Query(...), conn: DynamicConn = None):
    """
    Return historical model runs from app.ml_model_runs.
    TODO: implement via ml_service.get_model_runs()
    """
    raise HTTPException(status_code=501, detail="ML not yet implemented")
