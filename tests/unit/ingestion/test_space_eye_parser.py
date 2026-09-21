from pathlib import Path

import pytest

from satellite_catalog.ingestion.errors import ParsingError
from satellite_catalog.ingestion.parsers.space_is_no_limit import parse_space_is_no_limit

FIXTURE = Path(__file__).parents[2] / "fixtures" / "space_eye_sample.xml"


@pytest.fixture
def raw_space_eye() -> str:
    return FIXTURE.read_text()


def test_parses_id_and_collection(raw_space_eye: str) -> None:
    item = parse_space_is_no_limit(raw_space_eye)

    assert item["id"] == "SE02_L2A_20260824T104500_N001"
    assert item["collection"] == "SPACE_EYE"


def test_geometry_is_reprojected_to_wgs84(raw_space_eye: str) -> None:
    # Źródłowy FootprintWKT jest w EPSG:32634 (UTM 34N) - po reprojekcji
    # współrzędne muszą być w rozsądnym zakresie stopni geograficznych,
    # nie w metrach UTM (rząd wielkości 10^5-10^6).
    item = parse_space_is_no_limit(raw_space_eye)

    lons = [pt[0] for pt in item["geometry"]["coordinates"][0]]
    lats = [pt[1] for pt in item["geometry"]["coordinates"][0]]

    assert all(-180 <= lon <= 180 for lon in lons)
    assert all(-90 <= lat <= 90 for lat in lats)
    # centralny południk strefy UTM 34N to 21E - narożnik przy x=500000
    # (false easting) powinien wypaść dokładnie na 21.0E
    assert any(lon == pytest.approx(21.0, abs=1e-6) for lon in lons)


def test_bbox_is_derived_from_reprojected_geometry_not_global_bbox(
    raw_space_eye: str,
) -> None:
    # W tej próbce GlobalBBOX celowo NIE zgadza się z FootprintWKT
    # (patrz _warn_if_global_bbox_inconsistent) - upewniamy się, że
    # parser trzyma się geometrii jako źródła prawdy, a nie cichutko
    # podmienia bbox na to, co podał dostawca w GlobalBBOX.
    item = parse_space_is_no_limit(raw_space_eye)

    assert item["bbox"][0] == pytest.approx(21.0, abs=1e-3)
    assert item["bbox"] != [19.981, 51.355, 21.615, 52.342]


def test_inconsistent_global_bbox_logs_warning_but_does_not_raise(
    raw_space_eye: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("WARNING"):
        parse_space_is_no_limit(raw_space_eye)

    assert any("GlobalBBOX" in record.message for record in caplog.records)


def test_time_interval_maps_to_start_end_datetime_not_datetime(
    raw_space_eye: str,
) -> None:
    item = parse_space_is_no_limit(raw_space_eye)
    props = item["properties"]

    assert props["datetime"] is None
    assert props["start_datetime"] == "2026-08-24T10:45:00Z"
    assert props["end_datetime"] == "2026-08-24T10:45:18Z"


def test_maps_eo_and_processing_extensions(raw_space_eye: str) -> None:
    item = parse_space_is_no_limit(raw_space_eye)
    props = item["properties"]

    assert props["eo:cloud_cover"] == 4.85
    assert props["processing:level"] == "L2A"


def test_keeps_data_quality_status_as_custom_property(raw_space_eye: str) -> None:
    item = parse_space_is_no_limit(raw_space_eye)
    assert item["properties"]["spaceisnolimit:data_quality_status"] == "PASSED"


def test_assets_include_bands_and_overview(raw_space_eye: str) -> None:
    item = parse_space_is_no_limit(raw_space_eye)

    assert set(item["assets"].keys()) == {"b04_red", "b08_nir", "overview"}
    assert item["assets"]["b04_red"]["href"].startswith("s3://")
    assert item["assets"]["b04_red"]["gsd"] == 10.0
    assert item["assets"]["overview"]["roles"] == ["thumbnail"]


def test_missing_required_field_raises_parsing_error(raw_space_eye: str) -> None:
    broken = raw_space_eye.replace(
        "<GranuleID>SE02_L2A_20260824T104500_N001</GranuleID>", ""
    )

    with pytest.raises(ParsingError):
        parse_space_is_no_limit(broken)


def test_invalid_xml_raises_parsing_error() -> None:
    with pytest.raises(ParsingError):
        parse_space_is_no_limit("<not><valid")


def test_invalid_wkt_raises_parsing_error(raw_space_eye: str) -> None:
    broken = raw_space_eye.replace(
        "POLYGON((500000 5800000, 609780 5800000, 609780 5690220, "
        "500000 5690220, 500000 5800000))",
        "NOT A WKT",
    )

    with pytest.raises(ParsingError):
        parse_space_is_no_limit(broken)
