import { useQuery } from '@tanstack/react-query'
import { API_BASE, REFRESH } from '../utils/constants'
import useMapStore from '../stores/mapStore'

async function fetchMapData({ hours, minSeverity }) {
  const params = new URLSearchParams({ hours, min_severity: minSeverity })
  const res = await fetch(`${API_BASE}/api/map/data?${params}`)
  if (!res.ok) throw new Error('Failed to fetch map data')
  return res.json()
}

export function useMapData() {
  const hoursFilter = useMapStore((s) => s.hoursFilter)
  const minSeverity = useMapStore((s) => s.minSeverity)

  return useQuery({
    queryKey: ['mapData', hoursFilter, minSeverity],
    queryFn: () => fetchMapData({ hours: hoursFilter, minSeverity }),
    refetchInterval: REFRESH.mapData,
    staleTime: REFRESH.mapData - 5_000,
    refetchOnWindowFocus: false,
  })
}
