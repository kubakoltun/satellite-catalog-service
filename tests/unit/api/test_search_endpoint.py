import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from satellite_catalog.catalog.api import router as search_router
from satellite_catalog.deps import get_repository
from tests.unit.fakes import FakeCatalogRepository


@pytest.fixture
def fake_repository() -> FakeCatalogRepository:
    return FakeCatalogRepository()


@pytest.fixture
def client(fake_repository: FakeCatalogRepository) -> TestClient:
    # Świadomie nie używam `main.app` - ten wymaga realnej bazy w swoim
    # `lifespan`. Montuję tylko router `/search` na osobnej, minimalnej
    # aplikacji testowej z podmienionym repozytorium (dependency_overrides).
    app = FastAPI()
    app.include_router(search_router)
    app.dependency_overrides[get_repository] = lambda: fake_repository
    return TestClient(app)


def test_search_without_filters_passes_only_limit(
    client: TestClient, fake_repository: FakeCatalogRepository
) -> None:
    response = client.get("/search")

    assert response.status_code == 200
    assert response.json() == fake_repository.search_result
    assert fake_repository.last_search_body == {"limit": 10}


def test_search_forwards_bbox_datetime_and_filters(
    client: TestClient, fake_repository: FakeCatalogRepository
) -> None:
    response = client.get(
        "/search",
        params={
            "bbox": "20.9,52.1,21.3,52.4",
            "datetime": "2026-08-01T00:00:00Z/2026-09-01T00:00:00Z",
            "collections": "SKY_SHIELD,SPACE_EYE",
            "max_cloud_cover": 20,
            "processing_level": "L2A",
            "limit": 5,
        },
    )

    assert response.status_code == 200
    assert fake_repository.last_search_body == {
        "limit": 5,
        "bbox": [20.9, 52.1, 21.3, 52.4],
        "datetime": "2026-08-01T00:00:00Z/2026-09-01T00:00:00Z",
        "collections": ["SKY_SHIELD", "SPACE_EYE"],
        "query": {
            "eo:cloud_cover": {"lte": 20.0},
            "processing:level": {"eq": "L2A"},
        },
    }


def test_search_rejects_malformed_bbox(client: TestClient) -> None:
    response = client.get("/search", params={"bbox": "not-a-bbox"})

    assert response.status_code == 400
    assert "bbox" in response.json()["detail"]


def test_search_rejects_malformed_datetime(client: TestClient) -> None:
    response = client.get("/search", params={"datetime": "not-a-date"})

    assert response.status_code == 400


def test_search_rejects_cloud_cover_out_of_range(client: TestClient) -> None:
    response = client.get("/search", params={"max_cloud_cover": 142})

    assert response.status_code == 422  # walidacja Query(ge=0, le=100) przez FastAPI
