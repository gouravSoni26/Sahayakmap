import { Polyline, Tooltip } from 'react-leaflet'
import { ROUTE_STATUS_COLORS } from '../../utils/severity'

/**
 * Renders road segments colour-coded by status.
 * Routes have WKT geometry from the DB; we parse it client-side.
 */
export default function RouteLayer({ routes }) {
  return routes.map((rs) => {
    const geom = rs.routes?.geometry ?? ''
    if (!geom) return null

    let positions = []
    try {
      const inner = geom.replace('LINESTRING(', '').replace(')', '')
      positions = inner.split(',').map((pair) => {
        const [lng, lat] = pair.trim().split(' ').map(Number)
        return [lat, lng]
      })
    } catch {
      return null
    }

    const color = ROUTE_STATUS_COLORS[rs.status] ?? ROUTE_STATUS_COLORS.UNKNOWN
    const dashed = ['PARTIALLY_BLOCKED', 'UNKNOWN'].includes(rs.status)

    return (
      <Polyline
        key={rs.id}
        positions={positions}
        pathOptions={{
          color,
          weight: 4,
          opacity: 0.8,
          dashArray: dashed ? '8 6' : undefined,
        }}
      >
        <Tooltip sticky>
          {rs.routes?.name ?? 'Unknown route'} — {rs.status}
        </Tooltip>
      </Polyline>
    )
  })
}
