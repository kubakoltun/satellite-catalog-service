from pathlib import Path

import pytest

from satellite_catalog.catalog.errors import ItemPersistenceError
from satellite_catalog.core.mission import Mission
from satellite_catalog.ingestion.errors import ParsingError, UnsupportedMissionError
from satellite_catalog.ingestion.service import IngestionService
from tests.unit.fakes import FakeCatalogRepository

FIXTURES = Path(__file__).parents[2] / "fixtures"


@pytest.fixture
def repository() -> FakeCatalogRepository:
    return FakeCatalogRepository()


async def test_ingest_sky_shield_parses_and_saves(repository: FakeCatalogRepository) -> None:
    service = IngestionService(repository)
    raw = (FIXTURES / "sky_shield_sample.json").read_text()

    item = await service.ingest(Mission.SKY_SHIELD, raw)

    assert item["id"] == "SKY_SHIELD_20260824_091522_L1C_POL"
    assert repository.saved_items == [item]


async def test_ingest_space_eye_parses_and_saves(repository: FakeCatalogRepository) -> None:
    service = IngestionService(repository)
    raw = (FIXTURES / "space_eye_sample.xml").read_text()

    item = await service.ingest(Mission.SPACE_EYE, raw)

    assert item["id"] == "SE02_L2A_20260824T104500_N001"
    assert repository.saved_items == [item]


async def test_ingest_propagates_parsing_error_without_saving(
    repository: FakeCatalogRepository,
) -> None:
    service = IngestionService(repository)

    with pytest.raises(ParsingError):
        await service.ingest(Mission.SKY_SHIELD, b"{not valid json")

    assert repository.saved_items == []


async def test_ingest_propagates_repository_errors(repository: FakeCatalogRepository) -> None:
    class _FailingRepository(FakeCatalogRepository):
        async def save_item(self, item):  # type: ignore[override]
            raise ItemPersistenceError("db down")

    service = IngestionService(_FailingRepository())
    raw = (FIXTURES / "sky_shield_sample.json").read_text()

    with pytest.raises(ItemPersistenceError):
        await service.ingest(Mission.SKY_SHIELD, raw)
