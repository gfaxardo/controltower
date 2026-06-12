import { useState, useEffect, useCallback } from 'react'
import useGrowthIntelligence from './lima-growth-ui1a/hooks/useGrowthIntelligence.js'
import FreshnessBanner from './lima-growth-ui1a/components/FreshnessBanner.jsx'
import OverviewTab from './lima-growth-ui1a/sections/OverviewTab.jsx'
import ProgramsTab from './lima-growth-ui1a/sections/ProgramsTab.jsx'
import SegmentsTab from './lima-growth-ui1a/sections/SegmentsTab.jsx'
import MovementTab from './lima-growth-ui1a/sections/MovementTab.jsx'
import RNATab from './lima-growth-ui1a/sections/RNATab.jsx'
import DriverExplorerTab from './lima-growth-ui1a/sections/DriverExplorerTab.jsx'
import EffectivenessTab from './lima-growth-ui1a/sections/EffectivenessTab.jsx'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'programs', label: 'Programs' },
  { id: 'segments', label: 'Segments' },
  { id: 'movement', label: 'Movement' },
  { id: 'rna', label: 'RNA' },
  { id: 'explorer', label: 'Driver Explorer' },
  { id: 'effectiveness', label: 'Effectiveness' },
]

export default function LimaGrowthDashboardUI1A() {
  const [operationalDate, setOperationalDate] = useState(null)
  const [dateLoading, setDateLoading] = useState(true)
  const [dateError, setDateError] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')
  const [drilldownFilter, setDrilldownFilter] = useState(null)

  const { data, loading, errors, fetchSection, retryAll } = useGrowthIntelligence(operationalDate)

  useEffect(() => {
    let cancelled = false
    import('../services/api.js').then((m) =>
      m.default.get('/yego-lima-growth/refresh/operational-date')
    ).then((resp) => {
      if (cancelled) return
      const d = resp.data
      if (d?.operational_data_date) {
        setOperationalDate(d.operational_data_date)
        setDateLoading(false)
      } else {
        setDateError('No operational data found.')
        setDateLoading(false)
      }
    }).catch(() => {
      if (cancelled) return
      setDateLoading(false)
      setDateError('Backend unreachable.')
    })
    return () => { cancelled = true }
  }, [])

  const handleDrilldown = useCallback((filter) => {
    setDrilldownFilter(filter)
    setActiveTab('explorer')
  }, [])

  const clearDrilldown = useCallback(() => {
    setDrilldownFilter(null)
  }, [])

  const health = data.health
  const freshness = data.freshness
  const operability = data.operability
  const bannerLoading = loading.health && loading.freshness && loading.operability

  if (dateLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto mb-4" />
          <p className="text-sm text-gray-500">Inicializando Growth Intelligence Dashboard...</p>
        </div>
      </div>
    )
  }

  if (dateError && !operationalDate) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md text-center">
          <p className="text-sm font-bold text-red-800">ERROR</p>
          <p className="text-xs text-red-600 mt-2">{dateError}</p>
          <p className="text-xs text-red-400 mt-1">Verifica conectividad con el backend.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-screen bg-[#f6f8fb]">
      {/* Sidebar */}
      <aside className="w-52 flex-shrink-0 flex flex-col" style={{ backgroundColor: '#06244a' }}>
        <div className="px-4 py-5 border-b border-white/10">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-blue-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            <span className="text-white font-semibold text-sm">Lima Growth</span>
          </div>
          <p className="text-xs text-white/40 mt-1">Intelligence View</p>
        </div>
        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => { setActiveTab(tab.id); clearDrilldown() }}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all flex items-center gap-2 ${
                activeTab === tab.id
                  ? 'bg-white/15 text-white font-medium'
                  : 'text-white/60 hover:text-white hover:bg-white/5'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
        <div className="px-3 py-3 border-t border-white/10">
          <div className="text-xs text-white/40">
            <span>Date: {operationalDate || '—'}</span>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        {/* Freshness Banner */}
        <FreshnessBanner
          health={health}
          freshness={freshness}
          operability={operability}
          loading={bannerLoading}
        />

        {/* Drilldown filter context */}
        {drilldownFilter && activeTab === 'explorer' && (
          <div className="bg-blue-50 border-b border-blue-100 px-6 py-2 flex items-center gap-2 text-xs">
            <span className="text-blue-600 font-medium">Filter active:</span>
            {drilldownFilter.program && <span className="text-blue-500">Program: {drilldownFilter.program}</span>}
            {drilldownFilter.lifecycle && <span className="text-blue-500">Lifecycle: {drilldownFilter.lifecycle}</span>}
            {drilldownFilter.segment && <span className="text-blue-500">Segment: {drilldownFilter.segment}</span>}
            {drilldownFilter.driverId && <span className="text-blue-500">Driver: {drilldownFilter.driverId}</span>}
            <span className="flex-1" />
            <button onClick={clearDrilldown} className="text-blue-400 hover:text-blue-600 underline">Clear</button>
          </div>
        )}

        {/* Degraded state banner */}
        {health?.system_status === 'DEGRADED' || health?.system_status === 'CRITICAL' ? (
          <div className={`px-6 py-2 text-xs font-medium ${health.system_status === 'CRITICAL' ? 'bg-red-50 text-red-700' : 'bg-orange-50 text-orange-700'}`}>
            System {health.system_status}: Some data may be incomplete. UI remains operational.
          </div>
        ) : null}

        <div className="p-6">
          {activeTab === 'overview' && (
            <OverviewTab data={data} loading={loading} errors={errors} onRetry={retryAll} />
          )}
          {activeTab === 'programs' && (
            <ProgramsTab data={data} loading={loading} errors={errors} onRetry={retryAll} onDrilldown={(program) => handleDrilldown({ program })} />
          )}
          {activeTab === 'segments' && (
            <SegmentsTab data={data} loading={loading} errors={errors} onRetry={retryAll} onDrilldown={(f) => handleDrilldown(f)} />
          )}
          {activeTab === 'movement' && (
            <MovementTab data={data} loading={loading} errors={errors} onRetry={retryAll} onDrilldown={(f) => handleDrilldown(f)} />
          )}
          {activeTab === 'rna' && (
            <RNATab data={data} loading={loading} errors={errors} onRetry={retryAll} onDrilldown={(f) => handleDrilldown(f)} />
          )}
          {activeTab === 'explorer' && (
            <DriverExplorerTab data={data} loading={loading} errors={errors} onRetry={retryAll} initialFilter={drilldownFilter} />
          )}
          {activeTab === 'effectiveness' && (
            <EffectivenessTab />
          )}
        </div>
      </main>
    </div>
  )
}
