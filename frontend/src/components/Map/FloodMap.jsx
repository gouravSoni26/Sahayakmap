import { MapContainer, TileLayer, ZoomControl } from 'react-leaflet'
import { MAP_CENTER, MAP_DEFAULT_ZOOM, TILE_LAYERS } from '../../utils/constants'
import useMapStore from '../../stores/mapStore'
import { useMapData } from '../../hooks/useMapData'
import GaugeMarkers from './GaugeMarkers'
import AssetMarkers from './AssetMarkers'
import CampMarkers from './CampMarkers'
import RouteLayer from './RouteLayer'
import FloodOverlay from './FloodOverlay'

export default function FloodMap() {
  const layers = useMapStore((s) => s.layers)
  const { data, isLoading } = useMapData()

  return (
    <div className="relative w-full h-full">
      {isLoading && (
        <div className="absolute top-2 left-1/2 -translate-x-1/2 z-[1000] bg-slate-800 text-white text-xs px-3 py-1 rounded-full shadow">
          Loading map data…
        </div>
      )}

      <MapContainer
        center={MAP_CENTER}
        zoom={MAP_DEFAULT_ZOOM}
        zoomControl={false}
        className="w-full h-full"
      >
        <TileLayer {...TILE_LAYERS.dark} />
        <ZoomControl position="bottomright" />

        {layers.floodOverlay && data?.reports && (
          <FloodOverlay reports={data.reports} />
        )}
        {layers.routes && data?.routes && (
          <RouteLayer routes={data.routes} />
        )}
        {layers.camps && data?.camps && (
          <CampMarkers camps={data.camps} />
        )}
        {layers.gauges && data?.gauges && (
          <GaugeMarkers gauges={data.gauges} reports={data?.reports ?? []} />
        )}
        {layers.assets && (
          <AssetMarkers />
        )}
      </MapContainer>
    </div>
  )
}
