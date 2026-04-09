"""
Two asyncpg connection pools:
  personal_pool  — personal Supabase project (Transaction pooler, port 6543)
  public_pool    — public Supabase project  (Transaction pooler, port 6543)

Both are initialised at startup via the FastAPI lifespan hook in main.py.
"""

import asyncpg
from api.core.config import get_settings

personal_pool: asyncpg.Pool | None = None
public_pool:   asyncpg.Pool | None = None


async def init_pools() -> None:
    global personal_pool, public_pool
    settings = get_settings()

    personal_pool = await asyncpg.create_pool(
        dsn=settings.personal_db_url,
        min_size=1,
        max_size=10,
        statement_cache_size=0,           # required for Supabase PgBouncer
        max_inactive_connection_lifetime=300,  # recycle idle conns before Supabase kills them
    )

    if settings.public_db_url:
        public_pool = await asyncpg.create_pool(
            dsn=settings.public_db_url,
            min_size=1,
            max_size=10,
            statement_cache_size=0,
            max_inactive_connection_lifetime=300,
        )


async def close_pools() -> None:
    global personal_pool, public_pool
    if personal_pool:
        await personal_pool.close()
    if public_pool:
        await public_pool.close()
