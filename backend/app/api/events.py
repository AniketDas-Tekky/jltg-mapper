"""Event log endpoints: read derived state, sync events, append events.

Append is idempotent on ``client_event_id`` (409 on a duplicate that differs, the existing
event is returned via the 409 detail) and assigns a monotonic ``server_seq`` per game.
After a successful append the event is broadcast to WebSocket subscribers.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import services
from app.api.auth import get_current_player
from app.db import get_db
from app.models import Event, Game, Player
from app.schemas import EventResponse, PostEventRequest, StateResponse
from app.websocket import broadcast_event

router = APIRouter(prefix="/games", tags=["events"])


def _require_member(game_id: uuid.UUID, player: Player) -> None:
    if player.game_id != game_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Player does not belong to this game",
        )


def _get_game(db: Session, game_id: uuid.UUID) -> Game:
    game = db.scalar(select(Game).where(Game.id == game_id))
    if game is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Game not found")
    return game


def _to_response(event: Event) -> EventResponse:
    return EventResponse(
        id=event.id,
        game_id=event.game_id,
        server_seq=event.server_seq,
        client_event_id=event.client_event_id,
        player_id=event.player_id,
        type=event.type,
        payload=event.payload,
        created_at=event.created_at,
    )


@router.get("/{game_id}/state", response_model=StateResponse)
def get_state(
    game_id: uuid.UUID,
    db: Session = Depends(get_db),
    player: Player = Depends(get_current_player),
) -> StateResponse:
    _get_game(db, game_id)
    _require_member(game_id, player)
    state = services.compute_state(db, game_id)
    return StateResponse(game_id=game_id, last_seq=state.last_seq, state=state)


@router.get("/{game_id}/events", response_model=list[EventResponse])
def get_events(
    game_id: uuid.UUID,
    since_seq: int = 0,
    db: Session = Depends(get_db),
    player: Player = Depends(get_current_player),
) -> list[EventResponse]:
    _get_game(db, game_id)
    _require_member(game_id, player)
    events = services.load_events(db, game_id, since_seq=since_seq)
    return [_to_response(e) for e in events]


@router.post(
    "/{game_id}/events",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_event(
    game_id: uuid.UUID,
    body: PostEventRequest,
    db: Session = Depends(get_db),
    player: Player = Depends(get_current_player),
) -> EventResponse:
    _get_game(db, game_id)
    _require_member(game_id, player)

    # Idempotency: a duplicate client_event_id is a conflict. We surface 409 and include the
    # already-applied server_seq so clients can reconcile.
    existing = db.scalar(select(Event).where(Event.client_event_id == body.client_event_id))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "client_event_id already applied",
                "server_seq": existing.server_seq,
                "event_id": str(existing.id),
            },
        )

    result = services.append_event(
        db,
        game_id=game_id,
        client_event_id=body.client_event_id,
        player_id=player.id,
        type_=body.type,
        payload=body.payload,
    )
    response = _to_response(result.event)
    if result.created:
        await broadcast_event(game_id, response)
    return response
