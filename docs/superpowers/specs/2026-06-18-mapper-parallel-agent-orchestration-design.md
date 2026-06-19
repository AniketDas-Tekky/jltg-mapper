# jltg-mapper — Parallel Agent Orchestration Plan

**Date:** 2026-06-18
**Scope:** How to execute the 10 existing Task Master tasks (`.taskmaster/tasks/tasks.json`)
using parallel Claude Code agents, with maximum safe concurrency and clean integration.
**Owner decisions:** 2-track parallelism (recommended); dispatch via **harness sub-agents**
(`Agent` tool with `isolation: "worktree"`) driven from a single orchestrator session.

> This document is the *orchestration* plan only. The per-task implementation detail
> (what code to write, file-by-file) already lives in the Task Master tasks and is **not**
> duplicated here — each agent reads its assigned task(s) from `.taskmaster/tasks/tasks.json`
> via `task-master show <id>`.

---

## 1. Why this shape

The 10 tasks form a fixed dependency graph. The safety property that makes parallelism
possible is **non-overlapping file scope** between concurrently-running agents. Map the tasks
onto directory-bounded tracks and the only cross-track dependencies become **data/contract**
dependencies (one track writes files, another reads them) rather than same-file edits — which
are the source of merge pain.

### Dependency graph (from tasks.json)

```
1 (dev-env)
├── 2 (geo: border + zones) ──→ 3 (geo: voronoi + basemap) ┐
└── 4 (db models) → 5 (reducer) → 6 (REST API) → 7 (WS hub) │
                          └────────────────┐                │
                                     8 (deduction)  ← needs 3 + 5
                                                     9 (frontend map) ← needs 3 + 7 → 10 (game UI)
```

| Task | Title | Deps | Primary files |
|---|---|---|---|
| 1 | Dev env (Makefile + Docker Compose) | — | `Makefile`, `docker-compose.yml`, `README.md` |
| 2 | Geo: SF border + hiding zones | 1 | `scripts/build_border.py`, `scripts/build_hiding_zones.py`, `data/generated/` |
| 3 | Geo: Voronoi + basemap | 2 | `scripts/build_voronoi.py`, `scripts/build_basemap.sh`, `data/generated/voronoi/`, `frontend/public/basemap/` |
| 4 | Backend DB models + Alembic | 1 | `backend/app/db.py`, `models.py`, `backend/alembic/` |
| 5 | Backend event schemas + reducer | 4 | `backend/app/schemas.py`, `reducer.py` |
| 6 | Backend REST API + auth | 5 | `backend/app/api/`, `main.py` |
| 7 | Backend WebSocket hub | 6 | `backend/app/websocket.py`, `main.py` |
| 8 | Deduction engine | 3, 5 | `backend/app/deduction.py`, `reducer.py` |
| 9 | Frontend map foundation | 3, 7 | `frontend/src/lib/`, `frontend/src/components/Map.tsx` |
| 10 | Frontend game flow UI | 9 | `frontend/src/pages/` |

### Conflict surface (why the track boundaries are where they are)

- `backend/app/reducer.py` is edited by **5** *and* **8** → both must be owned by the **same** agent.
- `backend/app/main.py` is edited by **6** *and* **7** (router + ws endpoint registration) → same agent.
- Geo (`scripts/` + `data/generated/`) shares **no source files** with backend or frontend.
- Frontend (`frontend/src/`) shares no source files with backend; it consumes geo's generated
  assets (`data/generated/hiding-zones.geojson`, `frontend/public/basemap/*.pmtiles`) and the
  backend's REST/WS contract.

Keeping each shared file owned by exactly one agent eliminates all *in-flight* merge conflicts.

---

## 2. Track decomposition

| Track | Owns (write scope) | Tasks | Internal order | Reads from other tracks |
|---|---|---|---|---|
| **G — geo** | `scripts/`, `data/generated/` | 2, 3 | 2 → 3 | — |
| **B — backend** | `backend/app/`, `backend/alembic/` | 4, 5, 6, 7, 8 | 4 → 5 → 6 → 7 → 8 | G's `data/generated/voronoi/` + `hiding-zones.geojson` (for 8) |
| **F — frontend** | `frontend/src/`, `frontend/public/basemap/` | 9, 10 | 9 → 10 | G's generated assets; B's REST/WS contract |

**Task 8 lives inside Track B** (not split off) because it edits `reducer.py`, which Track B
already owns via task 5. Its dependency on geo (task 3) is satisfied by *merging Track G first*,
so the backend worktree contains `data/generated/` before task 8 runs.

---

## 3. Wave schedule (recommended: 2-track)

```
Wave 0   [Task 1] dev-env  ── solo, lands on main BEFORE any fan-out
                              (every sub-agent worktree must inherit Makefile /
                               docker-compose / .env, else each re-derives infra)
               │
         ┌─────┴──────┐
Wave 1   Agent G        Agent B          ← concurrent; zero source-file overlap
         2 → 3          4 → 5 → 6 → 7
               │              │
        merge G → main        │
               └──── rebase B on main ───┐
Wave 2                        Agent B continues → 8   (now sees data/generated/ from G)
                              merge B → main
                                    │
Wave 3                        Agent F (rebased on main = G + B): 9 → 10
                              merge F → main
```

**Critical path:** `1 → 4 → 5 → 6 → 7 → 9 → 10`. Geo (2→3) and deduction (8) overlap the
backend chain at no wall-clock cost. Frontend is deliberately last so it integrates against a
**real, running backend** rather than a mock — this matches the project's "keep the frontend
thin, owner is new to frontend" constraint (DESIGN.md §3), where reviewing F against live
endpoints is safer than against a contract guess.

### Concurrency mechanics

- **Wave 1** dispatches Agent G and Agent B *together* — launch both with `run_in_background: true`
  so they run in parallel; the orchestrator is notified as each completes.
- The orchestrator merges G → main as soon as G finishes, then tells Agent B (still running, or
  on its next step) to rebase before task 8 — OR, more simply, lets B finish 4→7, merges G, then
  dispatches task 8 as a short follow-up on a B worktree rebased on main.
- **Wave 3** is a single agent (9 → 10 are sequential and both in `frontend/`).

---

## 4. Dispatch model — harness sub-agents

Driven from **one orchestrator session**. Each track is an `Agent` tool call with
`isolation: "worktree"` so the agent works on an isolated copy and its branch can be merged back.

```
Agent(
  subagent_type: "general-purpose",
  isolation: "worktree",
  run_in_background: true,           # for Wave-1 concurrency
  description: "<track> track",
  prompt: <per-track prompt, see §5>
)
```

- The agent's final message returns to the orchestrator (not the user) — it should end with a
  crisp status: tasks completed, tests run + result, branch name, any follow-ups.
- Worktrees are auto-cleaned if unchanged; a track that produced commits leaves its branch for
  the orchestrator to merge.
- **Manual fallback** (if you'd rather drive sessions by hand): `scripts/worktree.sh new geo`
  / `backend` / `frontend` creates `agent/<name>` branches with isolated `.venv`/`node_modules`
  and a copied `.env`; open a Claude Code session per worktree and run dev servers on distinct
  ports (backend `8001`, frontend `5174`).

### Orchestrator loop

1. **Wave 0:** run task 1 (yourself or a solo sub-agent), verify `make install && make db-up &&
   make dev` work, merge to `main`.
2. **Wave 1:** dispatch Agent G and Agent B in background. Wait for both.
3. **Integrate G:** review, merge `agent/geo` → `main`.
4. **Wave 2:** ensure B's worktree is rebased on `main` (so `data/generated/` exists), have B
   run task 8. Review, merge `agent/backend` → `main`.
5. **Freeze the contract** (§6) from the merged backend.
6. **Wave 3:** dispatch Agent F on a worktree rebased on `main`. Review, merge → `main`.
7. After each track merges, flip its Task Master statuses: `task-master set-status --id=<n> --status=done`.

---

## 5. Per-agent contracts

Each agent gets: its task IDs, its write scope, its definition of done, and an instruction to
**read the task detail from Task Master** rather than re-deriving it. Definition of done for
every task = its own `testStrategy` passes **and** `make lint` is clean.

### Agent G — geo (Wave 1)

> You own the **geo data pipeline**. Implement Task Master tasks **2 then 3** (run
> `task-master show 2` and `task-master show 3` for full detail). Write **only** under
> `scripts/` and `data/generated/` (and `frontend/public/basemap/` for the basemap output in
> task 3). Do not touch `backend/` or `frontend/src/`.
> Definition of done: both tasks' `testStrategy` pass (193 hiding zones validated; Voronoi
> layers cover the SF border; basemap is a valid PMTiles file), `make lint` clean. End your
> final message with: tasks done, validation output, branch name.

### Agent B — backend (Wave 1 → Wave 2)

> You own the **backend** (`backend/app/`, `backend/alembic/`). Implement Task Master tasks
> **4 → 5 → 6 → 7** in order now (`task-master show <id>`). **Stop before task 8** and report —
> task 8 needs the geo assets to be merged first. Write only under `backend/`.
> Definition of done for this wave: migrations apply on a fresh Postgres; reducer unit tests
> pass; REST endpoints pass their httpx tests (incl. idempotency + 401); WS broadcast
> integration test passes; `make lint` clean. End with: tasks 4–7 done, test output, branch name.
>
> **Wave-2 follow-up (after geo is merged + you're rebased on main):** implement task **8**
> (deduction engine). It reads `data/generated/voronoi/*` and `hiding-zones.geojson` and
> integrates `filter_zones` into the `question_answered` handler in `reducer.py`. Done =
> golden-case deduction tests from `JETLAG-HIDE-AND-SEEK-RULES.md` pass; `make lint` clean.

### Agent F — frontend (Wave 3)

> You own the **frontend** (`frontend/src/`). Your worktree is rebased on `main`, which already
> contains the geo assets and a running backend (REST + WS). Implement Task Master tasks
> **9 → 10** in order (`task-master show <id>`). Integrate against the **real** backend on
> `localhost:8000` and the contract note at `docs/superpowers/specs/contract-freeze.md`. Write
> only under `frontend/`.
> Definition of done: map renders the basemap + 193 hiding zones with working POI toggles;
> Dexie event log + WS sync reconcile after a simulated offline period; full game flow
> (join → hide → ask → answer → zones shrink → scoreboard) works end-to-end across two browser
> windows; `make lint` clean.

---

## 6. Contract freeze (published when Track B merges)

Before dispatching Agent F, write `docs/superpowers/specs/contract-freeze.md` capturing the
stable interface from the merged backend, lifted from DESIGN.md §6–7:

- **Event types** and their payload shapes (`game_created`, `player_joined`, `role_assigned`,
  `hiding_started`, `question_asked` {category, subtype, seeker_location, asked_by},
  `question_answered`, `zone_excluded`/`zone_restored`, `curse_logged`, `note_added`,
  `game_paused`/`game_resumed`, `round_ended`, `role_rotated`).
- **REST**: `POST /api/games`, `POST /api/games/{code}/join`, `GET /api/games/{id}/state`,
  `GET /api/games/{id}/events?since_seq=N`, `POST /api/games/{id}/events` — request/response
  schemas + auth (bearer token) + status codes (incl. 409 on duplicate `client_event_id`).
- **WebSocket**: `/ws/{game_id}?token=…`, the on-connect state message, and the
  `{event, server_seq}` broadcast frame.

This is the seam the frontend reducer (a TS port of `reducer.py` + `deduction.py`) targets.

---

## 7. Integration & merge order

Linear, each track lands as a unit:

```
main ← [1 dev-env] ← [G geo] ← [B backend, rebased on G] ← [F frontend, rebased on G+B]
```

- Merge **G before B's task 8** so the backend worktree contains `data/generated/`.
- Merge **B before F** so the frontend integrates against real endpoints.
- Rebase (not merge-commit) each track onto the latest `main` before it merges, to keep history
  linear and surface any (rare) cross-track drift early.
- After each merge: run `make test && make lint` on `main` as a gate before the next wave.

---

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Task 1 not merged before fan-out → every worktree re-derives infra, conflicting `Makefile`/`docker-compose` | Wave 0 is a hard gate; nothing dispatches until task 1 is on `main`. |
| Geo assets large (PMTiles basemap) bloating git | Task 3 already `.gitignore`s `*.pmtiles`; the orchestrator regenerates via `make data` / `build_basemap.sh` rather than merging the binary. Frontend agent runs the basemap build locally. |
| Task 8's `reducer.py` edit conflicting with task 5 | Eliminated by design — same agent owns both. |
| Frontend built against a contract that later shifts | Frontend is Wave 3, after the contract freeze (§6) from a merged, tested backend. |
| Sub-agent worktree auto-cleaned before merge | Ensure each agent commits its work; an unchanged worktree means the agent did nothing — investigate rather than merge. |

---

## 9. Opt-in: aggressive 3-track (faster, more rework risk)

If you want to compress wall-clock, run **Agent F in Wave 1** alongside G and B, building the
map shell / Dexie / store / TS-reducer against the **documented event contract** (DESIGN.md
§6–7) and a mocked WS, then integrate against the real backend in a Wave-3 reconciliation pass.
Saves roughly the backend chain's length on the critical path, at the cost of: (a) rework when
the real contract differs from the guess, and (b) reviewing frontend work before there's a live
backend to click through. **Not recommended** given the thin-frontend / new-to-frontend
constraint, but available.

---

## 10. Fully-serial fallback

If parallel coordination overhead isn't worth it for a given session, run the dependency-ordered
sequence in one agent: `1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10`. Same DoD per task. This is the
zero-merge, zero-coordination baseline; the 2-track plan above trades a little coordination for
overlapping the geo + backend chains.
