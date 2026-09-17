class IngestionError(Exception):
    """Bazowy wyjątek dla wszystkich błędów warstwy ingestion."""


class UnsupportedMissionError(IngestionError):
    """Brak zarejestrowanego parsera dla podanej misji."""


class ParsingError(IngestionError):
    """Surowe dane nie dają się poprawnie zmapować na STAC Item.

    Odróżniamy to od `ValidationError` z pydantic/stac-pydantic - tu
    chodzi o problem na etapie odczytu/ekstrakcji pól z surowych danych
    (np. brakujący węzeł XML), nie o niezgodność wynikowego Itemu ze
    specyfikacją STAC (to zgłasza już `stac_models.validate_stac_item`).
    """
