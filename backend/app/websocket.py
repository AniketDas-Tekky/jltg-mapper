"""WebSocket hub for realtime game sync.

``/ws/{game_id}?token=...`` authenticates via the bearer token (query param, since browser
WebSocket clients can't set Authorization headers), registers the connection in an in-memory
:class:`ConnectionManager`, sends the current state snapshot, then relays inbound events and
broadcasts every appended event to all connections for that game.

The append path reuses :func:`app.services.append_event` so REST and WS are idempotent and
share one monotonic ``server_seq`` sequence. Broadcasting is also invoked from the REST
events endpoint via :data:`hub`.
"""

from __future__ import annotations

import asyncio
import uuid
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app import services
from app.api.auth import authenticate_token
from app.db import SessionLocal
from app.schemas import Event as EventSchema
from app.schemas import EventResponse

router = APIRouter()


class ConnectionManager:
    """Tracks active WebSocket connections per game and broadcasts JSON messages."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, game_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections[game_id].add(ws)

    async def disconnect(self, game_id: str, ws: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(game_id)
            if conns is not None:
                conns.discard(ws)
                if not conns:
                    self._connections.pop(game_id, None)

    def connection_count(self, game_id: str) -> int:
        return len(self._connections.get(game_id, ()))

    async def broadcast(self, game_id: str, message: dict[str, Any]) -> None:
        """Send ``message`` to every live connection for ``game_id`` (best-effort)."""
        async with self._lock:
            targets = list(self._connections.get(game_id, ()))
        dead: list[WebSocket] = []
        for ws in targets:
            if ws.application_state != WebSocketState.CONNECTED:
                dead.append(ws)
                continue
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 — drop broken connections
                dead.append(ws)
        if dead:
            async with self._lock:
                conns = self._connections.get(game_id)
                if conns is not None:
                    for ws in dead:
                        conns.discard(ws)


# Singleton hub shared by the WS endpoint and the REST events endpoint.
hub = ConnectionManager()


def _event_message(event: EventResponse) -> dict[str, Any]:
    return {"kind": "event", "event": event.model_dump(mode="json")}


async def broadcast_event(game_id: uuid.UUID, event: EventResponse) -> None:
    """Public helper for the REST layer to broadcast an appended event."""
    await hub.broadcast(str(game_id), _event_message(event))


def _to_event_response(event) -> EventResponse:  # noqa: ANN001 — ORM Event
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


@router.websocket("/ws/{game_id}")
async def game_ws(websocket: WebSocket, game_id: str, token: str | None = None) -> None:
    # Authenticate before accepting; close with policy-violation code on failure.
    try:
        game_uuid = uuid.UUID(game_id)
    except ValueError:
        await websocket.close(code=4400)
        return

    db = SessionLocal()
    try:
        player = authenticate_token(db, token)
        if player is None or player.game_id != game_uuid:
            await websocket.close(code=4401)
            return
        player_id = player.id

        # Snapshot current state for the freshly-connected client.
        state = services.compute_state(db, game_uuid)
    finally:
        db.close()

    await hub.connect(game_id, websocket)
    try:
        await websocket.send_json(
            {"kind": "state", "game_id": game_id, "last_seq": state.last_seq,
             "state": state.model_dump(mode="json")}
        )

        while True:
            raw = await websocket.receive_json()
            await _handle_inbound(websocket, game_uuid, player_id, raw)
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 — defensive: never crash the hub loop
        pass
    finally:
        await hub.disconnect(game_id, websocket)


async def _handle_inbound(
    websocket: WebSocket, game_id: uuid.UUID, player_id: uuid.UUID, raw: dict[str, Any]
) -> None:
    """Persist an inbound event (idempotent) and broadcast it; reply with errors as JSON."""
    try:
        client_event_id = uuid.UUID(str(raw["client_event_id"]))
        event_type = str(raw["type"])
        payload = raw.get("payload") or {}
    except (KeyError, ValueError, TypeError):
        await websocket.send_json({"kind": "error", "detail": "malformed event"})
        return

    # DB work is sync; run it without blocking the event loop unduly (fast, local).
    def _persist():
        db = SessionLocal()
        try:
            result = services.append_event(
                db,
                game_id=game_id,
                client_event_id=client_event_id,
                player_id=player_id,
                type_=event_type,
                payload=payload,
            )
            return _to_event_response(result.event), result.created
        finally:
            db.close()

    event_response, created = await asyncio.to_thread(_persist)

    # Broadcast on first persist only; idempotent replays still ack the sender with the
    # existing server_seq but don't re-broadcast to everyone.
    if created:
        await hub.broadcast(str(game_id), _event_message(event_response))
    else:
        await websocket.send_json(
            {"kind": "ack", "duplicate": True, "event": event_response.model_dump(mode="json")}
        )


# Re-export for type users.
__all__ = ["router", "hub", "ConnectionManager", "broadcast_event", "EventSchema"]
