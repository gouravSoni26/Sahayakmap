import { Marker, Tooltip } from 'react-leaflet'
import L from 'leaflet'
import { useAssets } from '../../hooks/useAssets'
import useMapStore from '../../stores/mapStore'

const STATUS_COLORS = {
  AVAILABLE: '#22c55e',
  DEPLOYED: '#f97316',
  IN_TRANSIT: '#eab308',
  MAINTENANCE: '#6b7280',
}

const ASSET_ICONS = { BOAT: '🚤', HELICOPTER: '🚁', RESCUE_TEAM: '🦺', SUPPLY_TRUCK: '🚛' }

function makeIcon(asset) {
  const color = STATUS_COLORS[asset.status] ?? '#6b7280'
  const emoji = ASSET_ICONS[asset.type] ?? '📍'
  const html = `<div style="background:${color};border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:14px;border:2px solid white;">${emoji}</div>`
  return L.divIcon({ html, className: '', iconSize: [28, 28], iconAnchor: [14, 14] })
}

export default function AssetMarkers() {
  const { data } = useAssets()
  const setSelectedAsset = useMapStore((s) => s.setSelectedAsset)
  const assets = data?.assets ?? []

  return assets.map((asset) => {
    const loc = asset.location ?? ''
    if (!loc) return null

    let lat, lng
    try {
      const coords = loc.replace('POINT(', '').replace(')', '').split(' ')
      lng = parseFloat(coords[0])
      lat = parseFloat(coords[1])
    } catch {
      return null
    }

    return (
      <Marker
        key={asset.id}
        position={[lat, lng]}
        icon={makeIcon(asset)}
        eventHandlers={{ click: () => setSelectedAsset(asset) }}
      >
        <Tooltip>
          <strong>{asset.name}</strong> ({asset.type})<br />
          Status: {asset.status}
        </Tooltip>
      </Marker>
    )
  })
}
