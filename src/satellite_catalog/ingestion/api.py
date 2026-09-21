"""Endpoint POST /ingest/{mission}

The endpoint only reads the raw request body (JSON or XML, depending on
the mission), schedules the processing as a background task, and
immediately returns 202 Accepted. Parsing and database persistence
happen after the request has been accepted, so the ground segment does
not have to wait for database persistence before receiving an
acknowledgement.

Parsing, validation, and persistence errors are caught and logged in the
background task rather than returned synchronously by the endpoint.
This is a deliberate trade-off: the implementation is simpler and
sufficient for the current requirements, but the client does not receive
immediate feedback when processing fails. 
TODO In a production system, this could be replaced with a durable message broker,
a dead-letter queue, and an ingestion-status endpoint such as
GET /ingest/{id}. These components are intentionally omitted so far.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import ValidationError

from satellite_catalog.catalog.errors import CatalogError
from satellite_catalog.catalog.repository import CatalogRepositoryPort
from satellite_catalog.core.mission import Mission
from satellite_catalog.deps import get_repository
from satellite_catalog.ingestion.errors import ParsingError
from satellite_catalog.ingestion.service import IngestionService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingestion"])


@router.post("/ingest/{mission}", status_code=202)
async def ingest(
    mission: Mission,
    request: Request,
    background_tasks: BackgroundTasks,
    repository: CatalogRepositoryPort = Depends(get_repository),
) -> dict:
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="Request body is empty")

    service = IngestionService(repository)
    background_tasks.add_task(_process_in_background, service, mission, raw)

    return {"status": "accepted", "mission": mission.value}


async def _process_in_background(
    service: IngestionService, mission: Mission, raw: bytes
) -> None:
    try:
        item = await service.ingest(mission, raw)
    except ParsingError as exc:
        logger.error("Metadata parsing error (mission=%s): %s", mission.value, exc)
    except ValidationError as exc:
        logger.error(
            "Resulting STAC Item does not conform to the specification (mission=%s): %s", mission.value, exc
        )
    except CatalogError as exc:
        logger.error("Catalog persistence error (mission=%s): %s", mission.value, exc)
    except Exception:  # noqa: BLE001 - last-resort safeguard for background processing
        logger.exception("Unexpected error during ingestion (mission=%s)", mission.value)
    else:
        logger.info("Ingested item '%s' (mission=%s)", item["id"], mission.value)
