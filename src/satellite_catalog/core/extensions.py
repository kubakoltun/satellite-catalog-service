"""Builds STAC Item properties for standard STAC extensions

Each function returns a dictionary containing the properties defined by a
specific STAC extension. The returned fragments are ready to be merged into
the final STAC Item's properties object.

The module also defines the corresponding STAC extension schema URLs, which
must be included in the Item's `stac_extensions` field when the respective
properties are used.
"""

from __future__ import annotations

EO_EXTENSION = "https://stac-extensions.github.io/eo/v1.1.0/schema.json"
PROCESSING_EXTENSION = "https://stac-extensions.github.io/processing/v1.1.0/schema.json"
VIEW_EXTENSION = "https://stac-extensions.github.io/view/v1.0.0/schema.json"
SAT_EXTENSION = "https://stac-extensions.github.io/sat/v1.0.0/schema.json"


def eo_properties(cloud_cover_percent: float) -> dict:
    """Build properties for the STAC Electro-Optical (EO) extension

    `eo:cloud_cover` represents cloud coverage as a percentage in the
    range [0, 100]. The value is validated here so invalid input is
    rejected close to its source.
    """
    if not 0 <= cloud_cover_percent <= 100:
        raise ValueError(
            f"cloud_cover_percent beyond range [0, 100]: {cloud_cover_percent}"
        )
    return {"eo:cloud_cover": round(cloud_cover_percent, 2)}


def processing_properties(level: str) -> dict:
    """Build properties for the STAC Processing extension
    
    `processing:level` identifies the processing level of the item.
    The value must be a non-empty string.
    """
    if not level:
        raise ValueError("processing level must not be empty")
    return {"processing:level": level}


def view_properties(sun_azimuth_deg: float, sun_elevation_deg: float) -> dict:
    """Build properties for the STAC View Geometry extension
    
    Adds the sun azimuth and sun elevation angles associated with the item.
    Both values are expressed in degrees.
    """
    return {
        "view:sun_azimuth": round(sun_azimuth_deg, 2),
        "view:sun_elevation": round(sun_elevation_deg, 2),
    }


def sat_orbit_state(direction: str) -> dict:
    """Build properties for the STAC Satellite extension
    
    The orbit state must be: `ascending`, `descending`, or
    `geostationary`. The value is normalized to lowercase before being
    returned.
    """
    normalized = direction.lower()
    if normalized not in {"ascending", "descending", "geostationary"}:
        raise ValueError(f"Unknown orbit direction: {direction}")
    return {"sat:orbit_state": normalized}
