import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { API_BASE, REFRESH } from '../utils/constants'

async function fetchBriefing() {
  const res = await fetch(`${API_BASE}/api/briefing`)
  if (!res.ok) throw new Error('Failed to fetch briefing')
  return res.json()
}

async function generateBriefing() {
  const res = await fetch(`${API_BASE}/api/briefing/generate`, { method: 'POST' })
  if (!res.ok) throw new Error('Failed to generate briefing')
  return res.json()
}

export function useBriefing() {
  return useQuery({
    queryKey: ['briefing'],
    queryFn: fetchBriefing,
    refetchInterval: REFRESH.briefing,
    staleTime: REFRESH.briefing - 5_000,
    refetchOnWindowFocus: false,
  })
}

export function useGenerateBriefing() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: generateBriefing,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['briefing'] }),
  })
}
