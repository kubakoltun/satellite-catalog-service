from enum import Enum


class Mission(str, Enum):
    """Missions supported by the catalog

    Each enum value corresponds to the name of a STAC Collection
    containing Items for that mission. The `collection` field of
    the resulting STAC Item will contain one of these values.
    """

    SKY_SHIELD = "SKY_SHIELD"
    SPACE_EYE = "SPACE_EYE"
