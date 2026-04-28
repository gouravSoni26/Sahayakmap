import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { API_BASE } from '../../utils/constants'

async function fetchScenarioState() {
  const res = await fetch(`${API_BASE}/api/scenario/state`)
  if (!res.ok) throw new Error('Failed to fetch scenario state')
  return res.json()
}

export default function DemoControls() {
  const [stepLabel, setStepLabel] = useState(null)
  const [loading, setLoading] = useState(false)

  const { data: state, refetch } = useQuery({
    queryKey: ['scenario-state'],
    queryFn: fetchScenarioState,
    refetchInterval: 5000,
  })

  async function handleLoad() {
    setLoading(true)
    try {
      await fetch(`${API_BASE}/api/scenario/load`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: 'cyclone_fani' }),
      })
      setStepLabel(null)
      refetch()
    } catch (err) {
      console.error('Failed to load scenario:', err)
    } finally {
      setLoading(false)
    }
  }

  async function handleTick() {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/scenario/tick`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ steps: 1 }),
      })
      if (res.ok) {
        const data = await res.json()
        setStepLabel(data.label ?? null)
        refetch()
      }
    } catch (err) {
      console.error('Failed to tick scenario:', err)
    } finally {
      setLoading(false)
    }
  }

  const isComplete = state?.scenario && state.current_step >= state.total_steps - 1
  const hasScenario = !!state?.scenario

  return (
    <div className="fixed bottom-4 left-4 z-[1000] bg-slate-800 border border-slate-700 rounded-lg p-3 text-xs text-slate-300 space-y-2 shadow-lg min-w-[180px]">
      <p className="font-semibold text-slate-200 uppercase tracking-wide">Demo</p>

      {hasScenario && (
        <p className="text-slate-400">
          Step{' '}
          <span className="text-white font-medium">{state.current_step + 1}</span>
          {' / '}
          <span className="text-white font-medium">{state.total_steps}</span>
        </p>
      )}

      {stepLabel && (
        <p className="text-blue-400 truncate max-w-[160px]" title={stepLabel}>
          {stepLabel}
        </p>
      )}

      <div className="flex gap-2">
        <button
          onClick={handleLoad}
          disabled={loading}
          className="flex-1 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 rounded px-2 py-1 text-xs transition-colors"
        >
          Load Fani
        </button>
        <button
          onClick={handleTick}
          disabled={loading || !hasScenario || isComplete}
          className="flex-1 bg-blue-700 hover:bg-blue-600 disabled:opacity-50 rounded px-2 py-1 text-xs transition-colors"
        >
          Next Step →
        </button>
      </div>

      {isComplete && (
        <p className="text-green-400 text-center">Scenario complete</p>
      )}
    </div>
  )
}
