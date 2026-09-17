from enum import Enum


class Mission(str, Enum):
    """Misje obsługiwane przez katalog.

    Wartość enuma = nazwa kolekcji STAC, do której trafiają Itemy tej misji
    (`collection` w wynikowym STAC Item odpowiada wprost tej wartości).
    """

    SKY_SHIELD = "SKY_SHIELD"
    SPACE_EYE = "SPACE_EYE"
