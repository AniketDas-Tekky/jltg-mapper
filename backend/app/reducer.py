"""Pure, deterministic event reducer for the event-sourced game state.

``reduce_events(events)`` folds an ordered list of :class:`~app.schemas.Event` into a
:class:`~app.schemas.GameState`. The function is pure: no I/O, no clock reads, no mutation
of its inputs. Given the same events it always returns the same state.

Unknown event types and malformed payloads are skipped (logged via the returned state's
log is intentionally avoided to keep purity) so the reducer is forward-compatible.

DEDUCTION SEAM (for task 8): zone elimination on ``question_answered`` is delegated to the
pluggable ``deduction_hook`` parameter (default :func:`_noop_deduction`, a STUB). Task 8's
geometry engine should supply a real :data:`DeductionHook`; nothing else in this module
needs to change. See the ``--- DEDUCTION SEAM ---`` marker below.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Any

from pydantic import ValidationError

from app.schemas import (
    PAYLOAD_MODELS,
    TOTAL_ZONES,
    EventType,
    GameLifecycleStatus,
    GameState,
    ScoreEntry,
)
from app.schemas import Event as EventSchema

# ===========================================================================
# --- DEDUCTION SEAM (task 8 plugs in here) ---
#
# A DeductionHook takes the currently-remaining zone ids plus the (already-validated)
# question_asked and question_answered payloads, and returns the subset of zone ids that
# remain after applying the geometric predicate. It MUST be pure and deterministic.
#
# Task 8 (app/deduction.py) will implement a real hook backed by Shapely/STRtree over the
# generated geo assets and pass it into ``reduce_events(..., deduction_hook=...)`` (or set
# the module-level default ``DEFAULT_DEDUCTION_HOOK``). Until then, the stub below keeps all
# zones (no elimination) so the rest of the pipeline works end to end.
# ===========================================================================

DeductionHook = Callable[[set[int], dict[str, Any], dict[str, Any]], set[int]]


def _noop_deduction(
    remaining_zone_ids: set[int],
    question_asked_payload: dict[str, Any],
    question_answered_payload: dict[str, Any],
) -> set[int]:
    """STUB deduction hook — eliminates nothing.

    Replaced by the real geometry engine in task 8 (``app/deduction.py``). Returning the
    input unchanged means a ``question_answered`` event is recorded but no zones are
    removed yet.
    """
    return set(remaining_zone_ids)


def _real_deduction(
    remaining_zone_ids: set[int],
    question_asked_payload: dict[str, Any],
    question_answered_payload: dict[str, Any],
) -> set[int]:
    """Default hook: delegate to the geometry engine in :mod:`app.deduction`.

    Imported lazily so merely importing the reducer never triggers geo-asset I/O — the
    Shapely/STRtree assets are loaded (and cached) only the first time a question is actually
    answered. The engine itself is fail-open, so this can never break event reduction.
    """
    from app.deduction import filter_zones

    return filter_zones(
        remaining_zone_ids, question_asked_payload, question_answered_payload
    )


# The real geometry engine is the default everywhere. Tests may still pass an explicit
# ``deduction_hook`` (e.g. ``_noop_deduction``) to override it.
DEFAULT_DEDUCTION_HOOK: DeductionHook = _real_deduction

# --- end deduction seam wiring (handlers below call self.deduction_hook) ---


def _parse_payload(event_type: str, payload: dict[str, Any]) -> Any | None:
    """Validate ``payload`` against the model for ``event_type``; return None on failure."""
    model = PAYLOAD_MODELS.get(event_type)
    if model is None:
        return None
    try:
        return model.model_validate(payload or {})
    except ValidationError:
        return None


class _StateBuilder:
    """Mutable working copy used while folding events; exported as an immutable GameState."""

    def __init__(self, deduction_hook: DeductionHook) -> None:
        self.deduction_hook = deduction_hook
        self.status = GameLifecycleStatus.lobby
        self.last_seq = 0
        self.remaining_zone_ids: set[int] = set()
        self.remaining_area: dict[str, Any] | None = None
        self.timers: dict[str, Any] = {}
        self.scoreboard: list[ScoreEntry] = []
        self.players: dict[str, dict[str, Any]] = {}
        self.questions: list[dict[str, Any]] = []
        self.notes: list[dict[str, Any]] = []
        self.curses: list[dict[str, Any]] = []
        # question_id -> asked payload, so question_answered can look up its question.
        self._questions_by_id: dict[str, dict[str, Any]] = {}

    # -- handlers ---------------------------------------------------------

    def on_game_created(self, p: Any) -> None:
        total = getattr(p, "total_zones", TOTAL_ZONES) or TOTAL_ZONES
        self.remaining_zone_ids = set(range(total))
        self.status = GameLifecycleStatus.lobby

    def on_player_joined(self, p: Any) -> None:
        self.players[str(p.player_id)] = {"name": p.name, "role": p.role}

    def on_role_assigned(self, p: Any) -> None:
        entry = self.players.setdefault(str(p.player_id), {})
        entry["role"] = p.role

    def on_hiding_started(self, p: Any) -> None:
        self.status = GameLifecycleStatus.hiding
        self.timers["hiding_started_at"] = p.started_at.isoformat()
        self.timers["hiding_duration_seconds"] = p.hiding_duration_seconds

    def on_question_asked(self, p: Any) -> None:
        # Asking a question marks the transition into active seeking.
        if self.status == GameLifecycleStatus.hiding:
            self.status = GameLifecycleStatus.seeking
        record = {
            "question_id": str(p.question_id),
            "category": p.category,
            "subtype": p.subtype,
            "seeker_location": {"lat": p.seeker_location.lat, "lon": p.seeker_location.lon},
            "asked_by": str(p.asked_by),
            "params": p.params,
            "answer": None,
        }
        self.questions.append(record)
        self._questions_by_id[str(p.question_id)] = record

    def on_question_answered(self, p: Any) -> None:
        record = self._questions_by_id.get(str(p.question_id))
        if record is not None:
            record["answer"] = p.answer
            # --- DEDUCTION SEAM invocation ---
            self.remaining_zone_ids = self.deduction_hook(
                set(self.remaining_zone_ids),
                {
                    "category": record["category"],
                    "subtype": record["subtype"],
                    "seeker_location": record["seeker_location"],
                    "params": record["params"],
                },
                {"answer": p.answer, "hider_id": str(p.hider_id)},
            )

    def on_zone_excluded(self, p: Any) -> None:
        self.remaining_zone_ids.discard(p.zone_id)

    def on_zone_restored(self, p: Any) -> None:
        self.remaining_zone_ids.add(p.zone_id)

    def on_curse_logged(self, p: Any) -> None:
        self.curses.append(
            {
                "curse": p.curse,
                "cast_by": str(p.cast_by) if p.cast_by else None,
                "note": p.note,
            }
        )

    def on_note_added(self, p: Any) -> None:
        self.notes.append({"text": p.text, "author": str(p.author) if p.author else None})

    def on_game_paused(self, p: Any) -> None:
        if self.status != GameLifecycleStatus.ended:
            self.timers["paused_at"] = p.paused_at.isoformat()
            self.timers["_status_before_pause"] = self.status.value
            self.status = GameLifecycleStatus.paused

    def on_game_resumed(self, p: Any) -> None:
        if self.status == GameLifecycleStatus.paused:
            prev = self.timers.pop("_status_before_pause", GameLifecycleStatus.seeking.value)
            self.status = GameLifecycleStatus(prev)
            self.timers["resumed_at"] = p.resumed_at.isoformat()
            self.timers.pop("paused_at", None)

    def on_round_ended(self, p: Any) -> None:
        self.status = GameLifecycleStatus.ended
        self.scoreboard.append(
            ScoreEntry(
                hider_id=p.hider_id,
                hider_name=p.hider_name,
                run_time_seconds=p.run_time_seconds,
            )
        )
        # Highest run time wins -> sort descending.
        self.scoreboard.sort(key=lambda s: s.run_time_seconds, reverse=True)

    def on_role_rotated(self, p: Any) -> None:
        for player_id, role in p.assignments.items():
            self.players.setdefault(player_id, {})["role"] = role
        # New round: reset zones and status back to lobby for the next hide.
        self.remaining_zone_ids = set(range(TOTAL_ZONES))
        self.remaining_area = None
        self.status = GameLifecycleStatus.lobby

    # -- dispatch ---------------------------------------------------------

    _HANDLERS: dict[str, str] = {
        EventType.game_created.value: "on_game_created",
        EventType.player_joined.value: "on_player_joined",
        EventType.role_assigned.value: "on_role_assigned",
        EventType.hiding_started.value: "on_hiding_started",
        EventType.question_asked.value: "on_question_asked",
        EventType.question_answered.value: "on_question_answered",
        EventType.zone_excluded.value: "on_zone_excluded",
        EventType.zone_restored.value: "on_zone_restored",
        EventType.curse_logged.value: "on_curse_logged",
        EventType.note_added.value: "on_note_added",
        EventType.game_paused.value: "on_game_paused",
        EventType.game_resumed.value: "on_game_resumed",
        EventType.round_ended.value: "on_round_ended",
        EventType.role_rotated.value: "on_role_rotated",
    }

    def apply(self, event: EventSchema) -> None:
        self.last_seq = max(self.last_seq, event.server_seq)
        handler_name = self._HANDLERS.get(event.type)
        if handler_name is None:
            return  # unknown event type -> no-op
        payload = _parse_payload(event.type, event.payload)
        if payload is None:
            return  # malformed payload -> skip, keep folding
        getattr(self, handler_name)(payload)

    def build(self) -> GameState:
        return GameState(
            status=self.status,
            last_seq=self.last_seq,
            remaining_zone_ids=sorted(self.remaining_zone_ids),
            remaining_area=self.remaining_area,
            timers=dict(self.timers),
            scoreboard=list(self.scoreboard),
            players=dict(self.players),
            questions=list(self.questions),
            notes=list(self.notes),
            curses=list(self.curses),
        )


def reduce_events(
    events: Sequence[EventSchema] | Iterable[EventSchema],
    *,
    deduction_hook: DeductionHook | None = None,
) -> GameState:
    """Fold ``events`` (ordered by server_seq) into a :class:`GameState`.

    Pure and deterministic. ``deduction_hook`` overrides the module default for zone
    elimination on ``question_answered`` (task 8 supplies the real implementation).
    """
    builder = _StateBuilder(deduction_hook or DEFAULT_DEDUCTION_HOOK)
    # Order defensively by server_seq so out-of-order input still reduces deterministically.
    ordered = sorted(events, key=lambda e: e.server_seq)
    for event in ordered:
        builder.apply(event)
    return builder.build()
