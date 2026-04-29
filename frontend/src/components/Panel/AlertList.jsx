import { useState } from 'react'
import { CheckCircle, ChevronDown, ChevronUp } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { useAlerts, useAcknowledgeAlert } from '../../hooks/useAlerts'
import SeverityBadge from '../common/SeverityBadge'
import useMapStore from '../../stores/mapStore'

export default function AlertList() {
  const { data, isLoading } = useAlerts({ minSeverity: 1 })
  const { mutate: ack } = useAcknowledgeAlert()
  const setSelectedAlert = useMapStore((s) => s.setSelectedAlert)
  const alerts = data?.alerts ?? []
  const [expandedId, setExpandedId] = useState(null)

  if (isLoading) return <p className="p-3 text-xs text-slate-500">Loading alerts…</p>
  if (!alerts.length) return <p className="p-3 text-xs text-slate-500">No active alerts.</p>

  return (
    <div className="divide-y divide-slate-700">
      {alerts.map((alert) => {
        const isExpanded = expandedId === alert.id
        return (
          <div
            key={alert.id}
            className={`p-3 transition-colors ${alert.acknowledged ? 'opacity-50' : ''}`}
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
                <p className="text-sm font-medium text-white leading-tight">{alert.title}</p>
              </div>
              <div className="flex items-center gap-1 shrink-0 mt-0.5">
                {!alert.acknowledged && (
                  <button
                    onClick={(e) => { e.stopPropagation(); ack(alert.id) }}
                    className="text-slate-500 hover:text-green-400"
                    title="Acknowledge"
                  >
                    <CheckCircle size={16} />
                  </button>
                )}
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
