import { Marker, Tooltip, Circle, useMap } from 'react-leaflet'
import L from 'leaflet'
import MarkerClusterGroup from 'react-leaflet-cluster'
import 'react-leaflet-cluster/lib/assets/MarkerCluster.css'
import 'react-leaflet-cluster/lib/assets/MarkerCluster.Default.css'
import { useRef, useState, useCallback, useEffect } from 'react'
import { useAssets, useUpdateAssetPosition } from '../../hooks/useAssets'
import { parseLocation } from '../../utils/constants'
import useMapStore from '../../stores/mapStore'
import { formatAssetStatus } from '../../utils/formatters'

const MIN_CLUSTER_RADIUS = 2000 // metres — minimum coverage circle even for tightly packed assets

function computeCoverageCircles(group) {
  const layers = group._featureGroup?._layers ?? {}
  return Object.values(layers)
    .filter((layer) => typeof layer.getAllChildMarkers === 'function')
    .map((cluster) => {
      const children = cluster.getAllChildMarkers()
      const lats = children.map((m) => m.getLatLng().lat)
      const lngs = children.map((m) => m.getLatLng().lng)
      const centerLat = lats.reduce((a, b) => a + b, 0) / lats.length
      const centerLng = lngs.reduce((a, b) => a + b, 0) / lngs.length
      const center = L.latLng(centerLat, centerLng)
      const maxDist = children.reduce((max, m) => Math.max(max, center.distanceTo(m.getLatLng())), 0)
      return {
        id: cluster._leaflet_id,
        center: [centerLat, centerLng],
        radius: Math.max(maxDist, MIN_CLUSTER_RADIUS),
      }
    })
}

const MIN_HIGHLIGHT_RADIUS = 8000 // metres — minimum circle for highlighted clusters

function computeHighlightCircles(group, assets, highlightedAssetIds) {
  if (!highlightedAssetIds.length || !group._featureGroup) return []
  const layers = group._featureGroup._layers ?? {}
  return Object.values(layers)
    .filter((layer) => typeof layer.getAllChildMarkers === 'function')
    .reduce((acc, cluster) => {
      const children = cluster.getAllChildMarkers()
      const hasHighlighted = children.some((child) => {
        const id = child.options?.title
        if (!id) return false
        if (highlightedAssetIds.includes(id)) return true
        const asset = assets.find((a) => a.id === id)
        return asset && highlightedAssetIds.some((h) => asset.name.toLowerCase().includes(h.toLowerCase()))
      })
      if (!hasHighlighted) return acc
      const lats = children.map((m) => m.getLatLng().lat)
      const lngs = children.map((m) => m.getLatLng().lng)
      const centerLat = lats.reduce((a, b) => a + b, 0) / lats.length
      const centerLng = lngs.reduce((a, b) => a + b, 0) / lngs.length
      const center = L.latLng(centerLat, centerLng)
      const maxDist = children.reduce((max, m) => Math.max(max, center.distanceTo(m.getLatLng())), 0)
      acc.push({
        id: cluster._leaflet_id,
        center: [centerLat, centerLng],
        radius: Math.max(maxDist, MIN_HIGHLIGHT_RADIUS),
      })
      return acc
    }, [])
}

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
  const flyToOnHighlight    = useMapStore((s) => s.flyToOnHighlight)
  const resetFlyTo          = useMapStore((s) => s.resetFlyTo)
  const { mutate: updatePosition } = useUpdateAssetPosition()
  const assets = data?.assets ?? []
  const hasHighlights = highlightedAssetIds.length > 0

  const map = useMap()
  const clusterRef = useRef(null)
  const [coverageCircles, setCoverageCircles] = useState([])
  const [highlightCircles, setHighlightCircles] = useState([])

  // Stable refs so handleAnimationEnd (empty deps) always sees latest values
  const assetsRef = useRef(assets)
  const highlightedRef = useRef(highlightedAssetIds)
  useEffect(() => { assetsRef.current = assets }, [assets])
  useEffect(() => { highlightedRef.current = highlightedAssetIds }, [highlightedAssetIds])

  const handleAnimationEnd = useCallback(() => {
    const group = clusterRef.current
    if (!group) return
    setCoverageCircles(computeCoverageCircles(group))
    setHighlightCircles(computeHighlightCircles(group, assetsRef.current, highlightedRef.current))
  }, [])

  // Recompute highlight circles immediately when highlighted IDs change (no map event needed)
  // Also flies the map to the first matched cluster, or to the asset itself if unclustered.
  useEffect(() => {
    const group = clusterRef.current
    if (!group) return
    const circles = computeHighlightCircles(group, assets, highlightedAssetIds)
    setHighlightCircles(circles)
    if (!highlightedAssetIds.length || !flyToOnHighlight) return
    if (circles.length > 0) {
      map.setView(circles[0].center, 11)
    } else {
      // Asset is unclustered at current zoom — jump to the asset's own position
      const target = assets.find((a) =>
        highlightedAssetIds.includes(a.id) ||
        highlightedAssetIds.some((h) => a.name.toLowerCase().includes(h.toLowerCase()))
      )
      if (target) {
        const pos = parseLocation(target.location)
        if (pos) map.setView(pos, 11)
      }
    }
    resetFlyTo()
  }, [highlightedAssetIds, assets, flyToOnHighlight])

  return (
    <>
      {highlightCircles.map(({ id, center, radius }) => (
        <Circle
          key={`hl-${id}`}
          center={center}
          radius={radius}
          interactive={false}
          pathOptions={{
            color: '#3b82f6',
            fillColor: '#3b82f6',
            fillOpacity: 0.08,
            opacity: 0.7,
            weight: 2,
            dashArray: '6 4',
          }}
        />
      ))}
      {coverageCircles.map(({ id, center, radius }) => (
        <Circle
          key={id}
          center={center}
          radius={radius}
          interactive={false}
          pathOptions={{
            color: '#3b82f6',
            fillColor: '#3b82f6',
            fillOpacity: 0.08,
            opacity: 0.4,
            weight: 1.5,
          }}
        />
      ))}
    <MarkerClusterGroup
      ref={clusterRef}
      chunkedLoading
      maxClusterRadius={60}
      spiderfyOnMaxZoom
      spiderfyOnEveryZoom
      eventHandlers={{
        animationend: handleAnimationEnd,
        zoomend: handleAnimationEnd,
        moveend: handleAnimationEnd,
      }}
    >
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
        title={asset.id}
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
    </>
  )
}
