import { useState, useEffect, useCallback } from 'react'
import FreshnessBanner from './lima-growth-ui1a/components/FreshnessBanner.jsx'
import ComandoDiarioSection from './lima-growth-ui1a/sections/ComandoDiarioSection.jsx'
import ListasTrabajoSection from './lima-growth-ui1a/sections/ListasTrabajoSection.jsx'

const TABS = [
  { id: 'comando', label: 'Comando Diario', enabled: true },
  { id: 'listas', label: 'Listas de Trabajo', enabled: true },
  { id: 'explorer', label: 'Explorador', enabled: true },
  { id: 'movement', label: 'Movimientos', enabled: false },
  { id: 'control', label: 'Control Loop', enabled: false },
  { id: 'resultados', label: 'Resultados', enabled: false },
]

function PlaceholderTab({ label, phase }) {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="text-center bg-gray-50 border border-gray-200 rounded-lg p-8 max-w-md">
        <span className="text-3xl block mb-2">🚧</span>
        <p className="text-sm font-bold text-gray-600">{label}</p>
        <p className="text-xs text-gray-400 mt-1">Próxima fase: {phase}</p>
      </div>
    </div>
  )
}

export default function LimaGrowthDashboardUI1A() {
  const [operationalDate, setOperationalDate] = useState(null)
  const [dateLoading, setDateLoading] = useState(true)
  const [dateError, setDateError] = useState(null)
  const [activeTab, setActiveTab] = useState('comando')
  const [bannerFreshness, setBannerFreshness] = useState(null)

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

  // ── LG-UI-LISTS-1C.1: Freshness Banner from exclusive-worklist summary ──
  useEffect(() => {
    let cancelled = false
    import('../services/api.js').then((m) =>
      m.getExclusiveWorklistSummary()
    ).then((result) => {
      if (cancelled) return
      const today = new Date().toISOString().substring(0, 10)
      const resolved = result?.resolved_generated_date
      const isFresh = resolved === today || resolved === operationalDate
      setBannerFreshness({
        system_status: result ? (isFresh ? 'HEALTHY' : 'WARNING') : 'CRITICAL',
        components_healthy: result ? 1 : 0,
        components_degraded: result && !isFresh ? 1 : 0,
        components_critical: result ? 0 : 1,
        stale_assets: result && !isFresh ? [{ name: `Worklist date: ${resolved}` }] : [],
        scheduler_status: isFresh ? 'RUNNING' : 'STALE',
        remediation: !result ? 'Exclusive worklist endpoint unreachable.' : (!isFresh ? `Worklist date ${resolved} may be stale.` : null),
      })
    }).catch(() => setBannerFreshness({ system_status: 'CRITICAL', remediation: 'Exclusive worklist endpoint unreachable.' }))
    return () => { cancelled = true }
  }, [operationalDate])

  if (dateLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto mb-4" />
          <p className="text-sm text-gray-500">Loading Growth Intelligence...</p>
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
          <p className="text-xs text-red-400 mt-1">Check backend connectivity.</p>
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
          <p className="text-xs text-white/40 mt-1">Intelligence View · LG-UI-LISTS-1C</p>
        </div>
        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => { if (tab.enabled) setActiveTab(tab.id) }}
              disabled={!tab.enabled}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all flex items-center gap-2 ${
                !tab.enabled ? 'text-white/20 cursor-not-allowed' :
                activeTab === tab.id ? 'bg-white/15 text-white font-medium' : 'text-white/60 hover:text-white hover:bg-white/5'
              }`}
            >
              {tab.label}
              {!tab.enabled && <span className="text-[10px] ml-auto opacity-40">soon</span>}
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
        <FreshnessBanner health={bannerFreshness} freshness={null} operability={null} loading={!bannerFreshness} />

        <div className="p-6">
          {activeTab === 'comando' && <ComandoDiarioSection />}
          {activeTab === 'listas' && <ListasTrabajoSection />}
          {activeTab === 'explorer' && <PlaceholderTab label="Explorador de Conductores" phase="LG-UI-DRILLDOWN-1D" />}
          {activeTab === 'movement' && <PlaceholderTab label="Movimientos" phase="LG-UI-MOVEMENT-1F" />}
          {activeTab === 'control' && <PlaceholderTab label="Control Loop" phase="LG-UI-CONTROL-1E" />}
          {activeTab === 'resultados' && <PlaceholderTab label="Resultados" phase="LG-UI-ACTIONS-1G" />}
        </div>
      </main>
    </div>
  )
}
