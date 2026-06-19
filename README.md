# jltg-mapper

A companion app for the **San Francisco Small-Game homebrew** variant of *Jet Lag: The Game —
Hide & Seek*. It gives seekers a live map that tracks the **remaining valid hiding zones**
(auto-eliminating them as the hider answers questions) with toggleable points-of-interest
layers, lets hiders answer questions, and keeps game state synced across phones through patchy
transit connectivity.

> Cards, curses, and coins stay physical — the app models the map, questions, deduction, timer,
> and scoreboard.

## Docs

- [docs/DESIGN.md](docs/DESIGN.md) — architecture, tech stack, deduction engine, sync model.
- [docs/data-pipeline.md](docs/data-pipeline.md) — how the geo assets are built.
- [JETLAG-HIDE-AND-SEEK-RULES.md](JETLAG-HIDE-AND-SEEK-RULES.md) — rules summary (incl. §8 SF variant).
- [data/README.md](data/README.md) — the curated SF data layers.

## Repo layout

```
backend/    FastAPI app, deduction engine (Python + Shapely)
frontend/   React + Vite PWA (MapLibre)
scripts/    geo-data build scripts
data/        curated GeoJSON layers + game-config.json
docs/        design & pipeline docs
```

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python tooling)
- Node 22 LTS + [pnpm](https://pnpm.io/) (managed via [Volta](https://volta.sh/))
- [Docker](https://docs.docker.com/get-docker/) (local Postgres via Compose)

## Quick start

The root `Makefile` wraps the common backend (`uv`) + frontend (`pnpm`) + database
(Docker) workflows. Run `make help` to list every target.

```bash
make install      # backend deps (uv sync) + frontend deps (pnpm install)
cp backend/.env.example backend/.env
make db-up        # start local Postgres in Docker (jltg/jltg/jltg on :5432)
make migrate      # apply DB migrations (once alembic is configured)
make dev          # run backend (:8000) + frontend (:5173) together
```

Prefer running things by hand? The underlying commands still work:

```bash
# Backend
cd backend
uv sync
uv run uvicorn app.main:app --reload   # http://localhost:8000

# Frontend (separate terminal)
cd frontend
pnpm install
pnpm dev                                # http://localhost:5173
```

## Make targets

| Target          | What it does                                                        |
|-----------------|---------------------------------------------------------------------|
| `make install`  | Install backend (`uv sync`) and frontend (`pnpm install`) deps.     |
| `make dev`      | Run backend + frontend dev servers together (Ctrl-C stops both).    |
| `make backend`  | Run the backend dev server (`uvicorn --reload`, :8000).             |
| `make frontend` | Run the frontend dev server (`vite`, :5173).                        |
| `make db-up`    | Start local Postgres 16 in Docker (`jltg-postgres`, :5432).         |
| `make db-down`  | Stop local Postgres (keeps the named data volume).                  |
| `make migrate`  | Apply Alembic migrations (no-op until `backend/alembic.ini` exists).|
| `make test`     | Run backend tests (`pytest`).                                       |
| `make lint`     | Lint backend (`ruff`) and frontend (`eslint`).                      |
| `make build`    | Build the frontend production bundle.                               |
| `make data`     | Build geo-data assets (no-op until `scripts/build_*` exist).        |

Local Postgres is defined in [`docker-compose.yml`](docker-compose.yml) and persists to a
named volume (`jltg-postgres-data`). The backend's `JLTG_DATABASE_URL` in
`backend/.env.example` already points at it.
