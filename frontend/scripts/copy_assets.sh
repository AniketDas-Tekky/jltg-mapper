#!/usr/bin/env bash
#
# copy_assets.sh — copy the generated geo assets from the repo `data/` dir into
# `frontend/public/data/` so Vite serves them statically.
#
# These copies are gitignored (regenerated from source). Run this after a fresh checkout
# or whenever the geo pipeline regenerates `data/generated/hiding-zones.geojson`.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DATA="$ROOT/data"
PUB="$(cd "$(dirname "$0")/.." && pwd)/public/data"

mkdir -p "$PUB/poi"

cp "$DATA/generated/hiding-zones.geojson" "$PUB/hiding-zones.geojson"
cp "$DATA/generated/sf-border.geojson" "$PUB/sf-border.geojson"

for f in consulates dog-parks libraries rail-stations museums hospitals \
         mountains golf-courses farmers-markets aquariums movie-theaters; do
  cp "$DATA/$f.geojson" "$PUB/poi/$f.geojson"
done

echo "Copied geo assets into $PUB"
