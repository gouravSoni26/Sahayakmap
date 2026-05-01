import { RefreshCw, AlertTriangle, TrendingUp } from 'lucide-react'
import { useBriefing, useGenerateBriefing } from '../../hooks/useBriefing'
import { useAssets } from '../../hooks/useAssets'
import { formatDistanceToNow } from 'date-fns'
import useMapStore from '../../stores/mapStore'

/** Map LLM name strings → asset UUIDs via case-insensitive partial match. */
function resolveAssetIds(names, assets) {
  if (!names?.length || !assets?.length) return []
  return assets
    .filter((a) => names.some((n) => a.name.toLowerCase().includes(n.toLowerCase())))
    .map((a) => a.id)
}

const PRIORITY_STYLES = {
  CRITICAL: 'bg-red-700 text-red-100',
  HIGH:     'bg-orange-700 text-orange-100',
  MEDIUM:   'bg-yellow-700 text-yellow-100',
  LOW:      'bg-blue-800 text-blue-200',
}

function parseBrief(brief) {
  if (!brief) return null
  // Groq sometimes returns summary_text as a raw JSON string
  if (typeof brief.summary_text === 'string' && brief.summary_text.trimStart().startsWith('{')) {
    try {
      const parsed = JSON.parse(brief.summary_text)
      return {
        ...brief,
        summary_text:          parsed.summary            ?? parsed.summary_text ?? brief.summary_text,
        recommended_actions:   parsed.recommended_actions ?? brief.recommended_actions,
        critical_developments: parsed.critical_developments ?? brief.critical_developments,
        key_risks:             parsed.key_risks           ?? brief.key_risks,
      }
    } catch {
      // parse failed — fall through and display raw string
    }
  }
  return brief
}

export default function SituationPanel() {
  const { data, isLoading, isError } = useBriefing()
  const { mutate: generate, isPending } = useGenerateBriefing()
  const brief = parseBrief(data?.brief)
  const { data: assetData } = useAssets()
  const allAssets = assetData?.assets ?? []
  const setHighlightedAssets   = useMapStore((s) => s.setHighlightedAssets)
  const setHighlightedDistrict = useMapStore((s) => s.setHighlightedDistrict)
  const clearHighlights        = useMapStore((s) => s.clearHighlights)

  return (
    <div className="flex flex-col border-b border-slate-700 shrink-0 max-h-[60vh]">
      <div className="flex items-center justify-between p-3 pb-2 shrink-0">
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

      {isLoading && <p className="text-xs text-slate-500 px-3 pb-3">Loading briefing…</p>}
      {isError && <p className="text-xs text-red-400 px-3 pb-3">⚠ Situation brief unavailable</p>}

      {brief && (
        <div className="overflow-y-auto max-h-[40vh] min-h-0 px-3 pb-3 space-y-2">
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

          {/* Recommended actions — click/hover to highlight assets on map */}
          {/* DB stores as "recommendations"; LLM JSON uses "recommended_actions" */}
          {((brief.recommendations ?? brief.recommended_actions) ?? []).length > 0 && (
            <div className="space-y-1">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Recommended Actions
              </span>
              {(brief.recommendations ?? brief.recommended_actions).map((action, i) => {
                const priorityStyle = PRIORITY_STYLES[action.priority] ?? PRIORITY_STYLES.LOW
                return (
                  <div
                    key={i}
                    className="flex flex-col gap-1 text-xs bg-blue-900/40 border border-blue-700 rounded p-2 cursor-pointer hover:bg-blue-800/50 transition-colors"
                    onMouseEnter={() => {
                      setHighlightedAssets(resolveAssetIds(action.assets_involved, allAssets))
                      setHighlightedDistrict(action.affected_district ?? null)
                    }}
                    onMouseLeave={clearHighlights}
                    onClick={() => {
                      setHighlightedAssets(resolveAssetIds(action.assets_involved, allAssets))
                      setHighlightedDistrict(action.affected_district ?? null)
                    }}
                  >
                    <div className="flex items-start gap-2">
                      <TrendingUp size={12} className="text-blue-400 shrink-0 mt-0.5" />
                      <span className="text-slate-200 flex-1">{action.action}</span>
                      {action.priority && (
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold shrink-0 ${priorityStyle}`}>
                          {action.priority}
                        </span>
                      )}
                    </div>
                    {action.rationale && (
                      <p className="text-slate-400 pl-5 leading-snug">{action.rationale}</p>
                    )}
                  </div>
                )
              })}
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
        <p className="text-xs text-slate-500 px-3 pb-3">No briefing yet. Click refresh to generate.</p>
      )}
    </div>
  )
}
