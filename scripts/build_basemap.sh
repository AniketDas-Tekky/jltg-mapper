#!/usr/bin/env bash
#
# build_basemap.sh — extract a Bay-Area / San Francisco basemap into a single
# PMTiles file for the offline MapLibre map.
#
# Output: frontend/public/basemap/bay-area.pmtiles  (git-ignored; large binary)
#
# Source / license
# ----------------
# Protomaps publishes a daily-built, OpenStreetMap-derived planet basemap in the
# PMTiles format. OSM data is © OpenStreetMap contributors, licensed ODbL 1.0
# (https://www.openstreetmap.org/copyright). The Protomaps basemap layers /
# schema are open (BSD-licensed). No tile-provider API token is required.
#
#   Build index: https://maps.protomaps.com/builds/
#   Format docs: https://docs.protomaps.com/pmtiles/
#
# Tooling: the `pmtiles` CLI (https://github.com/protomaps/go-pmtiles) can slice
# a bounding box out of the remote planet file over HTTP range requests without
# downloading the whole planet — only the tiles inside the bbox are fetched.
#
#   macOS:  brew install pmtiles
#   Go:     go install github.com/protomaps/go-pmtiles/pmtiles@latest
#
# Re-run only when the OSM extract needs refreshing (the bbox is stable).
set -euo pipefail

# --- config ---------------------------------------------------------------
# Bay-Area / SF bounding box (W,S,E,N). Generous enough to cover SF, the inner
# East Bay, the Peninsula and Marin so panning never hits empty tiles.
BBOX_W="${BBOX_W:--122.75}"
BBOX_S="${BBOX_S:-37.40}"
BBOX_E="${BBOX_E:--122.10}"
BBOX_N="${BBOX_N:-37.95}"

MAXZOOM="${MAXZOOM:-15}"

# A recent Protomaps planet build. Override PLANET_URL to pin a specific date.
PLANET_URL="${PLANET_URL:-https://build.protomaps.com/20240618.pmtiles}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${REPO_ROOT}/frontend/public/basemap"
OUT_FILE="${OUT_DIR}/bay-area.pmtiles"

mkdir -p "${OUT_DIR}"

if ! command -v pmtiles >/dev/null 2>&1; then
  echo "error: 'pmtiles' CLI not found." >&2
  echo "       Install it (brew install pmtiles  OR" >&2
  echo "       go install github.com/protomaps/go-pmtiles/pmtiles@latest) and re-run." >&2
  exit 1
fi

echo "Extracting Bay-Area bbox (${BBOX_W},${BBOX_S},${BBOX_E},${BBOX_N}) z0-${MAXZOOM}"
echo "  from ${PLANET_URL}"
echo "  -> ${OUT_FILE}"

# Slice the bbox straight out of the remote planet PMTiles (HTTP range reads).
pmtiles extract "${PLANET_URL}" "${OUT_FILE}" \
  --bbox="${BBOX_W},${BBOX_S},${BBOX_E},${BBOX_N}" \
  --maxzoom="${MAXZOOM}"

echo "Done. Verify with: pmtiles show \"${OUT_FILE}\""
echo "Note: ${OUT_FILE} is git-ignored (*.pmtiles) — do not commit it."
