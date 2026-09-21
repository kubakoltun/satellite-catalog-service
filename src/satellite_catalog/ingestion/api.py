"""Endpoint POST /ingest/{mission}

Validates the mission (via the `Mission` path converter) and that the
body is non-empty, publishes the raw payload to a durable RabbitMQ queue
through `QueuePort`, and returns 202 only once the broker has confirmed
the message is durably stored. Parsing and persistence happen
asynchronously in `ingestion/worker.py`, fully decoupled from the
request/response cycle and independently scalable - run more worker
containers to increase throughput without touching this endpoint.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from satellite_catalog.core.mission import Mission
from satellite_catalog.deps import get_queue
from satellite_catalog.ingestion.errors import QueuePublishError
from satellite_catalog.ingestion.queue_port import QueuePort

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ingestion"])


@router.post("/ingest/{mission}", status_code=202)
async def ingest(
    mission: Mission,
    request: Request,
    queue: QueuePort = Depends(get_queue),
) -> dict:
    raw = await request.body()
    if not raw:
        raise HTTPException(status_code=400, detail="Request body is empty")

    try:
        await queue.publish(mission, raw)
    except QueuePublishError as exc:
        logger.error("Failed to publish to queue (mission=%s): %s", mission.value, exc)
        raise HTTPException(status_code=503, detail="Could not enqueue payload for processing") from exc

    return {"status": "accepted", "mission": mission.value}