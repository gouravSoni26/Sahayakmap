import { getSeverityColor, getSeverityLabel } from '../../utils/severity'

export default function SeverityBadge({ severity, showLabel = true }) {
  const color = getSeverityColor(severity)
  const label = getSeverityLabel(severity)

  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-bold text-white"
      style={{ background: color }}
    >
      {severity}
      {showLabel && <span className="font-normal">{label}</span>}
    </span>
  )
}
