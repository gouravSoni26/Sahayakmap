import { useState } from 'react'
import { AlertTriangle, RefreshCw, Menu, ChevronDown, ChevronUp } from 'lucide-react'
import FloodMap from './components/Map/FloodMap'
import SituationPanel from './components/Panel/SituationPanel'
import AlertList from './components/Panel/AlertList'
import AssetPanel from './components/Panel/AssetPanel'
import DemoControls from './components/Panel/DemoControls'
import DataFreshness from './components/Panel/DataFreshness'
import { useAlerts } from './hooks/useAlerts'
import useMapStore from './stores/mapStore'

const TABS = ['Alerts', 'Assets', 'Freshness']

const SEV_LABEL = { 4: 'CRITICAL', 3: 'HIGH', 2: 'MEDIUM', 1: 'LOW' }

export default function App() {
  const [activeTab, setActiveTab] = useState('Alerts')
  const [panelOpen, setPanelOpen] = useState(true)
  const { data: alertsData } = useAlerts({ minSeverity: 3, unacknowledgedOnly: true })
  const criticalCount = alertsData?.alerts?.length ?? 0

  // Mobile drawer state
  const drawerOpen = useMapStore((s) => s.drawerOpen)
  const toggleDrawer = useMapStore((s) => s.toggleDrawer)

  // Summary for collapsed drawer
  const { data: allAlertsData } = useAlerts({ minSeverity: 1 })
  const allAlerts = allAlertsData?.alerts ?? []
  const uniqueAlerts = [...new Map(allAlerts.map((a) => [a.id, a])).values()]
  const drawerAlertCount = uniqueAlerts.length
  const maxSev = uniqueAlerts.reduce((m, a) => Math.max(m, a.severity ?? 0), 0)
  const topSevLabel = SEV_LABEL[maxSev] ?? null

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-900 text-white overflow-hidden">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-2 bg-slate-800 border-b border-slate-700 shrink-0">
        <div className="flex items-center gap-3">
          <button onClick={() => setPanelOpen(o => !o)} className="p-1 hover:bg-slate-700 rounded hidden md:block">
            <Menu size={20} />
          </button>
          <span className="font-bold text-base tracking-tight">SahayakMap</span>
          <span className="text-slate-400 text-sm hidden sm:inline">Mahanadi Basin</span>
        </div>
        <div className="flex items-center gap-3">
          {criticalCount > 0 && (
            <span className="flex items-center gap-1 bg-red-600 text-white text-xs font-bold px-2 py-1 rounded-full animate-pulse">
              <AlertTriangle size={12} />
              {criticalCount} alerts
            </span>
          )}
          <button className="p-1 hover:bg-slate-700 rounded">
            <RefreshCw size={16} className="text-slate-400" />
          </button>
        </div>
      </header>

      {/* Main layout: Map + Side Panel */}
      <div className="flex flex-1 overflow-hidden">
        {/* Map */}
        <div className="flex-1 relative">
          <FloodMap />
          <DemoControls />
        </div>

        {/* Side Panel — desktop only */}
        {panelOpen && (
          <aside className="hidden md:flex w-80 xl:w-96 flex-col bg-slate-800 border-l border-slate-700 overflow-hidden shrink-0">
            {/* AI Situation Brief */}
            <SituationPanel />

            {/* Tab strip */}
            <div className="flex border-b border-slate-700 shrink-0">
              {TABS.map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`flex-1 py-2 text-xs font-medium transition-colors ${
                    activeTab === tab
                      ? 'bg-slate-700 text-white border-b-2 border-blue-500'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-y-auto">
              {activeTab === 'Alerts' && <AlertList />}
              {activeTab === 'Assets' && <AssetPanel />}
              {activeTab === 'Freshness' && <DataFreshness />}
            </div>
          </aside>
        )}
      </div>

      {/* Mobile bottom drawer — hidden on md+ */}
      <div
        className="md:hidden fixed bottom-0 left-0 right-0 z-[900] bg-slate-800 border-t border-slate-700 flex flex-col transition-transform duration-300"
        style={{
          height: '70vh',
          transform: drawerOpen ? 'translateY(0)' : 'translateY(calc(100% - 60px))',
        }}
      >
        {/* Handle bar / collapsed header */}
        <div
          className="h-[60px] flex items-center justify-between px-4 cursor-pointer shrink-0"
          onClick={toggleDrawer}
        >
          <span className="text-sm text-slate-300 font-medium">
            {drawerAlertCount} alert{drawerAlertCount !== 1 ? 's' : ''}
            {topSevLabel ? ` · ${topSevLabel}` : ''}
          </span>
          <div className="flex items-center gap-2">
            {criticalCount > 0 && (
              <span className="flex items-center gap-1 bg-red-600 text-white text-xs font-bold px-2 py-0.5 rounded-full">
                <AlertTriangle size={10} />
                {criticalCount}
              </span>
            )}
            {drawerOpen
              ? <ChevronDown size={16} className="text-slate-400" />
              : <ChevronUp size={16} className="text-slate-400" />
            }
          </div>
        </div>

        {/* Drawer content */}
        <div className="flex-1 overflow-y-auto min-h-0">
          <SituationPanel />
          <AlertList />
        </div>
      </div>
    </div>
  )
}
