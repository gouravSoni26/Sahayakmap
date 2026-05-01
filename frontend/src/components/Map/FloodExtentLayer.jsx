import { useQuery } from '@tanstack/react-query'
import { GeoJSON } from 'react-leaflet'
import { API_BASE } from '../../utils/constants'

const POLYGON_STYLE = {
  fillColor: '#ff4500',
  fillOpacity: 0.25,
  color: '#ff2200',
  weight: 2,
}

function onEachFeature(feature, layer) {
  const { name, water_level_m, danger_level_m, radius_km } = feature.properties
  layer.bindTooltip(
    `${name}: ${water_level_m}m / ${danger_level_m}m danger<br>Flood radius: ${radius_km}km`,
    { sticky: true },
  )
}

// style must be a function so react-leaflet's GeoJSON layer applies it correctly
function getStyle() {
  return POLYGON_STYLE
}

async function fetchFloodExtent() {
  const res = await fetch(`${API_BASE}/api/map/flood-extent`)
  if (!res.ok) throw new Error(`flood-extent ${res.status}`)
  return res.json()
}

export default function FloodExtentLayer() {
  const { data, isError, error } = useQuery({
    queryKey: ['floodExtent'],
    queryFn: fetchFloodExtent,
    refetchInterval: 30_000,
  })

  if (isError || !data?.features?.length) return null

  return (
    <GeoJSON
      key={data.generated_at}
      data={data}
      style={getStyle}
      onEachFeature={onEachFeature}
    />
  )
}
