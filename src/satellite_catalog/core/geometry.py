"""Operacje geoprzestrzenne wspólne dla obu parserów.

STAC wymaga geometrii i bbox w WGS84 (EPSG:4326) - niezależnie od tego,
w jakim układzie dostawca opisuje footprint. SKY_SHIELD dostarcza dane
już w EPSG:4326 (nic do zrobienia poza walidacją), SPACE_EYE w UTM 34N
(EPSG:32634) - wymaga realnej reprojekcji, nie tylko przepisania liczb.
"""

from __future__ import annotations

from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform
from shapely.wkt import loads as wkt_loads
from pyproj import Transformer

_COORD_PRECISION = 6  # ~11 cm na równiku - więcej niż potrzeba, mniej niż szum GPS


def reproject_wkt_to_wgs84(wkt: str, source_epsg: str) -> dict:
    """Zamienia geometrię WKT w dowolnym CRS na GeoJSON w EPSG:4326.

    `source_epsg` w formacie "EPSG:32634" (dokładnie tak, jak przychodzi
    w metadanych SPACE_EYE).
    """
    geometry: BaseGeometry = wkt_loads(wkt)

    transformer = Transformer.from_crs(source_epsg, "EPSG:4326", always_xy=True)
    reprojected = transform(transformer.transform, geometry)

    return _round_geojson(mapping(reprojected))


def bbox_from_geometry(geometry: dict) -> tuple[float, float, float, float]:
    """Liczy bbox (minx, miny, maxx, maxy) z geometrii GeoJSON w WGS84."""
    minx, miny, maxx, maxy = shape(geometry).bounds
    return (
        round(minx, _COORD_PRECISION),
        round(miny, _COORD_PRECISION),
        round(maxx, _COORD_PRECISION),
        round(maxy, _COORD_PRECISION),
    )


def bbox_matches(
    computed: tuple[float, float, float, float],
    reference: tuple[float, float, float, float],
    tolerance_deg: float = 0.01,
) -> bool:
    """Porównuje przeliczony bbox z bboxem podanym wprost przez dostawcę.

    Używane jako sanity-check po reprojekcji (np. SPACE_EYE podaje
    `GlobalBBOX` niezależnie od `FootprintWKT`) - nie jako źródło prawdy,
    tylko jako wczesne ostrzeżenie, gdyby reprojekcja poszła nie tak.
    """
    return all(abs(a - b) <= tolerance_deg for a, b in zip(computed, reference, strict=True))


def _round_geojson(geometry: dict) -> dict:
    """Zaokrągla współrzędne w geometrii GeoJSON (dowolnego typu) do stałej precyzji."""

    def _round_coords(coords):
        if isinstance(coords[0], (int, float)):
            return [round(c, _COORD_PRECISION) for c in coords]
        return [_round_coords(c) for c in coords]

    return {**geometry, "coordinates": _round_coords(geometry["coordinates"])}
