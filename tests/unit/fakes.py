"""Fake `CatalogRepositoryPort` - do testów API i warstwy orkiestracji
(ingestion/search) bez dotykania prawdziwej bazy ani nawet asyncpg.

Różne od `tests/unit/catalog/fakes.py` (`FakeConnection`/`FakePool`),
które udają asyncpg na potrzeby testowania samej `PgstacRepository`.

Ten fake jest jeden poziom wyżej - udaje cały port `CatalogRepositoryPort`.
"""

from __future__ import annotations

from satellite_catalog.core.stac_models import STACItemDict
from satellite_catalog.core.mission import Mission


class FakeCatalogRepository:
    def __init__(self) -> None:
        self.saved_items: list[STACItemDict] = []
        self.ensured_collections: list[dict] = []
        self.search_result: dict = {"type": "FeatureCollection", "features": [], "links": []}
        self.last_search_body: dict | None = None

    async def ensure_collection(self, collection: dict) -> None:
        self.ensured_collections.append(collection)

    async def save_item(self, item: STACItemDict) -> None:
        self.saved_items.append(item)

    async def search(self, search_body: dict) -> dict:
        self.last_search_body = search_body
        return self.search_result


class FakeQueue:
    def __init__(self) -> None:
        self.missions: list[Mission] = []
        self.raw: list[dict] = []

    async def publish(self, mission: Mission, raw: bytes) -> None:
        self.missions = mission
        self.raw = raw
