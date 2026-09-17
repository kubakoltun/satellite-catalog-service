"""Rejestr parserów - mapuje `Mission` na implementację `ParserPort`.

To jest jedyne miejsce w kodzie, które "wie", że istnieją dwaj różni
dostawcy. `ingestion/service.py` (Krok 4) będzie pytał wyłącznie ten
rejestr - nigdy nie zobaczy `if mission == Mission.SKY_SHIELD`.
Dodanie trzeciego dostawcy to nowy wpis tutaj + nowy plik parsera,
zero zmian gdziekolwiek indziej.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from satellite_catalog.core.mission import Mission
from satellite_catalog.core.stac_models import STACItemDict
from satellite_catalog.ingestion.errors import UnsupportedMissionError
from satellite_catalog.ingestion.parsers.sky_shield_json import parse_sky_shield
from satellite_catalog.ingestion.parsers.space_eye_xml import parse_space_eye


@dataclass(frozen=True)
class _ParserEntry:
    mission: Mission
    parse: Callable[[bytes | str], STACItemDict]


_REGISTRY: dict[Mission, _ParserEntry] = {
    Mission.SKY_SHIELD: _ParserEntry(Mission.SKY_SHIELD, parse_sky_shield),
    Mission.SPACE_EYE: _ParserEntry(Mission.SPACE_EYE, parse_space_eye),
}


def get_parser(mission: Mission) -> Callable[[bytes | str], STACItemDict]:
    """Zwraca funkcję parsującą dla podanej misji.

    Podnosi `UnsupportedMissionError`, jeśli nikt się dla tej misji
    nie zarejestrował - to ma być jawny, czytelny błąd 4xx na warstwie
    API (Krok 4), nie KeyError gdzieś w głębi stosu.
    """
    entry = _REGISTRY.get(mission)
    if entry is None:
        raise UnsupportedMissionError(f"Brak parsera dla misji: {mission}")
    return entry.parse
