const GAUGE_ITEMS = [
  { color: '#22c55e', label: 'Normal — below warning level' },
  { color: '#eab308', label: 'Warning — above warning level' },
  { color: '#ef4444', label: 'Critical — above danger level' },
]

const ASSET_ITEMS = [
  { icon: '🚤', label: 'Boat' },
  { icon: '🚁', label: 'Helicopter' },
  { icon: '🚛', label: 'Supply Truck' },
  { icon: '🦺', label: 'Rescue Team' },
]

export default function MapLegend() {
  return (
    <div className="bg-gray-900/80 border border-gray-700 rounded-lg p-3 text-xs text-white w-44 space-y-3">
      <div>
        <p className="font-semibold text-gray-300 mb-1">Gauge Stations</p>
        {GAUGE_ITEMS.map(({ color, label }) => (
          <div key={label} className="flex items-center gap-2 mb-0.5">
            <span
              className="inline-block w-3 h-3 rounded-full shrink-0"
              style={{ backgroundColor: color }}
            />
            <span className="text-gray-200">{label}</span>
          </div>
        ))}
      </div>

      <div>
        <p className="font-semibold text-gray-300 mb-1">Flood Extent</p>
        <div className="flex items-center gap-2">
          <span className="inline-block w-3 h-3 rounded-sm shrink-0 bg-orange-500/70 border border-orange-400" />
          <span className="text-gray-200">Projected flood area (6h)</span>
        </div>
      </div>

      <div>
        <p className="font-semibold text-gray-300 mb-1">Opacity</p>
        <p className="text-gray-400">Bright = fresh data</p>
        <p className="text-gray-400">Faded = stale / low confidence</p>
      </div>

      <div>
        <p className="font-semibold text-gray-300 mb-1">Assets</p>
        {ASSET_ITEMS.map(({ icon, label }) => (
          <div key={label} className="flex items-center gap-2 mb-0.5">
            <span className="text-base leading-none">{icon}</span>
            <span className="text-gray-200">{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
