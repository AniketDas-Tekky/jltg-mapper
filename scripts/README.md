# scripts/

Geo-data build scripts that turn the curated source lists in [../data/](../data/) into the
runtime assets used by the deduction engine and the map. See
[../docs/data-pipeline.md](../docs/data-pipeline.md) for the full pipeline.

Planned (not yet implemented):

- `build_border.py` — SF border polygon (minus excluded areas).
- `build_hiding_zones.py` — ¼-mi hiding-zone polygons, clipped to the border.
- `build_voronoi.py` — per-POI Voronoi / nearest-region layers.
- `build_basemap.sh` — Bay-Area PMTiles basemap.

These reuse the backend's Shapely dependency; run them with `uv run` from `../backend` or a
shared tooling environment.
