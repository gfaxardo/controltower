/**
 * YEGO Control Tower — Navigation Registry Canónico
 *
 * Define cada vista con su motor arquitectónico, estado de fase y visibilidad.
 * Rige qué aparece en producción vs desarrollo.
 *
 * Reglas:
 * - productionReady = true  → puede aparecer en build de producción
 * - visibility = KEEP_VISIBLE → se muestra en navegación
 * - visibility = HIDE_FROM_NAV → no aparece en menú, ruta muestra placeholder
 * - visibility = DEV_ONLY → solo en desarrollo (import.meta.env.DEV o VITE_SHOW_DEV_MODULES)
 * - visibility = BACKLOG_ONLY → bloqueado hasta que su motor esté ACTIVE
 * - visibility = NEEDS_VALIDATION → existe pero requiere verificación antes de mostrar
 */

export const ENGINE = {
  CONTROL_FOUNDATION: 'Control Foundation',
  DIAGNOSTIC: 'Diagnostic Engine',
  REACHABILITY: 'Reachability Engine',
  FORECAST: 'Forecast Engine',
  SUGGESTION: 'Suggestion Engine',
  DECISION: 'Decision Engine',
  ACTION: 'Action Engine',
  AI_COPILOT: 'AI Copilot',
  LEARNING: 'Learning Engine',
  LEGACY: 'Legacy / Unknown',
}

export const PHASE_STATUS = {
  ACTIVE: 'ACTIVE',
  READY_NEXT: 'READY NEXT',
  BACKLOG: 'BACKLOG',
}

export const VISIBILITY = {
  KEEP_VISIBLE: 'KEEP_VISIBLE',
  HIDE_FROM_NAV: 'HIDE_FROM_NAV',
  DEV_ONLY: 'DEV_ONLY',
  BACKLOG_ONLY: 'BACKLOG_ONLY',
  NEEDS_VALIDATION: 'NEEDS_VALIDATION',
}

export const CONTROL_TOWER_NAVIGATION_REGISTRY = [
  // ═══════════════════════════════════════════════════════════════════
  // PERFORMANCE — Control Foundation (ACTIVE)
  // ═══════════════════════════════════════════════════════════════════
  {
    key: 'performance_resumen',
    label: 'Resumen',
    tab: 'Performance',
    component: 'ExecutiveSnapshotView',
    route: '/performance/resumen',
    engine: ENGINE.CONTROL_FOUNDATION,
    phaseStatus: PHASE_STATUS.ACTIVE,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: true,
    requiresValidation: false,
    reason: 'Core Control Foundation: KPIs ejecutivos, snapshot de métricas principales.',
    endpoints: ['/core/summary/monthly', '/ops/plan/monthly', '/ops/real/monthly'],
  },
  {
    key: 'performance_plan_vs_real',
    label: 'Plan vs Real',
    tab: 'Performance',
    component: 'MonthlySplitView + WeeklyPlanVsRealView',
    route: '/performance/plan-vs-real',
    engine: ENGINE.CONTROL_FOUNDATION,
    phaseStatus: PHASE_STATUS.ACTIVE,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: true,
    requiresValidation: false,
    reason: 'Core Control Foundation: comparación Plan vs Real mensual y semanal.',
    endpoints: ['/ops/plan-vs-real/monthly', '/ops/plan/monthly', '/ops/real/monthly', '/phase2b/weekly/plan-vs-real'],
  },
  {
    key: 'performance_real',
    label: 'Real (diario)',
    tab: 'Performance',
    component: 'RealOperationalView',
    route: '/performance/real',
    engine: ENGINE.CONTROL_FOUNDATION,
    phaseStatus: PHASE_STATUS.ACTIVE,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: true,
    requiresValidation: false,
    reason: 'Core Control Foundation: vista operacional diaria (hourly-first).',
    endpoints: ['/ops/real-operational/snapshot', '/ops/real-operational/day-view', '/ops/real-operational/hourly-view'],
  },
  {
    key: 'performance_yango_loyalty',
    label: 'Yango Loyalty',
    tab: 'Performance',
    component: 'YangoLoyaltyView',
    route: '/performance/yango-loyalty',
    engine: ENGINE.CONTROL_FOUNDATION,
    phaseStatus: PHASE_STATUS.ACTIVE,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: true,
    requiresValidation: false,
    reason: 'Control Foundation: tracker de cumplimiento Yango Loyalty / Oro por ciudad con KPIs operativos.',
    endpoints: ['/yango-loyalty/summary', '/yango-loyalty/kpis'],
  },

  // ═══════════════════════════════════════════════════════════════════
  // DRIVERS — Diagnostic Engine (READY NEXT) + Control Foundation
  // ═══════════════════════════════════════════════════════════════════
  {
    key: 'drivers_supply',
    label: 'Supply',
    tab: 'Drivers',
    component: 'SupplyView',
    route: '/drivers/supply',
    engine: ENGINE.CONTROL_FOUNDATION,
    phaseStatus: PHASE_STATUS.ACTIVE,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: true,
    requiresValidation: false,
    reason: 'Control Foundation: dinámicas de supply, segmentación y migración de conductores.',
    endpoints: ['/ops/supply/geo', '/ops/supply/series', '/ops/supply/summary', '/ops/supply/composition', '/ops/supply/migration'],
  },
  {
    key: 'drivers_lifecycle',
    label: 'Ciclo de vida',
    tab: 'Drivers',
    component: 'DriverLifecycleView',
    route: '/drivers/lifecycle',
    engine: ENGINE.CONTROL_FOUNDATION,
    phaseStatus: PHASE_STATUS.ACTIVE,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: true,
    requiresValidation: false,
    reason: 'Control Foundation: ciclo de vida de conductores, cohorts, métricas base.',
    endpoints: ['/ops/driver-lifecycle/weekly', '/ops/driver-lifecycle/monthly', '/ops/driver-lifecycle/series'],
  },
  {
    key: 'drivers_action_queues',
    label: 'Action Queues',
    tab: 'Drivers',
    component: 'DriverActionableLists',
    route: '/drivers/action-queues',
    engine: ENGINE.CONTROL_FOUNDATION,
    phaseStatus: PHASE_STATUS.ACTIVE,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: true,
    requiresValidation: false,
    reason: 'Control Foundation (D4): colas operacionales accionables. Listas priorizadas para mejorar supply.',
    endpoints: ['/drivers/actionable-list', '/drivers/actionable-summary'],
  },
  {
    key: 'drivers_diagnostic',
    label: 'Diagnostico',
    tab: 'Drivers',
    component: 'DriverLifecycleDashboard',
    route: '/drivers/diagnostic',
    engine: ENGINE.DIAGNOSTIC,
    phaseStatus: PHASE_STATUS.READY_NEXT,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: false,
    requiresValidation: true,
    reason: 'Diagnostic Engine (Fase 2A.1): diagnostico determinista de ciclo de vida, riesgo y leakage. Motor Diagnostic READY NEXT — NO ACTIVO. Visible como roadmap preview.',
    endpoints: ['/driver-lifecycle/summary', '/driver-lifecycle/funnel', '/driver-lifecycle/risk-list', '/driver-lifecycle/cohorts-basic'],
  },
  {
    key: 'drivers_behavior_benchmarking',
    label: 'Behavior',
    tab: 'Drivers',
    component: 'DriverBehaviorBenchmarkingDashboard',
    route: '/drivers/behavior-benchmarking',
    engine: ENGINE.DIAGNOSTIC,
    phaseStatus: PHASE_STATUS.READY_NEXT,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: false,
    requiresValidation: true,
    reason: 'Diagnostic Engine (Fase 2A.2): benchmarking comparativo de patrones operativos entre grupos. Motor Diagnostic READY NEXT — NO ACTIVO.',
    endpoints: ['/driver-behavior/summary', '/driver-behavior/group-benchmarks', '/driver-behavior/top-vs-risk'],
  },
  {
    key: 'drivers_behavioral_alerts',
    label: 'Alertas de conducta',
    tab: 'Drivers',
    component: 'BehavioralAlertsView',
    route: '/drivers/behavioral-alerts',
    engine: ENGINE.DIAGNOSTIC,
    phaseStatus: PHASE_STATUS.READY_NEXT,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: false,
    requiresValidation: true,
    reason: 'Diagnostic Engine (READY NEXT): alertas de desviación conductual vs baseline. Motor Diagnostic READY NEXT — NO ACTIVO.',
    endpoints: ['/ops/behavior-alerts/summary', '/ops/behavior-alerts/drivers', '/ops/behavior-alerts/driver-detail'],
  },
  {
    key: 'drivers_fleet_leakage',
    label: 'Fuga de flota',
    tab: 'Drivers',
    component: 'FleetLeakageView',
    route: '/drivers/fleet-leakage',
    engine: ENGINE.DIAGNOSTIC,
    phaseStatus: PHASE_STATUS.READY_NEXT,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: false,
    requiresValidation: true,
    reason: 'Diagnostic Engine (READY NEXT): monitoreo de fuga de flota. Bajo revisión de estabilidad runtime.',
    endpoints: ['/ops/leakage/summary', '/ops/leakage/drivers'],
  },
  {
    key: 'drivers_behavioral_patterns',
    label: 'Patrones',
    tab: 'Drivers',
    component: 'BehavioralPatternDiagnosisDashboard',
    route: '/drivers/behavioral-patterns',
    engine: ENGINE.DIAGNOSTIC,
    phaseStatus: PHASE_STATUS.READY_NEXT,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: false,
    requiresValidation: true,
    reason: 'Diagnostic Engine (Fase 2A.3): diagnóstico de patrones operativos. Motor Diagnostic READY NEXT — bloqueado hasta estabilizar Serving Governance.',
    endpoints: ['/behavioral-patterns/summary', '/behavioral-patterns/patterns', '/behavioral-patterns/group-profile', '/behavioral-patterns/decline-signals'],
  },
  {
    key: 'drivers_operational_intelligence',
    label: 'Operational Intel',
    tab: 'Drivers',
    component: 'OperationalBehavioralIntelligenceDashboard',
    route: '/drivers/operational-intelligence',
    engine: ENGINE.DIAGNOSTIC,
    phaseStatus: PHASE_STATUS.BACKLOG,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: false,
    requiresValidation: true,
    reason: 'FUTURE (BACKLOG): inteligencia operacional profunda con 7 sub-tabs. Depende de estabilización de Control Foundation + Diagnostic Engine completos. Pertenece a motores Decision/Suggestion no activos.',
    endpoints: ['/operational-intelligence/summary', '/operational-intelligence/efficiency', '/operational-intelligence/sessions', '/operational-intelligence/zones', '/operational-intelligence/time-patterns', '/operational-intelligence/pre-churn-signals', '/operational-intelligence/archetypes', '/operational-intelligence/top-vs-churned'],
  },
  {
    key: 'drivers_recoverability',
    label: 'Recoverability',
    tab: 'Drivers',
    component: 'RecoverabilityIntelligenceDashboard',
    route: '/drivers/recoverability',
    engine: ENGINE.REACHABILITY,
    phaseStatus: PHASE_STATUS.BACKLOG,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: false,
    requiresValidation: true,
    reason: 'BACKLOG (Reachability Engine): recoverability intelligence en shadow mode. Motor Reachability no activo. Bloqueado hasta estabilizar Driver Lifecycle + Diagnostic Engine.',
    endpoints: ['/recoverability/summary', '/recoverability/top-recoverable', '/recoverability/distribution', '/recoverability/driver/{driver_id}', '/recoverability/shadow-priority', '/recoverability/segments', '/recoverability/explainability/{driver_id}', '/recoverability/risk-distribution'],
  },

  // ═══════════════════════════════════════════════════════════════════
  // RIESGO — Diagnostic Engine (READY NEXT) + BACKLOG hidden
  // ═══════════════════════════════════════════════════════════════════
  {
    key: 'riesgo_driver_behavior',
    label: 'Desviación por ventanas',
    tab: 'Riesgo',
    component: 'DriverBehaviorView',
    route: '/riesgo/driver-behavior',
    engine: ENGINE.DIAGNOSTIC,
    phaseStatus: PHASE_STATUS.READY_NEXT,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: true,
    requiresValidation: false,
    reason: 'Diagnostic Engine (READY NEXT): desviación de conductores por ventanas temporales.',
    endpoints: ['/ops/driver-behavior/summary', '/ops/driver-behavior/drivers', '/ops/driver-behavior/driver-detail'],
  },
  {
    key: 'riesgo_action_engine',
    label: 'Acciones recomendadas',
    tab: 'Riesgo',
    component: 'ActionEngineView',
    route: '/riesgo/action-engine',
    engine: ENGINE.ACTION,
    phaseStatus: PHASE_STATUS.BACKLOG,
    visibility: VISIBILITY.HIDE_FROM_NAV,
    productionReady: false,
    requiresValidation: true,
    reason: 'BACKLOG: Action Engine no está activo. Requiere Decision Engine previo cerrado. Las acciones automatizadas no deben mostrarse en producción.',
    endpoints: ['/ops/action-engine/summary', '/ops/action-engine/cohorts', '/ops/action-engine/recommendations'],
  },

  // ═══════════════════════════════════════════════════════════════════
  // OPERACIÓN — Control Foundation (ACTIVE)
  // ═══════════════════════════════════════════════════════════════════
  {
    key: 'operacion_omniview_matrix',
    label: 'Omniview Matrix',
    tab: 'Operación',
    component: 'BusinessSliceOmniviewMatrix',
    route: '/operacion/omniview-matrix',
    engine: ENGINE.CONTROL_FOUNDATION,
    phaseStatus: PHASE_STATUS.ACTIVE,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: true,
    requiresValidation: false,
    reason: 'Core Control Foundation: vista canónica de verdad operacional. No debe romperse.',
    endpoints: ['/ops/business-slice/monthly', '/ops/business-slice/weekly', '/ops/business-slice/daily', '/ops/business-slice/matrix-operational-trust'],
  },
  {
    key: 'operacion_control_loop_pvr',
    label: 'Control Loop Plan vs Real',
    tab: 'Operación',
    component: 'ControlLoopPlanVsRealView',
    route: '/operacion/control-loop-plan-vs-real',
    engine: ENGINE.CONTROL_FOUNDATION,
    phaseStatus: PHASE_STATUS.ACTIVE,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: true,
    requiresValidation: false,
    reason: 'Control Foundation: Control Loop Plan vs Real con proyección integrada.',
    endpoints: ['/ops/control-loop/plan-vs-real', '/ops/control-loop/plan-versions'],
  },
  {
    key: 'operacion_reportes',
    label: 'Reportes',
    tab: 'Operación',
    component: 'BusinessSliceOmniviewReports',
    route: '/operacion/reportes',
    engine: ENGINE.CONTROL_FOUNDATION,
    phaseStatus: PHASE_STATUS.ACTIVE,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: true,
    requiresValidation: false,
    reason: 'Control Foundation: reportes de Omniview.',
    endpoints: ['/ops/business-slice/fact-status'],
  },
  {
    key: 'operacion_oportunidades',
    label: 'Oportunidades Operativas',
    tab: 'Operación',
    component: 'OperationalOpportunitiesView',
    route: '/operacion/oportunidades',
    engine: ENGINE.DIAGNOSTIC,
    phaseStatus: PHASE_STATUS.READY_NEXT,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: true,
    requiresValidation: false,
    reason: 'Diagnostic Engine (READY NEXT): oportunidades operativas y contextuales detectadas por proyección. Lenguaje de oportunidad, no de decisión automática.',
    endpoints: ['/ops/business-slice/omniview-projection', '/ops/control-loop/plan-versions', '/plan/versions'],
  },
  {
    key: 'operacion_lob_drill',
    label: 'Real LOB / Drill',
    tab: 'Operación',
    component: 'RealLOBDrillView',
    route: '/operacion/lob-drill',
    engine: ENGINE.CONTROL_FOUNDATION,
    phaseStatus: PHASE_STATUS.ACTIVE,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: true,
    requiresValidation: false,
    reason: 'Control Foundation: drill-down jerárquico por LOB, park y tipo de servicio.',
    endpoints: ['/ops/real-lob/drill', '/ops/real-lob/drill/children', '/ops/real-lob/drill/parks'],
  },
  {
    key: 'operacion_omniview',
    label: 'Omniview',
    tab: 'Operación',
    component: 'BusinessSliceOmniview',
    route: '/operacion/omniview',
    engine: ENGINE.CONTROL_FOUNDATION,
    phaseStatus: PHASE_STATUS.ACTIVE,
    visibility: VISIBILITY.HIDE_FROM_NAV,
    productionReady: true,
    requiresValidation: false,
    reason: 'FASE 1H.3 — redundante con Omniview Matrix. Ruta legacy oculta para evitar duplicación de navegación.',
    endpoints: ['/ops/business-slice/monthly', '/ops/business-slice/weekly', '/ops/business-slice/daily'],
  },
  {
    key: 'operacion_business_slice',
    label: 'Business Slice',
    tab: 'Operación',
    component: 'BusinessSliceView',
    route: '/operacion/business-slice',
    engine: ENGINE.CONTROL_FOUNDATION,
    phaseStatus: PHASE_STATUS.ACTIVE,
    visibility: VISIBILITY.HIDE_FROM_NAV,
    productionReady: true,
    requiresValidation: false,
    reason: 'FASE 1H.3 — redundante con Omniview Matrix. Ruta legacy oculta para evitar duplicación de navegación.',
    endpoints: ['/ops/business-slice/monthly', '/ops/business-slice/weekly', '/ops/business-slice/daily'],
  },

  // ═══════════════════════════════════════════════════════════════════
  // PLAN — Control Foundation (ACTIVE)
  // ═══════════════════════════════════════════════════════════════════
  {
    key: 'plan_acciones',
    label: 'Acciones',
    tab: 'Plan',
    component: 'Phase2BActionsTrackingView + Phase2CAccountabilityView',
    route: '/plan/acciones',
    engine: ENGINE.CONTROL_FOUNDATION,
    phaseStatus: PHASE_STATUS.ACTIVE,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: true,
    requiresValidation: false,
    reason: 'Control Foundation (accountability): seguimiento de acciones operativas. NO es Action Engine. Pertenece a Control Foundation.',
    endpoints: ['/phase2b/actions', '/phase2c/scoreboard', '/phase2c/backlog', '/phase2c/breaches'],
    legacyNote: 'phase2b_actions NO equivale al futuro Action Engine. Es registro operacional básico de Control Foundation.',
  },
  {
    key: 'plan_universo',
    label: 'Universo',
    tab: 'Plan',
    component: 'LobUniverseView',
    route: '/plan/universo',
    engine: ENGINE.CONTROL_FOUNDATION,
    phaseStatus: PHASE_STATUS.ACTIVE,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: true,
    requiresValidation: false,
    reason: 'Control Foundation: universo LOB con mapeo Plan vs Real. Pertenece a Phase 2C+ (legacy) → Control Foundation.',
    endpoints: ['/phase2c/lob-universe', '/phase2c/lob-universe/unmatched'],
  },
  {
    key: 'plan_validacion',
    label: 'Validación',
    tab: 'Plan',
    component: 'PlanTabs',
    route: '/plan/validacion',
    engine: ENGINE.CONTROL_FOUNDATION,
    phaseStatus: PHASE_STATUS.ACTIVE,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: true,
    requiresValidation: false,
    reason: 'Control Foundation: validación de plan (expansión, huecos).',
    endpoints: ['/plan/out_of_universe', '/plan/missing'],
  },

  // ═══════════════════════════════════════════════════════════════════
  // DIAGNÓSTICOS — Control Foundation (System Health)
  // ═══════════════════════════════════════════════════════════════════
  {
    key: 'system_health',
    label: 'System Health',
    tab: 'Diagnósticos',
    component: 'SystemHealthView',
    route: '/diagnosticos',
    engine: ENGINE.CONTROL_FOUNDATION,
    phaseStatus: PHASE_STATUS.ACTIVE,
    visibility: VISIBILITY.KEEP_VISIBLE,
    productionReady: true,
    requiresValidation: false,
    reason: 'Control Foundation: salud del sistema, integridad, freshness.',
    endpoints: ['/ops/system-health', '/ops/integrity-report', '/ops/data-freshness/global'],
  },

  // ═══════════════════════════════════════════════════════════════════
  // HIDDEN / BACKLOG — No visibles en producción
  // ═══════════════════════════════════════════════════════════════════
  {
    key: 'real_vs_projection',
    label: 'Real vs Proyección',
    tab: 'En revisión',
    component: 'RealVsProjectionView',
    route: '/en-revision/real-vs-proyeccion',
    engine: ENGINE.FORECAST,
    phaseStatus: PHASE_STATUS.BACKLOG,
    visibility: VISIBILITY.HIDE_FROM_NAV,
    productionReady: false,
    requiresValidation: true,
    reason: 'BACKLOG: Forecast Engine no está activo. Real vs Proyección es proto-forecast. Oculto hasta que Forecast Engine esté READY NEXT.',
    endpoints: ['/ops/real-vs-projection/overview', '/ops/real-vs-projection/dimensions'],
  },
  {
    key: 'en_revision_behavioral_alerts_legacy',
    label: 'Alertas de conducta (legacy)',
    tab: 'En revisión',
    component: 'BehavioralAlertsView',
    route: '/en-revision/alertas',
    engine: ENGINE.DIAGNOSTIC,
    phaseStatus: PHASE_STATUS.READY_NEXT,
    visibility: VISIBILITY.HIDE_FROM_NAV,
    productionReady: false,
    requiresValidation: false,
    reason: 'Movido a Drivers > Alertas de conducta. Esta ruta legacy se oculta para evitar duplicación.',
    endpoints: ['/ops/behavior-alerts/summary', '/ops/behavior-alerts/drivers'],
  },
  {
    key: 'en_revision_fleet_leakage_legacy',
    label: 'Fuga de flota (legacy)',
    tab: 'En revisión',
    component: 'FleetLeakageView',
    route: '/en-revision/flota',
    engine: ENGINE.DIAGNOSTIC,
    phaseStatus: PHASE_STATUS.READY_NEXT,
    visibility: VISIBILITY.HIDE_FROM_NAV,
    productionReady: false,
    reason: 'Movido a Drivers > Fuga de flota. Esta ruta legacy se oculta para evitar duplicación.',
    endpoints: ['/ops/leakage/summary', '/ops/leakage/drivers'],
  },
]

/**
 * Devuelve solo las vistas que deben mostrarse en navegación de producción.
 */
export function getVisibleNavigation () {
  const isDev = typeof import.meta !== 'undefined' && import.meta.env?.DEV
  const showDevModules = typeof import.meta !== 'undefined' && import.meta.env?.VITE_SHOW_DEV_MODULES === 'true'

  return CONTROL_TOWER_NAVIGATION_REGISTRY.filter((item) => {
    if (item.visibility === VISIBILITY.KEEP_VISIBLE) return true
    if (item.visibility === VISIBILITY.DEV_ONLY && (isDev || showDevModules)) return true
    return false
  })
}

/**
 * Agrupa vistas visibles por tab.
 */
export function getVisibleTabs () {
  const visible = getVisibleNavigation()
  const tabs = new Map()

  for (const item of visible) {
    if (!tabs.has(item.tab)) {
      tabs.set(item.tab, [])
    }
    tabs.get(item.tab).push(item)
  }

  return tabs
}

/**
 * Encuentra una entrada del registry por ruta.
 */
export function findRegistryEntry (pathname) {
  const exact = CONTROL_TOWER_NAVIGATION_REGISTRY.find((r) => r.route === pathname)
  if (exact) return exact
  const prefix = CONTROL_TOWER_NAVIGATION_REGISTRY.find(
    (r) => r.route !== '/' && pathname.startsWith(r.route)
  )
  return prefix || null
}
