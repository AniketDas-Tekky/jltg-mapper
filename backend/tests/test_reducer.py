"""Pure reducer unit tests — deterministic, no I/O."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.reducer import _noop_deduction, reduce_events
from app.schemas import TOTAL_ZONES, Event, GameLifecycleStatus


def _ev(seq: int, type_: str, payload: dict, *, player=None) -> Event:
    return Event(
        server_seq=seq,
        client_event_id=uuid.uuid4(),
        player_id=player,
        type=type_,
        payload=payload,
    )


def test_empty_event_list_yields_lobby_default():
    state = reduce_events([])
    assert state.status == GameLifecycleStatus.lobby
    assert state.last_seq == 0
    assert state.remaining_zone_ids == []
    assert state.scoreboard == []


def test_game_created_initializes_all_zones():
    state = reduce_events([_ev(1, "game_created", {"join_code": "ABC123"})])
    assert len(state.remaining_zone_ids) == TOTAL_ZONES
    assert state.remaining_zone_ids[0] == 0
    assert state.remaining_zone_ids[-1] == TOTAL_ZONES - 1


def test_player_joined_and_role_assigned():
    pid = uuid.uuid4()
    events = [
        _ev(1, "game_created", {"join_code": "ABC123"}),
        _ev(2, "player_joined", {"player_id": str(pid), "name": "Ada", "role": "seeker"}),
        _ev(3, "role_assigned", {"player_id": str(pid), "role": "hider"}),
    ]
    state = reduce_events(events)
    assert state.players[str(pid)]["name"] == "Ada"
    assert state.players[str(pid)]["role"] == "hider"


def test_hiding_started_sets_status_and_timer():
    started = datetime(2026, 6, 18, 12, 0, tzinfo=UTC)
    events = [
        _ev(1, "game_created", {"join_code": "ABC123"}),
        _ev(2, "hiding_started",
            {"started_at": started.isoformat(), "hiding_duration_seconds": 900}),
    ]
    state = reduce_events(events)
    assert state.status == GameLifecycleStatus.hiding
    assert state.timers["hiding_duration_seconds"] == 900
    assert "hiding_started_at" in state.timers


def test_question_asked_then_answered_records_and_calls_stub_hook():
    qid = uuid.uuid4()
    hid = uuid.uuid4()
    seeker = uuid.uuid4()
    events = [
        _ev(1, "game_created", {"join_code": "ABC123"}),
        _ev(2, "hiding_started", {"started_at": datetime.now(UTC).isoformat()}),
        _ev(3, "question_asked", {
            "question_id": str(qid),
            "category": "matching",
            "subtype": "nearest_hospital",
            "seeker_location": {"lat": 37.77, "lon": -122.42},
            "asked_by": str(seeker),
        }),
        _ev(4, "question_answered",
            {"question_id": str(qid), "answer": "UCSF", "hider_id": str(hid)}),
    ]
    state = reduce_events(events)
    assert state.status == GameLifecycleStatus.seeking
    assert len(state.questions) == 1
    assert state.questions[0]["answer"] == "UCSF"
    # Stub deduction keeps all zones.
    assert len(state.remaining_zone_ids) == TOTAL_ZONES


def test_deduction_hook_override_eliminates_zones():
    qid = uuid.uuid4()

    def keep_only_low(remaining, q_asked, q_answered):
        return {z for z in remaining if z < 5}

    events = [
        _ev(1, "game_created", {"join_code": "ABC123"}),
        _ev(2, "question_asked", {
            "question_id": str(qid),
            "category": "radar",
            "subtype": "within_500m",
            "seeker_location": {"lat": 37.77, "lon": -122.42},
            "asked_by": str(uuid.uuid4()),
        }),
        _ev(3, "question_answered",
            {"question_id": str(qid), "answer": True, "hider_id": str(uuid.uuid4())}),
    ]
    state = reduce_events(events, deduction_hook=keep_only_low)
    assert state.remaining_zone_ids == [0, 1, 2, 3, 4]


def test_zone_excluded_and_restored():
    events = [
        _ev(1, "game_created", {"join_code": "ABC123"}),
        _ev(2, "zone_excluded", {"zone_id": 7, "reason": "manual"}),
        _ev(3, "zone_excluded", {"zone_id": 8}),
        _ev(4, "zone_restored", {"zone_id": 7}),
    ]
    state = reduce_events(events)
    assert 7 in state.remaining_zone_ids
    assert 8 not in state.remaining_zone_ids


def test_pause_resume_round_trip():
    now = datetime.now(UTC)
    events = [
        _ev(1, "game_created", {"join_code": "ABC123"}),
        _ev(2, "hiding_started", {"started_at": now.isoformat()}),
        _ev(3, "game_paused", {"paused_at": now.isoformat()}),
    ]
    paused = reduce_events(events)
    assert paused.status == GameLifecycleStatus.paused

    events.append(_ev(4, "game_resumed", {"resumed_at": now.isoformat()}))
    resumed = reduce_events(events)
    assert resumed.status == GameLifecycleStatus.hiding


def test_round_ended_builds_sorted_scoreboard():
    events = [
        _ev(1, "game_created", {"join_code": "ABC123"}),
        _ev(2, "round_ended", {"hider_name": "Ada", "run_time_seconds": 600}),
        _ev(3, "round_ended", {"hider_name": "Bo", "run_time_seconds": 1200}),
    ]
    state = reduce_events(events)
    assert state.status == GameLifecycleStatus.ended
    assert [s.hider_name for s in state.scoreboard] == ["Bo", "Ada"]


def test_notes_and_curses_recorded():
    events = [
        _ev(1, "game_created", {"join_code": "ABC123"}),
        _ev(2, "note_added", {"text": "saw a seeker on Market St"}),
        _ev(3, "curse_logged", {"curse": "Curse of the Bridge Troll"}),
    ]
    state = reduce_events(events)
    assert state.notes[0]["text"] == "saw a seeker on Market St"
    assert state.curses[0]["curse"] == "Curse of the Bridge Troll"


def test_unknown_event_type_is_noop():
    events = [
        _ev(1, "game_created", {"join_code": "ABC123"}),
        _ev(2, "totally_unknown_event", {"foo": "bar"}),
    ]
    state = reduce_events(events)
    assert state.last_seq == 2
    assert len(state.remaining_zone_ids) == TOTAL_ZONES


def test_malformed_payload_is_skipped():
    events = [
        _ev(1, "game_created", {"join_code": "ABC123"}),
        # zone_excluded requires zone_id (int); omit it -> handler skipped.
        _ev(2, "zone_excluded", {"reason": "no id"}),
    ]
    state = reduce_events(events)
    assert len(state.remaining_zone_ids) == TOTAL_ZONES


def test_out_of_order_events_are_sorted_deterministically():
    events_forward = [
        _ev(1, "game_created", {"join_code": "ABC123"}),
        _ev(2, "zone_excluded", {"zone_id": 3}),
    ]
    events_reversed = list(reversed(events_forward))
    assert reduce_events(events_forward) == reduce_events(events_reversed)


def test_reducer_is_deterministic():
    events = [
        _ev(1, "game_created", {"join_code": "ABC123"}),
        _ev(2, "zone_excluded", {"zone_id": 1}),
        _ev(3, "zone_excluded", {"zone_id": 2}),
    ]
    assert reduce_events(events) == reduce_events(events)


def test_noop_deduction_returns_copy_unchanged():
    src = {1, 2, 3}
    out = _noop_deduction(src, {}, {})
    assert out == src
    assert out is not src
