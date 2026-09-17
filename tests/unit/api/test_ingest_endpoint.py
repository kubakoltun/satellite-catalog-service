from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from satellite_catalog.deps import get_repository
from satellite_catalog.ingestion.api import router as ingestion_router
from tests.unit.fakes import FakeCatalogRepository

FIXTURES = Path(__file__).parents[2] / "fixtures"


@pytest.fixture
def fake_repository() -> FakeCatalogRepository:
    return FakeCatalogRepository()


@pytest.fixture
def client(fake_repository: FakeCatalogRepository) -> TestClient:
    app = FastAPI()
    app.include_router(ingestion_router)
    app.dependency_overrides[get_repository] = lambda: fake_repository
    return TestClient(app)


def test_ingest_sky_shield_returns_202_immediately(client: TestClient) -> None:
    raw = (FIXTURES / "sky_shield_sample.json").read_bytes()

    response = client.post(
        "/ingest/SKY_SHIELD", content=raw, headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted", "mission": "SKY_SHIELD"}


def test_ingest_sky_shield_saves_item_via_background_task(
    client: TestClient, fake_repository: FakeCatalogRepository
) -> None:
    # Starlette wykonuje BackgroundTasks jako część tego samego cyklu
    # ASGI, więc po powrocie z client.post() zadanie w tle już się
    # zakończyło - można to sprawdzić bez sleep()/pollingu.
    raw = (FIXTURES / "sky_shield_sample.json").read_bytes()

    client.post("/ingest/SKY_SHIELD", content=raw)

    assert len(fake_repository.saved_items) == 1
    assert fake_repository.saved_items[0]["id"] == "SKY_SHIELD_20260824_091522_L1C_POL"


def test_ingest_space_eye_saves_item_via_background_task(
    client: TestClient, fake_repository: FakeCatalogRepository
) -> None:
    raw = (FIXTURES / "space_eye_sample.xml").read_bytes()

    client.post(
        "/ingest/SPACE_EYE", content=raw, headers={"Content-Type": "application/xml"}
    )

    assert len(fake_repository.saved_items) == 1
    assert fake_repository.saved_items[0]["id"] == "SE02_L2A_20260824T104500_N001"


def test_ingest_unknown_mission_rejected_by_path_validation(client: TestClient) -> None:
    response = client.post("/ingest/UNKNOWN_MISSION", content=b"{}")

    assert response.status_code == 422  # FastAPI waliduje Enum w ścieżce


def test_ingest_empty_body_returns_400(client: TestClient) -> None:
    response = client.post("/ingest/SKY_SHIELD", content=b"")

    assert response.status_code == 400


def test_ingest_invalid_payload_does_not_save_anything(
    client: TestClient, fake_repository: FakeCatalogRepository, caplog: pytest.LogCaptureFixture
) -> None:
    # Zły JSON - endpoint i tak zwraca 202 (błąd wykryje się dopiero w tle),
    # ale nic nie powinno wylądować w repozytorium, a błąd ma trafić do logów.
    with caplog.at_level("ERROR"):
        response = client.post("/ingest/SKY_SHIELD", content=b"{not valid json")

    assert response.status_code == 202
    assert fake_repository.saved_items == []
    assert any("Błąd parsowania" in record.message for record in caplog.records)
