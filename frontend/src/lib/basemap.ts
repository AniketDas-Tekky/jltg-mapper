/**
 * Basemap bootstrap with graceful fallback.
 *
 * The real basemap is a PMTiles vector tile archive (`public/basemap/sf.pmtiles`) that is a
 * large, gitignored download (see `scripts/build_basemap.sh`). It is NOT present by default.
 *
 * `resolveBaseStyle()` probes for the file:
 *   - if present  -> registers the `pmtiles://` protocol and returns a vector style that
 *                    draws land/water/roads from the archive.
 *   - if absent   -> returns a minimal blank style (just a dark background) so the hiding
 *                    zones + POI overlays still render legibly over nothing.
 *
 * Either way the app works; the basemap simply "lights up" once the file exists.
 */

import maplibregl, { type StyleSpecification } from 'maplibre-gl';
import { Protocol } from 'pmtiles';
import { BASEMAP_URL } from './layers';

let protocolRegistered = false;

function registerPmtilesProtocol(): void {
  if (protocolRegistered) return;
  const protocol = new Protocol();
  maplibregl.addProtocol('pmtiles', protocol.tile);
  protocolRegistered = true;
}

/** Minimal style used when no PMTiles basemap is available. */
function blankStyle(): StyleSpecification {
  return {
    version: 8,
    sources: {},
    glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
    layers: [
      {
        id: 'background',
        type: 'background',
        paint: { 'background-color': '#0b1220' },
      },
    ],
  };
}

/** Vector style that reads from the PMTiles archive (protomaps "basemaps" schema). */
function pmtilesStyle(): StyleSpecification {
  return {
    version: 8,
    glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
    sources: {
      basemap: {
        type: 'vector',
        url: `pmtiles://${BASEMAP_URL}`,
        attribution: '© OpenStreetMap contributors',
      },
    },
    layers: [
      { id: 'background', type: 'background', paint: { 'background-color': '#0b1220' } },
      {
        id: 'water',
        type: 'fill',
        source: 'basemap',
        'source-layer': 'water',
        paint: { 'fill-color': '#11203b' },
      },
      {
        id: 'landuse',
        type: 'fill',
        source: 'basemap',
        'source-layer': 'landuse',
        paint: { 'fill-color': '#0f1a2e', 'fill-opacity': 0.6 },
      },
      {
        id: 'roads',
        type: 'line',
        source: 'basemap',
        'source-layer': 'roads',
        paint: { 'line-color': '#1e2d4a', 'line-width': 0.6 },
      },
    ],
  };
}

/**
 * Resolve the base style. Performs a lightweight HEAD probe for the PMTiles file; falls back
 * to the blank style on any failure (missing file, network, CORS).
 */
export async function resolveBaseStyle(): Promise<StyleSpecification> {
  try {
    const res = await fetch(BASEMAP_URL, { method: 'HEAD' });
    if (res.ok) {
      registerPmtilesProtocol();
      return pmtilesStyle();
    }
  } catch {
    /* fall through to blank */
  }
  return blankStyle();
}
