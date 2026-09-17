"""Parser metadanych SPACE_EYE (dostawca: SpaceIsNoLimit, format: XML).

Dwie rzeczy odróżniają ten parser od SKY_SHIELD:
1. Geometria (`FootprintWKT`) jest w UTM (EPSG:32634) - wymaga realnej
   reprojekcji do WGS84, nie tylko przepisania współrzędnych.
2. Czas jest podany jako interwał (`StartTimeUTC`/`StopTimeUTC`), nie
   pojedynczy moment - mapujemy na `start_datetime`/`end_datetime`
   z `datetime=None`, zgodnie ze specyfikacją STAC Common Metadata.
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


def parse_space_eye(raw: bytes | str) -> STACItemDict:
    """Mapuje surowy XML SPACE_EYE na zwalidowany STAC Item."""
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

    try:
        geometry = reproject_wkt_to_wgs84(footprint_wkt, source_crs)
    except Exception as exc:  # noqa: BLE001 - opakowujemy w jeden czytelny błąd domenowy
        raise ParsingError(
            f"Nie udało się przeliczyć FootprintWKT ({source_crs} -> EPSG:4326): {exc}"
        ) from exc

    bbox = bbox_from_geometry(geometry)
    _warn_if_global_bbox_inconsistent(root, computed_bbox=bbox)

    properties = {
        "datetime": None,
        "start_datetime": start_datetime,
        "end_datetime": end_datetime,
        "platform": spacecraft_id,
        "mission": mission_name,
        "providers": [{"name": provider, "roles": ["producer"]}],
        **processing_properties(processing_level),
        **eo_properties(cloud_cover),
        # DataQualityStatus nie ma odpowiednika w oficjalnym rozszerzeniu
        # STAC - custom property w namespace dostawcy.
        "spaceeye:data_quality_status": quality_status,
    }

    assets = _extract_assets(root)

    item = build_stac_item(
        item_id=granule_id,
        collection=Mission.SPACE_EYE.value,
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
        raise ParsingError(f"Niepoprawny XML w metadanych SPACE_EYE: {exc}") from exc


def _required_text(element: etree._Element, xpath: str) -> str:
    value = element.findtext(xpath, namespaces=_NS)
    if value is None or not value.strip():
        raise ParsingError(f"Brakujący lub pusty węzeł '{xpath}' w metadanych SPACE_EYE")
    return value.strip()


def _extract_assets(root: etree._Element) -> dict:
    assets: dict[str, dict] = {}

    for band in root.findall("se:RasterFiles/se:Band", _NS):
        name = band.get("name")
        href = band.findtext("se:URL", namespaces=_NS)
        if name is None or href is None:
            raise ParsingError("Niepełny wpis <Band> w RasterFiles (brak name/URL)")

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
    """Miękka walidacja: `GlobalBBOX` to redundantne pole dostawcy - może
    się rozjechać z `FootprintWKT` (obserwowane realnie w próbce SPACE_EYE).
    Logujemy ostrzeżenie, ale to `FootprintWKT` jest źródłem prawdy dla
    faktycznego zasięgu produktu, więc NIGDY nie blokujemy na tej podstawie.
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
        return  # niepełny/niepoprawny GlobalBBOX - pomijamy sanity-check, to i tak pole pomocnicze

    if not bbox_matches(computed_bbox, reference_bbox, tolerance_deg=0.05):
        logger.warning(
            "GlobalBBOX z metadanych (%s) nie zgadza się z bboxem policzonym "
            "z FootprintWKT po reprojekcji (%s) - używam FootprintWKT jako źródła prawdy",
            reference_bbox,
            computed_bbox,
        )
