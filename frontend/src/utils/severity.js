/**
 * Severity color system — matches MASTERPLAN.md color table exactly.
 * Severity 1-5 maps to a consistent set of Tailwind + hex colors.
 */

export const SEVERITY_COLORS = {
  1: { hex: '#22c55e', tailwind: 'green-500',  label: 'Normal' },
  2: { hex: '#eab308', tailwind: 'yellow-500', label: 'Advisory' },
  3: { hex: '#f97316', tailwind: 'orange-500', label: 'Warning' },
  4: { hex: '#ef4444', tailwind: 'red-500',    label: 'Critical' },
  5: { hex: '#7c2d12', tailwind: 'red-900',    label: 'Emergency' },
}

export function getSeverityColor(severity) {
  return SEVERITY_COLORS[severity]?.hex ?? SEVERITY_COLORS[1].hex
}

export function getSeverityLabel(severity) {
  return SEVERITY_COLORS[severity]?.label ?? 'Unknown'
}

export function getSeverityTailwind(severity) {
  return SEVERITY_COLORS[severity]?.tailwind ?? 'green-500'
}

/** Returns a Leaflet-compatible marker color string. */
export function markerColor(severity) {
  const map = { 1: 'green', 2: 'gold', 3: 'orange', 4: 'red', 5: 'darkred' }
  return map[severity] ?? 'blue'
}

/** Color for route status overlay. */
export const ROUTE_STATUS_COLORS = {
  OPEN: '#22c55e',
  PARTIALLY_BLOCKED: '#eab308',
  BLOCKED: '#ef4444',
  SUBMERGED: '#7c3aed',
  UNKNOWN: '#6b7280',
}
