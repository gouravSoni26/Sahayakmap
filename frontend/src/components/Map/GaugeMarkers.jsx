import { CircleMarker, Popup, Tooltip } from 'react-leaflet'
import { getSeverityColor } from '../../utils/severity'
import { parseLocation } from '../../utils/constants'
import useMapStore from '../../stores/mapStore'

/**
 * Renders a coloured circle for each gauge station.
 * Color = severity of the latest CWC_GAUGE report for that station.
 * Opacity = freshness of the latest reading.
 */
export default function GaugeMarkers({ gauges, reports }) {
  const setSelectedGauge = useMapStore((s) => s.setSelectedGauge)

  // Build a map: station_code → latest report
  const latestByCode = {}
  for (const r of reports) {
    if (r.source_type !== 'CWC_GAUGE') continue
    const code = r.raw_payload?.station_code
    if (!code) continue
    if (!latestByCode[code] || r.reported_at > latestByCode[code].reported_at) {
      latestByCode[code] = r
    }
  }

  return gauges.map((gauge) => {
    const pos = parseLocation(gauge.location)
    if (!pos) return null
    const [lat, lng] = pos

    const latest = latestByCode[gauge.station_code]
    const severity = latest?.severity ?? 1
    const freshness = latest?.freshness_factor ?? 1
    const color = getSeverityColor(severity)
    const level = latest?.water_level_m

    return (
      <CircleMarker
        key={gauge.id}
        center={[lat, lng]}
        radius={12}
        pathOptions={{ color, fillColor: color, fillOpacity: 0.7 * freshness, weight: 2, opacity: freshness }}
        eventHandlers={{ click: () => setSelectedGauge(gauge) }}
      >
        <Tooltip direction="top" offset={[0, -8]}>
          <strong>{gauge.name}</strong> ({gauge.river_name})<br />
          {level ? `${level.toFixed(2)}m` : 'No data'} / Danger: {gauge.danger_level_m}m
        </Tooltip>
        <Popup>
          <div className="text-sm">
            <p className="font-bold">{gauge.name}</p>
            {gauge.river_name && <p className="text-gray-600">{gauge.river_name}</p>}
            <p>Level: <strong>{level ? `${level.toFixed(2)}m` : 'No data'}</strong></p>
            {level && (
              <p className="font-semibold">
                {level >= gauge.danger_level_m
                  ? '🔴 Above danger'
                  : level >= gauge.warning_level_m
                  ? '🟡 Above warning'
                  : '🟢 Normal'}
              </p>
            )}
            <p className="text-xs text-gray-500">Warning: {gauge.warning_level_m}m | Danger: {gauge.danger_level_m}m</p>
            {latest?.water_level_trend && <p className="text-xs text-gray-500">Trend: {latest.water_level_trend}</p>}
          </div>
        </Popup>
      </CircleMarker>
    )
  })
}
