import { CircleMarker, Tooltip } from 'react-leaflet'
import { getSeverityColor } from '../../utils/severity'
import { opacityFromFreshness } from '../../utils/freshness'
import { parseLocation } from '../../utils/constants'

/**
 * Renders flood report markers on the map.
 * Social media reports use a smaller, semi-transparent circle.
 * Official reports (district, satellite) use a larger marker.
 * Opacity is driven by freshness_factor.
 */
export default function FloodOverlay({ reports }) {
  return reports
    .filter((r) => r.data_sources?.type !== 'CWC_GAUGE') // gauges have their own layer
    .map((report) => {
      const pos = parseLocation(report.location)
      if (!pos) return null
      const [lat, lng] = pos

      const color = getSeverityColor(report.severity ?? 1)
      const opacity = opacityFromFreshness(report.freshness_factor ?? 1)
      const radius = report.data_sources?.type === 'SOCIAL_MEDIA' ? 6 : 10
      const dashed = report.is_stale

      return (
        <CircleMarker
          key={report.id}
          center={[lat, lng]}
          radius={radius}
          pathOptions={{
            color,
            fillColor: color,
            fillOpacity: opacity * 0.6,
            weight: dashed ? 1 : 2,
            opacity,
            dashArray: dashed ? '4 4' : undefined,
          }}
        >
          <Tooltip>
            <span className="text-xs">
              [{report.data_sources?.type ?? 'UNKNOWN'}] {report.description?.slice(0, 80)}
            </span>
          </Tooltip>
        </CircleMarker>
      )
    })
}
