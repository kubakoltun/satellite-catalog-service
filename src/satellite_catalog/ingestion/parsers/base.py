"""Parser Contract

Every provider has its own implementation of this protocol. The
`registry.py` module will select the appropriate implementation based
on the `Mission`, while `ingestion/service.py` will use only this
protocol and will not know anything about JSON or XML.
"""

from typing import Protocol

from satellite_catalog.core.mission import Mission
from satellite_catalog.core.stac_models import STACItemDict


class ParserPort(Protocol):
    mission: Mission

    def parse(self, raw: bytes) -> STACItemDict:
        """Turns raw bytes (JSON or XML) into a validated STAC Item

        Raises `ingestion.errors.ParsingError` when the input data are
        structurally invalid (e.g. required fields are missing), and
        `pydantic.ValidationError` when the resulting Item does not conform
        to the STAC specification.
        """
        ...
