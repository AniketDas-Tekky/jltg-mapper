/**
 * The shared map view.
 *
 * Renders, from bottom to top:
 *   - a basemap (PMTiles vector tiles if available, else a blank dark background),
 *   - the SF border outline,
 *   - the 193 hiding zones, shaded by whether they survive in `remaining_zone_ids`,
 *   - any POI overlays toggled on in the sidebar.
 *
 * Includes a MapLibre geolocate + navigation control and a connectivity indicator. The base
 * style is resolved asynchronously (probe for the basemap) so we don't block first paint.
 */

import { useEffect, useMemo, useState } from 'react';
import Map, {
  GeolocateControl,
  Layer,
  NavigationControl,
  Source,
  type MapLayerMouseEvent,
} from 'react-map-gl/maplibre';
import type { StyleSpecification } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { resolveBaseStyle } from '../lib/basemap';
import {
  HIDING_ZONES_URL,
  INITIAL_VIEW,
  POI_LAYERS,
  SF_BORDER_URL,
} from '../lib/layers';
import { useStore } from '../lib/store';

interface MapViewProps {
  /** Extra controls (e.g. a question composer) rendered in the top-left overlay. */
  children?: React.ReactNode;
}

export function MapView({ children }: MapViewProps) {
  const remaining = useStore((s) => s.state.remaining_zone_ids);
  const connectionStatus = useStore((s) => s.connectionStatus);
  const selectedLayers = useStore((s) => s.selectedLayers);
  const toggleLayer = useStore((s) => s.toggleLayer);

  const [baseStyle, setBaseStyle] = useState<StyleSpecification | null>(null);

  useEffect(() => {
    let alive = true;
    void resolveBaseStyle().then((style) => {
      if (alive) setBaseStyle(style);
    });
    return () => {
      alive = false;
    };
  }, []);

  // MapLibre filter selecting only the still-possible zones.
  const remainingFilter = useMemo(
    () => ['in', ['get', 'zone_id'], ['literal', remaining]] as unknown as never,
    [remaining],
  );

  if (!baseStyle) {
    return (
      <div className="flex h-full w-full items-center justify-center bg-[#0b1220] text-slate-400">
        Loading map…
      </div>
    );
  }

  const onClick = (e: MapLayerMouseEvent) => {
    const f = e.features?.[0];
    if (f && f.properties && 'name' in f.properties) {
      // Surface zone name in a transient title; full popups are a later enhancement.
      e.target.getCanvas().title = String(f.properties.name);
    }
  };

  return (
    <div className="relative h-full w-full">
      <Map
        initialViewState={INITIAL_VIEW}
        mapStyle={baseStyle}
        interactiveLayerIds={['zones-fill']}
        onClick={onClick}
        attributionControl={false}
      >
        <NavigationControl position="top-right" />
        <GeolocateControl
          position="top-right"
          trackUserLocation
          showUserHeading
          positionOptions={{ enableHighAccuracy: true }}
        />

        {/* SF border outline */}
        <Source id="sf-border" type="geojson" data={SF_BORDER_URL}>
          <Layer
            id="sf-border-line"
            type="line"
            paint={{ 'line-color': '#475569', 'line-width': 1.5, 'line-dasharray': [2, 2] }}
          />
        </Source>

        {/* Hiding zones: highlight remaining, dim eliminated */}
        <Source id="hiding-zones" type="geojson" data={HIDING_ZONES_URL}>
          <Layer
            id="zones-fill"
            type="fill"
            filter={remainingFilter}
            paint={{ 'fill-color': '#22d3ee', 'fill-opacity': 0.18 }}
          />
          <Layer
            id="zones-outline"
            type="line"
            filter={remainingFilter}
            paint={{ 'line-color': '#22d3ee', 'line-width': 0.8, 'line-opacity': 0.6 }}
          />
        </Source>

        {/* POI overlays (toggleable) */}
        {POI_LAYERS.map((poi) =>
          selectedLayers[poi.id] ? (
            <Source key={poi.id} id={`poi-${poi.id}`} type="geojson" data={poi.url}>
              <Layer
                id={`poi-${poi.id}-circle`}
                type="circle"
                paint={{
                  'circle-radius': 5,
                  'circle-color': poi.color,
                  'circle-stroke-width': 1,
                  'circle-stroke-color': '#0b1220',
                }}
              />
            </Source>
          ) : null,
        )}
      </Map>

      {/* Top-left overlay slot (question composer etc.) */}
      {children ? <div className="absolute left-3 top-3 z-10">{children}</div> : null}

      {/* Connectivity indicator */}
      <div className="absolute right-3 bottom-3 z-10">
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium shadow ${
            connectionStatus === 'online'
              ? 'bg-emerald-600 text-white'
              : connectionStatus === 'connecting'
                ? 'bg-amber-500 text-white'
                : 'bg-rose-600 text-white'
          }`}
          title={`Connection: ${connectionStatus}`}
        >
          {connectionStatus === 'online'
            ? 'Online'
            : connectionStatus === 'connecting'
              ? 'Connecting…'
              : 'Offline'}
        </span>
      </div>

      {/* POI layer toggle sidebar */}
      <div className="absolute left-3 bottom-3 z-10 max-h-[40vh] w-44 overflow-auto rounded-lg bg-slate-900/85 p-3 text-xs text-slate-200 shadow-lg backdrop-blur">
        <p className="mb-2 font-semibold uppercase tracking-wide text-slate-400">POI layers</p>
        <ul className="space-y-1">
          {POI_LAYERS.map((poi) => (
            <li key={poi.id}>
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  checked={!!selectedLayers[poi.id]}
                  onChange={() => toggleLayer(poi.id)}
                />
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: poi.color }}
                />
                {poi.label}
              </label>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

export default MapView;
