"""Geometric deduction engine for the JetLag hide-and-seek companion app.

This module implements the real :data:`~app.reducer.DeductionHook`: given the set of
hiding zones still in play plus a (question, answer) pair, it returns the subset of zones
that remain consistent with the answer.

Geometry source (all EPSG:4326 lon/lat):
  * ``data/generated/hiding-zones.geojson`` — 193 candidate hiding zones (``zone_id`` 0..192).
  * ``data/generated/voronoi/<layer>.geojson`` — one nearest-POI Voronoi partition per
    question layer (libraries, hospitals, rail-stations, …). Each feature is the cell of a
    single POI, tagged with ``properties.name``.

Distances must be in metres, but pyproj/geopandas are not dependencies. We project to a
local equirectangular plane anchored at the SF centroid; at city scale the error is well
under 1%, which is far below the resolution at which these predicates make decisions.

The hook is intentionally **fail-open**: any parsing/geometry error returns the input
unchanged so a malformed question can never break the event-sourced reducer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import geojson
from shapely import STRtree
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union

# Equirectangular projection anchor (SF centroid). A single shared anchor means every
# projected geometry lives in the same planar frame, so distances are comparable globally.
_ANCHOR_LAT = 37.7749
_ANCHOR_LON = -122.4194
_M_PER_DEG_LAT = 110540.0
_M_PER_DEG_LON = 111320.0 * math.cos(math.radians(_ANCHOR_LAT))

# Known Voronoi layers shipped in data/generated/voronoi. Layers absent on disk (e.g. the
# un-geocoded ``museums`` layer) are simply skipped — predicates referencing them no-op.
_VORONOI_LAYERS = (
    "aquariums",
    "consulates",
    "dog-parks",
    "farmers-markets",
    "golf-courses",
    "hospitals",
    "libraries",
    "mountains",
    "movie-theaters",
    "rail-stations",
)

# Maps a question subtype (or singular noun) to its Voronoi layer file stem.
_SUBTYPE_LAYER_ALIASES = {
    "aquarium": "aquariums",
    "consulate": "consulates",
    "dog_park": "dog-parks",
    "dogpark": "dog-parks",
    "park": "dog-parks",
    "farmers_market": "farmers-markets",
    "farmersmarket": "farmers-markets",
    "golf_course": "golf-courses",
    "golfcourse": "golf-courses",
    "golf": "golf-courses",
    "hospital": "hospitals",
    "library": "libraries",
    "mountain": "mountains",
    "hill": "mountains",
    "movie_theater": "movie-theaters",
    "theater": "movie-theaters",
    "cinema": "movie-theaters",
    "rail_station": "rail-stations",
    "railstation": "rail-stations",
    "station": "rail-stations",
    "rail": "rail-stations",
}


def _project(lon: float, lat: float) -> tuple[float, float]:
    """Project lon/lat degrees to metres on the shared equirectangular plane."""
    return (
        (lon - _ANCHOR_LON) * _M_PER_DEG_LON,
        (lat - _ANCHOR_LAT) * _M_PER_DEG_LAT,
    )


def _project_arrays(xs, ys, _z=None):
    """shapely.ops.transform callback: project parallel lon(x)/lat(y) coordinate arrays."""
    out_x = [(x - _ANCHOR_LON) * _M_PER_DEG_LON for x in xs]
    out_y = [(y - _ANCHOR_LAT) * _M_PER_DEG_LAT for y in ys]
    return out_x, out_y


def _to_metric(geom: BaseGeometry) -> BaseGeometry:
    """Project a lon/lat shapely geometry into the metric plane."""
    return transform(_project_arrays, geom)


def _point_metric(lat: float, lon: float):
    from shapely.geometry import Point

    return Point(_project(lon, lat))


def _find_repo_root() -> Path:
    """Walk upward from this file until the generated geo assets are found."""
    here = Path(__file__).resolve()
    for parent in (here, *here.parents):
        candidate = parent / "data" / "generated" / "hiding-zones.geojson"
        if candidate.exists():
            return parent
    # Fallback: two levels up from backend/app (repo root in the standard layout).
    return here.parents[2]


@dataclass(frozen=True)
class _Zone:
    zone_id: int
    polygon_lonlat: BaseGeometry
    polygon_metric: BaseGeometry
    rep_metric: Any  # representative point (metric), guaranteed inside the polygon


@dataclass
class GeoAssets:
    zones: list[_Zone]
    tree: STRtree
    tree_zone_ids: list[int]
    voronoi: dict[str, list[tuple[str, BaseGeometry]]] = field(default_factory=dict)

    def zone_ids(self) -> set[int]:
        return {z.zone_id for z in self.zones}


@lru_cache(maxsize=1)
def load_geo_assets() -> GeoAssets:
    """Load + project the hiding zones and Voronoi layers, building an STRtree. Cached."""
    root = _find_repo_root()
    gen = root / "data" / "generated"

    with (gen / "hiding-zones.geojson").open() as fh:
        hz = geojson.load(fh)

    zones: list[_Zone] = []
    for feat in hz["features"]:
        props = feat.get("properties") or {}
        zone_id = props.get("zone_id")
        if zone_id is None:
            continue
        poly = shape(feat["geometry"])
        poly_m = _to_metric(poly)
        rep_m = _to_metric(poly.representative_point())
        zones.append(_Zone(int(zone_id), poly, poly_m, rep_m))

    zones.sort(key=lambda z: z.zone_id)
    metric_polys = [z.polygon_metric for z in zones]
    tree = STRtree(metric_polys)
    tree_zone_ids = [z.zone_id for z in zones]

    voronoi: dict[str, list[tuple[str, BaseGeometry]]] = {}
    vdir = gen / "voronoi"
    for layer in _VORONOI_LAYERS:
        path = vdir / f"{layer}.geojson"
        if not path.exists():
            continue  # missing layer (e.g. museums) -> gracefully absent
        with path.open() as fh:
            fc = geojson.load(fh)
        cells: list[tuple[str, BaseGeometry]] = []
        for feat in fc["features"]:
            name = (feat.get("properties") or {}).get("name") or ""
            cells.append((str(name), _to_metric(shape(feat["geometry"]))))
        voronoi[layer] = cells

    return GeoAssets(zones=zones, tree=tree, tree_zone_ids=tree_zone_ids, voronoi=voronoi)


# --------------------------------------------------------------------------- param parsing


def _layer_for(subtype: str, params: dict[str, Any]) -> str | None:
    """Resolve the Voronoi layer name from explicit params or the question subtype."""
    explicit = params.get("layer")
    if isinstance(explicit, str) and explicit:
        return explicit
    s = (subtype or "").lower().strip()
    for prefix in ("nearest_", "same_", "matching_", "measuring_", "closest_"):
        if s.startswith(prefix):
            s = s[len(prefix) :]
            break
    if s in _VORONOI_LAYERS:
        return s
    return _SUBTYPE_LAYER_ALIASES.get(s)


def _radius_m(subtype: str, params: dict[str, Any]) -> float | None:
    """Resolve a radar radius in metres from params or a ``within_<n>(m|km)`` subtype."""
    for key in ("radius_m", "radius_metres", "radius_meters"):
        v = params.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    km = params.get("radius_km")
    if isinstance(km, (int, float)):
        return float(km) * 1000.0
    s = (subtype or "").lower()
    import re

    m = re.search(r"within[_-]?(\d+(?:\.\d+)?)(km|m)\b", s)
    if m:
        val = float(m.group(1))
        return val * 1000.0 if m.group(2) == "km" else val
    return None


def _bool_answer(answer: Any) -> bool | None:
    """Coerce an answer to True/False, or None if unrecognised (-> caller no-ops)."""
    if isinstance(answer, bool):
        return answer
    if isinstance(answer, str):
        a = answer.strip().lower()
        if a in ("true", "yes", "y", "same", "closer", "warmer", "hotter", "within"):
            return True
        if a in ("false", "no", "n", "different", "further", "farther", "colder", "outside"):
            return False
    return None


def _seeker_point(question_payload: dict[str, Any]):
    loc = question_payload.get("seeker_location") or {}
    return _point_metric(float(loc["lat"]), float(loc["lon"]))


def _latlon_point(d: dict[str, Any]):
    return _point_metric(float(d["lat"]), float(d["lon"]))


# --------------------------------------------------------------------------- predicates


def _cell_name_for(assets: GeoAssets, layer: str, point) -> str | None:
    """Name of the Voronoi cell (of ``layer``) containing ``point`` (metric)."""
    cells = assets.voronoi.get(layer)
    if not cells:
        return None
    for name, geom in cells:
        if geom.covers(point):
            return name
    # Point fell outside all cells (numerical edge): fall back to nearest cell.
    nearest = min(cells, key=lambda nc: nc[1].distance(point), default=None)
    return nearest[0] if nearest else None


def _matching(
    assets: GeoAssets, zones: list[_Zone], q: dict[str, Any], a: dict[str, Any]
) -> set[int]:
    layer = _layer_for(q.get("subtype", ""), q.get("params") or {})
    same = _bool_answer(a.get("answer"))
    if layer is None or layer not in assets.voronoi or same is None:
        return {z.zone_id for z in zones}  # missing layer / unknown answer -> no-op
    seeker_cell = _cell_name_for(assets, layer, _seeker_point(q))
    if seeker_cell is None:
        return {z.zone_id for z in zones}
    kept: set[int] = set()
    for z in zones:
        zone_cell = _cell_name_for(assets, layer, z.rep_metric)
        in_same = zone_cell == seeker_cell
        if in_same == same:
            kept.add(z.zone_id)
    return kept


def _poi_seeds(assets: GeoAssets, layer: str) -> list:
    """Representative points of each Voronoi cell — used as POI locations for measuring."""
    return [geom.representative_point() for _name, geom in assets.voronoi.get(layer, [])]


def _measuring(
    assets: GeoAssets, zones: list[_Zone], q: dict[str, Any], a: dict[str, Any]
) -> set[int]:
    params = q.get("params") or {}
    closer = _bool_answer(a.get("answer"))
    if closer is None:
        return {z.zone_id for z in zones}

    # POIs: an explicit point, or the seed points of the named layer's Voronoi cells.
    pois: list = []
    poi = params.get("poi")
    if isinstance(poi, dict) and "lat" in poi and "lon" in poi:
        pois = [_latlon_point(poi)]
    else:
        layer = _layer_for(q.get("subtype", ""), params)
        if layer is None or layer not in assets.voronoi:
            return {z.zone_id for z in zones}
        pois = _poi_seeds(assets, layer)
    if not pois:
        return {z.zone_id for z in zones}

    seeker = _seeker_point(q)
    seeker_dist = min(seeker.distance(p) for p in pois)
    kept: set[int] = set()
    for z in zones:
        zone_dist = min(z.rep_metric.distance(p) for p in pois)
        # Boundary-inclusive on both sides so a near-tie zone is never wrongly pruned.
        if (closer and zone_dist <= seeker_dist) or (not closer and zone_dist >= seeker_dist):
            kept.add(z.zone_id)
    return kept


def _radar(
    assets: GeoAssets, zones: list[_Zone], q: dict[str, Any], a: dict[str, Any]
) -> set[int]:
    radius = _radius_m(q.get("subtype", ""), q.get("params") or {})
    within = _bool_answer(a.get("answer"))
    if radius is None or within is None:
        return {z.zone_id for z in zones}
    seeker = _seeker_point(q)
    kept: set[int] = set()
    for z in zones:
        d = z.rep_metric.distance(seeker)
        if (within and d <= radius) or (not within and d > radius):
            kept.add(z.zone_id)
    return kept


def _thermometer(
    assets: GeoAssets, zones: list[_Zone], q: dict[str, Any], a: dict[str, Any]
) -> set[int]:
    params = q.get("params") or {}
    hotter = _bool_answer(a.get("answer"))
    if hotter is None:
        return {z.zone_id for z in zones}
    # Seekers travelled A -> B. Default A = seeker_location, B from params["to"].
    a_src = params.get("from")
    b_dst = params.get("to")
    try:
        pt_a = _latlon_point(a_src) if isinstance(a_src, dict) else _seeker_point(q)
        if not isinstance(b_dst, dict):
            return {z.zone_id for z in zones}
        pt_b = _latlon_point(b_dst)
    except (KeyError, TypeError, ValueError):
        return {z.zone_id for z in zones}
    kept: set[int] = set()
    for z in zones:
        d_from = z.rep_metric.distance(pt_a)
        d_to = z.rep_metric.distance(pt_b)
        # Hotter = moving A->B got closer to the hider (d_to < d_from). Keep ties on both
        # sides so a zone equidistant from A and B is never eliminated by either answer.
        if (hotter and d_to <= d_from) or (not hotter and d_to >= d_from):
            kept.add(z.zone_id)
    return kept


_DISPATCH = {
    "matching": _matching,
    "measuring": _measuring,
    "radar": _radar,
    "thermometer": _thermometer,
}


# --------------------------------------------------------------------------- public hook


def filter_zones(
    current_zone_ids: set[int],
    question_payload: dict[str, Any],
    answer_payload: dict[str, Any],
) -> set[int]:
    """Deduction hook: return the subset of ``current_zone_ids`` consistent with the answer.

    Fail-open: any unrecognised category, missing layer, or geometry error returns the input
    unchanged so the event reducer can never be broken by a bad question.
    """
    try:
        category = (question_payload or {}).get("category")
        predicate = _DISPATCH.get(category)
        if predicate is None:
            return set(current_zone_ids)
        assets = load_geo_assets()
        candidates = [z for z in assets.zones if z.zone_id in current_zone_ids]
        if not candidates:
            return set(current_zone_ids)
        kept = predicate(assets, candidates, question_payload, answer_payload)
        # Never expand the set; only intersect with what was already in play.
        return {zid for zid in kept if zid in current_zone_ids}
    except Exception:
        return set(current_zone_ids)


def dissolved_area(zone_ids: set[int]) -> dict[str, Any] | None:
    """Dissolve the given hiding zones into a single GeoJSON geometry dict (lon/lat).

    Useful for ``GameState.remaining_area``. Returns ``None`` for an empty selection.
    """
    if not zone_ids:
        return None
    assets = load_geo_assets()
    polys = [z.polygon_lonlat for z in assets.zones if z.zone_id in zone_ids]
    if not polys:
        return None
    return mapping(unary_union(polys))
