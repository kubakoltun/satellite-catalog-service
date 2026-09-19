"""Builds the query for `pgstac.search()` from filters passed to `/search`.

Separating query construction (this module, consisting only of pure functions)
from query execution (PgstacRepository.search) is intentional. It is easy 
to make a typo in an operator name or get the bbox ordering wrong, 
so it is useful to be able to test it without a database.

The resulting "search body" follows the STAC API Item Search request body format
(with the query extension) - exactly what pgstac.search() expects.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime as _datetime


@dataclass(frozen=True)
class SearchFilters:
    bbox: tuple[float, float, float, float] | None = None
    datetime: str | None = None
    collections: tuple[str, ...] | None = None
    max_cloud_cover: float | None = None
    processing_level: str | None = None
    limit: int = 10


def parse_bbox_param(bbox: str | None) -> tuple[float, float, float, float] | None:
    """Parses `bbox=minLon,minLat,maxLon,maxLat` (STAC API format).

    Raises `ValueError` for an invalid format - API layer maps to 400.
    """
    if bbox is None:
        return None

    parts = bbox.split(",")
    if len(parts) != 4:
        raise ValueError(
            f"bbox has to have exactly 4 values (minLon,minLat,maxLon,maxLat), got: {bbox!r}"
        )
    try:
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
    except ValueError as exc:
        raise ValueError(f"bbox contains a invalid number: {exc}") from exc

    if min_lon > max_lon or min_lat > max_lat:
        raise ValueError(f"bbox: minimum values must be less than or equal to maximum values: {bbox!r}")

    return (min_lon, min_lat, max_lon, max_lat)


def parse_collections_param(collections: str | None) -> tuple[str, ...] | None:
    """Parses `collections=SKY_SHIELD,SPACE_EYE` into a tuple of collection names."""
    if collections is None:
        return None
    parsed = tuple(c.strip() for c in collections.split(",") if c.strip())
    return parsed or None


def validate_datetime_param(value: str | None) -> str | None:
    """Validates the `datetime` parameter in STAC API format: a single
    RFC3339 instant or an interval `start/end` (with `..` representing
    an open end).
    Returns the input unchanged (`pgSTAC` parses it itself) - this is only
    early, readable format validation.
    """
    if value is None:
        return None

    parts = value.split("/")
    if len(parts) not in (1, 2):
        raise ValueError(f"Invalid format datetime (expected instant or start/end): {value!r}")

    for part in parts:
        if part == "..":
            continue
        _validate_rfc3339_instant(part)

    return value


def _validate_rfc3339_instant(value: str) -> None:
    normalized = value.replace("Z", "+00:00")
    try:
        _datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Invalid data/time in RFC3339 format: {value!r}") from exc


def build_pgstac_search_body(filters: SearchFilters) -> dict:
    """Search body, the format is compatible with `pgstac.search()` filters."""
    body: dict = {"limit": filters.limit}

    if filters.bbox is not None:
        body["bbox"] = list(filters.bbox)
    if filters.datetime is not None:
        body["datetime"] = filters.datetime
    if filters.collections:
        body["collections"] = list(filters.collections)

    query: dict = {}
    if filters.max_cloud_cover is not None:
        query["eo:cloud_cover"] = {"lte": filters.max_cloud_cover}
    if filters.processing_level is not None:
        query["processing:level"] = {"eq": filters.processing_level}
    if query:
        body["query"] = query

    return body
