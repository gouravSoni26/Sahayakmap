import { CircleMarker, Tooltip } from 'react-leaflet'
import { getSeverityColor } from '../../utils/severity'
import { opacityFromFreshness } from '../../utils/freshness'

/**
 * Renders flood report markers on the map.
 * Social media reports use a smaller, semi-transparent circle.
 * Official reports (district, satellite) use a larger marker.
 * Opacity is driven by freshness_factor.
 */
export default function FloodOverlay({ reports }) {
  return reports
    .filter((r) => r.source_type !== 'CWC_GAUGE') // gauges have their own layer
    .map((report) => {
      const loc = report.location ?? ''
      if (!loc) return null

      let lat, lng
      try {
        const coords = loc.replace('POINT(', '').replace(')', '').split(' ')
        lng = parseFloat(coords[0])
        lat = parseFloat(coords[1])
      } catch {
        return null
      }

      const color = getSeverityColor(report.severity ?? 1)
      const opacity = opacityFromFreshness(report.freshness_factor ?? 1)
      const radius = report.source_type === 'SOCIAL_MEDIA' ? 6 : 10
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
              [{report.source_type}] {report.description?.slice(0, 80)}
            </span>
          </Tooltip>
        </CircleMarker>
      )
    })
}
