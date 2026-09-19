"""Catalog repository

The `ingestion/service.py` and `catalog/serach.py` should depend only
on this protocol, never directly on `asyncpg` or SQL. The domain logic does not know,
that the underlying implementation is pgSTAC. It might as well be another STAC API implementation.
This simplifies tests, as no actual DB needs to be running. 
Using mock that implements the protocol would be enough.
"""

from typing import Protocol

from satellite_catalog.core.stac_models import STACItemDict


class CatalogRepositoryPort(Protocol):
    async def ensure_collection(self, collection: dict) -> None:
        """Registers Collection in catalog if there is none. Idempotent - 
        can be safely called on every app start."""
        ...

    async def save_item(self, item: STACItemDict) -> None:
        """Saves a STAC Item. Insert if there is no Item with given 'id'. 
        Update if there is an Item with the exact 'id'."""
        ...

    async def search(self, search_body: dict) -> dict:
        """Perform a search and return the raw result in STAC API format. The result 
        is an ItemCollection containing `features`, `links`, `context`, as returned by `pgstac.search()`. 
        The API layer simply passes this result through without transforming it."""
        ...
