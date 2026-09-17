import json

import asyncpg
import pytest

from satellite_catalog.catalog.collections import build_collection
from satellite_catalog.catalog.errors import (
    CollectionPersistenceError,
    ItemPersistenceError,
    SearchError,
)
from satellite_catalog.catalog.pgstac_repository import PgstacRepository
from satellite_catalog.core.mission import Mission
from satellite_catalog.ingestion.parsers.sky_shield_json import parse_sky_shield
from tests.unit.catalog.fakes import FakeConnection, FakePool


@pytest.fixture
def sky_shield_item():
    raw = (
        (__import__("pathlib").Path(__file__).parents[2] / "fixtures" / "sky_shield_sample.json")
        .read_text()
    )
    return parse_sky_shield(raw)


async def test_ensure_collection_calls_upsert_collection_with_payload():
    conn = FakeConnection()
    repo = PgstacRepository(FakePool(conn))
    collection = build_collection(Mission.SKY_SHIELD)

    await repo.ensure_collection(collection)

    assert len(conn.calls) == 1
    sql, args = conn.calls[0]
    assert "pgstac.upsert_collection" in sql
    assert json.loads(args[0]) == collection


async def test_save_item_calls_upsert_item_with_payload(sky_shield_item):
    conn = FakeConnection()
    repo = PgstacRepository(FakePool(conn))

    await repo.save_item(sky_shield_item)

    assert len(conn.calls) == 1
    sql, args = conn.calls[0]
    assert "pgstac.upsert_item" in sql
    assert json.loads(args[0])["id"] == sky_shield_item["id"]


async def test_save_item_wraps_database_errors():
    conn = FakeConnection(raise_error=asyncpg.PostgresError("boom"))
    repo = PgstacRepository(FakePool(conn))

    with pytest.raises(ItemPersistenceError):
        await repo.save_item({"id": "broken-item", "collection": "SKY_SHIELD"})


async def test_ensure_collection_wraps_database_errors():
    conn = FakeConnection(raise_error=asyncpg.PostgresError("boom"))
    repo = PgstacRepository(FakePool(conn))

    with pytest.raises(CollectionPersistenceError):
        await repo.ensure_collection({"id": "SKY_SHIELD"})


async def test_search_calls_pgstac_search_with_body_as_jsonb():
    fake_result = json.dumps({"type": "FeatureCollection", "features": [], "links": []})
    conn = FakeConnection(fetchval_result=fake_result)
    repo = PgstacRepository(FakePool(conn))

    result = await repo.search({"bbox": [20.9, 52.1, 21.3, 52.4], "limit": 10})

    assert len(conn.calls) == 1
    sql, args = conn.calls[0]
    assert "pgstac.search" in sql
    assert json.loads(args[0]) == {"bbox": [20.9, 52.1, 21.3, 52.4], "limit": 10}
    assert result == {"type": "FeatureCollection", "features": [], "links": []}


async def test_search_wraps_database_errors():
    conn = FakeConnection(raise_error=asyncpg.PostgresError("boom"))
    repo = PgstacRepository(FakePool(conn))

    with pytest.raises(SearchError):
        await repo.search({"limit": 10})
