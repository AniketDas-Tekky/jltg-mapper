/**
 * POI overlay catalogue and basemap helpers.
 *
 * Each POI layer is a static GeoJSON file copied into `public/data/poi/` (from the repo
 * `data/` dir). They're toggled on/off via the sidebar; each gets a circle layer keyed by a
 * stable id so the Map can drive visibility from `selectedLayers`.
 */

export interface PoiLayer {
  id: string;
  label: string;
  url: string;
  color: string;
}

export const POI_LAYERS: PoiLayer[] = [
  { id: 'rail-stations', label: 'Rail Stations', url: '/data/poi/rail-stations.geojson', color: '#38bdf8' },
  { id: 'museums', label: 'Museums', url: '/data/poi/museums.geojson', color: '#f472b6' },
  { id: 'libraries', label: 'Libraries', url: '/data/poi/libraries.geojson', color: '#a78bfa' },
  { id: 'hospitals', label: 'Hospitals', url: '/data/poi/hospitals.geojson', color: '#f87171' },
  { id: 'consulates', label: 'Consulates', url: '/data/poi/consulates.geojson', color: '#fbbf24' },
  { id: 'dog-parks', label: 'Dog Parks', url: '/data/poi/dog-parks.geojson', color: '#4ade80' },
  { id: 'golf-courses', label: 'Golf Courses', url: '/data/poi/golf-courses.geojson', color: '#22c55e' },
  { id: 'mountains', label: 'Mountains', url: '/data/poi/mountains.geojson', color: '#d6d3d1' },
  { id: 'movie-theaters', label: 'Movie Theaters', url: '/data/poi/movie-theaters.geojson', color: '#fb923c' },
  { id: 'farmers-markets', label: 'Farmers Markets', url: '/data/poi/farmers-markets.geojson', color: '#84cc16' },
  { id: 'aquariums', label: 'Aquariums', url: '/data/poi/aquariums.geojson', color: '#2dd4bf' },
];

/** SF default view (centred on Van Ness station, the game start point). */
export const INITIAL_VIEW = {
  longitude: -122.41924,
  latitude: 37.77509,
  zoom: 11.5,
};

export const HIDING_ZONES_URL = '/data/hiding-zones.geojson';
export const SF_BORDER_URL = '/data/sf-border.geojson';

/** Path to the optional PMTiles basemap. Absent by default (large gitignored download). */
export const BASEMAP_URL = '/basemap/sf.pmtiles';
