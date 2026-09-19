"""Test integracyjny `PgstacRepository` na REALNYM Postgresie+pgSTAC.

WYMAGA DOCKERA. Nie jest częścią domyślnego `pytest` (patrz `pytest.ini_options`
w pyproject.toml - testy integracyjne trzeba włączyć jawnie):

    pip install -e ".[dev,integration]"
    pytest tests/integration -v -m integration

`testcontainers` samo podniesie i zamknie kontener z obrazem
`ghcr.io/stac-utils/pgstac`, uruchomi `pypgstac migrate`, a na koniec
posprząta - nie trzeba wcześniej odpalać `docker-compose.yml`.

Uwaga uczciwości: ten plik NIE został uruchomiony w środowisku, w którym
go napisałem (brak Docker Daemon w tym sandboxie) - w przeciwieństwie do
testów jednostkowych w `tests/unit/`, które realnie przeszły. Uruchom go
u siebie jako pierwszą rzeczywistą weryfikację całej ścieżki zapisu.
"""

from __future__ import annotations

from pathlib import Path

import asyncpg
import pytest

from satellite_catalog.catalog.collections import build_collection
from satellite_catalog.catalog.pgstac_repository import PgstacRepository
from satellite_catalog.core.mission import Mission
from satellite_catalog.ingestion.parsers.sky_is_no_limit import parse_sky_is_no_limit

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).parents[1] / "fixtures" / "sky_shield_sample.json"


@pytest.fixture(scope="module")
def pgstac_dsn():
    """Podnosi kontener Postgres+pgSTAC i ładuje schemat migracją."""
    import subprocess

    from testcontainers.core.container import DockerContainer
    from testcontainers.core.waiting_utils import wait_for_logs

    container = (
        DockerContainer("ghcr.io/stac-utils/pgstac:latest")
        .with_env("POSTGRES_USER", "username")
        .with_env("POSTGRES_PASSWORD", "password")
        .with_env("POSTGRES_DB", "postgis")
        .with_exposed_ports(5432)
    )
    with container as running:
        wait_for_logs(running, "database system is ready to accept connections", timeout=60)
        host = running.get_container_host_ip()
        port = running.get_exposed_port(5432)
        dsn = f"postgresql://username:password@{host}:{port}/postgis"

        subprocess.run(["pypgstac", "migrate", "--dsn", dsn], check=True)
        yield dsn


@pytest.fixture
async def pool(pgstac_dsn: str):
    pool = await asyncpg.create_pool(dsn=pgstac_dsn)
    yield pool
    await pool.close()


async def test_save_item_persists_to_pgstac(pool: asyncpg.Pool) -> None:
    repo = PgstacRepository(pool)
    await repo.ensure_collection(build_collection(Mission.SKY_SHIELD))

    item = parse_sky_is_no_limit(FIXTURE.read_text())
    await repo.save_item(item)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, collection FROM pgstac.items WHERE id = $1;", item["id"]
        )

    assert row is not None
    assert row["collection"] == "SKY_SHIELD"


async def test_save_item_is_idempotent(pool: asyncpg.Pool) -> None:
    """Wymaganie F7: ponowne przesłanie tego samego produktu nie tworzy duplikatu."""
    repo = PgstacRepository(pool)
    await repo.ensure_collection(build_collection(Mission.SKY_SHIELD))

    item = parse_sky_is_no_limit(FIXTURE.read_text())
    await repo.save_item(item)
    await repo.save_item(item)  # ten sam Item, drugi raz

    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM pgstac.items WHERE id = $1;", item["id"]
        )

    assert count == 1


async def test_search_finds_saved_item_by_bbox_and_cloud_cover(pool: asyncpg.Pool) -> None:
    """Pełna ścieżka Kroku 2 + Kroku 3: zapisany Item musi dać się znaleźć
    przez /search - bbox obejmujący scenę i eo:cloud_cover <= wartość ze sceny."""
    repo = PgstacRepository(pool)
    await repo.ensure_collection(build_collection(Mission.SKY_SHIELD))

    item = parse_sky_is_no_limit(FIXTURE.read_text())
    await repo.save_item(item)

    result = await repo.search(
        {
            "collections": ["SKY_SHIELD"],
            "bbox": [20.0, 51.0, 22.0, 53.0],  # obejmuje scenę z fixture
            "query": {"eo:cloud_cover": {"lte": 20.0}},  # scena ma 14.2
            "limit": 10,
        }
    )

    found_ids = {feature["id"] for feature in result["features"]}
    assert item["id"] in found_ids


async def test_search_excludes_item_when_cloud_cover_filter_too_strict(
    pool: asyncpg.Pool,
) -> None:
    repo = PgstacRepository(pool)
    await repo.ensure_collection(build_collection(Mission.SKY_SHIELD))

    item = parse_sky_is_no_limit(FIXTURE.read_text())
    await repo.save_item(item)

    result = await repo.search(
        {
            "collections": ["SKY_SHIELD"],
            "query": {"eo:cloud_cover": {"lte": 5.0}},  # scena ma 14.2 - powinna odpaść
            "limit": 10,
        }
    )

    found_ids = {feature["id"] for feature in result["features"]}
    assert item["id"] not in found_ids
