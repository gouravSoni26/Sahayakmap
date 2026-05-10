import { Marker, Tooltip } from 'react-leaflet'
import L from 'leaflet'
import MarkerClusterGroup from 'react-leaflet-cluster'
import 'react-leaflet-cluster/lib/assets/MarkerCluster.css'
import 'react-leaflet-cluster/lib/assets/MarkerCluster.Default.css'
import { useAssets, useUpdateAssetPosition } from '../../hooks/useAssets'
import { parseLocation } from '../../utils/constants'
import useMapStore from '../../stores/mapStore'
import { formatAssetStatus } from '../../utils/formatters'

const STATUS_COLORS = {
  AVAILABLE: '#22c55e',
  DEPLOYED: '#f97316',
  IN_TRANSIT: '#eab308',
  MAINTENANCE: '#6b7280',
}

const ASSET_ICONS = { BOAT: '🚤', HELICOPTER: '🚁', RESCUE_TEAM: '🦺', SUPPLY_TRUCK: '🚛' }

function makeIcon(asset, highlighted = false) {
  const color = STATUS_COLORS[asset.status] ?? '#6b7280'
  const emoji = ASSET_ICONS[asset.type] ?? '📍'
  const ring = highlighted
    ? `box-shadow:0 0 0 3px #3b82f6,0 0 0 6px rgba(59,130,246,0.4);animation:asset-pulse 1s ease-in-out infinite;`
    : ''
  const html = `
    ${highlighted ? '<style>@keyframes asset-pulse{0%,100%{box-shadow:0 0 0 3px #3b82f6,0 0 0 6px rgba(59,130,246,0.4)}50%{box-shadow:0 0 0 3px #60a5fa,0 0 0 10px rgba(59,130,246,0.15)}}</style>' : ''}
    <div style="background:${color};border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:14px;border:2px solid white;${ring}">${emoji}</div>
  `
  return L.divIcon({ html, className: '', iconSize: [28, 28], iconAnchor: [14, 14] })
}

export default function AssetMarkers() {
  const { data } = useAssets()
  const setSelectedAsset    = useMapStore((s) => s.setSelectedAsset)
  const highlightedAssetIds = useMapStore((s) => s.highlightedAssetIds)
  const { mutate: updatePosition } = useUpdateAssetPosition()
  const assets = data?.assets ?? []
  const hasHighlights = highlightedAssetIds.length > 0

  return (
    <MarkerClusterGroup chunkedLoading maxClusterRadius={60}>
    {assets.map((asset) => {
    const pos = parseLocation(asset.location)
    if (!pos) return null
    const [lat, lng] = pos
    const isHighlighted = hasHighlights && (
      highlightedAssetIds.includes(asset.id) ||
      highlightedAssetIds.some((h) => asset.name.toLowerCase().includes(h.toLowerCase()))
    )

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
        icon={makeIcon(asset, isHighlighted)}
        draggable={true}
        zIndexOffset={isHighlighted ? 1000 : 0}
        eventHandlers={{ click: () => setSelectedAsset(asset), dragend: handleDragEnd }}
      >
        <Tooltip>
          <strong>{asset.name}</strong> ({asset.type})<br />
          Status: {formatAssetStatus(asset.status)}
        </Tooltip>
      </Marker>
    )
  })}
    </MarkerClusterGroup>
  )
}
