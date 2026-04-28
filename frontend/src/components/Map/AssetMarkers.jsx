import { Marker, Tooltip } from 'react-leaflet'
import L from 'leaflet'
import { useAssets, useUpdateAssetPosition } from '../../hooks/useAssets'
import { parseLocation } from '../../utils/constants'
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
  const { mutate: updatePosition } = useUpdateAssetPosition()
  const assets = data?.assets ?? []

  return assets.map((asset) => {
    const pos = parseLocation(asset.location)
    if (!pos) return null
    const [lat, lng] = pos

    function handleDragEnd(e) {
      const { lat: newLat, lng: newLng } = e.target.getLatLng()
      updatePosition(
        { assetId: asset.id, lat: newLat, lng: newLng },
        { onError: (err) => console.error('Failed to update asset position:', err) },
      )
    }

    return (
      <Marker
        key={asset.id}
        position={[lat, lng]}
        icon={makeIcon(asset)}
        draggable={true}
        eventHandlers={{ click: () => setSelectedAsset(asset), dragend: handleDragEnd }}
      >
        <Tooltip>
          <strong>{asset.name}</strong> ({asset.type})<br />
          Status: {asset.status}
        </Tooltip>
      </Marker>
    )
  })
}
