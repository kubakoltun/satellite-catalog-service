"""`GET /search` endpoint - delegates to `pgstac.search()`

Router is thin - parameters parsing-validation lives in `catalog/search.py`
(only testable function without FastAPI). This router connects 
parsing and validation together, then maps errors to HTTP codes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from satellite_catalog.catalog.errors import CatalogError
from satellite_catalog.catalog.repository import CatalogRepositoryPort
from satellite_catalog.catalog.search import (
    SearchFilters,
    build_pgstac_search_body,
    parse_bbox_param,
    parse_collections_param,
    validate_datetime_param,
)
from satellite_catalog.deps import get_repository

router = APIRouter(tags=["search"])


@router.get("/search")
async def search(
    bbox: str | None = Query(
        None, description="minLon,minLat,maxLon,maxLat (WGS84), ex. 20.9,52.1,21.3,52.4"
    ),
    datetime: str | None = Query(
        None,
        alias="datetime",
        description="RFC3339 instant or interval start/end, ex. 2026-08-01T00:00:00Z/2026-09-01T00:00:00Z",
    ),
    collections: str | None = Query(
        None, description="collection list separated by comma, ex. SKY_SHIELD,SPACE_EYE"
    ),
    max_cloud_cover: float | None = Query(
        None, ge=0, le=100, description="max eo:cloud_cover in percent"
    ),
    processing_level: str | None = Query(
        None, description="exact processing:level, ex. L2A"
    ),
    limit: int = Query(10, ge=1, le=1000),
    repository: CatalogRepositoryPort = Depends(get_repository),
) -> dict:
    try:
        filters = SearchFilters(
            bbox=parse_bbox_param(bbox),
            datetime=validate_datetime_param(datetime),
            collections=parse_collections_param(collections),
            max_cloud_cover=max_cloud_cover,
            processing_level=processing_level,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    search_body = build_pgstac_search_body(filters)

    try:
        return await repository.search(search_body)
    except CatalogError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
