"""Orchestrates ingestion: selecting the appropriate parser -> saving the result

This is the only place that connects these two layers.
"""

from __future__ import annotations

from satellite_catalog.catalog.repository import CatalogRepositoryPort
from satellite_catalog.core.mission import Mission
from satellite_catalog.core.stac_models import STACItemDict
from satellite_catalog.ingestion.parsers.registry import get_parser


class IngestionService:
    def __init__(self, repository: CatalogRepositoryPort) -> None:
        self._repository = repository

    async def ingest(self, mission: Mission, raw: bytes) -> STACItemDict:
        """Parses raw metadata and saves the resulting STAC Item

        It raises:
        - `UnsupportedMissionError` - no parser is available for the given mission
        - `ParsingError` - raw data is structurally invalid
        - `pydantic.ValidationError` - the resulting Item does not conform to the STAC specification
        - `CatalogError` (and subclasses) - saving the item to the database failed
        """
        parser = get_parser(mission)
        item = parser(raw)
        await self._repository.save_item(item)
        return item
