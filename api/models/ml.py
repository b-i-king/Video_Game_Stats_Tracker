from pydantic import BaseModel
from typing import Any


class MLModelRun(BaseModel):
    game_id: int
    player_id: int
    model_type: str          # "logistic_regression" | "random_forest" | "xgboost"
    target_stat: str
    metrics: dict[str, Any]  # accuracy, f1, auc, etc.
    coefficients: dict[str, float] | None = None   # LR only → stored as JSONB
    model_uri: str | None = None                   # GCS / Supabase Storage path
    trained_at: str | None = None                  # ISO-8601


class PredictionRequest(BaseModel):
    game_id: int
    player_id: int
    stat_inputs: dict[str, float]  # {stat_type: value, ...}


class PredictionResponse(BaseModel):
    game_id: int
    player_id: int
    prediction: float        # probability or predicted value
    model_type: str
    confidence: float | None = None
    feature_importances: dict[str, float] | None = None
