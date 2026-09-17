import asyncpg

from satellite_catalog.settings import settings

# Pula połączeń trzymana jako stan modułu, tworzona/zamykana w lifespanie
# aplikacji FastAPI (main.py). Prostota na Kroku 0 - jeśli w przyszłości
# będzie potrzeba łatwiejszego mockowania w testach, przeniesiemy to na
# app.state.
_pool: asyncpg.Pool | None = None


async def create_pool() -> asyncpg.Pool:
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=1,
        max_size=5,
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
            "Pula połączeń nie została zainicjalizowana - "
            "sprawdź lifespan aplikacji w main.py"
        )
    return _pool


async def check_connection() -> None:
    """Wykonuje realne zapytanie do bazy - używane przez /health."""
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT 1;")
        if result != 1:
            raise RuntimeError("Nieoczekiwana odpowiedź z bazy danych")
