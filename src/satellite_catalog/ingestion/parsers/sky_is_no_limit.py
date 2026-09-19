"""Parser metadanych SKY_SHIELD (dostawca: SkyIsNoLimit, format: JSON).

Dane geoprzestrzenne przychodzą już w EPSG:4326 - nie ma tu reprojekcji,
tylko mapowanie pól i budowa STAC Item.
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
    """Mapuje surowy JSON SKY_SHIELD na zwalidowany STAC Item."""
    data = _load_json(raw)

    # Cała ekstrakcja pól ze struktury dostawcy dzieje się w jednym
    # bloku try/except - każdy brakujący klucz, niezależnie na jakim
    # poziomie zagnieżdżenia, ma się zamienić w ten sam czytelny
    # ParsingError, a nie w gołego KeyError-a gdzieś dalej w funkcji.
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

        properties = {
            "datetime": acquisition["capture_timestamp_utc"],
            "platform": acquisition["satellite_id"],
            "mission": acquisition["mission_name"],
            "providers": [{"name": acquisition["provider_id"], "roles": ["producer"]}],
            **processing_properties(product["processing_level"]),
            **eo_properties(metrics["cloud_cover_percentage"]),
            **view_properties(metrics["sun_azimuth_deg"], metrics["sun_elevation_deg"]),
            **sat_orbit_state(orbit["direction"]),
            # Pola bez odpowiednika w oficjalnym rozszerzeniu STAC - trzymane
            # jako custom properties w namespace dostawcy (konwencja STAC:
            # `prefix:pole`), żeby nie zgubić informacji, ale też nie
            # udawać, że to część jakiegoś standardu.
            "skyshield:snow_cover_percentage": metrics["snow_cover_percentage"],
            "skyshield:orbit_path": orbit["path"],
            "skyshield:orbit_row": orbit["row"],
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
        raise ParsingError(f"Brakujące pole w metadanych SKY_SHIELD: {exc}") from exc

    _warn_if_bbox_inconsistent(geometry, bbox, source="SKY_SHIELD bounding_box")

    item = build_stac_item(
        item_id=acquisition["scene_identifier"],
        collection=Mission.SKY_SHIELD.value,
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
        raise ParsingError(f"Niepoprawny JSON w metadanych SKY_SHIELD: {exc}") from exc


def _extract_bbox(bounding_box: dict) -> tuple[float, float, float, float]:
    try:
        return (
            bounding_box["min_longitude"],
            bounding_box["min_latitude"],
            bounding_box["max_longitude"],
            bounding_box["max_latitude"],
        )
    except KeyError as exc:
        raise ParsingError(f"Niepełny bounding_box w metadanych SKY_SHIELD: {exc}") from exc


def _warn_if_bbox_inconsistent(
    geometry: dict, provider_bbox: tuple[float, float, float, float], *, source: str
) -> None:
    """Miękka walidacja spójności - loguje, ale NIGDY nie blokuje ingestion.

    Rozjazd między geometrią a osobno podanym bboxem to problem jakości
    danych dostawcy, nie powód do odrzucenia całego produktu.
    """
    computed = bbox_from_geometry(geometry)
    if not bbox_matches(computed, provider_bbox):
        logger.warning(
            "%s (%s) nie zgadza się z bboxem policzonym z geometrii (%s)",
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
