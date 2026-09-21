"""Geospatial operations shared by both parsers

STAC requires the geometry and bbox to be in WGS84 (EPSG:4326), regardless of the CRS 
used by the provider to describe the footprint. 
SKY_SHIELD already provides data in EPSG:4326 (nothing to do except validation), 
while SPACE_EYE uses UTM 34N (EPSG:32634) and therefore 
requires an actual reprojection.
"""

from __future__ import annotations

from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform
from shapely.wkt import loads as wkt_loads
from pyproj import Transformer

_COORD_PRECISION = 6  # ~11 cm at the equator; finer than the expected footprint accuracy


def reproject_wkt_to_wgs84(wkt: str, source_epsg: str) -> dict:
    """Reprojects a WKT geometry from the source CRS to WGS84 (EPSG:4326)
    and returns it as GeoJSON.

    `source_epsg` must be in the format "EPSG:32634", exactly as provided
    in the SPACE_EYE metadata.
    """
    geometry: BaseGeometry = wkt_loads(wkt)

    transformer = Transformer.from_crs(source_epsg, "EPSG:4326", always_xy=True)
    reprojected = transform(transformer.transform, geometry)

    return _round_geojson(mapping(reprojected))


def bbox_from_geometry(geometry: dict) -> tuple[float, float, float, float]:
    """Calculates the bbox (minx, miny, maxx, maxy) from a GeoJSON geometry in WGS84."""
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
    """Compares a calculated bbox with the bbox provided directly by the provider

    Used as a sanity check after reprojection. SPACE_EYE provides `GlobalBBOX`
    independently of `FootprintWKT`. It is not treated as the source of truth,
    but rather as an early warning if the reprojection goes wrong.
    """
    return all(abs(a - b) <= tolerance_deg for a, b in zip(computed, reference, strict=True))


def _round_geojson(geometry: dict) -> dict:
    """Rounds coordinates in a GeoJSON geometry of any type to a fixed precision."""

    def _round_coords(coords):
        if isinstance(coords[0], (int, float)):
            return [round(c, _COORD_PRECISION) for c in coords]
        return [_round_coords(c) for c in coords]

    return {**geometry, "coordinates": _round_coords(geometry["coordinates"])}
