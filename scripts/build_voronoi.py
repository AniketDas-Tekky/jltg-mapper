#!/usr/bin/env python3
"""Build per-POI Voronoi / nearest-region layers, clipped to the SF border.

For each proximity-based POI layer in ``data/`` we compute the Voronoi diagram
of its points (``shapely.ops.voronoi_diagram``) and clip every cell to the SF
border. Each cell is tagged with the POI it belongs to, so the deduction engine
can answer:

* **Matching** "is your nearest X the same as mine?" — a zone is consistent with
  *Yes* if it intersects the seeker's POI cell, *No* otherwise.
* **Measuring** "nearest X" — find the cell, then the point.

The diagram is built in **EPSG:26910** (metric) for a faithful equidistant
partition, then reprojected to WGS84. Output: one
``data/generated/voronoi/<layer>.geojson`` per layer.

Layers that are *not* proximity-based are skipped (parking-permit zones use the
polygon map directly; photo questions are not auto-deduced) — see
``docs/data-pipeline.md`` step 3.

Run (standalone)::

    uv run --with shapely,pyproj python scripts/build_voronoi.py

Requires ``data/generated/sf-border.geojson`` (run build_border.py first).
Deterministic + idempotent.
"""
from __future__ import annotations

import json
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import MultiPoint, Point, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, voronoi_diagram

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
GEN_DIR = DATA_DIR / "generated"
BORDER_PATH = GEN_DIR / "sf-border.geojson"
OUT_DIR = GEN_DIR / "voronoi"

# Proximity-based POI layers that get a nearest-region partition. Excludes
# parking-permit zones (polygon map) and any non-geojson / photo-only data.
PROXIMITY_LAYERS = [
    "rail-stations",
    "mountains",
    "dog-parks",
    "aquariums",
    "golf-courses",
    "museums",
    "movie-theaters",
    "libraries",
    "hospitals",
    "consulates",
    "farmers-markets",
]

_TO_UTM = Transformer.from_crs("EPSG:4326", "EPSG:26910", always_xy=True)
_TO_WGS = Transformer.from_crs("EPSG:26910", "EPSG:4326", always_xy=True)


def _to_utm(geom: BaseGeometry) -> BaseGeometry:
    return transform(_TO_UTM.transform, geom)


def _to_wgs(geom: BaseGeometry) -> BaseGeometry:
    return transform(_TO_WGS.transform, geom)


def load_border_utm() -> BaseGeometry:
    if not BORDER_PATH.exists():
        raise SystemExit(
            f"missing {BORDER_PATH} — run scripts/build_border.py first"
        )
    fc = json.loads(BORDER_PATH.read_text())
    geom = shape(fc["features"][0]["geometry"])
    if not geom.is_valid:
        geom = geom.buffer(0)
    return _to_utm(geom)


def build_layer(layer: str, border_utm: BaseGeometry) -> dict | None:
    src = DATA_DIR / f"{layer}.geojson"
    if not src.exists():
        print(f"  skip {layer}: no source file")
        return None

    fc = json.loads(src.read_text())
    feats = fc["features"]
    if not feats:
        print(f"  skip {layer}: no features")
        return None

    # Project points to metric, remembering each point's properties.
    pts_utm: list[Point] = []
    props_by_xy: dict[tuple[float, float], dict] = {}
    for feat in feats:
        lon, lat = feat["geometry"]["coordinates"]
        p = _to_utm(Point(lon, lat))
        pts_utm.append(p)
        props_by_xy[(round(p.x, 3), round(p.y, 3))] = feat.get("properties", {})

    # Voronoi needs an envelope at least as large as the clip region.
    envelope = border_utm.envelope.buffer(2000)
    diagram = voronoi_diagram(MultiPoint(pts_utm), envelope=envelope)

    out_features: list[dict] = []
    for cell in diagram.geoms:
        clipped = cell.intersection(border_utm)
        if clipped.is_empty:
            continue
        if not clipped.is_valid:
            clipped = clipped.buffer(0)

        # Match the cell back to its generating point (the only input point it
        # contains) so we can tag it with that POI's properties.
        owner = next((p for p in pts_utm if cell.covers(p)), None)
        props = (
            props_by_xy.get((round(owner.x, 3), round(owner.y, 3)), {})
            if owner is not None
            else {}
        )

        out_features.append(
            {
                "type": "Feature",
                "properties": dict(props),
                "geometry": mapping(_to_wgs(clipped)),
            }
        )

    return {
        "type": "FeatureCollection",
        "name": f"{layer} Voronoi (clipped to SF border)",
        "features": out_features,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    border_utm = load_border_utm()

    written = 0
    for layer in PROXIMITY_LAYERS:
        result = build_layer(layer, border_utm)
        if result is None:
            continue
        out = OUT_DIR / f"{layer}.geojson"
        out.write_text(json.dumps(result, indent=2) + "\n")
        print(f"  wrote {out.relative_to(REPO_ROOT)} ({len(result['features'])} cells)")
        written += 1

    print(f"wrote {written} voronoi layers to {OUT_DIR.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
