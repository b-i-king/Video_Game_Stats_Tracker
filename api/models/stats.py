from pydantic import BaseModel
import re

_STAT_TYPE_RE = re.compile(r'^[A-Za-z0-9 \-]{1,50}$')
_NAME_RE       = re.compile(r'^[A-Za-z0-9 _\-\.]{1,100}$')

_VALID_PARTY_SIZES = {"1", "2", "3", "4", "5+"}


class StatRow(BaseModel):
    stat_type:             str
    stat_value:            int
    game_mode:             str | None = None
    game_level:            int | None = None
    win:                   int | None = None
    ranked:                int | None = None
    pre_match_rank_value:  str | None = None
    post_match_rank_value: str | None = None
    overtime:              int = 0
    difficulty:            str | None = None
    input_device:          str = "Controller"
    platform:              str = "PC"
    first_session_of_day:  int = 1
    was_streaming:         int = 0
    solo_mode:             int | None = None
    party_size:            str | None = None
    source:                str = "manual"


class AddStatsRequest(BaseModel):
    game_name:        str
    game_installment: str | None = None
    game_genre:       str | None = None
    game_subgenre:    str | None = None
    player_name:      str
    stats:            list[StatRow]
    is_live:          bool = False
    queue_platforms:  list[str] | None = None   # ['twitter'], ['twitter','instagram']
    queue_mode:       bool = False               # legacy fallback
    active_platforms: list[str] | None = None
    credit_style:     str = "shoutout"


class UpdateStatRequest(BaseModel):
    stat_type:             str | None = None
    stat_value:            int | None = None
    game_mode:             str | None = None
    game_level:            int | None = None
    win:                   int | None = None
    ranked:                int | None = None
    pre_match_rank_value:  str | None = None
    post_match_rank_value: str | None = None
