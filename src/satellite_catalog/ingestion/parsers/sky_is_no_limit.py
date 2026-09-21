"""Metadata parser (provider: SkyIsNoLimit, format: JSON).\

Geospatial data already comes in EPSG:4326 - no reprojection is performed here.
I only map the provider fields and build the STAC Item.
"""

from __future__ import annotations

import json
import logging

from satellite_catalog.core.extensions import (
    EO_EXTENSION,
    PROCESSING_EXTENSION,
    SAT_EXTENSION,
    VIEW_EXTENSION,
    eo_properties,
    processing_properties,
    sat_orbit_state,
    view_properties,
)
from satellite_catalog.core.geometry import bbox_from_geometry, bbox_matches
from satellite_catalog.core.mission import Mission
from satellite_catalog.core.stac_models import (
    STACItemDict,
    build_stac_item,
    validate_stac_item,
)
from satellite_catalog.ingestion.errors import ParsingError

logger = logging.getLogger(__name__)


def parse_sky_is_no_limit(raw: bytes | str) -> STACItemDict:
    """Map raw SkyIsNoLimit JSON metadata to a validated STAC Item."""

    data = _load_json(raw)

    # I keep all field extraction from the provider structure in a single
    # try/except block. This ensures that any missing key, regardless of its
    # nesting level, is converted into the same clear `ParsingError` instead
    # of exposing a raw KeyError
    try:
        acquisition = data["acquisition_metadata"]
        orbit = acquisition["orbit"]
        product = data["product_characteristics"]
        metrics = product["metrics"]
        spatial = data["spatial_extent"]
        deliverables = data["data_deliverables"]
        bands = deliverables["image_bands"]

        geometry = spatial["geometry_geojson"]
        bbox = _extract_bbox(spatial["bounding_box"])

        mission = Mission(acquisition["mission_name"]) # Validate against the catalog's supported missions

        properties = {
            "datetime": acquisition["capture_timestamp_utc"],
            "platform": acquisition["satellite_id"],
            "mission": mission.value,
            "providers": [{"name": acquisition["provider_id"], "roles": ["producer"]}],
            **processing_properties(product["processing_level"]),
            **eo_properties(metrics["cloud_cover_percentage"]),
            **view_properties(metrics["sun_azimuth_deg"], metrics["sun_elevation_deg"]),
            **sat_orbit_state(orbit["direction"]),
      
            # I store fields without a corresponding official STAC extension
            # as custom properties using the provider namespace. This follows
            # the STAC convention of using a `prefix:field` property name and
            # preserves the original provider-specific information.
            "skyisnolimit:snow_cover_percentage": metrics["snow_cover_percentage"],
            "skyisnolimit:orbit_path": orbit["path"],
            "skyisnolimit:orbit_row": orbit["row"],
        }

        assets = {
            "red": _band_asset(bands["red"], "Red band (B04)"),
            "green": _band_asset(bands["green"], "Green band (B03)"),
            "blue": _band_asset(bands["blue"], "Blue band (B02)"),
            "nir": _band_asset(bands["nir"], "NIR band (B08)"),
            "thumbnail": {
                "href": deliverables["thumbnail"],
                "title": "Thumbnail",
                "type": "image/png",
                "roles": ["thumbnail"],
            },
        }
    except KeyError as exc:
        raise ParsingError(f"Missing field in SkyIsNoLimit metadata: {exc}") from exc

    _warn_if_bbox_inconsistent(geometry, bbox, source="SkyIsNoLimit bounding_box")

    item = build_stac_item(
        item_id=acquisition["scene_identifier"],
        collection=mission.value,
        geometry=geometry,
        bbox=bbox,
        properties=properties,
        assets=assets,
        stac_extensions=[EO_EXTENSION, PROCESSING_EXTENSION, VIEW_EXTENSION, SAT_EXTENSION],
    )
    return validate_stac_item(item)


def _load_json(raw: bytes | str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ParsingError(f"Invalid JSON in SkyIsNoLimit metadata: {exc}") from exc


def _extract_bbox(bounding_box: dict) -> tuple[float, float, float, float]:
    try:
        return (
            bounding_box["min_longitude"],
            bounding_box["min_latitude"],
            bounding_box["max_longitude"],
            bounding_box["max_latitude"],
        )
    except KeyError as exc:
        raise ParsingError(f"Incomplete bounding_box in SkyIsNoLimit metadata: {exc}") from exc


def _warn_if_bbox_inconsistent(
    geometry: dict, provider_bbox: tuple[float, float, float, float], *, source: str
) -> None:
    """Perform a soft consistency check without blocking ingestion

    I log a warning when the provider-supplied bbox does not match the bbox
    calculated from the geometry. I treat this as a provider data-quality
    issue rather than a reason to reject the entire product.
    """
    computed = bbox_from_geometry(geometry)
    if not bbox_matches(computed, provider_bbox):
        logger.warning(
            "%s (%s) does not match the bbox calculated from the geometry (%s)",
            source,
            provider_bbox,
            computed,
        )


def _band_asset(href: str, title: str) -> dict:
    return {
        "href": href,
        "title": title,
        "type": "image/tiff; application=geotiff",
        "roles": ["data"],
    }
