import { useMapData } from '../../hooks/useMapData'
import { freshnessFactor } from '../../utils/freshness'

const SOURCE_LABELS = {
  CWC_GAUGE: 'River Gauges (CWC)',
  IMD_WEATHER: 'Weather (IMD)',
  SOCIAL_MEDIA: 'Social Media',
  SATELLITE: 'Satellite Imagery',
  DISTRICT_REPORT: 'District Reports',
  OSM_ROAD: 'Road Network',
}

export default function DataFreshness() {
  const { data } = useMapData()
  const freshness = data?.source_freshness ?? {}

  return (
    <div className="p-3 space-y-2">
      <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Data Source Freshness</p>

      {Object.entries(SOURCE_LABELS).map(([type, label]) => {
        const lastUpdated = freshness[type]
        const factor = lastUpdated ? freshnessFactor(lastUpdated, type) : 0

        return (
          <div key={type} className="space-y-0.5">
            <div className="flex justify-between text-xs">
              <span className="text-slate-300">{label}</span>
              <span className={factor < 0.25 ? 'text-red-400' : factor < 0.5 ? 'text-yellow-400' : 'text-green-400'}>
                {lastUpdated
                  ? factor < 0.25
                    ? 'STALE'
                    : `${Math.round(factor * 100)}%`
                  : 'No data'}
              </span>
            </div>
            <div className="h-1 bg-slate-700 rounded overflow-hidden">
              <div
                className="h-full rounded transition-all"
                style={{
                  width: `${Math.round(factor * 100)}%`,
                  background: factor < 0.25 ? '#ef4444' : factor < 0.5 ? '#eab308' : '#22c55e',
                }}
              />
            </div>
            {lastUpdated && (
              <p className="text-xs text-slate-600">
                {new Date(lastUpdated).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' })}
              </p>
            )}
          </div>
        )
      })}
    </div>
  )
}
