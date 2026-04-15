/**
 * YEGO Control Tower — App principal.
 * Rediseño: navegación por bloques de decisión (Performance, Proyección, Drivers, Riesgo, Operación, Plan).
 * Real vs Proyección es tab principal. Diaria = Performance > Real; Semanal/Mensual = Operación > Drill.
 */
import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate, useLocation, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext.jsx'
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
import BusinessSliceOmniviewReports from './components/BusinessSliceOmniviewReports'
import ControlLoopPlanVsRealView from './components/ControlLoopPlanVsRealView'
import RealOperationalView from './components/RealOperationalView'
import DriverLifecycleView from './components/DriverLifecycleView'
import SupplyView from './components/SupplyView'
import BehavioralAlertsView from './components/BehavioralAlertsView'
import FleetLeakageView from './components/FleetLeakageView'
import DriverBehaviorView from './components/DriverBehaviorView'
import ActionEngineView from './components/ActionEngineView'
import SystemHealthView from './components/SystemHealthView'
import GlobalFreshnessBanner from './components/GlobalFreshnessBanner'
import RealMarginQualityCard from './components/RealMarginQualityCard'
import UploadPlan from './components/UploadPlan'
import PlanTabs from './components/PlanTabs'
import RealVsProjectionView from './components/RealVsProjectionView'

// ─── Navegación principal (bloques de decisión) ─────────────────────────────
const TAB_PERFORMANCE = 'performance'
const TAB_DRIVERS = 'drivers'
const TAB_RISK = 'risk'
const TAB_OPERACION = 'operacion'
const TAB_PLAN = 'plan'
const TAB_EN_REVISION = 'en_revision'
const TAB_SYSTEM_HEALTH = 'system_health'

const MAIN_NAV_TABS = [
  { id: TAB_PERFORMANCE, label: 'Performance' },
  { id: TAB_DRIVERS, label: 'Drivers' },
  { id: TAB_RISK, label: 'Riesgo' },
  { id: TAB_OPERACION, label: 'Operación' },
  { id: TAB_PLAN, label: 'Plan' },
  { id: TAB_EN_REVISION, label: 'En revisión' }
]

const PERFORMANCE_SUBTABS = [
  { id: 'resumen', label: 'Resumen' },
  { id: 'plan_vs_real', label: 'Plan vs Real' },
  { id: 'real', label: 'Real (diario)' }
]

const DRIVERS_SUBTABS = [
  { id: 'supply', label: 'Supply' },
  { id: 'lifecycle', label: 'Ciclo de vida' }
]

const RISK_SUBTABS = [
  { id: 'driver_behavior', label: 'Desviación por ventanas' },
  { id: 'action_engine', label: 'Acciones recomendadas' }
]

const EN_REVISION_SUBTABS = [
  { id: 'real_vs_projection', label: 'Real vs Proyección' },
  { id: 'behavioral_alerts', label: 'Alertas de conducta' },
  { id: 'fleet_leakage', label: 'Fuga de flota' }
]

const PLAN_SUBTABS = [
  { id: 'acciones', label: 'Acciones' },
  { id: 'universo', label: 'Universo' },
  { id: 'validacion', label: 'Validación' }
]

const OPERACION_SUBTABS = [
  { id: 'omniview_matrix', label: 'Omniview Matrix' },
  { id: 'control_loop_pvr', label: 'Control Loop Plan vs Real' },
  { id: 'reportes', label: 'Reportes' },
  { id: 'lob_drill', label: 'Real LOB / Drill' },
  { id: 'business_slice', label: 'Business Slice' },
  { id: 'business_slice_omniview', label: 'Omniview' },
]

// ─── Mapa URL <-> (tab, subtab) ─────────────────────────────────────────────
const ROUTE_MAP = [
  { path: '/', tab: TAB_OPERACION, sub: 'omniview_matrix' },
  { path: '/performance', tab: TAB_PERFORMANCE, sub: 'resumen' },
  { path: '/performance/resumen', tab: TAB_PERFORMANCE, sub: 'resumen' },
  { path: '/performance/plan-vs-real', tab: TAB_PERFORMANCE, sub: 'plan_vs_real' },
  { path: '/performance/real', tab: TAB_PERFORMANCE, sub: 'real' },
  { path: '/drivers', tab: TAB_DRIVERS, sub: 'supply' },
  { path: '/drivers/supply', tab: TAB_DRIVERS, sub: 'supply' },
  { path: '/drivers/lifecycle', tab: TAB_DRIVERS, sub: 'lifecycle' },
  { path: '/riesgo', tab: TAB_RISK, sub: 'driver_behavior' },
  { path: '/riesgo/driver-behavior', tab: TAB_RISK, sub: 'driver_behavior' },
  { path: '/riesgo/action-engine', tab: TAB_RISK, sub: 'action_engine' },
  { path: '/operacion', tab: TAB_OPERACION, sub: 'omniview_matrix' },
  { path: '/operacion/lob-drill', tab: TAB_OPERACION, sub: 'lob_drill' },
  { path: '/operacion/business-slice', tab: TAB_OPERACION, sub: 'business_slice' },
  { path: '/operacion/omniview', tab: TAB_OPERACION, sub: 'business_slice_omniview' },
  { path: '/operacion/omniview-matrix', tab: TAB_OPERACION, sub: 'omniview_matrix' },
  { path: '/operacion/control-loop-plan-vs-real', tab: TAB_OPERACION, sub: 'control_loop_pvr' },
  { path: '/operacion/reportes', tab: TAB_OPERACION, sub: 'reportes' },
  { path: '/plan', tab: TAB_PLAN, sub: 'acciones' },
  { path: '/plan/acciones', tab: TAB_PLAN, sub: 'acciones' },
  { path: '/plan/universo', tab: TAB_PLAN, sub: 'universo' },
  { path: '/plan/validacion', tab: TAB_PLAN, sub: 'validacion' },
  { path: '/en-revision', tab: TAB_EN_REVISION, sub: 'real_vs_projection' },
  { path: '/en-revision/real-vs-proyeccion', tab: TAB_EN_REVISION, sub: 'real_vs_projection' },
  { path: '/en-revision/alertas', tab: TAB_EN_REVISION, sub: 'behavioral_alerts' },
  { path: '/en-revision/flota', tab: TAB_EN_REVISION, sub: 'fleet_leakage' },
  { path: '/diagnosticos', tab: TAB_SYSTEM_HEALTH, sub: null },
]

const SUB_URL = {
  // Performance
  resumen: '/performance/resumen',
  plan_vs_real: '/performance/plan-vs-real',
  // Drivers
  supply: '/drivers/supply',
  lifecycle: '/drivers/lifecycle',
  // Riesgo
  driver_behavior: '/riesgo/driver-behavior',
  action_engine: '/riesgo/action-engine',
  // Operacion
  lob_drill: '/operacion/lob-drill',
  business_slice: '/operacion/business-slice',
  business_slice_omniview: '/operacion/omniview',
  omniview_matrix: '/operacion/omniview-matrix',
  control_loop_pvr: '/operacion/control-loop-plan-vs-real',
  reportes: '/operacion/reportes',
  // Plan
  acciones: '/plan/acciones',
  universo: '/plan/universo',
  validacion: '/plan/validacion',
  // En revisión
  real_vs_projection: '/en-revision/real-vs-proyeccion',
  behavioral_alerts: '/en-revision/alertas',
  fleet_leakage: '/en-revision/flota',
}

const TAB_DEFAULT_PATH = {
  [TAB_PERFORMANCE]: '/performance/resumen',
  [TAB_DRIVERS]: '/drivers/supply',
  [TAB_RISK]: '/riesgo/driver-behavior',
  [TAB_OPERACION]: '/operacion/omniview-matrix',
  [TAB_PLAN]: '/plan/acciones',
  [TAB_EN_REVISION]: '/en-revision/real-vs-proyeccion',
  [TAB_SYSTEM_HEALTH]: '/diagnosticos',
}

function parseRoute (pathname) {
  const match = ROUTE_MAP.find((r) => r.path === pathname)
  if (match) return match
  // fallback: prefix match
  const prefix = ROUTE_MAP.find((r) => r.path !== '/' && pathname.startsWith(r.path))
  return prefix || ROUTE_MAP[0]
}

/** Shell con toda la UI de Control Tower (hooks siempre en el mismo orden). */
function ControlTowerApp () {
  const navigate = useNavigate()
  const location = useLocation()
  const { authRequired, logout, username, role } = useAuth()

  const parsed = parseRoute(location.pathname)
  const activeTab = parsed.tab
  const routeSub = parsed.sub

  const [filters, setFilters] = useState({
    country: '',
    city: '',
    line_of_business: '',
    year_real: 2025,
    year_plan: 2026
  })
  const [refreshKey, setRefreshKey] = useState(0)

  // Subtabs derivados de la ruta; el estado local solo se usa para inner (plan validacion)
  const performanceSubTab = activeTab === TAB_PERFORMANCE ? (routeSub || 'resumen') : 'resumen'
  const driversSubTab = activeTab === TAB_DRIVERS ? (routeSub || 'supply') : 'supply'
  const riskSubTab = activeTab === TAB_RISK ? (routeSub || 'driver_behavior') : 'driver_behavior'
  const operacionSubTab = activeTab === TAB_OPERACION ? (routeSub || 'omniview_matrix') : 'omniview_matrix'
  const planSubTab = activeTab === TAB_PLAN ? (routeSub || 'acciones') : 'acciones'
  const enRevisionSubTab = activeTab === TAB_EN_REVISION ? (routeSub || 'real_vs_projection') : 'real_vs_projection'

  const [planValidacionInner, setPlanValidacionInner] = useState('out_of_universe')
  const [showAdminModal, setShowAdminModal] = useState(false)
  const [showDiagnosticsMenu, setShowDiagnosticsMenu] = useState(false)
  const diagnosticsRef = useRef(null)

  const setActiveTab = useCallback((tab) => {
    navigate(TAB_DEFAULT_PATH[tab] || '/')
  }, [navigate])

  const setPerformanceSubTab = useCallback((sub) => navigate(SUB_URL[sub] || '/performance/resumen'), [navigate])
  const setDriversSubTab = useCallback((sub) => navigate(SUB_URL[sub] || '/drivers/supply'), [navigate])
  const setRiskSubTab = useCallback((sub) => navigate(SUB_URL[sub] || '/riesgo/driver-behavior'), [navigate])
  const setOperacionSubTab = useCallback((sub) => navigate(SUB_URL[sub] || '/operacion/omniview-matrix'), [navigate])
  const setPlanSubTab = useCallback((sub) => navigate(SUB_URL[sub] || '/plan/acciones'), [navigate])
  const setEnRevisionSubTab = useCallback((sub) => navigate(SUB_URL[sub] || '/en-revision/real-vs-proyeccion'), [navigate])

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters)
  }

  const handleUploadSuccess = () => {
    setRefreshKey(prev => prev + 1)
    setShowAdminModal(false)
  }

  useEffect(() => {
    function handleClickOutside (e) {
      if (diagnosticsRef.current && !diagnosticsRef.current.contains(e.target)) {
        setShowDiagnosticsMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const openDiagnostics = (tab) => {
    setActiveTab(tab)
    setShowDiagnosticsMenu(false)
  }

  const navButtonClass = (isActive) =>
    `py-3 px-3 border-b-2 font-medium text-sm whitespace-nowrap transition-colors ${
      isActive
        ? 'border-blue-600 text-blue-600'
        : 'border-transparent text-gray-500 hover:text-gray-800 hover:border-gray-300'
    }`

  const subNavButtonClass = (isActive) =>
    `px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
      isActive
        ? 'bg-blue-600 text-white shadow-sm'
        : 'text-gray-500 hover:text-gray-800 hover:bg-gray-100'
    }`

  return (
    <div className="min-h-screen bg-gray-50">
      {/* ── Top bar ─────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 bg-white border-b border-gray-200 shadow-sm">
        <div className="w-full px-4 sm:px-6 h-14 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
              </svg>
            </div>
            <div>
              <span className="text-[15px] font-bold text-gray-900 tracking-tight">YEGO</span>
              <span className="text-[15px] font-normal text-gray-400 ml-1">Control Tower</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {authRequired && username && (
              <div className="flex flex-col items-end text-right min-w-0 max-w-[14rem] sm:max-w-[18rem]">
                <span className="text-xs text-gray-700 font-medium truncate w-full" title={username}>
                  {username}
                </span>
                {role && (
                  <span className="text-[11px] text-gray-500 truncate w-full mt-0.5" title={role}>
                    {role}
                  </span>
                )}
              </div>
            )}
            {authRequired && (
              <button
                type="button"
                onClick={() => {
                  logout()
                  navigate('/login', { replace: true })
                }}
                className="px-3 py-1.5 rounded-lg border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 text-xs font-medium"
              >
                Salir
              </button>
            )}
            <button
              type="button"
              onClick={() => setShowAdminModal(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 hover:border-gray-300 font-medium text-xs transition-all"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              Admin
            </button>
          </div>
        </div>
      </header>

      {/* ========== NAVEGACIÓN PRINCIPAL (full-width) ========== */}
      <div className="sticky top-14 z-30 bg-white border-b border-gray-200">
        <div className="w-full px-4 sm:px-6">
          <nav className="-mb-px flex flex-wrap items-center">
            {MAIN_NAV_TABS.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                onClick={() => setActiveTab(id)}
                className={navButtonClass(activeTab === id)}
              >
                {label}
              </button>
            ))}
            <div className="relative ml-auto" ref={diagnosticsRef}>
              <button
                type="button"
                onClick={() => setShowDiagnosticsMenu((v) => !v)}
                className={`py-3 px-3 border-b-2 font-medium text-sm whitespace-nowrap transition-colors ${
                  activeTab === TAB_SYSTEM_HEALTH
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-800 hover:border-gray-300'
                }`}
                aria-expanded={showDiagnosticsMenu}
                aria-haspopup="true"
              >
                Diagnósticos ▾
              </button>
              {showDiagnosticsMenu && (
                <div className="absolute right-0 top-full mt-1 py-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 min-w-[10rem]">
                  <button
                    type="button"
                    onClick={() => openDiagnostics(TAB_SYSTEM_HEALTH)}
                    className={`block w-full text-left px-4 py-2 text-sm ${activeTab === TAB_SYSTEM_HEALTH ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-700 hover:bg-gray-100'}`}
                  >
                    System Health
                  </button>
                </div>
              )}
            </div>
          </nav>
        </div>
      </div>

      {/* ========== SUB-NAV (full-width, condicional) ========== */}
      {activeTab === TAB_PERFORMANCE && (
        <div className="bg-white border-b border-gray-100 w-full px-4 sm:px-6 py-2 flex flex-wrap gap-1.5">
          {PERFORMANCE_SUBTABS.map(({ id, label }) => (
            <button key={id} type="button" onClick={() => setPerformanceSubTab(id)} className={subNavButtonClass(performanceSubTab === id)}>{label}</button>
          ))}
        </div>
      )}
      {activeTab === TAB_DRIVERS && (
        <div className="bg-white border-b border-gray-100 w-full px-4 sm:px-6 py-2 flex flex-wrap gap-1.5">
          {DRIVERS_SUBTABS.map(({ id, label }) => (
            <button key={id} type="button" onClick={() => setDriversSubTab(id)} className={subNavButtonClass(driversSubTab === id)}>{label}</button>
          ))}
        </div>
      )}
      {activeTab === TAB_RISK && (
        <div className="bg-white border-b border-gray-100 w-full px-4 sm:px-6 py-2 flex flex-wrap gap-1.5">
          {RISK_SUBTABS.map(({ id, label }) => (
            <button key={id} type="button" onClick={() => setRiskSubTab(id)} className={subNavButtonClass(riskSubTab === id)}>{label}</button>
          ))}
        </div>
      )}
      {activeTab === TAB_PLAN && (
        <div className="bg-white border-b border-gray-100 w-full px-4 sm:px-6 py-2 flex flex-wrap gap-1.5">
          {PLAN_SUBTABS.map(({ id, label }) => (
            <button key={id} type="button" onClick={() => setPlanSubTab(id)} className={subNavButtonClass(planSubTab === id)}>{label}</button>
          ))}
        </div>
      )}
      {activeTab === TAB_OPERACION && (
        <div className="bg-white border-b border-gray-100 w-full px-4 sm:px-6 py-2 flex flex-wrap gap-1.5">
          {OPERACION_SUBTABS.map(({ id, label }) => (
            <button key={id} type="button" onClick={() => setOperacionSubTab(id)} className={subNavButtonClass(operacionSubTab === id)}>{label}</button>
          ))}
        </div>
      )}
      {activeTab === TAB_EN_REVISION && (
        <div className="bg-amber-50 border-b border-amber-200 w-full px-4 sm:px-6 py-2 flex flex-wrap items-center gap-3">
          <span className="text-xs text-amber-700 font-medium">⚠ En revisión</span>
          <div className="flex flex-wrap gap-1.5">
            {EN_REVISION_SUBTABS.map(({ id, label }) => (
              <button key={id} type="button" onClick={() => setEnRevisionSubTab(id)} className={subNavButtonClass(enRevisionSubTab === id)}>{label}</button>
            ))}
          </div>
        </div>
      )}

      {/* ========== CONTENIDO ========== */}
      <div className="w-full px-4 sm:px-6 py-4">

        {showAdminModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true">
            <div className="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-semibold text-gray-800">Subir Plan</h2>
                <button
                  type="button"
                  onClick={() => setShowAdminModal(false)}
                  className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
                >
                  ×
                </button>
              </div>
              <UploadPlan onUploadSuccess={handleUploadSuccess} />
            </div>
          </div>
        )}

        {/* Omniview Matrix tiene su propia barra de contexto y controla su carga manualmente;
            se omiten los banners globales para no generar confusión ni queries adicionales. */}
        {operacionSubTab !== 'omniview_matrix' && operacionSubTab !== 'control_loop_pvr' && operacionSubTab !== 'reportes' && (
          <GlobalFreshnessBanner
            activeTab={
              activeTab === TAB_OPERACION || (activeTab === TAB_PERFORMANCE && performanceSubTab === 'real')
                ? 'real'
                : activeTab
            }
          />
        )}

        {(activeTab === TAB_PERFORMANCE && performanceSubTab === 'real') && <RealMarginQualityCard />}
        {(activeTab === TAB_OPERACION && operacionSubTab !== 'omniview_matrix' && operacionSubTab !== 'control_loop_pvr' && operacionSubTab !== 'reportes') && <RealMarginQualityCard />}

        <CollapsibleFilters onFilterChange={handleFilterChange} />

        {/* ========== CONTENIDO: Performance ========== */}
        {activeTab === TAB_PERFORMANCE && (
          <section className="space-y-4" aria-label="Performance">
            {performanceSubTab === 'resumen' && <ExecutiveSnapshotView key={`snapshot-${refreshKey}`} filters={filters} refreshKey={refreshKey} />}
            {performanceSubTab === 'plan_vs_real' && (
              <>
                <MonthlySplitView key={`monthly-${refreshKey}`} filters={filters} />
                <WeeklyPlanVsRealView key={`weekly-${refreshKey}`} filters={filters} />
              </>
            )}
            {performanceSubTab === 'real' && <RealOperationalView key={`real-operational-${refreshKey}`} country={filters.country} city={filters.city} />}
          </section>
        )}

        {/* ========== CONTENIDO: En revisión ========== */}
        {activeTab === TAB_EN_REVISION && (
          <section className="space-y-4" aria-label="En revisión">
            {enRevisionSubTab === 'real_vs_projection' && <RealVsProjectionView key={`real-vs-projection-${refreshKey}`} />}
            {enRevisionSubTab === 'behavioral_alerts' && <BehavioralAlertsView key={`behavioral-alerts-${refreshKey}`} />}
            {enRevisionSubTab === 'fleet_leakage' && <FleetLeakageView key={`fleet-leakage-${refreshKey}`} />}
          </section>
        )}

        {/* ========== CONTENIDO: Drivers ========== */}
        {activeTab === TAB_DRIVERS && (
          <section className="space-y-4" aria-label="Drivers">
            {driversSubTab === 'supply' && <SupplyView key={`supply-${refreshKey}`} />}
            {driversSubTab === 'lifecycle' && <DriverLifecycleView key={`driver-lifecycle-${refreshKey}`} />}
          </section>
        )}

        {/* ========== CONTENIDO: Riesgo ========== */}
        {activeTab === TAB_RISK && (
          <section className="space-y-4" aria-label="Riesgo">
            {riskSubTab === 'driver_behavior' && <DriverBehaviorView key={`driver-behavior-${refreshKey}`} />}
            {riskSubTab === 'action_engine' && <ActionEngineView key={`action-engine-${refreshKey}`} />}
          </section>
        )}

        {/* ========== CONTENIDO: Operación (desglose por LOB, park, tipo de servicio) ========== */}
        {activeTab === TAB_OPERACION && (
          <section className="space-y-4" aria-label="Operación">
            {operacionSubTab === 'lob_drill' && <RealLOBDrillView key={`real-lob-drill-${refreshKey}`} />}
            {operacionSubTab === 'business_slice' && <BusinessSliceView key={`business-slice-${refreshKey}`} />}
            {operacionSubTab === 'business_slice_omniview' && <BusinessSliceOmniview key={`business-slice-omniview-${refreshKey}`} />}
            {operacionSubTab === 'omniview_matrix' && <BusinessSliceOmniviewMatrix key={`bs-omniview-matrix-${refreshKey}`} />}
            {operacionSubTab === 'control_loop_pvr' && <ControlLoopPlanVsRealView key={`control-loop-pvr-${refreshKey}`} />}
            {operacionSubTab === 'reportes' && <BusinessSliceOmniviewReports key={`bs-omniview-reports-${refreshKey}`} />}
          </section>
        )}

        {/* ========== CONTENIDO: Plan ========== */}
        {activeTab === TAB_PLAN && (
          <section className="space-y-4" aria-label="Plan">
            {planSubTab === 'acciones' && (
              <>
                <Phase2BActionsTrackingView key={`actions-2b-${refreshKey}`} />
                <Phase2CAccountabilityView key={`accountability-2c-${refreshKey}`} />
              </>
            )}
            {planSubTab === 'universo' && <LobUniverseView key={`lob-universe-${refreshKey}`} filters={filters} />}
            {planSubTab === 'validacion' && (
              <>
                <div className="flex flex-wrap gap-1.5 mb-3">
                  <button
                    type="button"
                    onClick={() => setPlanValidacionInner('out_of_universe')}
                    className={subNavButtonClass(planValidacionInner === 'out_of_universe')}
                  >
                    Expansión
                  </button>
                  <button
                    type="button"
                    onClick={() => setPlanValidacionInner('missing')}
                    className={subNavButtonClass(planValidacionInner === 'missing')}
                  >
                    Huecos
                  </button>
                </div>
                <PlanTabs
                  key={`plan-tabs-${refreshKey}-${planValidacionInner}`}
                  filters={filters}
                  activeTab={planValidacionInner}
                  onTabChange={setPlanValidacionInner}
                />
              </>
            )}
          </section>
        )}

        {activeTab === TAB_SYSTEM_HEALTH && (
          <section className="space-y-4" aria-label="Diagnósticos">
            <SystemHealthView key={`system-health-${refreshKey}`} />
          </section>
        )}
      </div>
    </div>
  )
}

function App () {
  const location = useLocation()
  const { authRequired, isAuthenticated } = useAuth()

  if (!authRequired && location.pathname === '/login') {
    return <Navigate to="/" replace />
  }
  if (authRequired && !isAuthenticated && location.pathname !== '/login') {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  if (location.pathname === '/login') {
    if (authRequired && isAuthenticated) {
      return <Navigate to="/" replace />
    }
    return <LoginView />
  }

  return <ControlTowerApp />
}

export default App
