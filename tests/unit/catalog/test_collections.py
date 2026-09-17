from satellite_catalog.catalog.collections import build_collection, default_collections
from satellite_catalog.core.mission import Mission


def test_default_collections_cover_both_missions():
    collections = default_collections()
    ids = {c["id"] for c in collections}

    assert ids == {"SKY_SHIELD", "SPACE_EYE"}


def test_collection_is_valid_stac_collection():
    # build_collection() waliduje wewnętrznie (stac_pydantic.Collection) -
    # brak wyjątku oznacza, że kolekcja jest zgodna ze specyfikacją.
    collection = build_collection(Mission.SKY_SHIELD)

    assert collection["type"] == "Collection"
    assert collection["id"] == "SKY_SHIELD"
    assert collection["extent"]["spatial"]["bbox"] == [[-180.0, -90.0, 180.0, 90.0]]
