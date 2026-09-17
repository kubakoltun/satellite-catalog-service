"""Budowa właściwości ze standardowych rozszerzeń STAC.

Każda funkcja zwraca fragment `properties` (dict) gotowy do zmergowania
do finalnego Itemu, oraz odpowiadający jej URL schematu rozszerzenia do
wpisania w `stac_extensions`. Trzymanie tego razem (property + URL schematu)
zapobiega sytuacji, w której property jest ustawione, a rozszerzenie nie
zadeklarowane w `stac_extensions` (albo odwrotnie) - częsty błąd przy ręcznym
budowaniu Itemów.
"""

from __future__ import annotations

EO_EXTENSION = "https://stac-extensions.github.io/eo/v1.1.0/schema.json"
PROCESSING_EXTENSION = "https://stac-extensions.github.io/processing/v1.1.0/schema.json"
VIEW_EXTENSION = "https://stac-extensions.github.io/view/v1.0.0/schema.json"
SAT_EXTENSION = "https://stac-extensions.github.io/sat/v1.0.0/schema.json"


def eo_properties(cloud_cover_percent: float) -> dict:
    """Rozszerzenie Electro-Optical - wymagane przez zadanie.

    `eo:cloud_cover` w spec STAC to liczba 0-100 (procent), więc walidujemy
    zakres tu, a nie dopiero przy zapisie do bazy - błąd danych źródłowych
    ma być wykryty jak najbliżej miejsca, gdzie powstaje.
    """
    if not 0 <= cloud_cover_percent <= 100:
        raise ValueError(
            f"cloud_cover_percent poza zakresem [0, 100]: {cloud_cover_percent}"
        )
    return {"eo:cloud_cover": round(cloud_cover_percent, 2)}


def processing_properties(level: str) -> dict:
    """Rozszerzenie Processing - wymagane przez zadanie."""
    if not level:
        raise ValueError("processing level nie może być puste")
    return {"processing:level": level}


def view_properties(sun_azimuth_deg: float, sun_elevation_deg: float) -> dict:
    """Rozszerzenie View Geometry - opcjonalne, ale dane są dostępne wprost
    w metadanych SKY_SHIELD, więc szkoda by się zmarnowały."""
    return {
        "view:sun_azimuth": round(sun_azimuth_deg, 2),
        "view:sun_elevation": round(sun_elevation_deg, 2),
    }


def sat_orbit_state(direction: str) -> dict:
    """Rozszerzenie Satellite - kierunek orbity (ascending/descending)."""
    normalized = direction.lower()
    if normalized not in {"ascending", "descending", "geostationary"}:
        raise ValueError(f"Nieznany kierunek orbity: {direction}")
    return {"sat:orbit_state": normalized}
