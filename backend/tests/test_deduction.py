"""Golden-case tests for the geometric deduction engine (``app.deduction``).

These exercise the four implemented question predicates against the real generated geo
assets (193 hiding zones + the Voronoi layers), plus an end-to-end run through the reducer
with the real hook wired in.
"""

from __future__ import annotations

import time
import uuid

import pytest

from app.deduction import dissolved_area, filter_zones, load_geo_assets
from app.reducer import reduce_events
from app.schemas import TOTAL_ZONES, Event


@pytest.fixture(scope="module")
def assets():
    return load_geo_assets()


@pytest.fixture(scope="module")
def all_ids(assets):
    return assets.zone_ids()


def _rep_lonlat(zone):
    p = zone.polygon_lonlat.representative_point()
    return {"lat": p.y, "lon": p.x}


def _extreme_zones(assets):
    """Westernmost and easternmost zones by representative-point longitude."""
    ordered = sorted(assets.zones, key=lambda z: z.polygon_lonlat.representative_point().x)
    return ordered[0], ordered[-1]


# --------------------------------------------------------------------------- loading


def test_loads_all_zones_and_layers(assets):
    assert len(assets.zones) == TOTAL_ZONES
    assert assets.zone_ids() == set(range(TOTAL_ZONES))
    # All ten shipped Voronoi layers load; the un-geocoded museums layer is absent.
    assert {
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
    } <= set(assets.voronoi)
    assert "museums" not in assets.voronoi


def test_assets_are_cached_singleton():
    assert load_geo_assets() is load_geo_assets()


def test_strtree_query_is_fast(assets, all_ids):
    west, east = _extreme_zones(assets)
    q = {
        "category": "radar",
        "subtype": "within_1km",
        "seeker_location": _rep_lonlat(east),
        "params": {"radius_m": 1000},
    }
    start = time.perf_counter()
    for _ in range(50):
        filter_zones(set(all_ids), q, {"answer": True})
    avg_ms = (time.perf_counter() - start) / 50 * 1000
    assert avg_ms < 10.0  # comfortably under the 10ms budget for 193 zones


# --------------------------------------------------------------------------- radar


def test_radar_within_radius_keeps_nearby_excludes_far(assets, all_ids):
    west, east = _extreme_zones(assets)
    q = {
        "category": "radar",
        "subtype": "within_1km",
        "seeker_location": _rep_lonlat(east),
        "params": {"radius_m": 1000},
    }
    kept = filter_zones(set(all_ids), q, {"answer": True})
    assert east.zone_id in kept  # the seeker's own zone is within 1 km of itself
    assert west.zone_id not in kept  # opposite end of the city is far outside
    assert kept < all_ids


def test_radar_true_and_false_partition_all_zones(assets, all_ids):
    _, east = _extreme_zones(assets)
    q = {
        "category": "radar",
        "subtype": "within_1km",
        "seeker_location": _rep_lonlat(east),
        "params": {"radius_m": 1000},
    }
    inside = filter_zones(set(all_ids), q, {"answer": True})
    outside = filter_zones(set(all_ids), q, {"answer": False})
    assert inside | outside == all_ids
    assert inside & outside == set()


# --------------------------------------------------------------------------- measuring


def test_measuring_closer_shrinks_and_excludes_farthest(assets, all_ids):
    # Seeker downtown; "are you closer to the nearest hospital than we are?"
    q = {
        "category": "measuring",
        "subtype": "nearest_hospital",
        "seeker_location": {"lat": 37.7749, "lon": -122.4194},
        "params": {"layer": "hospitals"},
    }
    closer = filter_zones(set(all_ids), q, {"answer": True})
    further = filter_zones(set(all_ids), q, {"answer": False})
    assert closer < all_ids and further < all_ids
    # Together they cover everything (boundary zones may appear in both).
    assert closer | further == all_ids


def test_measuring_explicit_poi_point(all_ids):
    q = {
        "category": "measuring",
        "subtype": "coast",
        "seeker_location": {"lat": 37.7749, "lon": -122.4194},
        "params": {"poi": {"lat": 37.8083, "lon": -122.4156}},  # near Fisherman's Wharf
    }
    closer = filter_zones(set(all_ids), q, {"answer": True})
    further = filter_zones(set(all_ids), q, {"answer": False})
    assert closer | further == all_ids
    assert closer and further  # both non-empty


# --------------------------------------------------------------------------- matching


def test_matching_same_cell_partitions_zones(assets, all_ids):
    # Seeker downtown asking about nearest rail station: same-cell vs different-cell.
    q = {
        "category": "matching",
        "subtype": "nearest_station",
        "seeker_location": {"lat": 37.7749, "lon": -122.4194},
        "params": {"layer": "rail-stations"},
    }
    same = filter_zones(set(all_ids), q, {"answer": True})
    diff = filter_zones(set(all_ids), q, {"answer": False})
    assert same and diff  # the seeker's cell holds some zones, and others lie elsewhere
    assert same | diff == all_ids
    assert same & diff == set()


def test_matching_missing_layer_is_noop(all_ids):
    # The museums layer has no Voronoi -> the engine must keep every zone, not crash.
    q = {
        "category": "matching",
        "subtype": "museum",
        "seeker_location": {"lat": 37.7749, "lon": -122.4194},
        "params": {"layer": "museums"},
    }
    assert filter_zones(set(all_ids), q, {"answer": True}) == all_ids


def test_matching_unrecognised_answer_is_noop(all_ids):
    # A free-form string answer (not same/different) must not eliminate anything.
    q = {
        "category": "matching",
        "subtype": "nearest_hospital",
        "seeker_location": {"lat": 37.77, "lon": -122.42},
        "params": {},
    }
    assert filter_zones(set(all_ids), q, {"answer": "UCSF"}) == all_ids


# --------------------------------------------------------------------------- thermometer


def test_thermometer_hotter_keeps_zones_nearer_destination(assets, all_ids):
    west, east = _extreme_zones(assets)
    a_point = _rep_lonlat(west)
    b_point = _rep_lonlat(east)
    q = {
        "category": "thermometer",
        "subtype": "hotter_colder",
        "seeker_location": a_point,
        "params": {"from": a_point, "to": b_point},
    }
    hotter = filter_zones(set(all_ids), q, {"answer": "hotter"})
    colder = filter_zones(set(all_ids), q, {"answer": "colder"})
    # Moving west -> east got hotter: the eastern zone is kept, the western one dropped.
    assert east.zone_id in hotter and west.zone_id not in hotter
    assert west.zone_id in colder and east.zone_id not in colder
    assert hotter | colder == all_ids


# --------------------------------------------------------------------------- helpers


def test_dissolved_area_returns_geojson(all_ids):
    area = dissolved_area({0, 1, 2})
    assert area is not None
    assert area["type"] in ("Polygon", "MultiPolygon")
    assert dissolved_area(set()) is None


def test_filter_never_expands_zone_set(all_ids):
    # Starting from a small subset, the result is always a subset of it.
    subset = {0, 1, 2, 3, 4}
    q = {
        "category": "radar",
        "subtype": "within_1km",
        "seeker_location": {"lat": 37.7749, "lon": -122.4194},
        "params": {"radius_m": 1000},
    }
    assert filter_zones(set(subset), q, {"answer": True}) <= subset


# --------------------------------------------------------------------------- end to end


def _ev(seq: int, type_: str, payload: dict) -> Event:
    return Event(
        server_seq=seq,
        client_event_id=uuid.uuid4(),
        type=type_,
        payload=payload,
    )


def test_reduce_events_applies_real_deduction():
    qid = uuid.uuid4()
    events = [
        _ev(1, "game_created", {"join_code": "ABC123"}),
        _ev(
            2,
            "question_asked",
            {
                "question_id": str(qid),
                "category": "radar",
                "subtype": "within_1km",
                "seeker_location": {"lat": 37.7749, "lon": -122.4194},
                "asked_by": str(uuid.uuid4()),
                "params": {"radius_m": 1000},
            },
        ),
        _ev(
            3,
            "question_answered",
            {"question_id": str(qid), "answer": True, "hider_id": str(uuid.uuid4())},
        ),
    ]
    state = reduce_events(events)
    # The real hook actually filters now: fewer than all zones, but still some remain.
    assert 0 < len(state.remaining_zone_ids) < TOTAL_ZONES
