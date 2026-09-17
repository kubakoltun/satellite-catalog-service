"""Orkiestracja ingestion: wybór parsera (Krok 1) -> zapis (Krok 2).

To jest jedyne miejsce, które spina te dwie warstwy. Warstwa API (`api.py`)
nie wie nic o parserach ani o repozytorium - tylko o tym serwisie.
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
        """Parsuje surowe metadane i zapisuje wynikowy STAC Item.

        Podnosi (bez łapania - to decyzja wywołującego, jak je obsłużyć):
        - `UnsupportedMissionError` - brak parsera dla danej misji,
        - `ParsingError` - surowe dane strukturalnie niepoprawne,
        - `pydantic.ValidationError` - wynikowy Item niezgodny ze spec STAC,
        - `CatalogError` (i podklasy) - zapis do bazy się nie powiódł.
        """
        parser = get_parser(mission)
        item = parser(raw)
        await self._repository.save_item(item)
        return item
