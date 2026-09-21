from pathlib import Path

import pytest
import base64
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock

from satellite_catalog.core.mission import Mission
from satellite_catalog.ingestion.errors import ParsingError
from satellite_catalog.ingestion.worker import _handle_message
from satellite_catalog.deps import get_repository
from satellite_catalog.deps import get_queue
from satellite_catalog.ingestion.api import router as ingestion_router
from tests.unit.fakes import FakeCatalogRepository
from tests.unit.fakes import FakeQueue

FIXTURES = Path(__file__).parents[2] / "fixtures"


@pytest.fixture
def fake_repository() -> FakeCatalogRepository:
    return FakeCatalogRepository()

@pytest.fixture
def fake_queue() -> FakeQueue:
    return FakeQueue()


@pytest.fixture
def client(fake_repository: FakeCatalogRepository, fake_queue: FakeQueue) -> TestClient:
    app = FastAPI()
    app.include_router(ingestion_router)
    app.dependency_overrides[get_queue] = lambda: fake_queue
    app.dependency_overrides[get_repository] = lambda: fake_repository
    return TestClient(app)


def test_ingest_sky_shield_returns_202_immediately(client: TestClient) -> None:
    raw = (FIXTURES / "sky_shield_sample.json").read_bytes()

    response = client.post(
        "/ingest/SKY_SHIELD", content=raw, headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 202
    assert response.json() == {"status": "accepted", "mission": "SKY_SHIELD"}


def test_ingest_unknown_mission_rejected_by_path_validation(client: TestClient) -> None:
    response = client.post("/ingest/UNKNOWN_MISSION", content=b"{}")

    assert response.status_code == 422  # FastAPI waliduje Enum w ścieżce


def test_ingest_empty_body_returns_400(client: TestClient) -> None:
    response = client.post("/ingest/SKY_SHIELD", content=b"")

    assert response.status_code == 400
    assert response.json() == {"detail": "Request body is empty"}


@pytest.mark.asyncio
async def test_invalid_payload_is_dead_lettered(
    caplog: pytest.LogCaptureFixture,
) -> None:
    body = json.dumps(
        {
            "mission": Mission.SKY_SHIELD.value,
            "raw": base64.b64encode(b"{not valid json").decode("ascii"),
            "message_id": "test-message-id",
            "received_at": "2026-01-01T00:00:00+00:00",
        }
    ).encode()

    message = Mock()
    message.body = body
    message.ack = AsyncMock()
    message.nack = AsyncMock()

    service = Mock()
    service.ingest = AsyncMock(side_effect=ParsingError("Invalid JSON"))

    with caplog.at_level("ERROR", logger="satellite_catalog.worker"):
        await _handle_message(message, service)

    message.nack.assert_awaited_once_with(requeue=False)
    message.ack.assert_not_awaited()

    service.ingest.assert_awaited_once_with(
        Mission.SKY_SHIELD,
        b"{not valid json",
    )

    assert any("Unrecoverable ingestion error" in record.message for record in caplog.records)
