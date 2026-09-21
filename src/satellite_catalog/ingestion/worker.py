"""Ingestion worker entrypoint

A separate process from the FastAPI app (main.py). Consumes raw payloads
from the durable `ingestion.raw.q` queue and runs them through the exact
same `IngestionService.ingest()` that used to be called from an HTTP
background task - only the trigger changed, not the ingestion logic.

Ack strategy (manual ack, `no_ack=False`):
- success                          -> ack.
- ParsingError / ValidationError   -> nack(requeue=False). The data itself
  is malformed; retrying won't help, so it goes straight to the DLQ.
- CatalogError (transient DB issue) -> nack(requeue=True). The queue's
  `x-delivery-limit` (see rabbitmq_queue.py) makes RabbitMQ dead-letter
  the message automatically once it's been redelivered too many times -
  no manual attempt counter needed here.
- anything unexpected               -> nack(requeue=True), same reasoning
  as CatalogError: treat unknown failures as possibly transient.

Run standalone: `python -m satellite_catalog.ingestion.worker`.
"""

from __future__ import annotations

import asyncio
import logging

import aio_pika
from pydantic import ValidationError

from satellite_catalog.catalog.errors import CatalogError
from satellite_catalog.catalog.pgstac_repository import PgstacRepository
from satellite_catalog.db.session import worker_db_pool
from satellite_catalog.ingestion.errors import ParsingError
from satellite_catalog.ingestion.rabbitmq_queue import declare_topology, decode_envelope
from satellite_catalog.ingestion.service import IngestionService
from satellite_catalog.settings import settings

logger = logging.getLogger("satellite_catalog.worker")
logging.basicConfig(level=logging.INFO)


async def _handle_message(message: aio_pika.abc.AbstractIncomingMessage, service: IngestionService) -> None:
    try:
        mission, raw, envelope = decode_envelope(message.body)
    except Exception:  # noqa: BLE001 - malformed envelope, not just malformed provider data
        logger.exception("Could not decode message envelope - dead-lettering")
        await message.nack(requeue=False)
        return

    message_id = envelope.get("message_id")

    try:
        item = await service.ingest(mission, raw)
    except (ParsingError, ValidationError) as exc:
        logger.error(
            "Unrecoverable ingestion error (message_id=%s, mission=%s): %s - sending to DLQ",
            message_id, mission.value, exc,
        )
        await message.nack(requeue=False)
    except CatalogError as exc:
        logger.warning(
            "Transient catalog error (message_id=%s, mission=%s): %s - requeueing",
            message_id, mission.value, exc,
        )
        await message.nack(requeue=True)
    except Exception:  # noqa: BLE001 - last-resort safeguard, treated as transient
        logger.exception(
            "Unexpected error during ingestion (message_id=%s, mission=%s) - requeueing", message_id, mission.value
        )
        await message.nack(requeue=True)
    else:
        await message.ack()
        logger.info("Ingested item '%s' (message_id=%s, mission=%s)", item["id"], message_id, mission.value)


async def main() -> None:
    async with worker_db_pool() as pool:
        repository = PgstacRepository(pool)
        service = IngestionService(repository)

        connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=10)
            _exchange, queue = await declare_topology(channel)

            logger.info("Worker started, consuming from '%s'.", queue.name)
            await queue.consume(lambda msg: _handle_message(msg, service), no_ack=False)

            await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
