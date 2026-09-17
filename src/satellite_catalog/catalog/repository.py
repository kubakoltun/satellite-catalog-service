"""Kontrakt repozytorium katalogu - Repository pattern.

`ingestion/service.py` (Krok 4) i `catalog/search.py` (Krok 3) mają zależeć
wyłącznie od tego protokołu, nigdy od `asyncpg`/SQL wprost - to jest DIP:
logika domenowa nie wie, że pod spodem jest pgSTAC, mogłaby równie dobrze
być inną implementacją STAC API. Ułatwia to też testy jednostkowe use case'ów
bez realnej bazy (podstawiasz fake/mock implementujący ten protokół).
"""

from typing import Protocol

from satellite_catalog.core.stac_models import STACItemDict


class CatalogRepositoryPort(Protocol):
    async def ensure_collection(self, collection: dict) -> None:
        """Rejestruje Collection w katalogu, jeśli jeszcze nie istnieje
        (idempotentne - bezpieczne wywołanie przy każdym starcie aplikacji)."""
        ...

    async def save_item(self, item: STACItemDict) -> None:
        """Zapisuje STAC Item - insert lub update, jeśli Item o tym samym
        `id` już istnieje w tej kolekcji (idempotentne wg wymagania F7:
        ponowne przesłanie tego samego produktu nie tworzy duplikatu)."""
        ...

    async def search(self, search_body: dict) -> dict:
        """Wykonuje wyszukiwanie i zwraca surowy wynik zgodny ze STAC API
        (dict w kształcie ItemCollection: `features`, `links`, `context`) -
        to, co realnie zwraca `pgstac.search()`. Warstwa API tylko
        przekazuje dalej ten wynik, nie transformuje go ponownie."""
        ...
