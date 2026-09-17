import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from satellite_catalog.catalog.api import router as search_router
from satellite_catalog.catalog.collections import default_collections
from satellite_catalog.catalog.pgstac_repository import PgstacRepository
from satellite_catalog.db.session import check_connection, close_pool, create_pool, get_pool
from satellite_catalog.ingestion.api import router as ingestion_router

logger = logging.getLogger("satellite_catalog")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pula połączeń tworzona raz przy starcie aplikacji, nie per-request -
    # to jedyne miejsce w Kroku 0, gdzie "coś" trwale żyje obok requestów.
    await create_pool()
    logger.info("Połączono z bazą danych.")

    # Repozytorium tworzone raz i trzymane w app.state - endpointy
    # (search_router, ingestion_router) pobierają je przez Depends(get_repository)
    # (satellite_catalog.deps), nigdy nie importując PgstacRepository wprost.
    repository = PgstacRepository(get_pool())
    app.state.repository = repository

    # Obie kolekcje (SKY_SHIELD, SPACE_EYE) muszą istnieć w pgSTAC, zanim
    # jakikolwiek Item będzie mógł zostać zapisany (klucz obcy). Rejestracja
    # jest idempotentna (upsert), więc bezpieczna przy każdym starcie.
    for collection in default_collections():
        await repository.ensure_collection(collection)
    logger.info("Kolekcje STAC zarejestrowane.")

    yield
    await close_pool()
    logger.info("Zamknięto połączenie z bazą danych.")


app = FastAPI(
    title="Satellite Catalog Service",
    description="Mikroserwis STAC do przyjmowania i przeszukiwania metadanych zobrazowań satelitarnych.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(ingestion_router)
app.include_router(search_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Sprawdza, czy aplikacja żyje ORAZ czy ma realne połączenie z bazą.

    Celowo nie jest to statyczne {"status": "ok"} - sens Kroku 0 to
    zweryfikowanie całej rury (app <-> Postgres/pgSTAC), nie samego procesu.
    """
    try:
        await check_connection()
    except Exception as exc:  # noqa: BLE001 - health check ma łapać wszystko
        logger.exception("Health check nie powiódł się")
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc

    return {"status": "ok", "database": "reachable"}
