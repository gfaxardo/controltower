/**
 * YEGO Control Tower — App principal.
 * Fase 1: Navegación simplificada (Resumen, Real, Supply, Conductores en riesgo, Ciclo de vida, Plan y validación + Diagnósticos).
 * Identificadores internos de tab se mantienen para no romper lógica; solo cambian labels y jerarquía.
 */
import { useState, useRef, useEffect } from 'react'
import CollapsibleFilters from './components/CollapsibleFilters'
import ExecutiveSnapshotView from './components/ExecutiveSnapshotView'
import MonthlySplitView from './components/MonthlySplitView'
import WeeklyPlanVsRealView from './components/WeeklyPlanVsRealView'
import Phase2BActionsTrackingView from './components/Phase2BActionsTrackingView'
import Phase2CAccountabilityView from './components/Phase2CAccountabilityView'
import LobUniverseView from './components/LobUniverseView'
import RealLOBDrillView from './components/RealLOBDrillView'
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

// Navegación principal (primer nivel) — valores internos estables para no romper
const TAB_RESUMEN = 'resumen'
const TAB_REAL = 'real'
const TAB_SUPPLY = 'supply'
const TAB_DRIVER_RISK = 'driver_risk'
const TAB_LIFECYCLE = 'driver_lifecycle'
const TAB_PLAN_VALIDATION = 'plan_validation'
const TAB_SYSTEM_HEALTH = 'system_health'

// Sub-tabs de Conductores en riesgo (valores = mismos que antes para contenido)
const DRIVER_RISK_SUBTABS = [
  { id: 'behavioral_alerts', label: 'Alertas de conducta' },
  { id: 'driver_behavior', label: 'Desviación por ventanas' },
  { id: 'fleet_leakage', label: 'Fuga de flota' },
  { id: 'action_engine', label: 'Acciones recomendadas' }
]

// Sub-tabs de Plan y validación (Legacy)
const PLAN_VALIDATION_SUBTABS = [
  { id: 'valid', label: 'Plan Válido' },
  { id: 'out_of_universe', label: 'Expansión' },
  { id: 'missing', label: 'Huecos' },
  { id: 'actions', label: 'Fase 2B' },
  { id: 'accountability', label: 'Fase 2C' },
  { id: 'lob_universe', label: 'Universo & LOB' },
  { id: 'real_vs_projection', label: 'Real vs Proyección' }
]

function App () {
  const [filters, setFilters] = useState({
    country: '',
    city: '',
    line_of_business: '',
    year_real: 2025,
    year_plan: 2026
  })
  const [refreshKey, setRefreshKey] = useState(0)
  const [activeTab, setActiveTab] = useState(TAB_RESUMEN)
  const [driverRiskSubTab, setDriverRiskSubTab] = useState('behavioral_alerts')
  const [planValidationSubTab, setPlanValidationSubTab] = useState('valid')
  const [realSubTab, setRealSubTab] = useState('operational')
  const [showAdminModal, setShowAdminModal] = useState(false)
  const [showDiagnosticsMenu, setShowDiagnosticsMenu] = useState(false)
  const diagnosticsRef = useRef(null)

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters)
  }

  const handleUploadSuccess = () => {
    setRefreshKey(prev => prev + 1)
    setShowAdminModal(false)
  }

  // Cerrar dropdown Diagnósticos al hacer click fuera
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

  const mainNavTabs = [
    { id: TAB_RESUMEN, label: 'Resumen' },
    { id: TAB_REAL, label: 'Real' },
    { id: TAB_SUPPLY, label: 'Supply' },
    { id: TAB_DRIVER_RISK, label: 'Conductores en riesgo' },
    { id: TAB_LIFECYCLE, label: 'Ciclo de vida' },
    { id: TAB_PLAN_VALIDATION, label: 'Plan y validación' }
  ]

  const navButtonClass = (isActive) =>
    `py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap ${
      isActive
        ? 'border-blue-500 text-blue-600'
        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
    }`

  const subNavButtonClass = (isActive) =>
    `px-3 py-1.5 rounded text-sm ${isActive ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-2xl font-bold text-gray-800">
            YEGO Control Tower
          </h1>
          <button
            type="button"
            onClick={() => setShowAdminModal(true)}
            className="px-4 py-2 rounded-md border border-gray-400 bg-gray-100 text-gray-700 hover:bg-gray-200 font-medium text-sm"
          >
            ADMIN
          </button>
        </header>

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

        <GlobalFreshnessBanner activeTab={activeTab} />

        {activeTab === 'real' && <RealMarginQualityCard />}

        <CollapsibleFilters onFilterChange={handleFilterChange} />

        {/* ========== NAVEGACIÓN PRINCIPAL (primer nivel) ========== */}
        <div className="mb-4 border-b border-gray-200">
          <nav className="-mb-px flex flex-wrap items-center gap-1 sm:gap-2">
            {mainNavTabs.map(({ id, label }) => (
              <button
                key={id}
                type="button"
                onClick={() => setActiveTab(id)}
                className={navButtonClass(activeTab === id)}
              >
                {label}
              </button>
            ))}
            {/* Diagnósticos (segundo nivel): dropdown */}
            <div className="relative ml-2 sm:ml-4" ref={diagnosticsRef}>
              <button
                type="button"
                onClick={() => setShowDiagnosticsMenu((v) => !v)}
                className={`py-4 px-1 border-b-2 font-medium text-sm whitespace-nowrap border-transparent text-gray-500 hover:text-gray-700 ${
                  activeTab === TAB_SYSTEM_HEALTH ? 'border-blue-500 text-blue-600' : ''
                }`}
                aria-expanded={showDiagnosticsMenu}
                aria-haspopup="true"
              >
                Diagnósticos ▾
              </button>
              {showDiagnosticsMenu && (
                <div className="absolute right-0 top-full mt-1 py-1 bg-white border border-gray-200 rounded-md shadow-lg z-50 min-w-[10rem]">
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

        {/* ========== SUB-NAV: Conductores en riesgo ========== */}
        {activeTab === TAB_DRIVER_RISK && (
          <div className="mb-4 pb-2 border-b border-gray-200">
            <p className="text-xs text-gray-500 mb-2">Quiénes requieren atención</p>
            <div className="flex flex-wrap gap-2">
              {DRIVER_RISK_SUBTABS.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setDriverRiskSubTab(id)}
                  className={subNavButtonClass(driverRiskSubTab === id)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ========== SUB-NAV: Plan y validación ========== */}
        {activeTab === TAB_PLAN_VALIDATION && (
          <div className="mb-4 pb-2 border-b border-gray-200">
            <p className="text-xs text-gray-500 mb-2">Plan, validación y accountability</p>
            <div className="flex flex-wrap gap-2">
              {PLAN_VALIDATION_SUBTABS.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setPlanValidationSubTab(id)}
                  className={subNavButtonClass(planValidationSubTab === id)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ========== CONTENIDO POR TAB PRINCIPAL ========== */}
        {activeTab === TAB_RESUMEN && (
          <section className="space-y-4" aria-label="Resumen">
            <h2 className="text-xl font-semibold text-gray-800">Resumen</h2>
            <p className="text-sm text-gray-600">Plan vs Real en KPIs (viajes, conductores, revenue).</p>
            <ExecutiveSnapshotView key={`snapshot-${refreshKey}`} filters={filters} refreshKey={refreshKey} />
          </section>
        )}

        {/* SUB-NAV Real: Operativo (principal) vs Drill y diario (avanzado/legacy) */}
        {activeTab === TAB_REAL && (
          <div className="mb-4 pb-2 border-b border-gray-200">
            <p className="text-xs text-gray-500 mb-2">Vista operativa (hourly-first) y drill avanzado</p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => setRealSubTab('operational')}
                className={`px-3 py-1.5 rounded text-sm font-medium ${realSubTab === 'operational' ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
              >
                Operativo
              </button>
              <button
                type="button"
                onClick={() => setRealSubTab('drill')}
                className={`px-3 py-1.5 rounded text-sm ${realSubTab === 'drill' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-600 hover:bg-gray-300'}`}
                title="Drill mensual/semanal y vista diaria (legacy)"
              >
                Drill y diario (avanzado)
              </button>
            </div>
          </div>
        )}

        {activeTab === TAB_REAL && (
          <section className="space-y-4" aria-label="Real">
            <h2 className="text-xl font-semibold text-gray-800">Real</h2>
            {realSubTab === 'operational' ? (
              <>
                <p className="text-sm text-gray-600">Hoy, ayer, esta semana; por día; por hora; cancelaciones y comparativos operativos.</p>
                <RealOperationalView key={`real-operational-${refreshKey}`} country={filters.country} city={filters.city} />
              </>
            ) : (
              <>
                <p className="text-sm text-gray-600">Drill-down por país, periodo, LOB y park (vista avanzada).</p>
                <RealLOBDrillView key={`real-lob-drill-${refreshKey}`} />
              </>
            )}
          </section>
        )}

        {activeTab === TAB_SUPPLY && (
          <section className="space-y-4" aria-label="Supply">
            <h2 className="text-xl font-semibold text-gray-800">Supply</h2>
            <p className="text-sm text-gray-600">Dinámica de supply por park: overview, composición, migración y alertas.</p>
            <SupplyView key={`supply-${refreshKey}`} />
          </section>
        )}

        {activeTab === TAB_DRIVER_RISK && (
          <section className="space-y-4" aria-label="Conductores en riesgo">
            {driverRiskSubTab === 'behavioral_alerts' && (
              <BehavioralAlertsView key={`behavioral-alerts-${refreshKey}`} />
            )}
            {driverRiskSubTab === 'driver_behavior' && (
              <DriverBehaviorView key={`driver-behavior-${refreshKey}`} />
            )}
            {driverRiskSubTab === 'fleet_leakage' && (
              <FleetLeakageView key={`fleet-leakage-${refreshKey}`} />
            )}
            {driverRiskSubTab === 'action_engine' && (
              <ActionEngineView key={`action-engine-${refreshKey}`} />
            )}
          </section>
        )}

        {activeTab === TAB_LIFECYCLE && (
          <section className="space-y-4" aria-label="Ciclo de vida">
            <h2 className="text-xl font-semibold text-gray-800">Ciclo de vida</h2>
            <p className="text-sm text-gray-600">Evolución del parque y cohortes por park.</p>
            <DriverLifecycleView key={`driver-lifecycle-${refreshKey}`} />
          </section>
        )}

        {activeTab === TAB_PLAN_VALIDATION && (
          <section className="space-y-4" aria-label="Plan y validación">
            {planValidationSubTab === 'valid' && (
              <>
                <MonthlySplitView key={`monthly-${refreshKey}`} filters={filters} />
                <WeeklyPlanVsRealView key={`weekly-${refreshKey}`} filters={filters} />
              </>
            )}
            {planValidationSubTab === 'actions' && <Phase2BActionsTrackingView />}
            {planValidationSubTab === 'accountability' && <Phase2CAccountabilityView />}
            {planValidationSubTab === 'lob_universe' && (
              <LobUniverseView key={`lob-universe-${refreshKey}`} filters={filters} />
            )}
            {planValidationSubTab === 'real_vs_projection' && (
              <RealVsProjectionView key={`real-vs-projection-${refreshKey}`} />
            )}
            {['out_of_universe', 'missing'].includes(planValidationSubTab) && (
              <PlanTabs
                key={`tabs-${refreshKey}`}
                filters={filters}
                activeTab={planValidationSubTab}
                onTabChange={setPlanValidationSubTab}
              />
            )}
          </section>
        )}

        {activeTab === TAB_SYSTEM_HEALTH && (
          <section className="space-y-4" aria-label="Diagnósticos">
            <h2 className="text-xl font-semibold text-gray-800">System Health</h2>
            <p className="text-sm text-gray-600">Integridad de datos, freshness de MVs e ingestión. Uso técnico o de diagnóstico.</p>
            <SystemHealthView key={`system-health-${refreshKey}`} />
          </section>
        )}
      </div>
    </div>
  )
}

export default App
