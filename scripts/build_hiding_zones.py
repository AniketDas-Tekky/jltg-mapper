#!/usr/bin/env python3
"""Build the ¼-mile hiding-zone polygons, clipped to the SF border.

For each valid hiding station (``data/valid-hiding-stations.geojson``):

1. Buffer the station point by **¼ mile** (402.336 m). The buffer is computed in
   a metric CRS — **EPSG:26910** (NAD83 / UTM zone 10N) — for an accurate radius,
   then reprojected back to WGS84. We never buffer in degrees.
2. **Intersect** the buffer with the SF border polygon, so border-edge zones
   become semicircles (matching the rules' Bayshore example).
3. Carry the station's identifying properties (``name``, ``stopid``,
   ``primary_system``) into the zone, plus a stable ``zone_id`` so the deduction
   engine can map zone IDs back to stations.

Output: ``data/generated/hiding-zones.geojson`` — a FeatureCollection with one
polygon per input station.

Run (standalone)::

    uv run --with shapely,pyproj python scripts/build_hiding_zones.py

Requires ``data/generated/sf-border.geojson`` (run build_border.py first).
Deterministic + idempotent.
"""
from __future__ import annotations

import json
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import Point, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
GEN_DIR = DATA_DIR / "generated"
STATIONS_PATH = DATA_DIR / "valid-hiding-stations.geojson"
BORDER_PATH = GEN_DIR / "sf-border.geojson"
OUT_PATH = GEN_DIR / "hiding-zones.geojson"

QUARTER_MILE_M = 0.25 * 1609.344  # 402.336 m

# WGS84 (lon/lat) <-> NAD83 / UTM 10N (metres).
_TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:26910", always_xy=True)
_TO_WGS = Transformer.from_crs("EPSG:26910", "EPSG:4326", always_xy=True)


def _to_utm(geom: BaseGeometry) -> BaseGeometry:
    return transform(_TO_UTM.transform, geom)


def _to_wgs(geom: BaseGeometry) -> BaseGeometry:
    return transform(_TO_WGS.transform, geom)


def load_border() -> BaseGeometry:
    if not BORDER_PATH.exists():
        raise SystemExit(
            f"missing {BORDER_PATH} — run scripts/build_border.py first"
        )
    fc = json.loads(BORDER_PATH.read_text())
    geom = shape(fc["features"][0]["geometry"])
    if not geom.is_valid:
        geom = geom.buffer(0)
    return geom


def build_zones() -> list[dict]:
    stations = json.loads(STATIONS_PATH.read_text())
    border_utm = _to_utm(load_border())

    features: list[dict] = []
    unclipped: list[str] = []
    for idx, feat in enumerate(stations["features"]):
        lon, lat = feat["geometry"]["coordinates"]
        props = feat.get("properties", {})

        # Buffer in metric CRS, intersect with the border, back to WGS84.
        pt_utm = _to_utm(Point(lon, lat))
        buffer_utm = pt_utm.buffer(QUARTER_MILE_M, quad_segs=64)
        zone_utm = buffer_utm.intersection(border_utm)
        if zone_utm.is_empty:
            # The station sits outside the embedded moderate-resolution border
            # (e.g. a Treasure Island stop the rough outline misses). Keep the
            # full ¼-mi buffer so every station still has a zone, and flag it —
            # a higher-fidelity SF boundary (see data-pipeline.md) clips these
            # exactly. Better an unclipped zone than a missing candidate.
            zone_utm = buffer_utm
            unclipped.append(f"{idx} ({props.get('name')!r})")
        zone = _to_wgs(zone_utm)
        if not zone.is_valid:
            zone = zone.buffer(0)

        zone_props = {
            "zone_id": idx,
            "name": props.get("name"),
            "stopid": props.get("stopid"),
            "primary_system": props.get("primary_system"),
        }
        features.append(
            {
                "type": "Feature",
                "properties": zone_props,
                "geometry": mapping(zone),
            }
        )
    if unclipped:
        print(
            f"  note: {len(unclipped)} station(s) fell outside the border and kept "
            f"a full (unclipped) ¼-mi buffer: {', '.join(unclipped)}"
        )
    return features


def main() -> None:
    GEN_DIR.mkdir(parents=True, exist_ok=True)
    features = build_zones()
    fc = {
        "type": "FeatureCollection",
        "name": "SF hiding zones (¼ mi, clipped to border)",
        "features": features,
    }
    OUT_PATH.write_text(json.dumps(fc, indent=2) + "\n")
    print(f"wrote {OUT_PATH.relative_to(REPO_ROOT)} ({len(features)} zones)")


if __name__ == "__main__":
    main()
