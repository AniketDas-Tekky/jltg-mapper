"""Pydantic v2 schemas: event payloads, the wrapped event, and request/response models.

Each event ``type`` maps to a payload model. The reducer (``app.reducer``) folds a list
of :class:`Event` into a :class:`GameState`. Payloads are validated structurally; the
reducer treats unknown event types as no-ops so the log stays forward-compatible.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Total number of hiding zones in the SF game (zones 0..192). Sourced from the geo
# pipeline (193 valid hiding stations). Kept here so the reducer has no I/O dependency.
TOTAL_ZONES = 193


class EventType(enum.StrEnum):
    game_created = "game_created"
    player_joined = "player_joined"
    role_assigned = "role_assigned"
    hiding_started = "hiding_started"
    question_asked = "question_asked"
    question_answered = "question_answered"
    zone_excluded = "zone_excluded"
    zone_restored = "zone_restored"
    curse_logged = "curse_logged"
    note_added = "note_added"
    game_paused = "game_paused"
    game_resumed = "game_resumed"
    round_ended = "round_ended"
    role_rotated = "role_rotated"


class GameLifecycleStatus(enum.StrEnum):
    lobby = "lobby"
    hiding = "hiding"
    seeking = "seeking"
    paused = "paused"
    ended = "ended"


# --------------------------------------------------------------------------- payloads


class LatLon(BaseModel):
    lat: float
    lon: float


class GameCreatedPayload(BaseModel):
    join_code: str
    host_name: str | None = None
    total_zones: int = TOTAL_ZONES


class PlayerJoinedPayload(BaseModel):
    player_id: UUID
    name: str
    role: Literal["host", "seeker", "hider"]


class RoleAssignedPayload(BaseModel):
    player_id: UUID
    role: Literal["host", "seeker", "hider"]


class HidingStartedPayload(BaseModel):
    started_at: datetime
    hiding_duration_seconds: int = Field(default=3600, ge=0)


class QuestionAskedPayload(BaseModel):
    question_id: UUID
    category: Literal["matching", "measuring", "radar", "thermometer"]
    subtype: str
    seeker_location: LatLon
    asked_by: UUID
    # Free-form params for the deduction engine (e.g. radar radius, thermometer pois).
    params: dict[str, Any] = Field(default_factory=dict)


class QuestionAnsweredPayload(BaseModel):
    question_id: UUID
    answer: Any
    hider_id: UUID


class ZoneExcludedPayload(BaseModel):
    zone_id: int
    reason: str | None = None


class ZoneRestoredPayload(BaseModel):
    zone_id: int
    reason: str | None = None


class CurseLoggedPayload(BaseModel):
    curse: str
    cast_by: UUID | None = None
    note: str | None = None


class NoteAddedPayload(BaseModel):
    text: str
    author: UUID | None = None


class GamePausedPayload(BaseModel):
    paused_at: datetime


class GameResumedPayload(BaseModel):
    resumed_at: datetime


class RoundEndedPayload(BaseModel):
    hider_id: UUID | None = None
    hider_name: str | None = None
    run_time_seconds: int = Field(ge=0)


class RoleRotatedPayload(BaseModel):
    # Maps player_id -> new role for the next round.
    assignments: dict[str, str] = Field(default_factory=dict)


# Discriminator-free union used for documentation / typing. Validation per-type is done
# in ``reducer.parse_payload`` which dispatches on the event ``type``.
PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    EventType.game_created.value: GameCreatedPayload,
    EventType.player_joined.value: PlayerJoinedPayload,
    EventType.role_assigned.value: RoleAssignedPayload,
    EventType.hiding_started.value: HidingStartedPayload,
    EventType.question_asked.value: QuestionAskedPayload,
    EventType.question_answered.value: QuestionAnsweredPayload,
    EventType.zone_excluded.value: ZoneExcludedPayload,
    EventType.zone_restored.value: ZoneRestoredPayload,
    EventType.curse_logged.value: CurseLoggedPayload,
    EventType.note_added.value: NoteAddedPayload,
    EventType.game_paused.value: GamePausedPayload,
    EventType.game_resumed.value: GameResumedPayload,
    EventType.round_ended.value: RoundEndedPayload,
    EventType.role_rotated.value: RoleRotatedPayload,
}


# --------------------------------------------------------------------------- event wrapper


class Event(BaseModel):
    """A persisted event, as consumed by the reducer and returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID | None = None
    game_id: UUID | None = None
    server_seq: int
    client_event_id: UUID
    player_id: UUID | None = None
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


# --------------------------------------------------------------------------- derived state


class ScoreEntry(BaseModel):
    hider_id: UUID | None = None
    hider_name: str | None = None
    run_time_seconds: int


class GameState(BaseModel):
    """Reducer output: the full derived state of a game at a point in the log."""

    status: GameLifecycleStatus = GameLifecycleStatus.lobby
    last_seq: int = 0
    remaining_zone_ids: list[int] = Field(default_factory=list)
    remaining_area: dict[str, Any] | None = None
    timers: dict[str, Any] = Field(default_factory=dict)
    scoreboard: list[ScoreEntry] = Field(default_factory=list)
    players: dict[str, dict[str, Any]] = Field(default_factory=dict)
    questions: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[dict[str, Any]] = Field(default_factory=list)
    curses: list[dict[str, Any]] = Field(default_factory=list)


# --------------------------------------------------------------------------- API request/response


class CreateGameRequest(BaseModel):
    host_name: str = Field(default="Host", min_length=1, max_length=80)


class CreateGameResponse(BaseModel):
    game_id: UUID
    join_code: str
    player_id: UUID
    token: str


class JoinGameRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    role: Literal["seeker", "hider"] = "seeker"


class JoinGameResponse(BaseModel):
    game_id: UUID
    player_id: UUID
    token: str
    role: str


class PostEventRequest(BaseModel):
    client_event_id: UUID
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class EventResponse(BaseModel):
    id: UUID
    game_id: UUID
    server_seq: int
    client_event_id: UUID
    player_id: UUID | None
    type: str
    payload: dict[str, Any]
    created_at: datetime


class StateResponse(BaseModel):
    game_id: UUID
    last_seq: int
    state: GameState
