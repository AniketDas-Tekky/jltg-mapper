"""Shared domain services used by both the REST API and the WebSocket hub.

Centralises the event-append write path so HTTP and WS produce identical, idempotent,
monotonically-sequenced events.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Event, Game, GameStatus, Player, PlayerRole
from app.reducer import reduce_events
from app.schemas import Event as EventSchema
from app.schemas import GameState

_JOIN_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no ambiguous chars


class DuplicateClientEventError(Exception):
    """Raised when an event with the same client_event_id already exists (idempotency)."""

    def __init__(self, existing: Event) -> None:
        self.existing = existing
        super().__init__(f"client_event_id {existing.client_event_id} already applied")


@dataclass
class AppendResult:
    event: Event
    created: bool  # False if this was a duplicate (idempotent replay)


def generate_join_code(db: Session, length: int = 6) -> str:
    """Generate a join code unique among existing games."""
    for _ in range(20):
        code = "".join(secrets.choice(_JOIN_ALPHABET) for _ in range(length))
        if db.scalar(select(Game.id).where(Game.join_code == code)) is None:
            return code
    raise RuntimeError("could not allocate a unique join code")


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def create_game(db: Session, host_name: str) -> tuple[Game, Player]:
    """Create a game plus its host player, append the bootstrap events, and commit."""
    game = Game(join_code=generate_join_code(db), status=GameStatus.lobby)
    db.add(game)
    db.flush()

    host = Player(
        game_id=game.id,
        name=host_name,
        role=PlayerRole.host,
        token=generate_token(),
    )
    db.add(host)
    db.flush()

    _append(
        db,
        game_id=game.id,
        client_event_id=uuid.uuid4(),
        player_id=host.id,
        type_="game_created",
        payload={"join_code": game.join_code, "host_name": host_name},
    )
    _append(
        db,
        game_id=game.id,
        client_event_id=uuid.uuid4(),
        player_id=host.id,
        type_="player_joined",
        payload={"player_id": str(host.id), "name": host_name, "role": "host"},
    )
    db.commit()
    db.refresh(game)
    db.refresh(host)
    return game, host


def join_game(db: Session, join_code: str, name: str, role: str) -> tuple[Game, Player]:
    """Add a player to an existing game and append a player_joined event."""
    game = db.scalar(select(Game).where(Game.join_code == join_code))
    if game is None:
        raise LookupError("game not found")

    player = Player(
        game_id=game.id,
        name=name,
        role=PlayerRole(role),
        token=generate_token(),
    )
    db.add(player)
    db.flush()

    _append(
        db,
        game_id=game.id,
        client_event_id=uuid.uuid4(),
        player_id=player.id,
        type_="player_joined",
        payload={"player_id": str(player.id), "name": name, "role": role},
    )
    db.commit()
    db.refresh(player)
    return game, player


def _next_server_seq(db: Session, game_id: uuid.UUID) -> int:
    """Compute the next monotonic server_seq for a game.

    The (game_id, server_seq) unique constraint is the authority; concurrent writers that
    race here will collide on that constraint and the caller should retry. Within a single
    request this is sufficient and deterministic.
    """
    current = db.scalar(
        select(func.coalesce(func.max(Event.server_seq), 0)).where(Event.game_id == game_id)
    )
    return int(current) + 1


def _append(
    db: Session,
    *,
    game_id: uuid.UUID,
    client_event_id: uuid.UUID,
    player_id: uuid.UUID | None,
    type_: str,
    payload: dict,
) -> Event:
    """Low-level append within an open transaction (caller commits)."""
    event = Event(
        game_id=game_id,
        server_seq=_next_server_seq(db, game_id),
        client_event_id=client_event_id,
        player_id=player_id,
        type=type_,
        payload=payload or {},
    )
    db.add(event)
    db.flush()
    return event


def append_event(
    db: Session,
    *,
    game_id: uuid.UUID,
    client_event_id: uuid.UUID,
    player_id: uuid.UUID | None,
    type_: str,
    payload: dict,
) -> AppendResult:
    """Idempotently append an event for a game.

    If ``client_event_id`` already exists, returns the existing event with
    ``created=False`` (no new event, idempotent). Otherwise assigns the next server_seq,
    persists, commits, and returns ``created=True``.
    """
    existing = db.scalar(
        select(Event).where(Event.client_event_id == client_event_id)
    )
    if existing is not None:
        return AppendResult(event=existing, created=False)

    event = _append(
        db,
        game_id=game_id,
        client_event_id=client_event_id,
        player_id=player_id,
        type_=type_,
        payload=payload,
    )
    db.commit()
    db.refresh(event)
    return AppendResult(event=event, created=True)


def load_events(db: Session, game_id: uuid.UUID, since_seq: int = 0) -> list[Event]:
    return list(
        db.scalars(
            select(Event)
            .where(Event.game_id == game_id, Event.server_seq > since_seq)
            .order_by(Event.server_seq)
        )
    )


def compute_state(db: Session, game_id: uuid.UUID) -> GameState:
    """Replay all events for a game through the pure reducer."""
    events = [EventSchema.model_validate(e) for e in load_events(db, game_id, since_seq=0)]
    return reduce_events(events)
