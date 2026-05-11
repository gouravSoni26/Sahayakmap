import { Marker, Popup } from 'react-leaflet'
import L from 'leaflet'
import { getSeverityColor } from '../../utils/severity'
import { parseLocation } from '../../utils/constants'
import { useAcknowledgeAlert } from '../../hooks/useAlerts'

function makeAlertIcon(severity) {
  const color = getSeverityColor(severity)
  const pulse = severity >= 5 ? 'class="marker-emergency"' : ''
  const html = `<div ${pulse} style="background:${color};border-radius:50%;width:20px;height:20px;display:flex;align-items:center;justify-content:center;font-size:11px;border:2px solid white;box-shadow:0 0 6px ${color}">⚠</div>`
  return L.divIcon({ html, className: '', iconSize: [20, 20], iconAnchor: [10, 10] })
}

export default function AlertPopup({ alert }) {
  const { mutate: ack } = useAcknowledgeAlert()

  const pos = parseLocation(alert.location)
  if (!pos) return null
  const [lat, lng] = pos

  return (
    <Marker position={[lat, lng]} icon={makeAlertIcon(alert.severity)}>
      <Popup>
        <div className="text-sm max-w-xs">
          <p className="font-bold">{alert.title}</p>
          <p className="text-xs mt-1">{alert.description}</p>
          {alert.recommended_action && (
            <p className="text-xs mt-1 text-blue-700">→ {alert.recommended_action}</p>
          )}
          {!alert.acknowledged_at && (
            <button
              onClick={() => ack(alert.id)}
              className="mt-2 text-xs bg-slate-700 text-white px-2 py-1 rounded hover:bg-slate-600"
            >
              Acknowledge
            </button>
          )}
        </div>
      </Popup>
    </Marker>
  )
}
