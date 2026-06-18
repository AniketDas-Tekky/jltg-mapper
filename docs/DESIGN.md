# jltg-mapper — Design (v1)

A companion app for the **San Francisco Small-Game homebrew** variant of Jet Lag: Hide & Seek.
Rules and curated data already live in the repo:
[../JETLAG-HIDE-AND-SEEK-RULES.md](../JETLAG-HIDE-AND-SEEK-RULES.md),
[../data/](../data/) (`*.geojson`, `game-config.json`).

Cards / curses / coins stay physical; the app models the **map, questions, deduction, timer, and
scoreboard**.

---

## 1. Context & goals

**Primary user = seekers.** The core value is a live map that tracks the **remaining valid
hiding zones** and automatically eliminates zones as the hider answers questions, plus
toggleable POI layers (hospitals, libraries, museums, …) to help seekers decide what to ask.

**Hiders** use the app to answer questions; the app uses the hider's location to suggest/verify
the truthful answer.

Game state is **synced across all players' phones**, tolerates **intermittent connectivity**
(transit tunnels, dead zones), and survives **pause/resume across days**.

A **Discord integration** (chat + ask/answer from Discord) is a planned later phase; the API is
designed so Discord is "just another client."

### Decisions locked with the owner
| Area | Decision |
|---|---|
| Offline model | Intermittent connectivity. Each device works against a local copy and auto-syncs through the server on reconnect (optimistic, event-sourced). Same mechanism powers pause/resume. |
| Deduction | v1 auto-eliminates inconsistent zones after each answered question. |
| Delivery | Installable **PWA** (one React codebase; iOS/Android; geolocation + offline cache). |
| Hosting | Managed platform (**Fly.io** recommended) running FastAPI + Postgres. |
| Stack constraint | Owner is strong in Python, new to frontend → keep the hard logic (geometry, deduction, rules) in **Python on the backend**; keep the React frontend thin. |

---

## 2. Architecture overview

```
┌─────────────── Phone (PWA, React) ───────────────┐
│  MapLibre map + layer toggles + question UI       │
│  Local event log (IndexedDB) ── reducer ─► state  │
│  Outbox of unsynced actions                       │
└──────────────┬───────────────▲────────────────────┘
               │ WebSocket (+REST fallback)          │ broadcast
               ▼                                      │
┌─────────────────── FastAPI backend ───────────────────────┐
│  Game/event API · WebSocket hub · auth (game code+token)   │
│  Event store (append-only) ─► Deduction engine (Shapely)   │
│  Derived state cache (remaining zone ids + polygons)       │
└──────────────┬─────────────────────────────────────────────┘
               ▼
          Postgres   +   static geo assets (data/*.geojson, basemap PMTiles)
   (future) Discord bot  ──── same REST/WS API as any client
```

**Source of truth = a server-side append-only event log per game.** State (including the
deduction result) is a pure reduction over events. Clients keep their own copy of the log in
IndexedDB, reduce it to render offline, and reconcile with the server on reconnect.

---

## 3. Tech stack

### Backend (Python — owner's strength)
- **FastAPI + Uvicorn** — REST + native WebSockets.
- **PostgreSQL** + **SQLAlchemy / SQLModel** + **Alembic** migrations.
- **Pydantic** for event/payload schemas.
- **Shapely** (+ `rtree` / `STRtree` for nearest queries, `geojson` for I/O) for the deduction
  engine and the data-build scripts. Lighter than GeoPandas; add GeoPandas only if convenient.
- Auth: lightweight — join with a **game code**, receive a random **player token** (bearer).
  No accounts in v1.

### Frontend (kept deliberately thin)
- **React + Vite + TypeScript**.
- **MapLibre GL JS** (via `react-map-gl`) — vector rendering of the GeoJSON layers and zone
  shading. Free, no API token.
- **Protomaps PMTiles** basemap — a single Bay-Area file served from our backend/CDN and cached
  by the service worker → an **offline-capable basemap** with no tile-provider token.
- **Dexie** (IndexedDB) for the local event log + outbox.
- **vite-plugin-pwa** (Workbox) for installability + offline app shell + cached map assets/data.
- State: a small **Zustand** store fed by a pure **event reducer** (no Redux ceremony).
- **Tailwind CSS** for styling (beginner-friendly, no bespoke CSS system).
- Optional later: **Turf.js** for instant client-side deduction while offline.

**Why this split:** the geometry/rules — the genuinely hard part — live in Python where the
owner is productive. The frontend is mostly: render layers, capture geolocation, show questions,
reduce an event log.

---

## 4. Geo data pipeline

Precomputed, checked-in assets so the runtime never does heavy geometry on the fly. Build steps
are detailed in [data-pipeline.md](data-pipeline.md); they live under `scripts/`.

1. **`hiding-zones.geojson`** — ¼-mi buffer around each of the 193 stations, **clipped to the SF
   border** and minus excluded areas (Daly City / Brisbane, etc.) → border-edge zones become
   semicircles, exactly as the rules describe.
2. **Voronoi / nearest-region precompute per POI layer** (hospitals, libraries, museums, golf,
   consulates, dog parks, mountains, aquariums, rail stations, farmers markets) — enables fast,
   exact "nearest X" answers. The rules doc already ships Voronoi diagrams for several of these.
3. **SF border polygon** asset (city limits) used for clipping and coastline questions.
4. **Basemap PMTiles** for the Bay Area, cached client-side.

---

## 5. Deduction engine (server-side — the core)

Candidate set = the 193 hiding-zones. Each answered question is a **predicate** that keeps or
eliminates each candidate, evaluated against the **seeker's recorded location at ask-time** and
the static layers. A zone is kept if it is *possible* given the answer.

| Question type | Keep-zone predicate (vs seeker location `S`, answer `a`) |
|---|---|
| **Matching "nearest X"** | Keep zone if it intersects the Voronoi cell of `S`'s nearest X (answer Yes) / any other cell (answer No). |
| **Measuring "closer/further from X"** | `d_S = dist(S, nearest X)`. Keep if some point of the zone is closer than `d_S` (closer) / farther (further). |
| **Radar "within N of me"** | Keep if `dist(zone, S) ≤ N` (Yes) / the zone extends beyond `N` (No). |
| **Thermometer (moved A→B)** | Keep if the zone is nearer to `B` than `A` (hotter) / farther (colder). |
| **Rail Station / coastline / sea-level / water** | Same shape as measuring, against the relevant layer/feature. |
| **Photo / curses / homebrew untestable** | Not auto-deduced; seekers can **manually** exclude zones. |

- **v1 accuracy:** evaluate predicates against the **zone polygon** using the precomputed
  Voronoi / nearest regions (exact). A simpler **station-centroid approximation** is the
  documented fallback if any predicate is hard to get exact in time.
- **Where it runs:** server-side, triggered by each `question_answered` event; the result
  (`remaining_zone_ids` + a dissolved remaining-area polygon) is cached and broadcast. Given
  intermittent-but-mostly-online connectivity, clients show the last result and refresh on
  reconnect.
- **Offline-instant feedback (later):** port the predicates to **Turf.js** so the seeker's map
  updates immediately while offline; the server stays authoritative. Out of v1 scope.

---

## 6. Data model (Postgres)

| Table | Columns (essential) |
|---|---|
| `games` | id, join code, size, status (`setup`/`hiding`/`seeking`/`paused`/`ended`), timestamps |
| `players` | id, game_id, display name, role (`seeker`/`hider`/`spectator`), bearer token |
| `events` | id, game_id, **server seq** (monotonic), `client_event_id` (UUID, idempotency), player_id, type, `payload` (JSONB), created_at — **append-only** |
| `derived_state` (cache) | game_id, last_seq, remaining_zone_ids, remaining_area (GeoJSON), timers, scoreboard — rebuildable by replaying `events` |

### Event types (the whole game is these)
`game_created`, `player_joined`, `role_assigned`, `hiding_started`, `question_asked`
(category, subtype, **seeker_location**, asked_by), `question_answered` (answer, by hider),
`zone_excluded` / `zone_restored` (manual seeker override), `curse_logged`, `note_added`,
`game_paused` / `game_resumed`, `round_ended` (hider found + run time), `role_rotated`.

---

## 7. Sync protocol (intermittent connectivity)

1. Client actions append to a local **outbox** (Dexie) with a client-generated UUID and update
   local state optimistically via the reducer.
2. When connected, the client pushes outbox items over WebSocket (REST fallback). The server
   assigns the authoritative **seq**, persists, and **broadcasts** to the game's other clients.
   Idempotent on `client_event_id` (safe retries).
3. The client tracks `last_seq`; on reconnect it `GET events?since=last_seq`, appends, re-reduces.
4. **Conflict handling:** events are append-only and mostly commutative; the server `seq` defines
   total order. Last-write-wins matters only for manual zone overrides, resolved by latest seq.
5. **Pause/resume across days** uses the same flow: state is the event log; reopening the app
   replays the local log and syncs the gap. A `game_paused` event freezes timers.

---

## 8. Frontend screens (v1)

- **Join / lobby** — enter game code + name, pick role; host starts the game / hiding timer.
- **Seeker map** (primary) — basemap + **remaining hiding-zones** shaded; toggleable POI layers
  from `data/`; question composer (pick category/subtype, captures current geolocation); list of
  asked questions + answers; manual zone exclude/restore; run-time clock.
- **Hider view** — incoming questions to answer; the app uses the **hider's geolocation** to
  suggest/verify the truthful answer; hiding-zone confirmation at hide time.
- **Scoreboard** — run times across rotating hiders; leaderboard (longest time).

---

## 9. Repo structure

```
backend/    FastAPI app, models, deduction engine, ws hub, tests
frontend/   React PWA (Vite + TS)
scripts/    geo-data build (hiding zones, voronoi precompute)
data/       existing GeoJSON + game-config.json (+ generated assets)
docs/       DESIGN.md, data-pipeline.md
```

---

## 10. Deployment

**Fly.io**: the FastAPI app (persistent process → WebSockets) + **Fly Postgres** + a volume for
static geo / basemap assets. The frontend is built static and **served by FastAPI** for a single
deploy in v1 (can split to Cloudflare Pages later). Containerized (Dockerfile) so the host stays
swappable.

---

## 11. Discord (future phase — design-for-now)

A **discord.py** bot as a separate service that calls the same REST/WS API and authenticates as
a player. It posts new questions/answers to a channel and accepts slash commands to ask/answer.
This requires no backend changes beyond the existing event/API model — that's why the API is
transport-agnostic from day one.

---

## 12. Verification (of the eventual build)

- **Deduction:** Python unit tests feeding known seeker locations + answers and asserting the
  expected `remaining_zone_ids` (golden cases drawn from the rules doc's Voronoi examples — e.g.
  the Japantown / McLaren Park transit-line examples).
- **Sync:** simulate a client going offline, queuing actions, and reconnecting; assert
  convergence to the same reduced state on all clients (idempotent replays, no duplicates).
- **Data pipeline:** validate `hiding-zones.geojson` (193 zones, all within the SF bbox, edge
  zones clipped) and that every POI layer loads and renders.
- **End-to-end:** run backend + frontend locally, play a scripted mini-game (hide → ask a
  measuring question → answer → confirm zones shrink on the map); install the PWA on a phone and
  confirm geolocation + offline reload.

---

## 13. Deferred (not v1)

Client-side (Turf.js) instant offline deduction; the Discord bot; accounts / auth hardening;
spectator-mode polish; multi-game scale tuning.
