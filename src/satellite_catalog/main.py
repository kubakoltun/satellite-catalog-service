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
    # Connection pool created once on app startup, not per request.
    # It is the only place where something persists across requests.
    await create_pool()
    logger.info("Connected to the database.")

    # Repository created once and stored in app.state.
    # Endpoints (search_router, ingestion_router) get it through
    # Depends(get_repository) (satellite_catalog.deps), so they never
    # import PgstacRepository directly.
    repository = PgstacRepository(get_pool())
    app.state.repository = repository

    # Collections must exist in pgSTAC before any Item can be inserted
    # because of the foreign key constraint. Registration is idempotent
    # (upsert), so it is safe to run on every application startup.
    for collection in default_collections():
        await repository.ensure_collection(collection)
    logger.info("STAC collection registered.")

    yield
    await close_pool()
    logger.info("Closed the database connection.")


app = FastAPI(
    title="Satellite Catalog Service",
    description="Mikroserwis STAC do przyjmowania i przeszukiwania metadanych zobrazowań satelitarnych.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(ingestion_router)
app.include_router(search_router)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Check whether the app is up and the database is reachable

    The purpose of the health check is to verify the entire pipeline
    (app <-> Postgres/pgSTAC).
    """
    try:
        await check_connection()
    except Exception as exc:  # noqa: BLE001 - health check should catch all
        logger.exception("Health check did not succeed")
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc

    return {"status": "ok", "database": "reachable"}
