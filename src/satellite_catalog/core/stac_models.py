"""Model domenowy STAC Item.

Celowo NIE trzymamy tu klasy domenowej innej niż `dict` - STAC Item to
z definicji dokument GeoJSON, a `stac-pydantic` daje nam gotową, zgodną ze
specyfikacją walidację (`validate_stac_item`). Zamiast pisać własną warstwę
encji domenowej, wykorzystujemy `Item` z tej biblioteki jako "wyrocznię"
poprawności - parser buduje zwykły dict (żeby był trywialny do testowania
i logowania), a walidacja jest osobnym, jawnym krokiem.

To jest miejsce, w którym w przyszłości (Krok 2) repozytorium pgSTAC
będzie oczekiwać danych wejściowych - kontrakt parserów kończy się tutaj.
"""

from __future__ import annotations

from typing import Any

from stac_pydantic import Item

STAC_VERSION = "1.0.0"

# Typ dla czytelności sygnatur - STAC Item to zwykły dict zgodny ze schematem GeoJSON Feature.
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
    """Składa surowy dict STAC Item z gotowych już fragmentów.

    Funkcja jest celowo "głupia" - nie zna specyfiki żadnego dostawcy,
    tylko układa podane części w kształt zgodny ze STAC. Cała wiedza
    o tym, *skąd* wziąć poszczególne wartości, żyje w parserach
    (`ingestion/parsers/*`), nie tutaj.
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
    """Waliduje dict względem specyfikacji STAC 1.0.0 (przez stac-pydantic).

    Zwraca ten sam dict bez zmian, jeśli jest poprawny - podnosi
    `pydantic.ValidationError` w przeciwnym razie. Rozdzielenie budowy
    (`build_stac_item`) od walidacji jest świadome: parser zawsze
    produkuje *jakiś* dict, nawet gdy dane wejściowe są wątpliwe, a to
    właśnie walidacja decyduje, czy trafi on dalej, czy do dead-letter.
    """
    Item.model_validate(item)
    return item
