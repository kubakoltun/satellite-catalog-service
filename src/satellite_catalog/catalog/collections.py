"""Definicje STAC Collection dla obsługiwanych misji.

pgSTAC wymaga, żeby Collection istniała w bazie zanim wstawisz do niej
jakikolwiek Item (klucz obcy `collection` w tabeli items). Te dwie
kolekcje są statyczne (znamy je już teraz - SKY_SHIELD, SPACE_EYE),
więc nie ma potrzeby dynamicznego tworzenia kolekcji "w locie" przy
ingestion - są rejestrowane raz, jawnie, przy starcie aplikacji.

Zasięg przestrzenny/czasowy kolekcji celowo jest maksymalnie szeroki
([-180,-90,180,90], interval [None, None]) - kolekcja reprezentuje całą
misję, nie pojedynczą scenę, a jej faktyczny zasięg rośnie z każdym
zaingestowanym Itemem. Zawężanie go teraz "na sztywno" byłoby fałszywą
precyzją.
"""

from __future__ import annotations

from stac_pydantic import Collection

from satellite_catalog.core.mission import Mission
from satellite_catalog.core.stac_models import STAC_VERSION

_FULL_EXTENT = {
    "spatial": {"bbox": [[-180.0, -90.0, 180.0, 90.0]]},
    "temporal": {"interval": [[None, None]]},
}

_MISSION_METADATA: dict[Mission, dict[str, str]] = {
    Mission.SKY_SHIELD: {
        "title": "SKY_SHIELD",
        "description": (
            "Zobrazowania optyczne wielospektralne z misji SKY_SHIELD, "
            "dostarczane przez SkyIsNoLimit."
        ),
    },
    Mission.SPACE_EYE: {
        "title": "SPACE_EYE",
        "description": (
            "Zobrazowania z misji SPACE_EYE, dostarczane przez SpaceIsNoLimit."
        ),
    },
}


def build_collection(mission: Mission) -> dict:
    """Buduje i waliduje STAC Collection dla podanej misji."""
    meta = _MISSION_METADATA[mission]

    collection = {
        "type": "Collection",
        "stac_version": STAC_VERSION,
        "id": mission.value,
        "title": meta["title"],
        "description": meta["description"],
        "license": "proprietary",
        "extent": _FULL_EXTENT,
        "links": [],
    }

    Collection.model_validate(collection)  # rzuci przy niezgodności ze spec
    return collection


def default_collections() -> list[dict]:
    """Wszystkie kolekcje, które muszą istnieć w katalogu przy starcie aplikacji."""
    return [build_collection(mission) for mission in Mission]
