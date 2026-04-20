import { Marker, Tooltip, Popup } from 'react-leaflet'
import L from 'leaflet'
import { parseLocation } from '../../utils/constants'

const STATUS_COLORS = {
  ACTIVE: '#22c55e',
  AT_RISK: '#f97316',
  EVACUATING: '#ef4444',
  CLOSED: '#6b7280',
}

function makeIcon(status) {
  const color = STATUS_COLORS[status] ?? '#6b7280'
  const html = `<div style="background:${color};border-radius:3px;width:22px;height:22px;display:flex;align-items:center;justify-content:center;font-size:13px;border:2px solid white;">⛺</div>`
  return L.divIcon({ html, className: '', iconSize: [22, 22], iconAnchor: [11, 11] })
}

export default function CampMarkers({ camps }) {
  return camps.map((camp) => {
    const pos = parseLocation(camp.location)
    if (!pos) return null
    const [lat, lng] = pos

    const pct = camp.max_capacity > 0
      ? Math.round((camp.current_population / camp.max_capacity) * 100)
      : 0

    return (
      <Marker key={camp.id} position={[lat, lng]} icon={makeIcon(camp.status)}>
        <Tooltip>
          <strong>{camp.name}</strong><br />
          {camp.current_population} / {camp.max_capacity} ({pct}%)<br />
          Elevation: {camp.elevation_m}m | Status: {camp.status}
        </Tooltip>
        <Popup>
          <div className="text-sm">
            <p className="font-bold">{camp.name}</p>
            <p>Population: {camp.current_population} / {camp.max_capacity}</p>
            <p>Elevation: {camp.elevation_m}m</p>
            <p>Status: <strong>{camp.status}</strong></p>
            {camp.flood_risk_hours && (
              <p className="text-red-600">⚠ Flood risk in ~{camp.flood_risk_hours.toFixed(1)} hours</p>
            )}
          </div>
        </Popup>
      </Marker>
    )
  })
}
