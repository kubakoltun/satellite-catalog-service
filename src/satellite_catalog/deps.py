"""Zależności FastAPI (Depends) - cienka warstwa DI.

Repozytorium jest tworzone raz w `main.py` (`lifespan`) i trzymane w
`app.state`. Endpointy pobierają je przez tę funkcję zamiast importować
`PgstacRepository` bezpośrednio - dzięki temu routery zależą tylko od
`CatalogRepositoryPort` (DIP), nie od tego, że pod spodem jest akurat
pgSTAC. W testach jednostkowych ta funkcja jest podmieniana przez
`app.dependency_overrides` na fake repozytorium - zero realnej bazy.
"""

from fastapi import Request

from satellite_catalog.catalog.repository import CatalogRepositoryPort


def get_repository(request: Request) -> CatalogRepositoryPort:
    return request.app.state.repository
