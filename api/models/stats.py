from pydantic import BaseModel
from typing import Any


class StatEntry(BaseModel):
    game_id: int
    player_id: int
    stat_type: str
    stat_value: float
    game_mode: str | None = None
    rank: str | None = None
    placement: int | None = None
    notes: str | None = None
    played_at: str | None = None  # ISO-8601; defaults to NOW() server-side if omitted


class AddStatsRequest(BaseModel):
    stats: list[StatEntry]
    tz: str | None = None


class UpdateStatRequest(BaseModel):
    stat_type: str | None = None
    stat_value: float | None = None
    game_mode: str | None = None
    rank: str | None = None
    placement: int | None = None
    notes: str | None = None
    played_at: str | None = None


class StatResponse(BaseModel):
    stat_id: int
    game_id: int
    player_id: int
    stat_type: str
    stat_value: float
    game_mode: str | None
    rank: str | None
    placement: int | None
    notes: str | None
    played_at: str
