class IngestionError(Exception):
    """Base exception for every erros of ingestion layer."""


class UnsupportedMissionError(IngestionError):
    """No registered parser for given mission."""


class ParsingError(IngestionError):
    """Raw data could not be mapped to a STAC Item

    I use `ParsingError` for problems that occur while reading or extracting
    fields from raw data, such as a missing XML node or path.

    This differs from `ValidationError` from `stac-pydantic`, which indicates
    that the resulting STAC Item does not conform to the STAC specification.
    Validation is handled by `stac_models.validate_stac_item`.
    """
