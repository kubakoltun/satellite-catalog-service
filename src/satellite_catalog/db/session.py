import asyncpg

from satellite_catalog.settings import settings
from contextlib import asynccontextmanager

# The connection pool is kept as module-level state. It is created and closed
# during the FastAPI application lifespan.
_pool: asyncpg.Pool | None = None


async def create_pool() -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1,
        max_size=5,
        server_settings={
            # The default search_path can cause issues during the first startup.
            # If it does not include pgstac, the service cannot use its functions.
            "search_path": settings.database_search_path
        }
    )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError(
            "Connection pool was not initialized - check the application lifespan configuration in main.py"
        )
    return _pool


async def check_connection() -> None:
    """Performs a simple query against the database - used by the `/health` endpoint."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1;")
        if result != 1:
            raise RuntimeError("Unexpected answer from the database")


@asynccontextmanager
async def worker_db_pool():
    """Async context manager wrapping create_pool/close_pool for worker.py.

    The worker is its own process/container, entirely separate from
    FastAPI's lifespan, so it needs its own entry point into the same
    pool-creation logic - this is that second caller, scoped to the
    worker's own lifetime instead of an ASGI app's.
    """
    pool = await create_pool()
    try:
        yield pool
    finally:
        await close_pool()
