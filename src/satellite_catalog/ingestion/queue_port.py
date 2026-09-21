"""Queue Port

Abstraction over a durable message queue used to decouple ingestion
from processing. `ingestion/api.py` publishes raw payloads through
this protocol - it does not know whether the underlying implementation
is RabbitMQ or anything else.
"""

from typing import Protocol

from satellite_catalog.core.mission import Mission


class QueuePort(Protocol):
    async def publish(self, mission: Mission, raw: bytes) -> None:
        """Publishes a raw payload for the given mission to a durable queue

        Must not return until the broker has confirmed persistence of the
        message (publisher confirms), so a caller receiving success knows
        the message will survive a broker restart until it's consumed.

        Raises `QueuePublishError` if the broker did not confirm the publish.
        """
        ...