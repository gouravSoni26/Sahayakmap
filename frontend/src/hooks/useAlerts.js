import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { API_BASE, REFRESH } from '../utils/constants'

async function fetchAlerts({ minSeverity = 1, unacknowledgedOnly = false, districtId = null } = {}) {
  const params = new URLSearchParams({ min_severity: minSeverity })
  if (unacknowledgedOnly) params.append('unacknowledged_only', 'true')
  if (districtId) params.append('district_id', districtId)

  const res = await fetch(`${API_BASE}/api/alerts?${params}`)
  if (!res.ok) throw new Error('Failed to fetch alerts')
  return res.json()
}

async function acknowledgeAlert(alertId) {
  const res = await fetch(`${API_BASE}/api/alerts/${alertId}/ack`, { method: 'PUT' })
  if (res.status === 409) return  // already acknowledged — guard response, not an error
  if (!res.ok) throw new Error('Failed to acknowledge alert')
  return res.json()
}

export function useAlerts(options = {}) {
  return useQuery({
    queryKey: ['alerts', options],
    queryFn: () => fetchAlerts(options),
    refetchInterval: REFRESH.alerts,
    staleTime: REFRESH.alerts - 5_000,
    refetchOnWindowFocus: false,
  })
}

export function useAcknowledgeAlert() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: acknowledgeAlert,
    onMutate: async (alertId) => {
      await queryClient.cancelQueries({ queryKey: ['alerts'] })
      const previous = queryClient.getQueriesData({ queryKey: ['alerts'] })
      queryClient.setQueriesData({ queryKey: ['alerts'] }, (old) => {
        if (!old?.alerts) return old
        return {
          ...old,
          alerts: old.alerts.map((a) =>
            a.id === alertId
              ? { ...a, acknowledged_at: new Date().toISOString(), acknowledged: true }
              : a
          ),
        }
      })
      return { previous }
    },
    onError: (_err, _alertId, context) => {
      context?.previous?.forEach(([queryKey, data]) => {
        queryClient.setQueryData(queryKey, data)
      })
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
  })
}
