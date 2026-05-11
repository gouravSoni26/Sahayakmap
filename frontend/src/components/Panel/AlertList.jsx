import { useState } from 'react'
import { CheckCircle, ChevronDown, ChevronUp } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { useAlerts, useAcknowledgeAlert } from '../../hooks/useAlerts'
import SeverityBadge from '../common/SeverityBadge'
import useMapStore from '../../stores/mapStore'

export default function AlertList() {
  const { data, isLoading, isError } = useAlerts({ minSeverity: 1 })
  const { mutate: ack } = useAcknowledgeAlert()
  const setSelectedAlert = useMapStore((s) => s.setSelectedAlert)
  const [expandedId, setExpandedId] = useState(null)
  const [ackedIds, setAckedIds] = useState(new Set())

  function handleAck(e, alertId) {
    e.stopPropagation()
    setAckedIds((prev) => new Set([...prev, alertId]))
    ack(alertId)
  }

  if (isLoading) {
    return (
      <div className="divide-y divide-slate-700">
        {[0, 1, 2].map((i) => (
          <div key={i} className="p-3 animate-pulse">
            <div className="h-3 w-14 bg-slate-700 rounded mb-2" />
            <div className="h-4 w-full bg-slate-700 rounded mb-1" />
            <div className="h-4 w-3/4 bg-slate-700 rounded" />
          </div>
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <p className="p-3 text-xs text-red-400">
        ⚠ Alert feed unavailable — check backend connection
      </p>
    )
  }

  // Dedup by id — API may return duplicates from scenario ticks; acked alerts sort to bottom
  const seen = new Set()
  const alerts = (data?.alerts ?? [])
    .filter((a) => {
      if (seen.has(a.id)) return false
      seen.add(a.id)
      return true
    })
    .sort((a, b) => {
      const aAcked = (ackedIds.has(a.id) || !!a.acknowledged_at) ? 1 : 0
      const bAcked = (ackedIds.has(b.id) || !!b.acknowledged_at) ? 1 : 0
      if (aAcked !== bAcked) return aAcked - bAcked
      return b.severity - a.severity
    })

  if (!alerts.length) return <p className="p-3 text-xs text-slate-500">No active alerts.</p>

  return (
    <div className="divide-y divide-slate-700">
      {alerts.map((alert) => {
        const isExpanded = expandedId === alert.id
        const isAcked = ackedIds.has(alert.id) || !!alert.acknowledged_at
        return (
          <div
            key={alert.id}
            className={`p-3 transition-colors ${isAcked ? 'opacity-40' : ''}`}
          >
            {/* Collapsed header */}
            <div className="flex items-start justify-between gap-2">
              <div
                className="flex-1 min-w-0 cursor-pointer"
                onClick={() => setSelectedAlert(alert)}
              >
                <div className="flex items-center gap-2 mb-1">
                  <SeverityBadge severity={alert.severity} />
                </div>
                <p className={`text-sm font-medium text-white leading-tight ${isAcked ? 'line-through' : ''}`}>{alert.title}</p>
              </div>
              <div className="flex items-center gap-1 shrink-0 mt-0.5">
                <button
                  onClick={(e) => handleAck(e, alert.id)}
                  className={`shrink-0 ${isAcked ? 'text-green-400' : 'text-slate-500 hover:text-green-400'}`}
                  title={isAcked ? 'Acknowledged' : 'Acknowledge'}
                >
                  <CheckCircle size={12} />
                  <span className="sr-only">{isAcked ? 'Acknowledged' : 'Acknowledge alert'}</span>
                </button>
                <button
                  onClick={() => setExpandedId(isExpanded ? null : alert.id)}
                  className="text-slate-500 hover:text-slate-300"
                  title={isExpanded ? 'Collapse' : 'Why this alert?'}
                >
                  {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </button>
              </div>
            </div>

            {/* Expanded body */}
            {isExpanded && (
              <div className="mt-2 pt-2 border-t border-slate-700 space-y-1.5">
                <p className="text-xs text-slate-300 leading-relaxed">{alert.description}</p>
                {alert.recommended_action && (
                  <p className="text-xs text-blue-400">→ {alert.recommended_action}</p>
                )}
                <div className="flex items-center gap-2 pt-0.5">
                  <span className="text-xs text-slate-500 font-mono bg-slate-800 px-1.5 py-0.5 rounded uppercase tracking-wide">
                    {alert.type}
                  </span>
                  <span className="text-slate-600">·</span>
                  <span className="text-xs text-slate-600">
                    {formatDistanceToNow(new Date(alert.generated_at), { addSuffix: true })}
                  </span>
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
