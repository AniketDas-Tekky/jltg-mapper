# scripts/

Geo-data build scripts that turn the curated source lists in [../data/](../data/) into the
runtime assets used by the deduction engine and the map. See
[../docs/data-pipeline.md](../docs/data-pipeline.md) for the full pipeline.

## What each script produces

| Script | Output | Notes |
|---|---|---|
| `build_border.py` | `data/generated/sf-border.geojson` | SF land border (incl. Treasure Island), minus excluded areas |
| `build_hiding_zones.py` | `data/generated/hiding-zones.geojson` | One ¼-mi zone per valid station, clipped to the border |
| `build_voronoi.py` | `data/generated/voronoi/<layer>.geojson` | Per-POI nearest-region cells, clipped to the border |
| `build_basemap.sh` | `frontend/public/basemap/bay-area.pmtiles` | Bay-Area PMTiles basemap (git-ignored, large) |

`build_hiding_zones.py` and `build_voronoi.py` depend on `sf-border.geojson`, so run
`build_border.py` first.

## Dependencies

These are **standalone** scripts — they do **not** reuse the backend env (the backend has
`shapely` but not `pyproj`, and we keep geo tooling out of the app deps). They buffer in a
metric CRS (**EPSG:26910**, NAD83 / UTM 10N) and output WGS84. Requires `shapely` 2.x +
`pyproj`.

The cleanest way to run them without polluting any project environment is with `uv run --with`:

```sh
uv run --with shapely,pyproj python scripts/build_border.py
uv run --with shapely,pyproj python scripts/build_hiding_zones.py
uv run --with shapely,pyproj python scripts/build_voronoi.py
```

(Or `uv venv scripts/.venv && uv pip install -r scripts/requirements.txt` for a persistent
env — see `scripts/requirements.txt`.)

## Basemap (PMTiles)

```sh
brew install pmtiles            # or: go install github.com/protomaps/go-pmtiles/pmtiles@latest
bash scripts/build_basemap.sh   # slices a Bay-Area bbox out of the Protomaps planet build
```

Output is OpenStreetMap-derived (© OpenStreetMap contributors, ODbL); no API token needed.
`*.pmtiles` is git-ignored — do not commit the binary.

## Tests

```sh
uv run --with shapely,pyproj,pytest pytest scripts/tests
```

The tests rebuild the assets and assert the invariants from `docs/data-pipeline.md`
(border validity, Treasure Island included, zone count == station count, edge zones clipped
inside the border, one Voronoi layer per proximity POI layer).

## Re-running

The Python scripts are deterministic and idempotent. Re-run steps 1–3 whenever the source
lists in `data/` change; rebuild the basemap (step 4) only when the OSM extract is refreshed.
