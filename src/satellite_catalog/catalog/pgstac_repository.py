"""Implementation of `CatalogRepositoryPort` based on pgSTAC SQL functions.

We deliberately do not write raw SQL that operates directly on the `pgstac.items`/`pgstac.collections` tables, 
as they are partitioned and have non-trivial internal logic, 
including automatic time-based partitioning and triggers that maintain indexes. 
Instead, we use the official SQL functions provided by pgSTAC in the 'pgstac' schema.
"""

from __future__ import annotations

import json
import logging

import asyncpg

from satellite_catalog.catalog.errors import (
    CollectionPersistenceError,
    ItemPersistenceError,
    SearchError,
)
from satellite_catalog.core.stac_models import STACItemDict

logger = logging.getLogger(__name__)


class PgstacRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def ensure_collection(self, collection: dict) -> None:
        payload = json.dumps(collection)
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("SELECT pgstac.upsert_collection($1::jsonb);", payload)
        except asyncpg.PostgresError as exc:
            raise CollectionPersistenceError(
                f"Did not manage to register the collection '{collection.get('id')}': {exc}"
            ) from exc

        logger.info("Collection '%s' register/updated.", collection.get("id"))

    async def save_item(self, item: STACItemDict) -> None:
        payload = json.dumps(item)
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("SELECT pgstac.upsert_item($1::jsonb);", payload)
        except asyncpg.PostgresError as exc:
            raise ItemPersistenceError(
                f"Did not manage to save Item '{item.get('id')}' "
                f"(collection='{item.get('collection')}'): {exc}"
            ) from exc

        logger.info(
            "Item '%s' saved to collection '%s'.", item.get("id"), item.get("collection")
        )

    async def search(self, search_body: dict) -> dict:
        payload = json.dumps(search_body)
        try:
            async with self._pool.acquire() as conn:
                raw = await conn.fetchval("SELECT * FROM pgstac.search($1::jsonb);", payload)
        except asyncpg.PostgresError as exc:
            raise SearchError(f"searching in the catalog did not succeed: {exc}") from exc

        # `pgstac.search` zwraca kolumnę typu jsonb; asyncpg (bez dodatkowego
        # codeca) oddaje ją jako string JSON, nie dict - trzeba go dociąć.
        return json.loads(raw) if isinstance(raw, (str, bytes)) else raw
