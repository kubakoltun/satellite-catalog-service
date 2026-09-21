"""RabbitMQ implementation of `QueuePort`, based on aio-pika

Publishes raw ingestion payloads to a durable direct exchange, wrapped
in a small JSON envelope so the worker knows which mission the bytes
belong to and can track basic provenance (message_id, received_at).

Publisher confirms: the channel is opened with `publisher_confirms=True`,
so `exchange.publish(...)` does not return until RabbitMQ has ack'd the
publish - a successful `publish()` here means the broker has durably
stored the message, not just that it was written to the socket.

Retry/DLQ topology: `ingestion.raw.q` is declared as a quorum queue
with `x-delivery-limit` set. Combined with `x-dead-letter-exchange`, this
means:
- `nack(requeue=False)` (bad/unparseable data) -> straight to the DLQ.
- `nack(requeue=True)` (transient DB issue) -> redelivered, and RabbitMQ
  itself dead-letters the message to the DLQ once the delivery limit is
  exceeded, with no manual attempt-counting needed on our side.
"""

from __future__ import annotations

import base64
import json
import logging
import uuid
from datetime import datetime, timezone

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message

from satellite_catalog.core.mission import Mission
from satellite_catalog.ingestion.errors import QueuePublishError
from satellite_catalog.ingestion.queue_port import QueuePort

logger = logging.getLogger(__name__)

EXCHANGE_NAME = "ingestion.raw"
QUEUE_NAME = "ingestion.raw.q"
ROUTING_KEY = "ingestion.raw"

DLX_NAME = "ingestion.raw.dlx"
DLQ_NAME = "ingestion.raw.dlq"
DLQ_ROUTING_KEY = "ingestion.raw.dead"

# How many times a message may be nack(requeue=True)'d (CatalogError /
# transient DB issue) before RabbitMQ dead-letters it automatically.
MAX_DELIVERY_ATTEMPTS = 5


async def declare_topology(channel: aio_pika.abc.AbstractChannel) -> tuple[aio_pika.abc.AbstractExchange, aio_pika.abc.AbstractQueue]:
    """Declares exchange/queue/DLQ topology. Idempotent - safe to call from
    both the app (on FastAPI startup) and the worker (on its own startup),
    in either order, without one depending on the other having run first.
    """
    exchange = await channel.declare_exchange(EXCHANGE_NAME, ExchangeType.DIRECT, durable=True)

    dlx = await channel.declare_exchange(DLX_NAME, ExchangeType.DIRECT, durable=True)
    dlq = await channel.declare_queue(DLQ_NAME, durable=True)
    await dlq.bind(dlx, routing_key=DLQ_ROUTING_KEY)

    queue = await channel.declare_queue(
        QUEUE_NAME,
        durable=True,
        arguments={
            "x-queue-type": "quorum",
            "x-delivery-limit": MAX_DELIVERY_ATTEMPTS,
            "x-dead-letter-exchange": DLX_NAME,
            "x-dead-letter-routing-key": DLQ_ROUTING_KEY,
        },
    )
    await queue.bind(exchange, routing_key=ROUTING_KEY)

    return exchange, queue


class RabbitMQQueue:
    """QueuePort implementation backed by a RabbitMQ exchange/queue

    Owns a single robust connection/channel, created once at app startup
    and reused for every publish - like the asyncpg pool, connections are
    too expensive to open per-request.
    """

    def __init__(
        self,
        connection: aio_pika.abc.AbstractRobustConnection,
        channel: aio_pika.abc.AbstractChannel,
        exchange: aio_pika.abc.AbstractExchange,
    ) -> None:
        self._connection = connection
        self._channel = channel
        self._exchange = exchange

    @classmethod
    async def connect(cls, url: str) -> "RabbitMQQueue":
        connection = await aio_pika.connect_robust(url)
        channel = await connection.channel(publisher_confirms=True)
        exchange, _queue = await declare_topology(channel)
        logger.info("RabbitMQ topology ready (exchange=%s, queue=%s).", EXCHANGE_NAME, QUEUE_NAME)
        return cls(connection, channel, exchange)

    async def close(self) -> None:
        await self._connection.close()

    async def publish(self, mission: Mission, raw: bytes) -> None:
        envelope = _build_envelope(mission, raw)
        body = json.dumps(envelope).encode("utf-8")

        message = Message(
            body=body,
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json",
            message_id=envelope["message_id"],
        )

        try:
            await self._exchange.publish(message, routing_key=ROUTING_KEY)
        except Exception as exc:  # noqa: BLE001 - any broker/connection failure
            raise QueuePublishError(
                f"Broker did not confirm publish for mission={mission.value}: {exc}"
            ) from exc

        logger.info("Published raw payload (mission=%s, message_id=%s).", mission.value, envelope["message_id"])


def _build_envelope(mission: Mission, raw: bytes) -> dict:
    """`raw` is base64-encoded rather than embedded as UTF-8 text so the
    envelope stays binary-safe regardless of what a future provider sends -
    JSON/XML today happen to be UTF-8, but nothing guarantees that forever.
    """
    return {
        "mission": mission.value,
        "raw": base64.b64encode(raw).decode("ascii"),
        "message_id": str(uuid.uuid4()),
        "received_at": datetime.now(timezone.utc).isoformat(),
    }


def decode_envelope(body: bytes) -> tuple[Mission, bytes, dict]:
    """Inverse of `_build_envelope`, used by the worker. Returns the parsed
    envelope too, so the worker can log `message_id`/`received_at`."""
    envelope = json.loads(body)
    mission = Mission(envelope["mission"])
    raw = base64.b64decode(envelope["raw"])
    return mission, raw, envelope