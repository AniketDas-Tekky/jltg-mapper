"""Validation tests for the geo-data pipeline outputs.

These build the assets in a temp copy of ``data/generated`` (via the build
modules' ``main``-equivalents writing to the real ``data/generated``) and assert
the structural / geometric invariants from ``docs/data-pipeline.md``.

Run::

    uv run --with shapely,pyproj,pytest pytest scripts/tests
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPTS_DIR.parent
DATA_DIR = REPO_ROOT / "data"
GEN_DIR = DATA_DIR / "generated"

sys.path.insert(0, str(SCRIPTS_DIR))

shape = pytest.importorskip("shapely.geometry").shape  # noqa: E402
import build_border  # noqa: E402
import build_hiding_zones  # noqa: E402
import build_voronoi  # noqa: E402

# SF bounding box (loose) for sanity-checking coordinates.
SF_BBOX = (-122.55, 37.70, -122.34, 37.84)


@pytest.fixture(scope="module", autouse=True)
def built_assets():
    """Build all assets once for the module."""
    build_border.main()
    build_hiding_zones.main()
    build_voronoi.main()
    yield


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _in_bbox(geom) -> bool:
    minx, miny, maxx, maxy = geom.bounds
    w, s, e, n = SF_BBOX
    return minx >= w and miny >= s and maxx <= e and maxy <= n


def test_border_valid_and_single():
    fc = _load(GEN_DIR / "sf-border.geojson")
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 1
    geom = shape(fc["features"][0]["geometry"])
    assert geom.is_valid
    assert not geom.is_empty
    assert geom.geom_type in ("Polygon", "MultiPolygon")


def test_border_includes_treasure_island():
    fc = _load(GEN_DIR / "sf-border.geojson")
    geom = shape(fc["features"][0]["geometry"])
    Point = pytest.importorskip("shapely.geometry").Point
    # A point on Treasure Island should be inside the border.
    assert geom.contains(Point(-122.3680, 37.8230))


def test_border_excludes_south_of_daly_city():
    fc = _load(GEN_DIR / "sf-border.geojson")
    geom = shape(fc["features"][0]["geometry"])
    Point = pytest.importorskip("shapely.geometry").Point
    # Well into Daly City (south of the 37.708 limit) must be excluded.
    assert not geom.contains(Point(-122.4700, 37.7000))


def test_hiding_zones_count_matches_stations():
    stations = _load(DATA_DIR / "valid-hiding-stations.geojson")
    zones = _load(GEN_DIR / "hiding-zones.geojson")
    assert len(zones["features"]) == len(stations["features"])


def test_hiding_zones_valid_nonempty_in_bbox():
    zones = _load(GEN_DIR / "hiding-zones.geojson")
    for feat in zones["features"]:
        geom = shape(feat["geometry"])
        assert geom.is_valid
        assert not geom.is_empty
        assert _in_bbox(geom)


def test_hiding_zones_carry_station_props():
    zones = _load(GEN_DIR / "hiding-zones.geojson")
    ids = {f["properties"]["zone_id"] for f in zones["features"]}
    assert len(ids) == len(zones["features"])  # unique ids
    for feat in zones["features"]:
        assert "name" in feat["properties"]
        assert "primary_system" in feat["properties"]


def test_edge_zones_clipped_inside_border():
    border = shape(_load(GEN_DIR / "sf-border.geojson")["features"][0]["geometry"])
    zones = _load(GEN_DIR / "hiding-zones.geojson")
    # Every zone must lie within the border (edge zones become semicircles).
    for feat in zones["features"]:
        geom = shape(feat["geometry"])
        # Allow a tiny floating-point overshoot from reprojection.
        assert geom.difference(border.buffer(1e-7)).area < 1e-9


def test_voronoi_layer_per_proximity_layer():
    out_dir = GEN_DIR / "voronoi"
    for layer in build_voronoi.PROXIMITY_LAYERS:
        src = DATA_DIR / f"{layer}.geojson"
        if not src.exists():
            continue
        out = out_dir / f"{layer}.geojson"
        assert out.exists(), f"missing voronoi output for {layer}"
        fc = _load(out)
        assert len(fc["features"]) >= 1
        for feat in fc["features"]:
            geom = shape(feat["geometry"])
            assert geom.is_valid
            assert not geom.is_empty
