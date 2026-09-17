"""Budowa zapytania do `pgstac.search()` z filtrów przekazanych w `/search`.

Rozdzielenie budowy zapytania (ten moduł, same czyste funkcje) od jego
wykonania (`PgstacRepository.search`) jest świadome - to jest dokładnie
ta część, w której najłatwiej o literówkę w nazwie operatora czy
przestawioną kolejność `bbox`, więc warto móc to testować bez bazy danych.

Format wynikowego "search body" to STAC API Item Search request body
(rozszerzenie `query`) - dokładnie to, czego oczekuje `pgstac.search()`.
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
    """Parsuje `bbox=minLon,minLat,maxLon,maxLat` (format STAC API).

    Podnosi `ValueError` przy niepoprawnym formacie - warstwa API mapuje
    to na 400, nie na 500 z głębi zapytania do bazy.
    """
    if bbox is None:
        return None

    parts = bbox.split(",")
    if len(parts) != 4:
        raise ValueError(
            f"bbox musi mieć dokładnie 4 wartości (minLon,minLat,maxLon,maxLat), otrzymano: {bbox!r}"
        )
    try:
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
    except ValueError as exc:
        raise ValueError(f"bbox zawiera niepoprawną liczbę: {exc}") from exc

    if min_lon > max_lon or min_lat > max_lat:
        raise ValueError(f"bbox: wartości minimalne muszą być <= maksymalnym: {bbox!r}")

    return (min_lon, min_lat, max_lon, max_lat)


def parse_collections_param(collections: str | None) -> tuple[str, ...] | None:
    """Parsuje `collections=SKY_SHIELD,SPACE_EYE` na krotkę nazw kolekcji."""
    if collections is None:
        return None
    parsed = tuple(c.strip() for c in collections.split(",") if c.strip())
    return parsed or None


def validate_datetime_param(value: str | None) -> str | None:
    """Waliduje parametr `datetime` w formacie STAC API: pojedynczy
    RFC3339 instant, albo interwał `start/end` (z `..` jako otwartym
    końcem). Zwraca wejście bez zmian (pgSTAC sam je sparsuje) - to jest
    tylko wczesna, czytelna walidacja formatu.
    """
    if value is None:
        return None

    parts = value.split("/")
    if len(parts) not in (1, 2):
        raise ValueError(f"Niepoprawny format datetime (oczekiwano instant lub start/end): {value!r}")

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
        raise ValueError(f"Niepoprawna data/czas w formacie RFC3339: {value!r}") from exc


def build_pgstac_search_body(filters: SearchFilters) -> dict:
    """Składa search body zgodne z tym, czego oczekuje `pgstac.search()`."""
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
