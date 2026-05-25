/**
 * YEGO Control Tower — App principal.
 * Navegación fusionada en barra única. Paleta gris armónica.
 * Solo se muestran vistas KEEP_VISIBLE + productionReady del motor ACTIVE o READY NEXT.
 * FASE 1H.4 — Operational Maturity Governance: badges de madurez en navegación.
 */
import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate, useLocation, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext.jsx'
import { CONTROL_TOWER_NAVIGATION_REGISTRY, VISIBILITY, getVisibleTabs } from './config/controlTowerNavigationRegistry'
import { getMaturityBadgeInfo, OPERATIONAL_MATURITY_REGISTRY } from './config/operationalMaturityRegistry.js'
import LoginView from './components/LoginView.jsx'
import CollapsibleFilters from './components/CollapsibleFilters'
import ExecutiveSnapshotView from './components/ExecutiveSnapshotView'
import MonthlySplitView from './components/MonthlySplitView'
import WeeklyPlanVsRealView from './components/WeeklyPlanVsRealView'
import Phase2BActionsTrackingView from './components/Phase2BActionsTrackingView'
import Phase2CAccountabilityView from './components/Phase2CAccountabilityView'
import LobUniverseView from './components/LobUniverseView'
import RealLOBDrillView from './components/RealLOBDrillView'
import BusinessSliceView from './components/BusinessSliceView'
import BusinessSliceOmniview from './components/BusinessSliceOmniview'
import BusinessSliceOmniviewMatrix from './components/BusinessSliceOmniviewMatrix'
import OmniviewErrorBoundary from './components/OmniviewErrorBoundary'
import BusinessSliceOmniviewReports from './components/BusinessSliceOmniviewReports'
import ControlLoopPlanVsRealView from './components/ControlLoopPlanVsRealView'
import RealOperationalView from './components/RealOperationalView'
import DriverLifecycleView from './components/DriverLifecycleView'
import DriverLifecycleDashboard from './components/driverLifecycle/DriverLifecycleDashboard'
import DriverBehaviorBenchmarkingDashboard from './components/driverBehavior/DriverBehaviorBenchmarkingDashboard'
import SupplyView from './components/SupplyView'
import BehavioralAlertsView from './components/BehavioralAlertsView'
import FleetLeakageView from './components/FleetLeakageView'
import BehavioralPatternDiagnosisDashboard from './components/behavioralPatterns/BehavioralPatternDiagnosisDashboard'
import OperationalBehavioralIntelligenceDashboard from './components/operationalIntelligence/OperationalBehavioralIntelligenceDashboard'
import RecoverabilityIntelligenceDashboard from './components/recoverability/RecoverabilityIntelligenceDashboard'
import DriverBehaviorView from './components/DriverBehaviorView'
import ActionEngineView from './components/ActionEngineView'
import SystemHealthView from './components/SystemHealthView'
import GlobalFreshnessBanner from './components/GlobalFreshnessBanner'
import RealMarginQualityCard from './components/RealMarginQualityCard'
import UploadPlan from './components/UploadPlan'
import PlanTabs from './components/PlanTabs'
import BacklogPlaceholder from './components/BacklogPlaceholder'
import OperationalOpportunitiesView from './components/operacion/OperationalOpportunitiesView'
import YangoLoyaltyView from './components/yangoLoyalty/YangoLoyaltyView'
import { MaturityStatusBar } from './components/operational/MaturityIndicators.jsx'

const TAB_PERFORMANCE = 'Performance'
const TAB_DRIVERS = 'Drivers'
const TAB_RISK = 'Riesgo'
const TAB_OPERACION = 'Operación'
const TAB_PLAN = 'Plan'
const TAB_SYSTEM_HEALTH = 'Diagnósticos'

const VISIBLE_TABS = getVisibleTabs()

const MAIN_NAV_TABS = Array.from(VISIBLE_TABS.keys())
  .filter((tab) => !['En revisión'].includes(tab))
  .map((tab) => ({ id: tab, label: tab }))

function getSubtabsForTab (tab) {
  const entries = VISIBLE_TABS.get(tab) || []
  return entries.map((e) => ({ id: e.key, label: e.label }))
}

const SUBTABS_MAP = {
  [TAB_PERFORMANCE]: getSubtabsForTab(TAB_PERFORMANCE),
  [TAB_DRIVERS]: getSubtabsForTab(TAB_DRIVERS),
  [TAB_RISK]: getSubtabsForTab(TAB_RISK),
  [TAB_PLAN]: getSubtabsForTab(TAB_PLAN),
  [TAB_OPERACION]: getSubtabsForTab(TAB_OPERACION),
}

const ROUTE_MAP = [
  { path: '/', tab: TAB_OPERACION, sub: 'operacion_omniview_matrix' },
  { path: '/performance', tab: TAB_PERFORMANCE, sub: 'performance_resumen' },
  { path: '/performance/resumen', tab: TAB_PERFORMANCE, sub: 'performance_resumen' },
  { path: '/performance/plan-vs-real', tab: TAB_PERFORMANCE, sub: 'performance_plan_vs_real' },
  { path: '/performance/real', tab: TAB_PERFORMANCE, sub: 'performance_real' },
  { path: '/performance/yango-loyalty', tab: TAB_PERFORMANCE, sub: 'performance_yango_loyalty' },
  { path: '/drivers', tab: TAB_DRIVERS, sub: 'drivers_supply' },
  { path: '/drivers/supply', tab: TAB_DRIVERS, sub: 'drivers_supply' },
  { path: '/drivers/lifecycle', tab: TAB_DRIVERS, sub: 'drivers_lifecycle' },
  { path: '/drivers/diagnostic', tab: TAB_DRIVERS, sub: 'drivers_diagnostic' },
  { path: '/drivers/behavior-benchmarking', tab: TAB_DRIVERS, sub: 'drivers_behavior_benchmarking' },
  { path: '/drivers/behavioral-alerts', tab: TAB_DRIVERS, sub: 'drivers_behavioral_alerts' },
  { path: '/drivers/fleet-leakage', tab: TAB_DRIVERS, sub: 'drivers_fleet_leakage' },
  { path: '/drivers/behavioral-patterns', tab: TAB_DRIVERS, sub: 'drivers_behavioral_patterns' },
  { path: '/drivers/operational-intelligence', tab: TAB_DRIVERS, sub: 'drivers_operational_intelligence' },
  { path: '/drivers/recoverability', tab: TAB_DRIVERS, sub: 'drivers_recoverability' },
  { path: '/riesgo', tab: TAB_RISK, sub: 'riesgo_driver_behavior' },
  { path: '/riesgo/driver-behavior', tab: TAB_RISK, sub: 'riesgo_driver_behavior' },
  { path: '/operacion', tab: TAB_OPERACION, sub: 'operacion_omniview_matrix' },
  { path: '/operacion/lob-drill', tab: TAB_OPERACION, sub: 'operacion_lob_drill' },
  { path: '/operacion/business-slice', tab: TAB_OPERACION, sub: 'operacion_business_slice' },
  { path: '/operacion/omniview', tab: TAB_OPERACION, sub: 'operacion_omniview' },
  { path: '/operacion/omniview-matrix', tab: TAB_OPERACION, sub: 'operacion_omniview_matrix' },
  { path: '/operacion/control-loop-plan-vs-real', tab: TAB_OPERACION, sub: 'operacion_control_loop_pvr' },
  { path: '/operacion/reportes', tab: TAB_OPERACION, sub: 'operacion_reportes' },
  { path: '/operacion/oportunidades', tab: TAB_OPERACION, sub: 'operacion_oportunidades' },
  { path: '/plan', tab: TAB_PLAN, sub: 'plan_acciones' },
  { path: '/plan/acciones', tab: TAB_PLAN, sub: 'plan_acciones' },
  { path: '/plan/universo', tab: TAB_PLAN, sub: 'plan_universo' },
  { path: '/plan/validacion', tab: TAB_PLAN, sub: 'plan_validacion' },
  { path: '/diagnosticos', tab: TAB_SYSTEM_HEALTH, sub: 'system_health' },
]

const SUB_URL = {
  performance_resumen: '/performance/resumen',
  performance_plan_vs_real: '/performance/plan-vs-real',
  performance_real: '/performance/real',
  performance_yango_loyalty: '/performance/yango-loyalty',
  drivers_supply: '/drivers/supply',
  drivers_lifecycle: '/drivers/lifecycle',
  drivers_diagnostic: '/drivers/diagnostic',
  drivers_behavior_benchmarking: '/drivers/behavior-benchmarking',
  drivers_behavioral_alerts: '/drivers/behavioral-alerts',
  drivers_fleet_leakage: '/drivers/fleet-leakage',
  drivers_behavioral_patterns: '/drivers/behavioral-patterns',
  drivers_operational_intelligence: '/drivers/operational-intelligence',
  drivers_recoverability: '/drivers/recoverability',
  riesgo_driver_behavior: '/riesgo/driver-behavior',
  operacion_lob_drill: '/operacion/lob-drill',
  operacion_business_slice: '/operacion/business-slice',
  operacion_omniview: '/operacion/omniview',
  operacion_omniview_matrix: '/operacion/omniview-matrix',
  operacion_control_loop_pvr: '/operacion/control-loop-plan-vs-real',
  operacion_reportes: '/operacion/reportes',
  operacion_oportunidades: '/operacion/oportunidades',
  plan_acciones: '/plan/acciones',
  plan_universo: '/plan/universo',
  plan_validacion: '/plan/validacion',
  system_health: '/diagnosticos',
}

const TAB_DEFAULT_PATH = {
  [TAB_PERFORMANCE]: '/performance/resumen',
  [TAB_DRIVERS]: '/drivers/supply',
  [TAB_RISK]: '/riesgo/driver-behavior',
  [TAB_OPERACION]: '/operacion/omniview-matrix',
  [TAB_PLAN]: '/plan/acciones',
  [TAB_SYSTEM_HEALTH]: '/diagnosticos',
}

function parseRoute (pathname) {
  const match = ROUTE_MAP.find((r) => r.path === pathname)
  if (match) return match
  const prefix = ROUTE_MAP.find((r) => r.path !== '/' && pathname.startsWith(r.path))
  return prefix || ROUTE_MAP[0]
}

function ControlTowerApp () {
  const navigate = useNavigate()
  const location = useLocation()
  const { authRequired, logout, username, role } = useAuth()

  const parsed = parseRoute(location.pathname)
  const activeTab = parsed.tab
  const routeSub = parsed.sub

  const [filters, setFilters] = useState({ country: '', city: '', line_of_business: '', year_real: 2025, year_plan: 2026 })
  const [refreshKey, setRefreshKey] = useState(0)
  const [planValidacionInner, setPlanValidacionInner] = useState('out_of_universe')
  const [showAdminModal, setShowAdminModal] = useState(false)
  const [tabMenuOpen, setTabMenuOpen] = useState(false)
  const tabMenuRef = useRef(null)

  const performanceSubTab = activeTab === TAB_PERFORMANCE ? (routeSub || 'performance_resumen') : 'performance_resumen'
  const driversSubTab = activeTab === TAB_DRIVERS ? (routeSub || 'drivers_supply') : 'drivers_supply'
  const riskSubTab = activeTab === TAB_RISK ? (routeSub || 'riesgo_driver_behavior') : 'riesgo_driver_behavior'
  const operacionSubTab = activeTab === TAB_OPERACION ? (routeSub || 'operacion_omniview_matrix') : 'operacion_omniview_matrix'
  const planSubTab = activeTab === TAB_PLAN ? (routeSub || 'plan_acciones') : 'plan_acciones'

  const setActiveTab = useCallback((tab) => { navigate(TAB_DEFAULT_PATH[tab] || '/'); setTabMenuOpen(false) }, [navigate])
  const setSubTab = useCallback((subKey) => { navigate(SUB_URL[subKey] || '/'); setTabMenuOpen(false) }, [navigate])

  const handleUploadSuccess = () => { setRefreshKey(prev => prev + 1); setShowAdminModal(false) }
  const handleFilterChange = (newFilters) => setFilters(newFilters)

  useEffect(() => {
    function handleClickOutside (e) {
      if (tabMenuRef.current && !tabMenuRef.current.contains(e.target)) setTabMenuOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const activeSubtabs = SUBTABS_MAP[activeTab] || []
  const activeSub = [TAB_PERFORMANCE, TAB_DRIVERS, TAB_RISK, TAB_OPERACION, TAB_PLAN].includes(activeTab)
    ? routeSub
    : null
  const activeSubLabel = activeSubtabs.find((s) => s.id === activeSub)?.label || ''

  const tabBtn = (id, label) => (
    <button
      key={id}
      type="button"
      onClick={() => id === TAB_SYSTEM_HEALTH ? navigate('/diagnosticos') : setActiveTab(id)}
      className={`px-3 py-1.5 rounded-md text-xs font-medium whitespace-nowrap transition-all ${
        activeTab === id
          ? 'bg-white/15 text-white'
          : 'text-ct-nav-text/70 hover:text-white hover:bg-white/10'
      }`}
    >
      {label}
    </button>
  )

  const subPill = (id, label) => {
    const maturityInfo = getMaturityBadgeInfo(id)
    return (
      <button
        key={id}
        type="button"
        onClick={() => setSubTab(id)}
        className={`px-2.5 py-1 rounded text-xs font-medium transition-all inline-flex items-center gap-1.5 ${
          activeSub === id
            ? 'bg-ct-accent text-white shadow-sm'
            : 'text-ct-text2 hover:text-ct-text hover:bg-ct-border'
        }`}
      >
        {label}
        {maturityInfo && !(activeSub === id) && (
          <span className={`inline-block w-1 h-1 rounded-full ${maturityInfo.label.includes('construcción') ? 'bg-blue-400' : maturityInfo.label === 'Hardening' ? 'bg-amber-400' : 'bg-gray-400'}`} />
        )}
      </button>
    )
  }

  return (
    <div className="min-h-screen bg-ct-bg">
      {/* ── Barra única: logo + tabs + user ─────────────────────── */}
      <header className="sticky top-0 z-40 bg-ct-nav border-b border-white/10">
        <div className="h-11 px-4 flex items-center gap-3">
          <div className="flex items-center gap-2 flex-shrink-0">
            <div className="w-6 h-6 rounded bg-ct-accent flex items-center justify-center">
              <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
              </svg>
            </div>
            <span className="text-sm font-bold text-white tracking-tight hidden sm:inline">YEGO</span>
            <span className="text-sm text-ct-nav-text/50 hidden lg:inline">Control Tower</span>
          </div>

          {/* Tabs principales */}
          <nav className="flex items-center gap-0.5 flex-1 min-w-0 overflow-x-auto">
            {MAIN_NAV_TABS.map(({ id, label }) => tabBtn(id, label))}
          </nav>

          {/* Acciones derecha */}
          <div className="flex items-center gap-1.5 flex-shrink-0">
            {authRequired && username && (
              <span className="text-xs text-ct-nav-text/70 max-w-[8rem] truncate hidden md:inline" title={username}>{username}</span>
            )}
            {authRequired && (
              <button type="button" onClick={() => { logout(); navigate('/login', { replace: true }) }}
                className="px-2 py-1 rounded text-xs text-ct-nav-text/70 hover:text-white hover:bg-white/10 transition-colors">
                Salir
              </button>
            )}
            <button type="button" onClick={() => setShowAdminModal(true)}
              className="px-2 py-1 rounded text-xs text-ct-nav-text/70 hover:text-white hover:bg-white/10 transition-colors flex items-center gap-1">
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span className="hidden sm:inline">Admin</span>
            </button>
            <button type="button" onClick={() => navigate('/diagnosticos')}
              className={`px-2 py-1 rounded text-xs transition-colors ${
                activeTab === TAB_SYSTEM_HEALTH ? 'bg-white/15 text-white' : 'text-ct-nav-text/70 hover:text-white hover:bg-white/10'
              }`}>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />
              </svg>
            </button>
          </div>
        </div>

        {/* Sub-nav (solo si hay subtabs) */}
        {activeSubtabs.length > 1 && (
          <div className="bg-ct-surface border-b border-ct-border px-4 py-1.5 flex items-center gap-1.5 overflow-x-auto">
            {activeSubtabs.map(({ id, label }) => subPill(id, label))}
          </div>
        )}

        {/* ── Maturity status bar (FASE 1H.4) — visible para vistas no-STABLE ── */}
        {activeSub && OPERATIONAL_MATURITY_REGISTRY[activeSub] && OPERATIONAL_MATURITY_REGISTRY[activeSub].maturity !== 'stable' && (
          <div className="bg-ct-bg/80 border-b border-ct-border px-4 py-1 flex items-center gap-2 flex-wrap">
            <MaturityStatusBar
              moduleKey={activeSub}
              phase={OPERATIONAL_MATURITY_REGISTRY[activeSub].phase}
              engine={OPERATIONAL_MATURITY_REGISTRY[activeSub].engine}
            />
          </div>
        )}
      </header>

      {/* ========== CONTENIDO ========== */}
      <div className="ct-page w-full px-3 sm:px-4 py-2">
        {showAdminModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-ct-nav/60 p-4" role="dialog" aria-modal="true">
            <div className="bg-ct-card rounded-xl shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-5">
              <div className="flex justify-between items-center mb-3">
                <h2 className="text-base font-semibold text-ct-text">Subir Plan</h2>
                <button type="button" onClick={() => setShowAdminModal(false)} className="text-ct-text3 hover:text-ct-text text-xl leading-none">×</button>
              </div>
              <UploadPlan onUploadSuccess={handleUploadSuccess} />
            </div>
          </div>
        )}

        {/* Rutas ocultas */}
        {(location.pathname.startsWith('/en-revision') || location.pathname === '/riesgo/action-engine') ? (
          <BacklogPlaceholder />
        ) : (
          <>
            {operacionSubTab !== 'operacion_omniview_matrix' && operacionSubTab !== 'operacion_control_loop_pvr' && operacionSubTab !== 'operacion_reportes' && (
              <GlobalFreshnessBanner activeTab={activeTab === TAB_OPERACION || (activeTab === TAB_PERFORMANCE && performanceSubTab === 'performance_real') ? 'real' : activeTab} />
            )}
            {(activeTab === TAB_PERFORMANCE && performanceSubTab === 'performance_real') && <RealMarginQualityCard />}
            {(activeTab === TAB_OPERACION && operacionSubTab !== 'operacion_omniview_matrix' && operacionSubTab !== 'operacion_control_loop_pvr' && operacionSubTab !== 'operacion_reportes') && <RealMarginQualityCard />}
            {/* FASE 1H.3 — Omniview tiene sus propios filtros; omitir globales */}
            {!(activeTab === TAB_OPERACION && (operacionSubTab === 'operacion_omniview_matrix' || operacionSubTab === 'operacion_omniview' || operacionSubTab === 'operacion_business_slice')) && (
              <CollapsibleFilters onFilterChange={handleFilterChange} />
            )}

            {activeTab === TAB_PERFORMANCE && (
              <section aria-label="Performance">
                {performanceSubTab === 'performance_resumen' && <ExecutiveSnapshotView key={`snapshot-${refreshKey}`} filters={filters} refreshKey={refreshKey} />}
                {performanceSubTab === 'performance_plan_vs_real' && <><MonthlySplitView key={`monthly-${refreshKey}`} filters={filters} /><WeeklyPlanVsRealView key={`weekly-${refreshKey}`} filters={filters} /></>}
                {performanceSubTab === 'performance_real' && <RealOperationalView key={`real-operational-${refreshKey}`} country={filters.country} city={filters.city} />}
                {performanceSubTab === 'performance_yango_loyalty' && <YangoLoyaltyView key={`yango-loyalty-${refreshKey}`} />}
              </section>
            )}

            {activeTab === TAB_DRIVERS && (
              <section aria-label="Drivers">
                {driversSubTab === 'drivers_supply' && <SupplyView key={`supply-${refreshKey}`} />}
                {driversSubTab === 'drivers_lifecycle' && <DriverLifecycleView key={`driver-lifecycle-${refreshKey}`} />}
                {driversSubTab === 'drivers_diagnostic' && <DriverLifecycleDashboard key={`driver-diagnostic-${refreshKey}`} />}
                {driversSubTab === 'drivers_behavior_benchmarking' && <DriverBehaviorBenchmarkingDashboard key={`driver-behavior-bench-${refreshKey}`} />}
                {driversSubTab === 'drivers_behavioral_alerts' && <BehavioralAlertsView key={`behavioral-alerts-${refreshKey}`} />}
                {driversSubTab === 'drivers_fleet_leakage' && <FleetLeakageView key={`fleet-leakage-${refreshKey}`} />}
                {driversSubTab === 'drivers_behavioral_patterns' && <BehavioralPatternDiagnosisDashboard key={`behavioral-patterns-${refreshKey}`} />}
                {driversSubTab === 'drivers_operational_intelligence' && <OperationalBehavioralIntelligenceDashboard key={`operational-intel-${refreshKey}`} />}
                {driversSubTab === 'drivers_recoverability' && <RecoverabilityIntelligenceDashboard key={`recoverability-${refreshKey}`} />}
              </section>
            )}

            {activeTab === TAB_RISK && (
              <section aria-label="Riesgo">
                {riskSubTab === 'riesgo_driver_behavior' && <DriverBehaviorView key={`driver-behavior-${refreshKey}`} />}
                {riskSubTab === 'riesgo_action_engine' && <BacklogPlaceholder />}
              </section>
            )}

            {activeTab === TAB_OPERACION && (
              <section aria-label="Operación">
                {operacionSubTab === 'operacion_lob_drill' && <RealLOBDrillView key={`real-lob-drill-${refreshKey}`} />}
                {operacionSubTab === 'operacion_business_slice' && <BusinessSliceView key={`business-slice-${refreshKey}`} />}
                {operacionSubTab === 'operacion_omniview' && <BusinessSliceOmniview key={`business-slice-omniview-${refreshKey}`} />}
                {operacionSubTab === 'operacion_omniview_matrix' && <OmniviewErrorBoundary key={`bs-omniview-matrix-${refreshKey}`}><BusinessSliceOmniviewMatrix /></OmniviewErrorBoundary>}
                {operacionSubTab === 'operacion_control_loop_pvr' && <ControlLoopPlanVsRealView key={`control-loop-pvr-${refreshKey}`} />}
                {operacionSubTab === 'operacion_reportes' && <BusinessSliceOmniviewReports key={`bs-omniview-reports-${refreshKey}`} />}
                {operacionSubTab === 'operacion_oportunidades' && <OperationalOpportunitiesView key={`oportunidades-${refreshKey}`} />}
              </section>
            )}

            {activeTab === TAB_PLAN && (
              <section aria-label="Plan">
                {planSubTab === 'plan_acciones' && <><Phase2BActionsTrackingView key={`actions-2b-${refreshKey}`} /><Phase2CAccountabilityView key={`accountability-2c-${refreshKey}`} /></>}
                {planSubTab === 'plan_universo' && <LobUniverseView key={`lob-universe-${refreshKey}`} filters={filters} />}
                {planSubTab === 'plan_validacion' && (
                  <>
                    <div className="flex flex-wrap gap-1.5 mb-2">
                      <button type="button" onClick={() => setPlanValidacionInner('out_of_universe')}
                        className={`px-2.5 py-1 rounded text-xs font-medium transition-all ${planValidacionInner === 'out_of_universe' ? 'bg-ct-accent text-white shadow-sm' : 'text-ct-text2 hover:text-ct-text hover:bg-ct-border'}`}>Expansión</button>
                      <button type="button" onClick={() => setPlanValidacionInner('missing')}
                        className={`px-2.5 py-1 rounded text-xs font-medium transition-all ${planValidacionInner === 'missing' ? 'bg-ct-accent text-white shadow-sm' : 'text-ct-text2 hover:text-ct-text hover:bg-ct-border'}`}>Huecos</button>
                    </div>
                    <PlanTabs key={`plan-tabs-${refreshKey}-${planValidacionInner}`} filters={filters} activeTab={planValidacionInner} onTabChange={setPlanValidacionInner} />
                  </>
                )}
              </section>
            )}

            {activeTab === TAB_SYSTEM_HEALTH && (
              <section aria-label="Diagnósticos">
                <SystemHealthView key={`system-health-${refreshKey}`} />
              </section>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function App () {
  const location = useLocation()
  const { authRequired, isAuthenticated } = useAuth()
  if (!authRequired && location.pathname === '/login') return <Navigate to="/" replace />
  if (authRequired && !isAuthenticated && location.pathname !== '/login') return <Navigate to="/login" replace state={{ from: location }} />
  if (location.pathname === '/login') {
    if (authRequired && isAuthenticated) return <Navigate to="/" replace />
    return <LoginView />
  }
  return <ControlTowerApp />
}

export default App
