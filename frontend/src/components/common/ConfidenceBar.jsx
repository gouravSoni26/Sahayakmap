/**
 * Horizontal bar showing a confidence score 0.0 – 1.0.
 * Color shifts from red (low) to yellow (mid) to green (high).
 */
export default function ConfidenceBar({ confidence, showLabel = true }) {
  const pct = Math.round((confidence ?? 0) * 100)
  const color = pct < 40 ? '#ef4444' : pct < 70 ? '#eab308' : '#22c55e'

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-700 rounded overflow-hidden">
        <div
          className="h-full rounded transition-all"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      {showLabel && (
        <span className="text-xs text-slate-400 w-8 text-right">{pct}%</span>
      )}
    </div>
  )
}
