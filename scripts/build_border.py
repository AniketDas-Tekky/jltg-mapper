#!/usr/bin/env python3
"""Build the San Francisco playable border polygon.

Produces ``data/generated/sf-border.geojson`` — a single (multi)polygon of the
City & County of San Francisco *land* limits that count as in-play for the
Hide & Seek homebrew variant.

Per ``docs/data-pipeline.md`` / ``data/game-config.json``:

* **Include** the SF mainland peninsula and **Treasure Island**.
* **Exclude** rule-excluded areas so they can never be playable:
  - Daly City / Brisbane (zips 94015, 94014, 94005) — clipped off the south edge.
  - Alcatraz (federal land), the Farallon Islands, and the SF-owned slivers of
    Angel / Alameda Islands — these are simply not part of the embedded land
    geometry, so they are excluded by construction.

The land outline is embedded as a deterministic, network-free WGS84 polygon (a
moderate-resolution trace of the SF shoreline). Buffering / metric work that
needs an accurate radius is done in EPSG:26910 (UTM 10N) by build_hiding_zones;
this script only does WGS84 polygon algebra, then writes WGS84 GeoJSON.

Run (standalone, no project pollution)::

    uv run --with shapely,pyproj python scripts/build_border.py

Deterministic + idempotent: safe to re-run.
"""
from __future__ import annotations

import json
from pathlib import Path

from shapely.geometry import Polygon, mapping
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

# --- paths -----------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "data" / "generated"
OUT_PATH = OUT_DIR / "sf-border.geojson"

# --- SF mainland land outline (WGS84, lon/lat) -----------------------------
# A moderate-resolution trace of the San Francisco peninsula shoreline. The ring
# runs from the NW corner (Lands End), down the Pacific coast (Ocean Beach),
# across the southern city limit (the Daly City / Brisbane line at ~lat 37.708),
# up the bay shore (Hunters Point, the Embarcadero) and back along the northern
# waterfront (Marina, the Golden Gate at Lands End). Coordinates approximate the
# official City & County boundary closely enough for zone clipping; refine from
# SF Open Data if a higher-fidelity coastline is needed (see data-pipeline.md).
SF_MAINLAND = [
    (-122.5145, 37.7855),  # Lands End / NW
    (-122.5097, 37.7806),
    (-122.5089, 37.7710),  # Ocean Beach (Pacific) north
    (-122.5096, 37.7600),
    (-122.5098, 37.7480),
    (-122.5085, 37.7350),
    (-122.5060, 37.7240),  # Fort Funston / SW corner
    (-122.4960, 37.7130),  # southern city limit (Daly City line) — SW
    (-122.4700, 37.7085),
    (-122.4540, 37.7080),
    (-122.4350, 37.7082),
    (-122.4180, 37.7085),
    (-122.4050, 37.7088),  # southern city limit — SE (Brisbane line)
    (-122.3950, 37.7120),
    (-122.3870, 37.7210),  # Candlestick Point
    (-122.3780, 37.7290),
    (-122.3760, 37.7380),  # Hunters Point
    (-122.3700, 37.7400),
    (-122.3640, 37.7470),  # India Basin
    (-122.3770, 37.7560),
    (-122.3860, 37.7620),
    (-122.3870, 37.7680),  # Islais Creek / Pier 80
    (-122.3870, 37.7770),  # Mission Bay
    (-122.3870, 37.7860),  # Oracle Park / China Basin
    (-122.3865, 37.7930),  # Bay Bridge approach
    (-122.3905, 37.7990),  # Ferry Building / Embarcadero
    (-122.3960, 37.8060),
    (-122.4030, 37.8090),  # Pier 39 / Fisherman's Wharf
    (-122.4170, 37.8095),
    (-122.4280, 37.8085),  # Aquatic Park
    (-122.4380, 37.8075),  # Fort Mason
    (-122.4470, 37.8085),  # Marina Green
    (-122.4610, 37.8090),  # Crissy Field
    (-122.4730, 37.8110),  # Fort Point / Golden Gate
    (-122.4780, 37.8095),
    (-122.4870, 37.8030),  # Lincoln Park bluffs
    (-122.5060, 37.7900),  # Lands End approach
    (-122.5145, 37.7855),  # close ring
]

# Treasure Island + Yerba Buena Island (in-play island in the bay).
TREASURE_ISLAND = [
    (-122.3760, 37.8090),
    (-122.3700, 37.8240),
    (-122.3640, 37.8290),
    (-122.3580, 37.8260),
    (-122.3590, 37.8180),
    (-122.3640, 37.8090),
    (-122.3690, 37.8030),  # Yerba Buena Island
    (-122.3730, 37.8050),
    (-122.3760, 37.8090),
]

# Southern clip: anything south of the SF / Daly City limit is excluded
# regardless of the outline (defence-in-depth for the 94015/94014/94005 zips).
SOUTH_LIMIT_LAT = 37.7080


def build_border() -> BaseGeometry:
    mainland = Polygon(SF_MAINLAND)
    ti = Polygon(TREASURE_ISLAND)

    border = unary_union([mainland, ti])

    # Clip off everything south of the Daly City / Brisbane limit.
    clip = Polygon(
        [
            (-122.6, SOUTH_LIMIT_LAT),
            (-122.3, SOUTH_LIMIT_LAT),
            (-122.3, 37.95),
            (-122.6, 37.95),
            (-122.6, SOUTH_LIMIT_LAT),
        ]
    )
    border = border.intersection(clip)

    if not border.is_valid:
        border = border.buffer(0)
    return border


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    border = build_border()

    if border.is_empty:
        raise SystemExit("border geometry is empty — check the embedded outline")
    if not border.is_valid:
        raise SystemExit("border geometry is invalid after buffer(0)")

    feature = {
        "type": "Feature",
        "properties": {
            "name": "San Francisco playable border",
            "definition": "City & County of SF land limits, incl. Treasure Island",
            "excludes": [
                "Daly City / Brisbane (zips 94015, 94014, 94005)",
                "Alcatraz",
                "Farallon Islands",
                "Angel / Alameda Island SF slivers",
            ],
        },
        "geometry": mapping(border),
    }
    fc = {"type": "FeatureCollection", "name": "SF border", "features": [feature]}

    OUT_PATH.write_text(json.dumps(fc, indent=2) + "\n")
    print(f"wrote {OUT_PATH.relative_to(REPO_ROOT)} ({border.geom_type})")


if __name__ == "__main__":
    main()
