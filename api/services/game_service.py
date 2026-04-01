"""
Game / player business logic.
"""

import asyncpg
from typing import Any


async def get_games(conn: asyncpg.Connection) -> list[dict]:
    rows = await conn.fetch(
        "SELECT game_id, game_name, platform, franchise, installment, genre, is_active FROM dim.dim_games ORDER BY game_name"
    )
    return [dict(r) for r in rows]


async def get_players(conn: asyncpg.Connection) -> list[dict]:
    rows = await conn.fetch(
        "SELECT player_id, player_name, display_name, is_active FROM dim.dim_players ORDER BY player_name"
    )
    return [dict(r) for r in rows]


async def get_game_details(conn: asyncpg.Connection, game_id: int) -> dict[str, Any]:
    # TODO: port from flask_app.py get_game_details
    raise NotImplementedError


async def update_game(conn: asyncpg.Connection, game_id: int, fields: dict) -> dict[str, Any]:
    # TODO: port from flask_app.py update_game
    raise NotImplementedError


async def delete_game(conn: asyncpg.Connection, game_id: int) -> None:
    # TODO: port from flask_app.py delete_game
    raise NotImplementedError
