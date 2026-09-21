"""FastAPI Dependencies (Depends) - thin DI layer

Both the repository and the queue are created once in main.py (lifespan)
and stored on app.state. Endpoints get them through these functions
instead of importing PgstacRepository/RabbitMQQueue directly, so routers
depend only on the CatalogRepositoryPort / QueuePort abstractions.
In unit tests, both can be swapped via `app.dependency_overrides` - no
real database or broker needed.
"""

from fastapi import Request

from satellite_catalog.catalog.repository import CatalogRepositoryPort
from satellite_catalog.ingestion.queue_port import QueuePort


def get_repository(request: Request) -> CatalogRepositoryPort:
    return request.app.state.repository


def get_queue(request: Request) -> QueuePort:
    return request.app.state.queue
