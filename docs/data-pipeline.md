# Geo data pipeline

Build steps that turn the curated source lists in [../data/](../data/) into runtime assets used
by the deduction engine and the map. Everything here is **precomputed and checked in** so the
backend never runs heavy geometry on a request path. Scripts live under `scripts/` (Python +
Shapely). See [DESIGN.md](DESIGN.md) §4–5 for how these feed the app.

## Inputs (already in the repo)

- `data/valid-hiding-stations.geojson` — 193 station points (the candidate set).
- `data/*.geojson` — POI layers (hospitals, libraries, museums, golf-courses, consulates,
  dog-parks, mountains, aquariums, rail-stations, farmers-markets).
- `data/game-config.json` — borders, excluded areas/zips, hiding radius (¼ mi), question config.

## Outputs (generated)

| Asset | Produced by | Used for |
|---|---|---|
| `data/generated/sf-border.geojson` | `scripts/build_border.py` | Clipping zones; coastline/sea-level questions |
| `data/generated/hiding-zones.geojson` | `scripts/build_hiding_zones.py` | The shaded candidate zones; deduction geometry |
| `data/generated/voronoi/<layer>.geojson` | `scripts/build_voronoi.py` | Exact "nearest X" matching answers |
| `frontend/public/basemap/bay-area.pmtiles` | `scripts/build_basemap.sh` | Offline MapLibre basemap |

> Keep generated assets in `data/generated/` (separate from the hand-curated source files) so
> it's always clear what is authored vs derived.

## Step 1 — SF border polygon (`build_border.py`)

- Source the City & County of San Francisco land boundary (e.g. SF Open Data "City Lots" /
  official boundary, or OSM admin relation), reproject to WGS84.
- Subtract the rule-excluded areas so they can never appear as playable: Daly City / Brisbane
  (zips 94015, 94014, 94005), Alcatraz, the Farallones, and the SF-owned slivers of Angel /
  Alameda Islands. **Include** Treasure Island.
- Output a single (multi)polygon `sf-border.geojson`.

## Step 2 — Hiding zones (`build_hiding_zones.py`)

For each of the 193 stations:

1. Buffer the station point by **¼ mi**. Do the buffer in a metric CRS (e.g. EPSG:3857 or a
   local UTM/State-Plane zone) for an accurate radius, then reproject back to WGS84 — **do not**
   buffer in degrees.
2. **Intersect** the buffer with the SF border polygon → border-edge zones become semicircles
   (matching the rules' Bayshore example).
3. Carry the station's `objectid` / `name` / `primary_system` into the zone's properties so the
   deduction result can map zone IDs back to stations.

Output `hiding-zones.geojson` (a `FeatureCollection` of 193 polygons). **Validation:** 193
features, all within the SF bbox, every zone non-empty, edge zones strictly inside the border.

## Step 3 — Voronoi / nearest regions per POI layer (`build_voronoi.py`)

For each POI layer, compute the Voronoi diagram of its points (Shapely
`shapely.ops.voronoi_diagram`), **clipped to the SF border**. Each cell is tagged with the POI
it belongs to. This lets the deduction engine answer:

- **Matching** "is your nearest X the same as mine?" → a zone is consistent with *Yes* if it
  intersects the seeker's POI cell, with *No* if it intersects any other cell.
- It also accelerates **Measuring** "nearest X" distance lookups (find the cell, then the point).

Output one `voronoi/<layer>.geojson` per layer. Skip layers that aren't proximity-based
(parking-permit zones use the polygon map directly; photo questions aren't auto-deduced).

## Step 4 — Basemap PMTiles (`build_basemap.sh`)

- Extract a Bay-Area / SF bounding box from an OpenStreetMap source into a single **PMTiles**
  file (e.g. via the Protomaps `pmtiles extract` from a planet/region PMTiles, or `tippecanoe`
  + `pmtiles convert`).
- Serve it from the backend (or CDN); the service worker caches it so the map renders offline.
- No tile-provider API token required.

## Re-running

These scripts are deterministic and idempotent. When the source lists in `data/` change
(e.g. the owners update the Google Sheet and re-export), re-run Steps 1–3 and re-validate. The
basemap (Step 4) only needs rebuilding when the OSM extract is refreshed.

## Notes / caveats

- The Google Sheet is the source of truth for the POI lists; a few counts differ from the prose
  rules doc (the doc says "16 hills" / "36 dog parks"; the sheet currently has 19 / 33). The
  pipeline mirrors the sheet — see [../data/README.md](../data/README.md).
- Voronoi assumes a flat plane; cells near borders should be treated as approximate, consistent
  with the rules doc's own disclaimer on its Voronoi diagrams. The runtime can fall back to exact
  point-distance checks when a seeker/zone is close to a cell boundary.
