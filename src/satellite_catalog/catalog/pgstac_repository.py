"""Implementacja `CatalogRepositoryPort` oparta o funkcje SQL pgSTAC.

Celowo NIE piszemy surowego SQL-a operującego bezpośrednio na tabelach
`pgstac.items`/`pgstac.collections` - są partycjonowane i mają nietrywialną
logikę wewnętrzną (m.in. automatyczne partycjonowanie po czasie, triggery
utrzymujące indeksy). Zamiast tego wywołujemy oficjalne funkcje SQL, które
pgSTAC do tego udostępnia w schemacie `pgstac` (ten sam mechanizm, którego
pod spodem używa `pypgstac`).

UWAGA (do zweryfikowania przy pierwszym realnym uruchomieniu): nazwy
`pgstac.upsert_collection` / `pgstac.upsert_item` / `pgstac.search`
odpowiadają publicznemu API pgSTAC w wersji, na którą wskazuje
`docker-compose.yml`. Jeśli po podniesieniu `docker compose up` zapis lub
wyszukiwanie zwróci błąd "function ... does not exist", sprawdź dokładne
nazwy funkcji w załadowanym schemacie:

    docker compose exec postgres psql -U username -d postgis -c "\\df pgstac.*"

i podmień wywołanie SQL poniżej na właściwą nazwę - kontrakt
`CatalogRepositoryPort` (save_item/ensure_collection/search) się nie
zmienia, więc żaden kod poza tym plikiem nie wymaga wtedy modyfikacji.
"""

from __future__ import annotations

import json
import logging

import asyncpg

from satellite_catalog.catalog.errors import (
    CollectionPersistenceError,
    ItemPersistenceError,
    SearchError,
)
from satellite_catalog.core.stac_models import STACItemDict

logger = logging.getLogger(__name__)


class PgstacRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def ensure_collection(self, collection: dict) -> None:
        payload = json.dumps(collection)
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("SELECT pgstac.upsert_collection($1::jsonb);", payload)
        except asyncpg.PostgresError as exc:
            raise CollectionPersistenceError(
                f"Nie udało się zarejestrować kolekcji '{collection.get('id')}': {exc}"
            ) from exc

        logger.info("Kolekcja '%s' zarejestrowana/zaktualizowana.", collection.get("id"))

    async def save_item(self, item: STACItemDict) -> None:
        payload = json.dumps(item)
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("SELECT pgstac.upsert_item($1::jsonb);", payload)
        except asyncpg.PostgresError as exc:
            raise ItemPersistenceError(
                f"Nie udało się zapisać Itemu '{item.get('id')}' "
                f"(collection='{item.get('collection')}'): {exc}"
            ) from exc

        logger.info(
            "Item '%s' zapisany do kolekcji '%s'.", item.get("id"), item.get("collection")
        )

    async def search(self, search_body: dict) -> dict:
        payload = json.dumps(search_body)
        try:
            async with self._pool.acquire() as conn:
                raw = await conn.fetchval("SELECT * FROM pgstac.search($1::jsonb);", payload)
        except asyncpg.PostgresError as exc:
            raise SearchError(f"Wyszukiwanie w katalogu nie powiodło się: {exc}") from exc

        # `pgstac.search` zwraca kolumnę typu jsonb; asyncpg (bez dodatkowego
        # codeca) oddaje ją jako string JSON, nie dict - trzeba go dociąć.
        return json.loads(raw) if isinstance(raw, (str, bytes)) else raw
