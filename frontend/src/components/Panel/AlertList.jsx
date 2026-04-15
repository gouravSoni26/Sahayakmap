import { CheckCircle } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { useAlerts, useAcknowledgeAlert } from '../../hooks/useAlerts'
import SeverityBadge from '../common/SeverityBadge'
import useMapStore from '../../stores/mapStore'

export default function AlertList() {
  const { data, isLoading } = useAlerts({ minSeverity: 1 })
  const { mutate: ack } = useAcknowledgeAlert()
  const setSelectedAlert = useMapStore((s) => s.setSelectedAlert)
  const alerts = data?.alerts ?? []

  if (isLoading) return <p className="p-3 text-xs text-slate-500">Loading alerts…</p>
  if (!alerts.length) return <p className="p-3 text-xs text-slate-500">No active alerts.</p>

  return (
    <div className="divide-y divide-slate-700">
      {alerts.map((alert) => (
        <div
          key={alert.id}
          className={`p-3 cursor-pointer hover:bg-slate-700/50 transition-colors ${alert.acknowledged ? 'opacity-50' : ''}`}
          onClick={() => setSelectedAlert(alert)}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <SeverityBadge severity={alert.severity} />
                <span className="text-xs text-slate-400 truncate">{alert.type}</span>
              </div>
              <p className="text-sm font-medium text-white leading-tight">{alert.title}</p>
              <p className="text-xs text-slate-400 mt-0.5 line-clamp-2">{alert.description}</p>
              {alert.recommended_action && (
                <p className="text-xs text-blue-400 mt-1">→ {alert.recommended_action}</p>
              )}
            </div>
            {!alert.acknowledged && (
              <button
                onClick={(e) => { e.stopPropagation(); ack(alert.id) }}
                className="text-slate-500 hover:text-green-400 shrink-0 mt-0.5"
                title="Acknowledge"
              >
                <CheckCircle size={16} />
              </button>
            )}
          </div>
          <p className="text-xs text-slate-600 mt-1">
            {formatDistanceToNow(new Date(alert.generated_at), { addSuffix: true })}
          </p>
        </div>
      ))}
    </div>
  )
}
