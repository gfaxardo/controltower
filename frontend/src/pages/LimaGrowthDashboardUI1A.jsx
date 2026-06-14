import React, { useState, useEffect } from 'react'
import api from '../services/api.js'
import { getExclusiveWorklistSummary, getExclusiveWorklistControlLoopPreview } from '../services/api.js'
import FreshnessBanner from './lima-growth-ui1a/components/FreshnessBanner.jsx'
import ComandoDiarioSection from './lima-growth-ui1a/sections/ComandoDiarioSection.jsx'
import ListasTrabajoSection from './lima-growth-ui1a/sections/ListasTrabajoSection.jsx'

const TABS = [
  { id: 'comando', label: 'Comando Diario', enabled: true },
  { id: 'listas', label: 'Listas de Trabajo', enabled: true },
  { id: 'explorer', label: 'Explorador', enabled: false },
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
  const [bannerStatus, setBannerStatus] = useState('loading')

  // Fetch operational date
  useEffect(() => {
    let cancelled = false
    api.get('/yego-lima-growth/refresh/operational-date')
      .then((resp) => {
        if (cancelled) return
        const d = resp.data
        if (d?.operational_data_date) {
          setOperationalDate(d.operational_data_date)
        } else {
          setDateError('No operational data found.')
        }
      })
      .catch(() => {
        if (cancelled) return
        setDateError('Backend unreachable.')
      })
      .finally(() => {
        if (!cancelled) setDateLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  // Fetch freshness from exclusive-worklist summary
  useEffect(() => {
    let cancelled = false
    getExclusiveWorklistSummary()
      .then((result) => {
        if (cancelled) return
        const today = new Date().toISOString().substring(0, 10)
        const resolved = result?.resolved_generated_date
        const isFresh = resolved === today || resolved === operationalDate
        setBannerStatus(isFresh ? 'HEALTHY' : (resolved ? 'WARNING' : 'UNKNOWN'))
      })
      .catch(() => {
        if (cancelled) return
        setBannerStatus('CRITICAL')
      })
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

  // Simple freshness banner
  const bannerColor = 
    bannerStatus === 'loading' ? 'bg-gray-50 border-gray-200 text-gray-500' :
    bannerStatus === 'HEALTHY' ? 'bg-green-50 border-green-200 text-green-700' :
    bannerStatus === 'WARNING' ? 'bg-yellow-50 border-yellow-200 text-yellow-700' :
    bannerStatus === 'UNKNOWN' ? 'bg-gray-50 border-gray-200 text-gray-600' :
    'bg-red-50 border-red-200 text-red-700'

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
          <p className="text-xs text-white/40 mt-1">Intelligence View · LG-UI-LISTS-1C.3</p>
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
        {/* Freshness bar */}
        <div className={`border-b px-4 py-2 text-xs font-medium ${bannerColor}`}>
          {bannerStatus === 'loading' ? 'Verificando datos...' :
           bannerStatus === 'HEALTHY' ? '● Worklist data is current' :
           bannerStatus === 'WARNING' ? '● Worklist date may be behind' :
           bannerStatus === 'UNKNOWN' ? '● Freshness unknown — data may be stale' :
           '● Backend unreachable — check connectivity'}
        </div>

        <div className="p-6">
          {activeTab === 'comando' && <ErrorBoundary><ComandoDiarioSection /></ErrorBoundary>}
          {activeTab === 'listas' && <ErrorBoundary><ListasTrabajoSection /></ErrorBoundary>}
          {activeTab === 'explorer' && <PlaceholderTab label="Explorador de Conductores" phase="LG-UI-DRILLDOWN-1D" />}
          {activeTab === 'movement' && <PlaceholderTab label="Movimientos" phase="LG-UI-MOVEMENT-1F" />}
          {activeTab === 'control' && <PlaceholderTab label="Control Loop" phase="LG-UI-CONTROL-1E" />}
          {activeTab === 'resultados' && <PlaceholderTab label="Resultados" phase="LG-UI-ACTIONS-1G" />}
        </div>
      </main>
    </div>
  )
}

// Minimal error boundary to prevent white screen
class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <p className="text-sm font-bold text-red-800">Component Error</p>
          <p className="text-xs text-red-600 mt-1 font-mono">{this.state.error?.message || 'Unknown error'}</p>
          <button onClick={() => this.setState({ hasError: false })} className="mt-3 px-3 py-1 bg-red-600 text-white rounded text-xs">Retry</button>
        </div>
      )
    }
    return this.props.children
  }
}
