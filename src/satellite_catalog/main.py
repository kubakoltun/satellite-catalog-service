import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from satellite_catalog.catalog.api import router as search_router
from satellite_catalog.catalog.collections import default_collections
from satellite_catalog.catalog.pgstac_repository import PgstacRepository
from satellite_catalog.db.session import check_connection, close_pool, create_pool, get_pool
from satellite_catalog.ingestion.api import router as ingestion_router
from satellite_catalog.ingestion.rabbitmq_queue import RabbitMQQueue
from satellite_catalog.settings import settings

logger = logging.getLogger("satellite_catalog")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_pool()
    logger.info("Connected to the database.")

    repository = PgstacRepository(get_pool())
    app.state.repository = repository

    for collection in default_collections():
        await repository.ensure_collection(collection)
    logger.info("STAC collections registered.")

    queue = await RabbitMQQueue.connect(settings.rabbitmq_url)
    app.state.queue = queue
    logger.info("Connected to RabbitMQ.")

    yield

    await queue.close()
    await close_pool()
    logger.info("Closed the database and RabbitMQ connections.")


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
    try:
        await check_connection()
    except Exception as exc:  # noqa: BLE001 - health check should catch all
        logger.exception("Health check did not succeed")
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}") from exc

    return {"status": "ok", "database": "reachable"}
