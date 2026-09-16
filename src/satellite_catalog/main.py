import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from satellite_catalog.db.session import check_connection, close_pool, create_pool

logger = logging.getLogger("satellite_catalog")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pula połączeń tworzona raz przy starcie aplikacji, nie per-request
    await create_pool()
    logger.info("Połączono z bazą danych.")
    yield
    await close_pool()
    logger.info("Zamknięto połączenie z bazą danych.")


app = FastAPI(
    title="Satellite Catalog Service",
    description="Mikroserwis STAC do przyjmowania i przeszukiwania metadanych zobrazowań satelitarnych.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Sprawdza, czy aplikacja żyje oraz czy ma realne połączenie z bazą.

    Celowo nie jest to statyczne {"status": "ok"} - zweryfikowanie app <-> Postgres/pgSTAC
    """
    try:
        await check_connection()
    except Exception as exc:  # noqa: BLE001 - health check ma łapać wszystko
        logger.exception("Health check nie powiódł się")
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc

    return {"status": "ok", "database": "reachable"}
