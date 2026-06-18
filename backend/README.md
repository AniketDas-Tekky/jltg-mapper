# jltg-mapper backend

FastAPI + SQLAlchemy + Shapely. Hosts the game/event API, WebSocket sync hub, and the
deduction engine. See [../docs/DESIGN.md](../docs/DESIGN.md).

## Develop

```bash
uv sync                                   # install deps into .venv
cp .env.example .env                      # configure (Postgres URL, CORS)
uv run uvicorn app.main:app --reload      # http://localhost:8000  (/health, /docs)

uv run pytest                             # tests
uv run ruff check .                       # lint
```

## Layout

```
app/
  main.py     FastAPI entrypoint (health check + CORS today)
  config.py   settings (env-driven, JLTG_ prefix)
tests/        pytest
```
