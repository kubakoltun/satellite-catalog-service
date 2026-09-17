import pytest

from satellite_catalog.catalog.search import (
    SearchFilters,
    build_pgstac_search_body,
    parse_bbox_param,
    parse_collections_param,
    validate_datetime_param,
)


def test_parse_bbox_param_valid():
    assert parse_bbox_param("20.912,52.185,21.245,52.398") == (20.912, 52.185, 21.245, 52.398)


def test_parse_bbox_param_none_when_missing():
    assert parse_bbox_param(None) is None


@pytest.mark.parametrize(
    "bbox",
    [
        "20.912,52.185,21.245",  # za mało wartości
        "a,52.185,21.245,52.398",  # nie liczba
        "21.245,52.185,20.912,52.398",  # minLon > maxLon
    ],
)
def test_parse_bbox_param_rejects_invalid_input(bbox: str):
    with pytest.raises(ValueError):
        parse_bbox_param(bbox)


def test_parse_collections_param_splits_and_trims():
    assert parse_collections_param("SKY_SHIELD, SPACE_EYE") == ("SKY_SHIELD", "SPACE_EYE")


def test_parse_collections_param_none_when_missing():
    assert parse_collections_param(None) is None


def test_validate_datetime_param_accepts_single_instant():
    value = "2026-08-24T09:15:22.451Z"
    assert validate_datetime_param(value) == value


def test_validate_datetime_param_accepts_interval():
    value = "2026-08-01T00:00:00Z/2026-09-01T00:00:00Z"
    assert validate_datetime_param(value) == value


def test_validate_datetime_param_accepts_open_ended_interval():
    value = "../2026-09-01T00:00:00Z"
    assert validate_datetime_param(value) == value


def test_validate_datetime_param_none_when_missing():
    assert validate_datetime_param(None) is None


@pytest.mark.parametrize(
    "value",
    ["not-a-date", "2026-13-99T00:00:00Z", "2026-08-01/2026-09-01/2026-10-01"],
)
def test_validate_datetime_param_rejects_invalid_input(value: str):
    with pytest.raises(ValueError):
        validate_datetime_param(value)


def test_build_pgstac_search_body_minimal():
    body = build_pgstac_search_body(SearchFilters(limit=10))
    assert body == {"limit": 10}


def test_build_pgstac_search_body_with_all_filters():
    filters = SearchFilters(
        bbox=(20.9, 52.1, 21.3, 52.4),
        datetime="2026-08-01T00:00:00Z/2026-09-01T00:00:00Z",
        collections=("SKY_SHIELD", "SPACE_EYE"),
        max_cloud_cover=20.0,
        processing_level="L2A",
        limit=5,
    )

    body = build_pgstac_search_body(filters)

    assert body == {
        "limit": 5,
        "bbox": [20.9, 52.1, 21.3, 52.4],
        "datetime": "2026-08-01T00:00:00Z/2026-09-01T00:00:00Z",
        "collections": ["SKY_SHIELD", "SPACE_EYE"],
        "query": {
            "eo:cloud_cover": {"lte": 20.0},
            "processing:level": {"eq": "L2A"},
        },
    }


def test_build_pgstac_search_body_omits_absent_filters():
    body = build_pgstac_search_body(SearchFilters(max_cloud_cover=15.0, limit=10))
    assert body == {"limit": 10, "query": {"eo:cloud_cover": {"lte": 15.0}}}
