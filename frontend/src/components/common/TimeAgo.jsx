import { formatDistanceToNow } from 'date-fns'

/**
 * Renders a human-readable "X minutes ago" string.
 * Optionally shows a warning colour when data is stale.
 */
export default function TimeAgo({ date, isStale = false, className = '' }) {
  if (!date) return <span className="text-slate-500 text-xs">—</span>

  const relative = formatDistanceToNow(new Date(date), { addSuffix: true })
  const colorClass = isStale ? 'text-red-400' : 'text-slate-400'

  return (
    <time
      dateTime={date}
      className={`text-xs ${colorClass} ${className}`}
      title={new Date(date).toLocaleString('en-IN')}
    >
      {isStale && '⚠ '}{relative}
    </time>
  )
}
