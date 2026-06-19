"""WebSocket hub integration tests (require Postgres; skipped if unreachable).

Uses Starlette's TestClient WebSocket support, which drives the same ASGI app and the same
``hub`` / ``services.append_event`` write path as production.
"""

from __future__ import annotations

import uuid

from tests.conftest import requires_db


def _create_game(client, host_name="Host"):
    resp = client.post("/api/games", json={"host_name": host_name})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _join(client, join_code, name="Seeker", role="seeker"):
    resp = client.post(f"/api/games/{join_code}/join", json={"name": name, "role": role})
    assert resp.status_code == 201, resp.text
    return resp.json()


@requires_db
def test_connect_receives_state_snapshot(app_client):
    game = _create_game(app_client)
    url = f"/ws/{game['game_id']}?token={game['token']}"
    with app_client.websocket_connect(url) as ws:
        msg = ws.receive_json()
        assert msg["kind"] == "state"
        assert msg["last_seq"] >= 2
        assert len(msg["state"]["remaining_zone_ids"]) == 193


@requires_db
def test_invalid_token_rejected(app_client):
    game = _create_game(app_client)
    url = f"/ws/{game['game_id']}?token=bogus"
    import pytest
    from starlette.websockets import WebSocketDisconnect

    # The server closes before accept(); the TestClient surfaces this as a disconnect
    # either at connect time or on first receive.
    with pytest.raises(WebSocketDisconnect):
        with app_client.websocket_connect(url) as ws:
            ws.receive_json()
            ws.receive_json()


@requires_db
def test_send_event_broadcasts_to_self(app_client):
    game = _create_game(app_client)
    url = f"/ws/{game['game_id']}?token={game['token']}"
    with app_client.websocket_connect(url) as ws:
        ws.receive_json()  # state snapshot
        ws.send_json({
            "client_event_id": str(uuid.uuid4()),
            "type": "zone_excluded",
            "payload": {"zone_id": 9},
        })
        msg = ws.receive_json()
        assert msg["kind"] == "event"
        assert msg["event"]["type"] == "zone_excluded"
        assert msg["event"]["server_seq"] >= 3


@requires_db
def test_multi_client_broadcast(app_client):
    game = _create_game(app_client)
    seeker = _join(app_client, game["join_code"], name="Seeker", role="seeker")

    host_url = f"/ws/{game['game_id']}?token={game['token']}"
    seeker_url = f"/ws/{game['game_id']}?token={seeker['token']}"

    with app_client.websocket_connect(host_url) as host_ws, \
            app_client.websocket_connect(seeker_url) as seeker_ws:
        host_ws.receive_json()    # state
        seeker_ws.receive_json()  # state

        host_ws.send_json({
            "client_event_id": str(uuid.uuid4()),
            "type": "note_added",
            "payload": {"text": "broadcast me"},
        })

        host_msg = host_ws.receive_json()
        seeker_msg = seeker_ws.receive_json()
        assert host_msg["kind"] == "event"
        assert seeker_msg["kind"] == "event"
        assert host_msg["event"]["server_seq"] == seeker_msg["event"]["server_seq"]
        assert seeker_msg["event"]["payload"]["text"] == "broadcast me"


@requires_db
def test_idempotent_duplicate_acks_without_rebroadcast(app_client):
    game = _create_game(app_client)
    url = f"/ws/{game['game_id']}?token={game['token']}"
    ceid = str(uuid.uuid4())
    with app_client.websocket_connect(url) as ws:
        ws.receive_json()  # state
        ws.send_json({"client_event_id": ceid, "type": "zone_excluded", "payload": {"zone_id": 1}})
        first = ws.receive_json()
        assert first["kind"] == "event"

        # Same client_event_id again -> ack with duplicate flag, no new server_seq.
        ws.send_json({"client_event_id": ceid, "type": "zone_excluded", "payload": {"zone_id": 1}})
        dup = ws.receive_json()
        assert dup["kind"] == "ack"
        assert dup["duplicate"] is True
        assert dup["event"]["server_seq"] == first["event"]["server_seq"]
