from pathlib import Path

import pytest

from satellite_catalog.ingestion.errors import ParsingError
from satellite_catalog.ingestion.parsers.sky_is_no_limit import parse_sky_is_no_limit

FIXTURE = Path(__file__).parents[2] / "fixtures" / "sky_shield_sample.json"


@pytest.fixture
def raw_sky_shield() -> str:
    return FIXTURE.read_text()


def test_parses_id_and_collection(raw_sky_shield: str) -> None:
    item = parse_sky_is_no_limit(raw_sky_shield)

    assert item["id"] == "SKY_SHIELD_20260824_091522_L1C_POL"
    assert item["collection"] == "SKY_SHIELD"
    assert item["type"] == "Feature"
    assert item["stac_version"] == "1.0.0"


def test_geometry_and_bbox_are_passed_through_unchanged(raw_sky_shield: str) -> None:
    # SKY_SHIELD dostarcza dane już w EPSG:4326 - nie powinno być żadnej
    # reprojekcji, tylko wierne przepisanie.
    item = parse_sky_is_no_limit(raw_sky_shield)

    assert item["geometry"]["type"] == "Polygon"
    assert item["bbox"] == [20.912, 52.185, 21.245, 52.398]


def test_maps_eo_and_processing_extensions(raw_sky_shield: str) -> None:
    item = parse_sky_is_no_limit(raw_sky_shield)
    props = item["properties"]

    assert props["eo:cloud_cover"] == 14.2
    assert props["processing:level"] == "L1C"
    assert "https://stac-extensions.github.io/eo/v1.1.0/schema.json" in item["stac_extensions"]
    assert (
        "https://stac-extensions.github.io/processing/v1.1.0/schema.json"
        in item["stac_extensions"]
    )


def test_maps_optional_extensions_when_data_available(raw_sky_shield: str) -> None:
    item = parse_sky_is_no_limit(raw_sky_shield)
    props = item["properties"]

    assert props["view:sun_azimuth"] == 154.32
    assert props["view:sun_elevation"] == 48.71
    assert props["sat:orbit_state"] == "descending"


def test_keeps_non_standard_fields_as_custom_properties(raw_sky_shield: str) -> None:
    item = parse_sky_is_no_limit(raw_sky_shield)
    props = item["properties"]

    assert props["skyisnolimit:snow_cover_percentage"] == 0.0
    assert props["skyisnolimit:orbit_path"] == 142
    assert props["skyisnolimit:orbit_row"] == 33


def test_datetime_is_a_single_instant(raw_sky_shield: str) -> None:
    item = parse_sky_is_no_limit(raw_sky_shield)

    assert item["properties"]["datetime"] is not None
    assert "start_datetime" not in item["properties"]


def test_assets_include_all_bands_and_thumbnail(raw_sky_shield: str) -> None:
    item = parse_sky_is_no_limit(raw_sky_shield)

    assert set(item["assets"].keys()) == {"red", "green", "blue", "nir", "thumbnail"}
    assert item["assets"]["red"]["href"].endswith("SKY_SHIELD_B04.tif")
    assert item["assets"]["thumbnail"]["roles"] == ["thumbnail"]


def test_result_is_valid_against_stac_item_schema(raw_sky_shield: str) -> None:
    # parse_sky_is_no_limit() waliduje wewnętrznie (validate_stac_item) -
    # jeśli funkcja zwróciła wynik bez wyjątku, item jest już poprawny.
    # Ten test dokumentuje to explicite jako wymaganie, nie tylko efekt uboczny.
    item = parse_sky_is_no_limit(raw_sky_shield)
    assert item is not None


def test_missing_required_field_raises_parsing_error(raw_sky_shield: str) -> None:
    import json

    broken = json.loads(raw_sky_shield)
    del broken["product_characteristics"]["metrics"]["cloud_cover_percentage"]

    with pytest.raises(ParsingError):
        parse_sky_is_no_limit(json.dumps(broken))


def test_invalid_json_raises_parsing_error() -> None:
    with pytest.raises(ParsingError):
        parse_sky_is_no_limit("{not valid json")


def test_cloud_cover_out_of_range_raises_value_error(raw_sky_shield: str) -> None:
    import json

    broken = json.loads(raw_sky_shield)
    broken["product_characteristics"]["metrics"]["cloud_cover_percentage"] = 142.0

    with pytest.raises(ValueError):
        parse_sky_is_no_limit(json.dumps(broken))
