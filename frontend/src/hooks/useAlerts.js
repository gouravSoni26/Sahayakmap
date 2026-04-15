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
  if (!res.ok) throw new Error('Failed to acknowledge alert')
  return res.json()
}

export function useAlerts(options = {}) {
  return useQuery({
    queryKey: ['alerts', options],
    queryFn: () => fetchAlerts(options),
    refetchInterval: REFRESH.alerts,
  })
}

export function useAcknowledgeAlert() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: acknowledgeAlert,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['alerts'] }),
  })
}
