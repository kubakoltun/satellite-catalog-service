"""Metadata parser (provider: SpaceIsNoLimit, format: XML)

The provider metadata requires two transformations:
1. Geometry (`FootprintWKT`) is provided in UTM (EPSG:32634) and must be
   reprojected to WGS84.
2. Time is provided as an interval (`StartTimeUTC`/`StopTimeUTC`), so I map it
   to `start_datetime`/`end_datetime` and set `datetime=None`, as required
   by the STAC Common Metadata specification.

I also map the remaining provider fields and build the STAC Item.
"""

from __future__ import annotations

import logging

from lxml import etree

from satellite_catalog.core.extensions import (
    EO_EXTENSION,
    PROCESSING_EXTENSION,
    eo_properties,
    processing_properties,
)
from satellite_catalog.core.geometry import (
    bbox_from_geometry,
    bbox_matches,
    reproject_wkt_to_wgs84,
)
from satellite_catalog.core.mission import Mission
from satellite_catalog.core.stac_models import (
    STACItemDict,
    build_stac_item,
    validate_stac_item,
)
from satellite_catalog.ingestion.errors import ParsingError

logger = logging.getLogger(__name__)

_NS = {"se": "http://spaceisnolimit.com/schemas/metadata/v2"}


def parse_space_is_no_limit(raw: bytes | str) -> STACItemDict:
    """Map raw XML SpaceIsNoLimit to validated STAC Item."""
    root = _load_xml(raw)

    granule_id = _required_text(root, "se:HeaderInfo/se:GranuleID")
    provider = _required_text(root, "se:HeaderInfo/se:Provider")
    mission_name = _required_text(root, "se:HeaderInfo/se:Mission")
    spacecraft_id = _required_text(root, "se:HeaderInfo/se:SpacecraftID")

    start_datetime = _required_text(root, "se:TemporalCoverage/se:StartTimeUTC")
    end_datetime = _required_text(root, "se:TemporalCoverage/se:StopTimeUTC")

    processing_level = _required_text(root, "se:ProductQuality/se:ProcessingLevel")
    cloud_cover = float(
        _required_text(root, "se:ProductQuality/se:CloudCoveragePercentage")
    )
    quality_status = _required_text(root, "se:ProductQuality/se:DataQualityStatus")

    source_crs = _required_text(root, "se:GeometricProperties/se:CRS")
    footprint_wkt = _required_text(root, "se:GeometricProperties/se:FootprintWKT")

    mission = Mission(mission_name) # Validate against the catalog's supported missions

    try:
        geometry = reproject_wkt_to_wgs84(footprint_wkt, source_crs)
    except Exception as exc:  # noqa: BLE001 - wrap any reprojection error in a domain-specific error
        raise ParsingError(
            f"Could not calculate FootprintWKT ({source_crs} -> EPSG:4326): {exc}"
        ) from exc

    bbox = bbox_from_geometry(geometry)
    _warn_if_global_bbox_inconsistent(root, computed_bbox=bbox)

    properties = {
        "datetime": None,
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "platform": spacecraft_id,
        "mission": mission.value,
        "providers": [{"name": provider, "roles": ["producer"]}],
        **processing_properties(processing_level),
        **eo_properties(cloud_cover),

        # `DataQualityStatus` has no corresponding STAC extension property,
        # so I preserve it as a custom property in the provider namespace.
        "spaceisnolimit:data_quality_status": quality_status,
    }

    assets = _extract_assets(root)

    item = build_stac_item(
        item_id=granule_id,
        collection=mission.value,
        geometry=geometry,
        bbox=bbox,
        properties=properties,
        assets=assets,
        stac_extensions=[EO_EXTENSION, PROCESSING_EXTENSION],
    )
    return validate_stac_item(item)


def _load_xml(raw: bytes | str) -> etree._Element:
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    try:
        return etree.fromstring(raw)
    except etree.XMLSyntaxError as exc:
        raise ParsingError(f"Invalid XML in SpaceIsNoLimit metadata: {exc}") from exc


def _required_text(element: etree._Element, xpath: str) -> str:
    value = element.findtext(xpath, namespaces=_NS)
    if value is None or not value.strip():
        raise ParsingError(f"Missing or empty node '{xpath}' in SpaceIsNoLimit metadata")
    return value.strip()


def _extract_assets(root: etree._Element) -> dict:
    assets: dict[str, dict] = {}

    for band in root.findall("se:RasterFiles/se:Band", _NS):
        name = band.get("name")
        href = band.findtext("se:URL", namespaces=_NS)
        if name is None or href is None:
            raise ParsingError("Incomplete <Band> entry in RasterFiles (missing name or URL)")

        asset: dict = {
            "href": href,
            "title": name,
            "type": "image/tiff; application=geotiff",
            "roles": ["data"],
        }
        resolution = band.get("resolution_m")
        if resolution is not None:
            asset["gsd"] = float(resolution)

        assets[name.lower()] = asset

    overview = root.find("se:RasterFiles/se:OverviewFile", _NS)
    if overview is not None:
        href = overview.findtext("se:URL", namespaces=_NS)
        if href:
            assets["overview"] = {
                "href": href,
                "title": overview.get("type", "Overview"),
                "type": "image/jpeg",
                "roles": ["thumbnail"],
            }

    if not assets:
        raise ParsingError("Brak jakichkolwiek assetów w RasterFiles")

    return assets


def _warn_if_global_bbox_inconsistent(
    root: etree._Element, *, computed_bbox: tuple[float, float, float, float]
) -> None:
    """Perform a soft consistency check of the provider-supplied GlobalBBOX

    `GlobalBBOX` is redundant with `FootprintWKT` and may differ from the
    footprint. I log a warning when the two values do not match, but I use
    the reprojected `FootprintWKT` as the source of truth for the product
    extent and never reject the product based on `GlobalBBOX` alone.
    """
    bbox_el = root.find("se:GeometricProperties/se:GlobalBBOX", _NS)
    if bbox_el is None:
        return

    try:
        reference_bbox = (
            float(bbox_el.findtext("se:WestBoundLongitude", namespaces=_NS)),
            float(bbox_el.findtext("se:SouthBoundLatitude", namespaces=_NS)),
            float(bbox_el.findtext("se:EastBoundLongitude", namespaces=_NS)),
            float(bbox_el.findtext("se:NorthBoundLatitude", namespaces=_NS)),
        )
    except (TypeError, ValueError):
        # Invalid or incomplete GlobalBBOX - skip the sanity check because
        # this is only a supplementary provider field.
        return

    if not bbox_matches(computed_bbox, reference_bbox, tolerance_deg=0.05):
        logger.warning(
            "GlobalBBOX from metadata (%s) does not match the bbox calculated "
            "from FootprintWKT after reprojection (%s) - using FootprintWKT "
            "as the source of truth",
            reference_bbox,
            computed_bbox,
        )
