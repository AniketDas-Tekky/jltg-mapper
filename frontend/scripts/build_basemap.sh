#!/usr/bin/env bash
#
# build_basemap.sh — fetch / build the PMTiles basemap for the SF map.
#
# The basemap is a large (~tens of MB) vector-tile archive and is intentionally NOT checked
# into git (see frontend/.gitignore). The app renders fine without it (blank dark base);
# running this script makes the basemap "light up".
#
# Output: frontend/public/basemap/sf.pmtiles
#
# Two options:
#
# 1) Download a prebuilt Protomaps "basemaps" extract for the SF bounding box (fastest):
#
#      pmtiles extract \
#        https://build.protomaps.com/20240101.pmtiles \
#        frontend/public/basemap/sf.pmtiles \
#        --bbox=-122.55,37.70,-122.35,37.84
#
#    (`pmtiles` CLI: https://github.com/protomaps/go-pmtiles — `brew install pmtiles`.)
#
# 2) Build from an OSM .osm.pbf with tilemaker / planetiler, then convert MBTiles->PMTiles:
#
#      planetiler --download --area=san-francisco --output=sf.mbtiles
#      pmtiles convert sf.mbtiles frontend/public/basemap/sf.pmtiles
#
# After it exists, basemap.ts's HEAD probe finds it and switches to the vector style. If you
# use a non-Protomaps tile schema, adjust the `source-layer` names in basemap.ts.

set -euo pipefail

OUT_DIR="$(cd "$(dirname "$0")/.." && pwd)/public/basemap"
OUT="$OUT_DIR/sf.pmtiles"
mkdir -p "$OUT_DIR"

if ! command -v pmtiles >/dev/null 2>&1; then
  echo "error: 'pmtiles' CLI not found. Install via 'brew install pmtiles' or see" >&2
  echo "       https://github.com/protomaps/go-pmtiles" >&2
  exit 1
fi

echo "Extracting SF bbox from the Protomaps daily build into $OUT ..."
pmtiles extract \
  "https://build.protomaps.com/20240101.pmtiles" \
  "$OUT" \
  --bbox=-122.55,37.70,-122.35,37.84

echo "Done: $OUT"
