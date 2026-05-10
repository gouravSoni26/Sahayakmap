import { useState, useEffect } from 'react'
import { GeoJSON } from 'react-leaflet'

const ODISHA_GEOJSON_URL =
  'https://cdn.jsdelivr.net/gh/udit-001/india-maps-data@ef25ebc/geojson/states/odisha.geojson'

const BOUNDARY_STYLE = { color: '#ffffff', weight: 1, opacity: 0.3, fillOpacity: 0 }

export default function DistrictLayer() {
  const [geojson, setGeojson] = useState(null)

  useEffect(() => {
    fetch(ODISHA_GEOJSON_URL)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to fetch district boundaries: ${res.status}`)
        return res.json()
      })
      .then(setGeojson)
      .catch(() => {
        // Silently ignore — district boundaries are decorative context only
      })
  }, [])

  if (!geojson) return null

  return (
    <GeoJSON
      key="odisha-districts"
      data={geojson}
      style={BOUNDARY_STYLE}
      onEachFeature={(feature, layer) => {
        const name =
          feature.properties?.district ||
          feature.properties?.NAME_2 ||
          feature.properties?.name
        if (name) {
          layer.bindTooltip(name, { sticky: true, className: 'district-tooltip' })
        }
      }}
    />
  )
}
