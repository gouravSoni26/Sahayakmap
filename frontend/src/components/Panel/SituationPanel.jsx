import { RefreshCw, AlertTriangle, TrendingUp } from 'lucide-react'
import { useBriefing, useGenerateBriefing } from '../../hooks/useBriefing'
import { formatDistanceToNow } from 'date-fns'

export default function SituationPanel() {
  const { data, isLoading } = useBriefing()
  const { mutate: generate, isPending } = useGenerateBriefing()
  const brief = data?.brief

  return (
    <div className="p-3 border-b border-slate-700 shrink-0">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">Situation Brief</span>
        <button
          onClick={() => generate()}
          disabled={isPending}
          className="p-1 hover:bg-slate-700 rounded text-slate-400 hover:text-white disabled:opacity-40"
          title="Regenerate briefing"
        >
          <RefreshCw size={12} className={isPending ? 'animate-spin' : ''} />
        </button>
      </div>

      {isLoading && <p className="text-xs text-slate-500">Loading briefing…</p>}

      {brief && (
        <div className="space-y-2">
          <p className="text-sm leading-snug text-slate-200">{brief.summary_text}</p>

          {/* Critical developments */}
          {brief.key_risks?.slice(0, 3).map((risk, i) => (
            <div key={i} className="flex gap-2 text-xs bg-slate-700 rounded p-2">
              <AlertTriangle size={12} className="text-orange-400 shrink-0 mt-0.5" />
              <span className="text-slate-300">
                <strong className="text-white">{risk.affected_area ?? risk.location}:</strong>{' '}
                {risk.risk}
                {risk.eta_hours && <span className="text-orange-400"> ({risk.eta_hours}h)</span>}
              </span>
            </div>
          ))}

          {/* Top recommendation */}
          {brief.recommendations?.[0] && (
            <div className="flex gap-2 text-xs bg-blue-900/40 border border-blue-700 rounded p-2">
              <TrendingUp size={12} className="text-blue-400 shrink-0 mt-0.5" />
              <span className="text-slate-200">{brief.recommendations[0].action}</span>
            </div>
          )}

          <p className="text-xs text-slate-500">
            {formatDistanceToNow(new Date(brief.generated_at), { addSuffix: true })}
            {brief.overall_confidence && (
              <span className="ml-1">· {Math.round(brief.overall_confidence * 100)}% confidence</span>
            )}
          </p>
        </div>
      )}

      {!brief && !isLoading && (
        <p className="text-xs text-slate-500">No briefing yet. Click refresh to generate.</p>
      )}
    </div>
  )
}
