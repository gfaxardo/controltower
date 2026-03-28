/**
 * YEGO Control Tower — App principal.
 * Rediseño: navegación por bloques de decisión (Performance, Proyección, Drivers, Riesgo, Operación, Plan).
 * Real vs Proyección es tab principal. Diaria = Performance > Real; Semanal/Mensual = Operación > Drill.
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
import BusinessSliceView from './components/BusinessSliceView'
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
  { id: 'lob_drill', label: 'Real LOB / Drill' },
  { id: 'business_slice', label: 'Business Slice' }
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
  const [activeTab, setActiveTab] = useState(TAB_PERFORMANCE)
  const [performanceSubTab, setPerformanceSubTab] = useState('resumen')
  const [driversSubTab, setDriversSubTab] = useState('supply')
  const [riskSubTab, setRiskSubTab] = useState('driver_behavior')
  const [enRevisionSubTab, setEnRevisionSubTab] = useState('real_vs_projection')
  const [planSubTab, setPlanSubTab] = useState('acciones')
  const [operacionSubTab, setOperacionSubTab] = useState('lob_drill')
  const [planValidacionInner, setPlanValidacionInner] = useState('out_of_universe')
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

        <GlobalFreshnessBanner
          activeTab={
            activeTab === TAB_OPERACION || (activeTab === TAB_PERFORMANCE && performanceSubTab === 'real')
              ? 'real'
              : activeTab
          }
        />

        {(activeTab === TAB_PERFORMANCE && performanceSubTab === 'real') && <RealMarginQualityCard />}
        {(activeTab === TAB_OPERACION) && <RealMarginQualityCard />}

        <CollapsibleFilters onFilterChange={handleFilterChange} />

        {/* ========== NAVEGACIÓN PRINCIPAL ========== */}
        <div className="mb-4 border-b border-gray-200">
          <nav className="-mb-px flex flex-wrap items-center gap-1 sm:gap-2">
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

        {/* ========== SUB-NAV: Performance ========== */}
        {activeTab === TAB_PERFORMANCE && (
          <div className="mb-4 pb-2 border-b border-gray-200">
            <p className="text-xs text-gray-500 mb-2">Qué está pasando: viajes, revenue, Plan vs Real</p>
            <div className="flex flex-wrap gap-2">
              {PERFORMANCE_SUBTABS.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setPerformanceSubTab(id)}
                  className={subNavButtonClass(performanceSubTab === id)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ========== SUB-NAV: Drivers ========== */}
        {activeTab === TAB_DRIVERS && (
          <div className="mb-4 pb-2 border-b border-gray-200">
            <p className="text-xs text-gray-500 mb-2">Quién lo hace: supply y ciclo de vida</p>
            <div className="flex flex-wrap gap-2">
              {DRIVERS_SUBTABS.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setDriversSubTab(id)}
                  className={subNavButtonClass(driversSubTab === id)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ========== SUB-NAV: Riesgo ========== */}
        {activeTab === TAB_RISK && (
          <div className="mb-4 pb-2 border-b border-gray-200">
            <p className="text-xs text-gray-500 mb-2">Qué se rompe: alertas, fuga, acciones</p>
            <div className="flex flex-wrap gap-2">
              {RISK_SUBTABS.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setRiskSubTab(id)}
                  className={subNavButtonClass(riskSubTab === id)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ========== SUB-NAV: Plan ========== */}
        {activeTab === TAB_PLAN && (
          <div className="mb-4 pb-2 border-b border-gray-200">
            <p className="text-xs text-gray-500 mb-2">Validación del plan: acciones, universo, expansión y huecos</p>
            <div className="flex flex-wrap gap-2">
              {PLAN_SUBTABS.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setPlanSubTab(id)}
                  className={subNavButtonClass(planSubTab === id)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ========== CONTENIDO: Performance ========== */}
        {activeTab === TAB_PERFORMANCE && (
          <section className="space-y-4" aria-label="Performance">
            <h2 className="text-xl font-semibold text-gray-800">Performance</h2>
            {performanceSubTab === 'resumen' && (
              <>
                <p className="text-sm text-gray-600">Plan vs Real en KPIs (viajes, conductores, revenue).</p>
                <ExecutiveSnapshotView key={`snapshot-${refreshKey}`} filters={filters} refreshKey={refreshKey} />
              </>
            )}
            {performanceSubTab === 'plan_vs_real' && (
              <>
                <p className="text-sm text-gray-600">Detalle mensual y semanal Plan vs Real.</p>
                <MonthlySplitView key={`monthly-${refreshKey}`} filters={filters} />
                <WeeklyPlanVsRealView key={`weekly-${refreshKey}`} filters={filters} />
              </>
            )}
            {performanceSubTab === 'real' && (
              <>
                <p className="text-sm text-gray-600">Vista diaria: hoy, ayer, por día y por hora. Para desglose semanal o mensual por LOB y parque → pestaña Operación.</p>
                <RealOperationalView key={`real-operational-${refreshKey}`} country={filters.country} city={filters.city} />
              </>
            )}
          </section>
        )}

        {/* ========== CONTENIDO: En revisión (fuera de flujo principal) ========== */}
        {activeTab === TAB_EN_REVISION && (
          <>
            <div className="mb-4 pb-2 border-b border-amber-200 bg-amber-50/50 rounded px-3 py-2">
              <p className="text-xs text-amber-800 font-medium mb-2">Pantallas en revisión: no considerar datos como definitivos.</p>
              <div className="flex flex-wrap gap-2">
                {EN_REVISION_SUBTABS.map(({ id, label }) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setEnRevisionSubTab(id)}
                    className={subNavButtonClass(enRevisionSubTab === id)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>
            <section className="space-y-4" aria-label="En revisión">
              <h2 className="text-xl font-semibold text-gray-800">En revisión</h2>
              {enRevisionSubTab === 'real_vs_projection' && <RealVsProjectionView key={`real-vs-projection-${refreshKey}`} />}
              {enRevisionSubTab === 'behavioral_alerts' && <BehavioralAlertsView key={`behavioral-alerts-${refreshKey}`} />}
              {enRevisionSubTab === 'fleet_leakage' && <FleetLeakageView key={`fleet-leakage-${refreshKey}`} />}
            </section>
          </>
        )}

        {/* ========== CONTENIDO: Drivers ========== */}
        {activeTab === TAB_DRIVERS && (
          <section className="space-y-4" aria-label="Drivers">
            <h2 className="text-xl font-semibold text-gray-800">Drivers</h2>
            {driversSubTab === 'supply' && (
              <>
                <p className="text-sm text-gray-600">Dinámica de supply por park: overview, composición, migración y alertas.</p>
                <SupplyView key={`supply-${refreshKey}`} />
              </>
            )}
            {driversSubTab === 'lifecycle' && (
              <>
                <p className="text-sm text-gray-600">Evolución del parque y cohortes por park.</p>
                <DriverLifecycleView key={`driver-lifecycle-${refreshKey}`} />
              </>
            )}
          </section>
        )}

        {/* ========== CONTENIDO: Riesgo ========== */}
        {activeTab === TAB_RISK && (
          <section className="space-y-4" aria-label="Riesgo">
            <h2 className="text-xl font-semibold text-gray-800">Riesgo</h2>
            {riskSubTab === 'driver_behavior' && <DriverBehaviorView key={`driver-behavior-${refreshKey}`} />}
            {riskSubTab === 'action_engine' && <ActionEngineView key={`action-engine-${refreshKey}`} />}
          </section>
        )}

        {/* ========== SUB-NAV: Operación ========== */}
        {activeTab === TAB_OPERACION && (
          <div className="mb-4 pb-2 border-b border-gray-200">
            <p className="text-xs text-gray-500 mb-2">Desglose operativo y tajadas ejecutivas (Business Slice)</p>
            <div className="flex flex-wrap gap-2">
              {OPERACION_SUBTABS.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setOperacionSubTab(id)}
                  className={subNavButtonClass(operacionSubTab === id)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ========== CONTENIDO: Operación (desglose por LOB, park, tipo de servicio) ========== */}
        {activeTab === TAB_OPERACION && (
          <section className="space-y-4" aria-label="Operación">
            <h2 className="text-xl font-semibold text-gray-800">Operación</h2>
            {operacionSubTab === 'lob_drill' && (
              <>
                <p className="text-sm text-gray-600">Desglose semanal y mensual por país, LOB, parque y tipo de servicio.</p>
                <RealLOBDrillView key={`real-lob-drill-${refreshKey}`} />
              </>
            )}
            {operacionSubTab === 'business_slice' && (
              <>
                <p className="text-sm text-gray-600">Tajadas de negocio (Business Slice): matriz mensual REAL y auditoría de cobertura.</p>
                <BusinessSliceView key={`business-slice-${refreshKey}`} />
              </>
            )}
          </section>
        )}

        {/* ========== CONTENIDO: Plan ========== */}
        {activeTab === TAB_PLAN && (
          <section className="space-y-4" aria-label="Plan">
            <h2 className="text-xl font-semibold text-gray-800">Plan</h2>
            {planSubTab === 'acciones' && (
              <>
                <p className="text-sm text-gray-600">Fase 2B (acciones) y Fase 2C (accountability).</p>
                <Phase2BActionsTrackingView key={`actions-2b-${refreshKey}`} />
                <Phase2CAccountabilityView key={`accountability-2c-${refreshKey}`} />
              </>
            )}
            {planSubTab === 'universo' && (
              <>
                <p className="text-sm text-gray-600">Universo y LOB.</p>
                <LobUniverseView key={`lob-universe-${refreshKey}`} filters={filters} />
              </>
            )}
            {planSubTab === 'validacion' && (
              <>
                <p className="text-sm text-gray-600">Expansión y huecos del plan.</p>
                <div className="flex flex-wrap gap-2 mb-3">
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
            <h2 className="text-xl font-semibold text-gray-800">System Health</h2>
            <p className="text-sm text-gray-600">Integridad de datos, freshness de MVs e ingestión.</p>
            <SystemHealthView key={`system-health-${refreshKey}`} />
          </section>
        )}
      </div>
    </div>
  )
}

export default App
