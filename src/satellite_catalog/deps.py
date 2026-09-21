"""FastAPI Dependencies (Depends) - thin DI layer

The repository is created once in main.py (lifespan) and stored in app.state.
Endpoints get it through this function instead of importing `PgstacRepository` directly.
This keeps the routers dependent only on the `CatalogRepositoryPort` abstraction,
rather than on the specific pgSTAC implementation underneath.
In unit tests, I can replace this dependency with a fake repository using
`app.dependency_overrides` - no real database is needed.
"""

from fastapi import Request

from satellite_catalog.catalog.repository import CatalogRepositoryPort


def get_repository(request: Request) -> CatalogRepositoryPort:
    return request.app.state.repository
