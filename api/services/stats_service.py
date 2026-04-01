"""
Stats business logic.

Sync utils (chart_utils, ai_utils, etc.) are called via asyncio.to_thread()
so they don't block the async event loop.
"""

import asyncio
import asyncpg
from typing import Any


async def get_recent_stats(
    conn: asyncpg.Connection,
    player_id: int,
    game_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    # TODO: port query from flask_app.py get_recent_stats
    raise NotImplementedError


async def add_stats(conn: asyncpg.Connection, stats: list[dict], tz: str | None = None) -> list[int]:
    """
    Insert stat rows and trigger chart generation as a side-effect.
    Chart generation calls chart_utils (sync) via asyncio.to_thread().
    """
    # TODO: port from flask_app.py add_stats
    raise NotImplementedError


async def get_summary(conn: asyncpg.Connection, game_id: int, player_id: int) -> dict[str, Any]:
    # TODO: port from flask_app.py get_summary
    raise NotImplementedError


async def get_streaks(conn: asyncpg.Connection, game_id: int, player_id: int) -> dict[str, Any]:
    # TODO: port from flask_app.py get_streaks
    raise NotImplementedError


async def get_ticker_facts(
    conn: asyncpg.Connection,
    game_id: int,
    player_id: int,
) -> list[str]:
    """
    15-minute server-side cache.  Returns tiered facts:
      basic (< 10 sessions) → descriptive (< 30) → advanced (30+)
    """
    # TODO: port from flask_app.py get_ticker_facts
    raise NotImplementedError
