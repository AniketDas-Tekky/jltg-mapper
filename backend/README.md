# jltg-mapper backend

FastAPI + SQLAlchemy + Shapely. Hosts the game/event API, WebSocket sync hub, and the
deduction engine. See [../docs/DESIGN.md](../docs/DESIGN.md).

## Develop

```bash
uv sync                                   # install deps into .venv
cp .env.example .env                      # configure (Postgres URL, CORS)

# database (needs Postgres — `make db-up` from the repo root)
uv run alembic upgrade head               # apply migrations
uv run alembic downgrade -1               # roll back one
uv run alembic revision --autogenerate -m "msg"

uv run uvicorn app.main:app --reload      # http://localhost:8000  (/health, /docs)

uv run pytest                             # tests (DB tests skip if Postgres is down)
uv run ruff check .                       # lint
```

## Layout

```
app/
  main.py       FastAPI entrypoint (CORS, REST routers, WS hub)
  config.py     settings (env-driven, JLTG_ prefix)
  db.py         SQLAlchemy engine / session / get_db dependency
  models.py     ORM models: Game, Player, Event, DerivedState
  schemas.py    Pydantic v2 event payloads + GameState + API DTOs
  reducer.py    pure reduce_events(); deduction hook seam for task 8
  services.py   shared write path (idempotent append, server_seq)
  api/
    auth.py     bearer-token auth dependency
    games.py    POST /api/games, POST /api/games/{code}/join
    events.py   GET state, GET/POST events (idempotent, 409 on dup)
  websocket.py  /ws/{game_id} hub: ConnectionManager + broadcast
alembic/        migration environment + versions/
tests/          pytest (reducer is pure; api/ws/migrations need Postgres)
```

## Event sourcing

State is derived by folding the append-only `events` log through the pure
`reduce_events()` reducer. Zone elimination on `question_answered` is delegated to a
pluggable **deduction hook** (currently a no-op stub) so task 8's geometry engine can
plug in without touching the reducer. See the `--- DEDUCTION SEAM ---` marker in
`app/reducer.py`.
