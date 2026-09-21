"""Mock satellite

Stands in for the ground segment's payload acquisition: at random
intervals, picks one of the two missions and POSTs a sample metadata
fixture to the catalog service's `POST /ingest/{mission}` - the exact
HTTP contract a real acquisition system would use. Lets the pipeline
(API -> RabbitMQ -> worker) be exercised end-to-end without a real feed.
"""

from __future__ import annotations

import asyncio
import logging
import random
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mock_satellite")

CATALOG_URL = "http://app:8000"
FIXTURES_DIR = Path(__file__).parent / "fixtures"

MIN_INTERVAL_SECONDS = 5
MAX_INTERVAL_SECONDS = 30

_MISSIONS = {
    "SKY_SHIELD": {
        "path": FIXTURES_DIR / "sky_shield_sample.json",
        "content_type": "application/json",
    },
    "SPACE_EYE": {
        "path": FIXTURES_DIR / "space_eye_sample.xml",
        "content_type": "application/xml",
    },
}


async def _send_one(client: httpx.AsyncClient) -> None:
    mission = random.choice(list(_MISSIONS))
    config = _MISSIONS[mission]
    raw = config["path"].read_bytes()

    try:
        response = await client.post(
            f"{CATALOG_URL}/ingest/{mission}",
            content=raw,
            headers={"Content-Type": config["content_type"]},
            timeout=10.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Failed to send %s payload: %s", mission, exc)
        return

    logger.info("Sent %s payload -> %s %s", mission, response.status_code, response.json())


async def main() -> None:
    logger.info(
        "Mock satellite started - sending to %s every %d-%ds.",
        CATALOG_URL, MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS,
    )
    async with httpx.AsyncClient() as client:
        while True:
            await _send_one(client)
            await asyncio.sleep(random.uniform(MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS))


if __name__ == "__main__":
    asyncio.run(main())
