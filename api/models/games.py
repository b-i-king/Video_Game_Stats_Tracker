from pydantic import BaseModel


class UpdateGameRequest(BaseModel):
    game_name: str | None = None
    platform: str | None = None
    franchise: str | None = None
    installment: str | None = None
    genre: str | None = None
    is_active: bool | None = None


class UpdatePlayerRequest(BaseModel):
    player_name: str | None = None
    display_name: str | None = None
    is_active: bool | None = None
