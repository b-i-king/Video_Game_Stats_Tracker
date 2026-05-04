from pydantic import BaseModel


class AddGameRequest(BaseModel):
    """
    Fields for creating a new game entry in dim.dim_games.
    Sourced from IGDB lookup or manual input (Trusted/Owner only).
    """
    game_name:        str
    game_installment: str | None = None   # IGDB: series/franchise title
    game_genre:       str | None = None   # IGDB: primary genre
    game_subgenre:    str | None = None   # IGDB: theme / secondary genre


class UpdateGameRequest(BaseModel):
    """Partial update — only provided fields are changed."""
    game_name:        str | None = None
    game_installment: str | None = None
    game_genre:       str | None = None
    game_subgenre:    str | None = None


class RequestGameRequest(BaseModel):
    """
    Free/Premium users submit a game request when it doesn't exist in the catalog.
    Written to app.game_requests for Trusted/Owner review.
    """
    game_name:        str
    game_installment: str | None = None


class UpdatePlayerRequest(BaseModel):
    player_name: str | None = None


class GameScoreRequest(BaseModel):
    """Payload sent by a browser-hosted game after a session ends."""
    game_name:    str
    player_name:  str
    score:        float
    checkpoints:  int = 0
    platform:     str = 'PC'
    input_device: str = 'Keyboard & Mouse'
    player_id:    int | None = None
