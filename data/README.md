# SF Hide & Seek — Structured Data

Machine-readable data for the San Francisco Small-Game homebrew variant, extracted from the
companion [Google Sheet](https://docs.google.com/spreadsheets/d/1VyhjPUGxNSybxBV7yFSEECI9sKcdJOME2TpFpAaXpok/edit)
and [rules doc](https://docs.google.com/document/d/17xUTygVHs2I1ohq7xvBnkbqEZYaWY5ZM7zHXJmdUIgs/edit).
Prose summary lives in [../JETLAG-HIDE-AND-SEEK-RULES.md](../JETLAG-HIDE-AND-SEEK-RULES.md) §8.

## GeoJSON point layers

All are `FeatureCollection`s of `Point` features with `[lon, lat]` coordinates (WGS84) and
descriptive `properties`. Drop straight into Leaflet / Mapbox / MapLibre.

| File | Features | Used by |
|------|----------|---------|
| `valid-hiding-stations.geojson` | 193 | Where the hider may end (¼-mi zones). Props: `name`, `stopid`, `primary_system`, `associated_lines`, `other_systems`, `notes` |
| `rail-stations.geojson` | 35 | Measuring → "Rail Station" (BART/Caltrain + select Muni Metro) |
| `mountains.geojson` | 19 | Matching/Measuring → "Mountain" (hills >400 ft). Props include `height` |
| `dog-parks.geojson` | 33 | Matching/Measuring → "Park" |
| `aquariums.geojson` | 2 | Measuring → "Aquarium" (Matching aquarium is disabled — too powerful) |
| `golf-courses.geojson` | 8 | Matching/Measuring → "Golf Course" |
| `museums.geojson` | 49 | Matching/Measuring → "Museum". Props: `name`, `address` |
| `movie-theaters.geojson` | 17 | Matching/Measuring → "Movie Theater" |
| `libraries.geojson` | 29 | Matching/Measuring → "Library" (28 SFPL branches + TI kiosk) |
| `hospitals.geojson` | 16 | Matching/Measuring → "Hospital" |
| `consulates.geojson` | 38 | Matching/Measuring → "Foreign Consulate". Props: `name` (country), `address` |
| `farmers-markets.geojson` | 17 | Homebrew Matching → "Farmers Market". Props: `dotw` (day of week) |

## Config / reference JSON

| File | Contents |
|------|----------|
| `game-config.json` | Borders, start point, hiding period/radius, landmasses, per-category question lists (active / modified / removed / homebrew), curses |
| `transit-modes.json` | Allowed vs forbidden transit |
| `parking-permit-zones.json` | Homebrew Matching permit-color question: color → zone-letter mapping |

## Notes

- The **Google Sheet is the source of truth.** A few counts differ from the prose rules doc
  (e.g. the doc says "16 hills" / "36 dog parks" while the sheet currently lists 19 / 33). The
  data here mirrors the sheet as extracted.
- Markdown escapes from the export (`\_`, `\-`, `\&`) were stripped; coordinates validated to
  fall within the SF bounding box.
- Not extracted (working/source tabs, not game-rule lists): the raw SFMTA stop dump and an
  incomplete hiding-spot scouting list with subjective ratings.
- To refresh, re-export the sheet and re-run the extraction (see git history / the generation
  step that produced these files).
