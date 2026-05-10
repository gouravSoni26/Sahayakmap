import { useAssets } from '../../hooks/useAssets'
import useMapStore from '../../stores/mapStore'
import { formatAssetStatus } from '../../utils/formatters'

const STATUS_STYLES = {
  AVAILABLE: 'bg-green-900/50 text-green-400 border-green-700',
  DEPLOYED: 'bg-orange-900/50 text-orange-400 border-orange-700',
  IN_TRANSIT: 'bg-yellow-900/50 text-yellow-400 border-yellow-700',
  MAINTENANCE: 'bg-slate-700 text-slate-400 border-slate-600',
}

const TYPE_EMOJI = { BOAT: '🚤', HELICOPTER: '🚁', RESCUE_TEAM: '🦺', SUPPLY_TRUCK: '🚛' }

export default function AssetPanel() {
  const { data, isLoading } = useAssets()
  const setSelectedAsset = useMapStore((s) => s.setSelectedAsset)
  const assets = data?.assets ?? []

  if (isLoading) return <p className="p-3 text-xs text-slate-500">Loading assets…</p>

  const grouped = assets.reduce((acc, a) => {
    if (!acc[a.type]) acc[a.type] = []
    acc[a.type].push(a)
    return acc
  }, {})

  return (
    <div className="p-3 space-y-3">
      {Object.entries(grouped).map(([type, list]) => (
        <div key={type}>
          <p className="text-xs font-semibold text-slate-400 uppercase mb-1">
            {TYPE_EMOJI[type]} {type.replace('_', ' ')} ({list.length})
          </p>
          <div className="space-y-1">
            {list.map((asset) => (
              <div
                key={asset.id}
                className="flex items-center justify-between text-xs cursor-pointer hover:bg-slate-700 rounded px-2 py-1"
                onClick={() => setSelectedAsset(asset)}
              >
                <span className="text-slate-200 truncate">{asset.name}</span>
                <span className={`px-1.5 py-0.5 rounded border text-xs shrink-0 ml-2 ${STATUS_STYLES[asset.status] ?? ''}`}>
                  {formatAssetStatus(asset.status)}
                </span>
              </div>
            ))}
          </div>
        </div>
      ))}
      {!assets.length && <p className="text-xs text-slate-500">No assets found.</p>}
    </div>
  )
}
