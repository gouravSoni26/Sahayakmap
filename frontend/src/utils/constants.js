// Odisha / Mahanadi basin map defaults
export const MAP_CENTER = [
  parseFloat(import.meta.env.VITE_MAP_CENTER_LAT ?? '20.46'),
  parseFloat(import.meta.env.VITE_MAP_CENTER_LNG ?? '85.88'),
]
export const MAP_DEFAULT_ZOOM = parseInt(import.meta.env.VITE_MAP_DEFAULT_ZOOM ?? '8', 10)

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

// Map bounds for Odisha
export const ODISHA_BOUNDS = [
  [17.8, 81.4],  // SW
  [22.6, 87.5],  // NE
]

/**
 * Parse a location from Supabase PostGIS — returns [lat, lng] or null.
 * Supabase returns geometry as GeoJSON: { type: "Point", coordinates: [lng, lat] }
 * Falls back to WKT "POINT(lng lat)" for any manually constructed strings.
 */
export function parseLocation(location) {
  if (!location) return null
  // GeoJSON object from Supabase
  if (typeof location === 'object' && location.coordinates) {
    const [lng, lat] = location.coordinates
    return [lat, lng]
  }
  // WKT string fallback
  if (typeof location === 'string') {
    try {
      const coords = location.replace('POINT(', '').replace(')', '').trim().split(' ')
      return [parseFloat(coords[1]), parseFloat(coords[0])]
    } catch {
      return null
    }
  }
  return null
}

// Tile layers
export const TILE_LAYERS = {
  osm: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
  dark: {
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
}

// Refresh intervals (ms)
export const REFRESH = {
  mapData: 60_000,
  alerts: 30_000,
  briefing: 5 * 60_000,
  assets: 60_000,
  floodExtent: 30_000,
  demoState: 10_000,
}
