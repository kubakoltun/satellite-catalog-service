"""STAC Collection definitions for operated missions.

pgSTAC requires created Collection in the database before inserting any Item (FK of 'collection' table).
Therefore, I am inserting a two static collections - known two missions: SKY_SHIELD, SPACE_EYE.
The assumption is that I will always know about the mission ahead of time. So there is no need to create
the collections dynamically. 

Range of the spatial-temporal extent is intentionally broad:
([-180, -90, 180, 90], interval [None, None]).

The Collection represents the entire mission, it's actual extent depends on the
Items ingested into it. It may expand as new Items are added.

At application startup, the exact extent is not yet known. Using a narrower extent
would imply having specific information about the range. Therefore, the Collection
metadata would give a false sense of precision. The extent is updated as Items are ingested.
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
            "Multispectral optical imagery from the SKY_SHIELD mission, provided by SkyIsNoLimit."
        ),
    },
    Mission.SPACE_EYE: {
        "title": "SPACE_EYE",
        "description": (
            "Imagery from the SPACE_EYE mission, provided by SpaceIsNoLimit."
        ),
    },
}


def build_collection(mission: Mission) -> dict:
    """Building a validating a STAC Collection for given mission."""
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

    Collection.model_validate(collection)  # throws if it does not match the spec
    return collection


def default_collections() -> list[dict]:
    """Every collections that need to exist in the catalog on app start-up."""
    return [build_collection(mission) for mission in Mission]
