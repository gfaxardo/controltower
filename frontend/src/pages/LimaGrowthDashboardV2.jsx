import { useState, useEffect, useCallback } from 'react'
import useLimaGrowthData from './lima-growth-v2/hooks/useLimaGrowthData.js'
import TodayActionPlanSection from './lima-growth-v2/sections/TodayActionPlanSection.jsx'
import ProgramsSection from './lima-growth-v2/sections/ProgramsSection.jsx'
import ExecutionQueueSection from './lima-growth-v2/sections/ExecutionQueueSection.jsx'
import ControlConfigSection from './lima-growth-v2/sections/ControlConfigSection.jsx'
import IntradaySignalsSection from './lima-growth-v2/sections/IntradaySignalsSection.jsx'
import { formatNum, StatusBadge, HealthDot, StaleDataBanner } from './lima-growth-v2/components/SharedComponents.jsx'

const NAV_ITEMS = [
  { id: 'action_plan', label: "Today's Action Plan", testid: 'nav-today-action-plan' },
  { id: 'programs', label: 'Programas y Estado', testid: 'nav-programs' },
  { id: 'queue', label: 'Execution Queue', testid: 'nav-execution-queue' },
  { id: 'intraday_signals', label: 'Intraday Signals', testid: 'nav-intraday-signals' },
  { id: 'config', label: 'Configuracion', testid: 'nav-control-config' },
]

export default function LimaGrowthDashboardV2() {
  const [operationalDate, setOperationalDate] = useState(null)
  const [dateLoading, setDateLoading] = useState(true)
  const [dateError, setDateError] = useState(null)
  const [governance, setGovernance] = useState(null)
  const [governanceError, setGovernanceError] = useState(null)
  const [activeSection, setActiveSection] = useState('action_plan')
  const [crossSectionFilter, setCrossSectionFilter] = useState(null)
  const { data, loading, errors, refreshQueue, buildQueue, exportQueue, saveCapacity, fetchSection } = useLimaGrowthData(operationalDate)

  useEffect(() => {
    let cancelled = false
    import('../services/api.js').then(m => {
      return m.api.get('/yego-lima-growth/refresh/operational-date')
    }).then(resp => {
      if (cancelled) return
      const d = resp.data
      if (d?.operational_data_date) {
        setOperationalDate(d.operational_data_date)
        setDateLoading(false)
      } else {
        setDateError('No operational data found. Run refresh pipeline.')
        setDateLoading(false)
      }
    }).catch((err) => {
      if (cancelled) return
      setDateLoading(false)
      setDateError('Backend unreachable: operational-date endpoint failed. Check API connectivity.')
    })

    import('../services/api.js').then(m => {
      return m.api.get('/yego-lima-growth/refresh/governance-status')
    }).then(resp => {
      if (cancelled) return
      setGovernance(resp.data)
    }).catch((err) => {
      if (cancelled) return
      setGovernanceError('Governance status endpoint failed. Check server logs.')
    })
    return () => { cancelled = true }
  }, [])

  const handleRetryAll = () => {
    fetchSection('todayActionPlan', () => import('../services/api.js').then(m => m.getLimaGrowthTodayActionPlan(operationalDate)))
    fetchSection('summary', () => import('../services/api.js').then(m => m.getLimaGrowthOperationalSummary(operationalDate)))
    fetchSection('driverState', () => import('../services/api.js').then(m => m.getLimaGrowthDriverStateSummary(operationalDate)))
    fetchSection('programs', () => import('../services/api.js').then(m => m.getLimaGrowthProgramsSummary(operationalDate)))
    fetchSection('intradaySignals', () => import('../services/api.js').then(m => m.getLimaGrowthIntradaySignalsSummary(operationalDate)))
    fetchSection('intradaySignalsByCampaign', () => import('../services/api.js').then(m => m.getLimaGrowthIntradaySignalsByCampaign(operationalDate)))
    fetchSection('intradaySignalsByProgram', () => import('../services/api.js').then(m => m.getLimaGrowthIntradaySignalsByProgram(operationalDate)))
  }

  const navigateTo = useCallback((section, filter = null) => {
    setActiveSection(section)
    setCrossSectionFilter(filter)
    if (section === 'config' && filter?.scrollTo) {
      setTimeout(() => {
        const el = document.getElementById(filter.scrollTo)
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }, 300)
    }
  }, [])

  const clearFilter = useCallback(() => {
    setCrossSectionFilter(null)
  }, [])

  const summary = data.summary
  const plan = data.todayActionPlan
  const config = data.config

  return (
    <div className="flex h-full min-h-screen bg-[#f6f8fb]">
      {/* Sidebar */}
      <aside className="w-52 flex-shrink-0 flex flex-col" style={{ backgroundColor: '#06244a' }}>
        <div className="px-4 py-5 border-b border-white/10">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            <span className="text-white font-semibold text-sm">Lima Growth</span>
          </div>
          <p className="text-xs text-white/50 mt-1">Engine v2.0</p>
        </div>
        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              data-testid={item.testid}
              onClick={() => navigateTo(item.id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all flex items-center gap-2 ${
                activeSection === item.id ? 'bg-white/15 text-white font-medium' : 'text-white/60 hover:text-white hover:bg-white/5'
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="px-3 py-3 border-t border-white/10">
          <div className="flex items-center gap-2 text-xs text-white/40">
            <span className={`w-2 h-2 rounded-full ${config?.enabled ? 'bg-green-400' : 'bg-gray-400'}`} />
            LC: {config?.mode || '...'}
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        <header className="bg-white border-b border-gray-100 px-6 py-3 flex items-center justify-between sticky top-0 z-10">
          <div>
            <h1 className="text-lg font-bold text-gray-800">YEGO Lima Growth Engine</h1>
            <p className="text-xs text-gray-400">
              {plan?.operational_status === 'QUEUE_NOT_BUILT' ? 'Cola no construida — ve a Execution Queue' :
               plan?.operational_status === 'READY_TO_EXPORT' ? 'Listo para exportar — ejecuta las acciones recomendadas' :
               plan?.operational_status === 'READY_WITH_BLOCKERS' ? 'Hay bloqueadores — resuelve HELD primero' :
               'Pipeline operacional: Universo → Priorizacion → Capacidad → Queue → Export'}
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs text-gray-400">
            <span>Fecha data: {operationalDate}</span>
            <span>Universo: {formatNum(summary?.universe_total) || '...'}</span>
            <span>READY: {formatNum(plan?.workload?.ready) ?? '...'}</span>
            <span>HELD: {formatNum(plan?.workload?.held) ?? '...'}</span>
            {(plan?.freshness?.driver_snapshot?.status === 'STALE' || plan?.freshness?.driver_snapshot?.status === 'WARNING') && (
              <span className="text-yellow-500">Datos {plan.freshness.driver_snapshot.status}</span>
            )}
          </div>
        </header>

        {/* Breadcrumb / Filter context */}
        {crossSectionFilter && (
          <div className="bg-blue-50 border-b border-blue-100 px-6 py-2 flex items-center gap-2 text-xs">
            <span className="text-blue-600 font-medium">
              {crossSectionFilter.label || 'Filtro activo'}
            </span>
            {crossSectionFilter.program && <span className="text-blue-500">Programa: {crossSectionFilter.program.replace('PROGRAM_', '')}</span>}
            {crossSectionFilter.status && <span className="text-blue-500">Status: {crossSectionFilter.status}</span>}
            {crossSectionFilter.channel && <span className="text-blue-500">Canal: {crossSectionFilter.channel}</span>}
            <span className="flex-1" />
            <button onClick={clearFilter} className="text-blue-400 hover:text-blue-600 underline">Limpiar filtro</button>
          </div>
        )}

        <div className="p-6">
          {dateLoading && (
            <div className="flex items-center justify-center py-20">
              <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-3" />
                <p className="text-sm text-gray-500">Cargando operational date...</p>
              </div>
            </div>
          )}

          {dateError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4">
              <p className="text-xs font-bold text-red-800">ERROR: {dateError}</p>
              <p className="text-xs text-red-600 mt-1">
                La UI NO puede usar un valor default silencioso. Verifica conectividad con backend.
              </p>
              {operationalDate && (
                <p className="text-xs text-red-400 mt-1">Fallback date activo: {operationalDate} (ultimo valor conocido)</p>
              )}
            </div>
          )}

          {governanceError && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 text-xs text-red-700">
              {governanceError}
            </div>
          )}

          {/* Governance Banner */}
          {governance && !governance.is_operable_today && (
            <div className="bg-red-100 border border-red-300 rounded-lg p-4 mb-4">
              <p className="text-sm font-bold text-red-800">NO usar para operacion diaria</p>
              <p className="text-xs text-red-600 mt-1">
                Data cerrada: {governance.operational_data_date} ({governance.days_behind} dias de atraso).
                {governance.freshness_status === 'STALE' && ` Datos desactualizados (${governance.freshness_age_minutes}min).`}
              </p>
              {governance.blocking_reasons?.map((r, i) => <p key={i} className="text-xs text-red-500">- {r}</p>)}
              {governance.required_action && (
                <p className="text-xs text-red-600 mt-1 font-medium">{governance.required_action}</p>
              )}
            </div>
          )}

          {governance?.operability === 'OPERABLE_STALE_WARNING' && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-4 text-xs text-yellow-700">
              Datos {governance.days_behind} dia(s) de atraso. Ultimo refresh: {governance.last_successful_refresh_at || 'nunca'}.
              {governance.required_action && <span className="block mt-1 font-medium">{governance.required_action}</span>}
            </div>
          )}

          {/* Governance Summary */}
          {governance && (
            <div className="flex items-center gap-3 mb-4 text-xs text-gray-500 bg-gray-50 rounded-lg px-4 py-2">
              <span className="font-medium">Refresh Governance:</span>
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                governance.operability === 'OPERABLE' ? 'bg-green-100 text-green-700' :
                governance.operability === 'OPERABLE_STALE_WARNING' ? 'bg-yellow-100 text-yellow-700' :
                'bg-red-100 text-red-700'
              }`}>{governance.operability}</span>
              <span>|</span>
              <span>Facts: {governance.facts?.filter(f => f.status === 'OK').length || 0} OK</span>
              {governance.facts?.filter(f => f.status === 'STALE').length > 0 && (
                <span className="text-yellow-600">/ {governance.facts.filter(f => f.status === 'STALE').length} STALE</span>
              )}
              {governance.facts?.filter(f => f.status === 'MISSING').length > 0 && (
                <span className="text-red-600">/ {governance.facts.filter(f => f.status === 'MISSING').length} MISSING</span>
              )}
              <span className="flex-1" />
              <span>Data: {governance.operational_data_date}</span>
            </div>
          )}

          {/* Global stale data warning */}
          {plan?.freshness && (
            <StaleDataBanner freshness={plan.freshness.driver_snapshot} className="mb-3" />
          )}

          {activeSection === 'action_plan' && (
            <div id="today-action-plan-section" data-testid="today-action-plan-section">
              <TodayActionPlanSection data={data} loading={loading} errors={errors} onRetry={handleRetryAll} navigateTo={navigateTo} />
            </div>
          )}
          {activeSection === 'programs' && (
            <div id="programs-section" data-testid="programs-section">
              <ProgramsSection data={data} loading={loading} errors={errors} onRetry={handleRetryAll} sectionFilter={crossSectionFilter} />
            </div>
          )}
          {activeSection === 'queue' && (
            <div id="execution-queue-section" data-testid="execution-queue-section">
              <ExecutionQueueSection
                data={data} loading={loading} errors={errors}
                onBuildQueue={buildQueue} onExport={exportQueue}
                onRefresh={(filters) => refreshQueue(filters)}
                sectionFilter={crossSectionFilter}
                navigateTo={navigateTo}
              />
            </div>
          )}
          {activeSection === 'config' && (
            <div id="control-config-section" data-testid="control-config-section">
              <ControlConfigSection data={data} loading={loading} errors={errors} onSaveCapacity={saveCapacity} navigateTo={navigateTo} />
            </div>
          )}
          {activeSection === 'intraday_signals' && (
            <div id="intraday-signals-section" data-testid="intraday-signals-section">
              <IntradaySignalsSection data={data} loading={loading} errors={errors} onRetry={handleRetryAll} navigateTo={navigateTo} />
            </div>
          )}
        </div>
      </main>
    </div>
  )
}