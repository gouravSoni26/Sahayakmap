import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { API_BASE, REFRESH } from '../utils/constants'

async function fetchAssets() {
  const res = await fetch(`${API_BASE}/api/assets`)
  if (!res.ok) throw new Error('Failed to fetch assets')
  return res.json()
}

async function updateAssetPosition({ assetId, lat, lng }) {
  const res = await fetch(`${API_BASE}/api/assets/${assetId}/position`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lat, lng }),
  })
  if (!res.ok) throw new Error('Failed to update asset position')
  return res.json()
}

async function updateAssetStatus({ assetId, status }) {
  const res = await fetch(`${API_BASE}/api/assets/${assetId}/status`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  })
  if (!res.ok) throw new Error('Failed to update asset status')
  return res.json()
}

export function useAssets() {
  return useQuery({
    queryKey: ['assets'],
    queryFn: fetchAssets,
    refetchInterval: REFRESH.assets,
    staleTime: REFRESH.assets - 5_000,
    refetchOnWindowFocus: false,
  })
}

export function useUpdateAssetPosition() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: updateAssetPosition,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['assets'] }),
  })
}

export function useUpdateAssetStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: updateAssetStatus,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['assets'] }),
  })
}
