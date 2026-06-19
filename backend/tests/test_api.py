"""REST API integration tests (require Postgres; skipped if unreachable)."""

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
def test_create_game_returns_code_and_token(app_client):
    data = _create_game(app_client)
    assert "join_code" in data and len(data["join_code"]) == 6
    assert data["token"]
    assert data["game_id"]
    assert data["player_id"]


@requires_db
def test_join_game_creates_player(app_client):
    game = _create_game(app_client)
    joined = _join(app_client, game["join_code"], name="Ada", role="hider")
    assert joined["role"] == "hider"
    assert joined["token"] != game["token"]
    assert joined["game_id"] == game["game_id"]


@requires_db
def test_join_unknown_code_404(app_client):
    resp = app_client.post("/api/games/ZZZZZZ/join", json={"name": "X", "role": "seeker"})
    assert resp.status_code == 404


@requires_db
def test_get_state_requires_auth(app_client):
    game = _create_game(app_client)
    # No token -> 401
    resp = app_client.get(f"/api/games/{game['game_id']}/state")
    assert resp.status_code == 401

    # Invalid token -> 401
    resp = app_client.get(
        f"/api/games/{game['game_id']}/state",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert resp.status_code == 401


@requires_db
def test_get_state_with_valid_token(app_client):
    game = _create_game(app_client)
    headers = {"Authorization": f"Bearer {game['token']}"}
    resp = app_client.get(f"/api/games/{game['game_id']}/state", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # game_created + player_joined were appended at creation.
    assert body["last_seq"] >= 2
    assert len(body["state"]["remaining_zone_ids"]) == 193


@requires_db
def test_post_event_assigns_monotonic_seq(app_client):
    game = _create_game(app_client)
    headers = {"Authorization": f"Bearer {game['token']}"}
    seqs = []
    for zone_id in (10, 11, 12):
        resp = app_client.post(
            f"/api/games/{game['game_id']}/events",
            headers=headers,
            json={
                "client_event_id": str(uuid.uuid4()),
                "type": "zone_excluded",
                "payload": {"zone_id": zone_id},
            },
        )
        assert resp.status_code == 201, resp.text
        seqs.append(resp.json()["server_seq"])
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == 3  # strictly increasing / unique


@requires_db
def test_duplicate_client_event_id_409(app_client):
    game = _create_game(app_client)
    headers = {"Authorization": f"Bearer {game['token']}"}
    ceid = str(uuid.uuid4())
    body = {"client_event_id": ceid, "type": "zone_excluded", "payload": {"zone_id": 5}}

    first = app_client.post(f"/api/games/{game['game_id']}/events", headers=headers, json=body)
    assert first.status_code == 201

    dup = app_client.post(f"/api/games/{game['game_id']}/events", headers=headers, json=body)
    assert dup.status_code == 409
    assert dup.json()["detail"]["server_seq"] == first.json()["server_seq"]


@requires_db
def test_post_event_updates_derived_state(app_client):
    game = _create_game(app_client)
    headers = {"Authorization": f"Bearer {game['token']}"}
    app_client.post(
        f"/api/games/{game['game_id']}/events",
        headers=headers,
        json={
            "client_event_id": str(uuid.uuid4()),
            "type": "zone_excluded",
            "payload": {"zone_id": 42},
        },
    )
    state = app_client.get(f"/api/games/{game['game_id']}/state", headers=headers).json()
    assert 42 not in state["state"]["remaining_zone_ids"]
    assert len(state["state"]["remaining_zone_ids"]) == 192


@requires_db
def test_get_events_since_seq(app_client):
    game = _create_game(app_client)
    headers = {"Authorization": f"Bearer {game['token']}"}
    app_client.post(
        f"/api/games/{game['game_id']}/events",
        headers=headers,
        json={
            "client_event_id": str(uuid.uuid4()),
            "type": "note_added",
            "payload": {"text": "hi"},
        },
    )
    resp = app_client.get(f"/api/games/{game['game_id']}/events?since_seq=2", headers=headers)
    assert resp.status_code == 200
    events = resp.json()
    assert all(e["server_seq"] > 2 for e in events)
    assert any(e["type"] == "note_added" for e in events)
