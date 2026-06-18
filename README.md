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

## Quick start

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
