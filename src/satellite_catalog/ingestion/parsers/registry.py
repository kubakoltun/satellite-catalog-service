"""Parsers registry - maps `Mission` to a `ParserPort` implementation

This is the only place that "knows" about the different providers.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from satellite_catalog.core.mission import Mission
from satellite_catalog.core.stac_models import STACItemDict
from satellite_catalog.ingestion.errors import UnsupportedMissionError
from satellite_catalog.ingestion.parsers.sky_is_no_limit import parse_sky_is_no_limit
from satellite_catalog.ingestion.parsers.space_is_no_limit import parse_space_is_no_limit


@dataclass(frozen=True)
class _ParserEntry:
    mission: Mission
    parse: Callable[[bytes | str], STACItemDict]


_REGISTRY: dict[Mission, _ParserEntry] = {
    Mission.SKY_SHIELD: _ParserEntry(Mission.SKY_SHIELD, parse_sky_is_no_limit),
    Mission.SPACE_EYE: _ParserEntry(Mission.SPACE_EYE, parse_space_is_no_limit),
}


def get_parser(mission: Mission) -> Callable[[bytes | str], STACItemDict]:
    """Returns a parsing function for the given mission

    Raises `UnsupportedMissionError` if no parser is registered
    for the given mission. This allows the API layer to return
    a clear 4xx error.
    """
    entry = _REGISTRY.get(mission)
    if entry is None:
        raise UnsupportedMissionError(f"No parser for mission: {mission}")
    return entry.parse
