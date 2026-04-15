/**
 * Client-side freshness calculation.
 * Mirrors the half-life model in backend/fusion/temporal.py.
 */

// Half-life in minutes — keep in sync with backend
const HALF_LIFE = {
  CWC_GAUGE: 30,
  IMD_WEATHER: 60,
  SOCIAL_MEDIA: 120,
  SATELLITE: 360,
  OSM_ROAD: 240,
  DISTRICT_REPORT: 180,
}

/**
 * Returns 0.0 – 1.0. 1.0 = just reported, 0.5 = one half-life, 0.0 = very stale.
 */
export function freshnessFactor(reportedAt, sourceType) {
  const hl = HALF_LIFE[sourceType] ?? 120
  const ageMs = Date.now() - new Date(reportedAt).getTime()
  const ageMin = ageMs / 60_000
  if (ageMin <= 0) return 1.0
  return Math.pow(0.5, ageMin / hl)
}

/**
 * Map freshness to opacity (0.15 – 1.0).
 */
export function opacityFromFreshness(factor) {
  return Math.max(0.15, Math.min(1.0, factor))
}

/**
 * Human-readable staleness string, e.g. "2 min ago" or "STALE (3 hrs)"
 */
export function freshnessLabel(reportedAt, sourceType) {
  const factor = freshnessfactor(reportedAt, sourceType)
  const ageMs = Date.now() - new Date(reportedAt).getTime()
  const ageMin = Math.round(ageMs / 60_000)

  if (ageMin < 1) return 'Just now'
  if (ageMin < 60) return `${ageMin}m ago`
  const ageHrs = Math.round(ageMin / 60)
  const prefix = factor < 0.25 ? 'STALE — ' : ''
  return `${prefix}${ageHrs}h ago`
}

// Fix typo in export
function freshnessfield(...args) { return freshnessLabel(...args) }
