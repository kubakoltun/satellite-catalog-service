"""Domain model for a STAC Item

Deliberately, I do not introduce a separate domain class here: a STAC Item
is a GeoJSON Feature, and `stac-pydantic` provides ready-made validation
(`validate_stac_item`). Instead of introducing my own domain entity layer,
I am using `Item` from the library as the validation authority.
The parser builds a regular Python dictionary so that it is easy to test
and log, while validation remains a separate, explicit step.
"""

from __future__ import annotations

from typing import Any

from stac_pydantic import Item

STAC_VERSION = "1.0.0"

# Readability type alias - a STAC Item is a regular dict
# conforming to the GeoJSON Feature structure
STACItemDict = dict[str, Any]


def build_stac_item(
    *,
    item_id: str,
    collection: str,
    geometry: dict,
    bbox: tuple[float, float, float, float],
    properties: dict,
    assets: dict,
    stac_extensions: list[str],
) -> STACItemDict:
    """Build a raw STAC Item dictionary from the provided components

    The function is intentionally provider-agnostic: it does not contain
    any provider-specific logic and only assembles the supplied components
    into a structure conforming to the STAC specification.
    """
    return {
        "type": "Feature",
        "stac_version": STAC_VERSION,
        "id": item_id,
        "collection": collection,
        "geometry": geometry,
        "bbox": list(bbox),
        "properties": properties,
        "assets": assets,
        "links": [],
        "stac_extensions": stac_extensions,
    }


def validate_stac_item(item: STACItemDict) -> STACItemDict:
    """Validate the dictionary against the STAC 1.0.0 specification\

    Returns the dictionary unchanged if validation succeeds.
    Raises `pydantic.ValidationError` if validation fails.

    Building (`build_stac_item`) and validation are intentionally separate:
    the parser always produces a dictionary, even when the input data is
    questionable. Validation determines whether the item continues through
    the pipeline or is sent to the dead-letter queue.
    """
    Item.model_validate(item)
    return item
