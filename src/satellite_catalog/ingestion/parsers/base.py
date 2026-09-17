"""Kontrakt parsera - Strategy pattern.

Każdy dostawca ma swoją implementację tego protokołu. `registry.py` (Krok 4)
będzie dobierał właściwą implementację po `Mission`, a `ingestion/service.py`
będzie operował wyłącznie na tym protokole - nie będzie wiedział nic
o istnieniu JSON-a czy XML-a. To jest dokładnie ten "przełącznik" OCP,
o którym mówiliśmy przy projektowaniu architektury: nowy dostawca = nowa
implementacja tego protokołu, zero zmian gdzie indziej.
"""

from typing import Protocol

from satellite_catalog.core.mission import Mission
from satellite_catalog.core.stac_models import STACItemDict


class ParserPort(Protocol):
    mission: Mission

    def parse(self, raw: bytes) -> STACItemDict:
        """Zamienia surowe bajty (JSON albo XML - zależnie od dostawcy)
        na zwalidowany STAC Item.

        Podnosi `ingestion.errors.ParsingError` gdy dane wejściowe są
        strukturalnie niepoprawne (brakujące wymagane pola), oraz
        `pydantic.ValidationError` gdy wynikowy Item nie jest zgodny
        ze specyfikacją STAC.
        """
        ...
