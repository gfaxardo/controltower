/**
 * YEGO Control Tower — Operational Maturity Registry
 * FASE 1H.4: Operational Maturity Governance Layer
 *
 * Clasifica cada módulo/vista por madurez operacional.
 * Define visibilidad, gobernanza de fase, engine ownership,
 * feature flags, y estado de navegación.
 *
 * NO hardcodear estados de madurez en componentes.
 * Consumir este registry como fuente canónica.
 */

export const MATURITY = {
  ACTIVE: 'active',
  STABLE: 'stable',
  HARDENING: 'hardening',
  READY_NEXT: 'ready_next',
  IN_CONSTRUCTION: 'in_construction',
  EXPERIMENTAL: 'experimental',
  FUTURE: 'future',
  LEGACY: 'legacy',
  DEPRECATED: 'deprecated',
  BLOCKED: 'blocked',
}

export const ENGINE_OWNER = {
  CONTROL_FOUNDATION: 'Control Foundation',
  DIAGNOSTIC: 'Diagnostic Engine',
  REACHABILITY: 'Reachability Engine',
  FORECAST: 'Forecast Engine',
  SUGGESTION: 'Suggestion Engine',
  DECISION: 'Decision Engine',
  ACTION: 'Action Engine',
  AI_COPILOT: 'AI Copilot',
  LEARNING: 'Learning Engine',
  OPERATIONAL_WORKFLOW: 'Operational Workflow',
  DECISION_SUGGESTION: 'Decision / Suggestion',
}

export const DRIVER_PHASE = {
  D1: 'D1 — Supply Foundation',
  D2: 'D2 — Supply Hardening',
  D3: 'D3 — Lifecycle Intelligence',
  D4: 'D4 — Actionable Lists',
  D5: 'D5 — Lifecycle Hardening',
  D6: 'D6 — Diagnostic Readiness',
  D7: 'D7 — Recoverability Readiness',
  FUTURE: 'FUTURE — Backlog',
}

export const NAVIGATION_GROUP = {
  PERFORMANCE: 'Performance',
  DRIVERS: 'Drivers',
  RIESGO: 'Riesgo',
  OPERACION: 'Operacion',
  PLAN: 'Plan',
  SYSTEM_HEALTH: 'System Health',
  LEGACY: 'Legacy',
}

/**
 * Registry de madurez operacional.
 *
 * Cada entrada define:
 *  - maturity:       MATURITY.*
 *  - phase:          fase actual (1H, 2A, etc.)
 *  - engine:         ENGINE_OWNER.*
 *  - visible:        aparece en navegación principal
 *  - navigationGroup: agrupación de navegación
 *  - legacy:         marcado como legacy (ruta antigua redundante)
 *  - experimental:   requiere feature flag para mostrarse
 *  - featureFlag:    nombre del feature flag (si experimental)
 *  - description:    resumen operacional
 *  - endpoints:      API endpoints asociados
 */
export const OPERATIONAL_MATURITY_REGISTRY = {
  // ═══════════════════════════════════════════════════════════════════
  // PERFORMANCE
  // ═══════════════════════════════════════════════════════════════════
  performance_resumen: {
    maturity: MATURITY.STABLE,
    phase: '1H',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.PERFORMANCE,
    legacy: false,
    experimental: false,
    description: 'KPIs ejecutivos, snapshot de métricas principales.',
    endpoints: ['/core/summary/monthly', '/ops/plan/monthly', '/ops/real/monthly'],
  },
  performance_plan_vs_real: {
    maturity: MATURITY.STABLE,
    phase: '1H',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.PERFORMANCE,
    legacy: false,
    experimental: false,
    description: 'Comparación Plan vs Real mensual y semanal.',
    endpoints: ['/ops/plan-vs-real/monthly', '/ops/plan/monthly', '/ops/real/monthly'],
  },
  performance_real: {
    maturity: MATURITY.STABLE,
    phase: '1H',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.PERFORMANCE,
    legacy: false,
    experimental: false,
    description: 'Vista operacional diaria (hourly-first).',
    endpoints: ['/ops/real-operational/snapshot', '/ops/real-operational/day-view'],
  },
  performance_yango_loyalty: {
    maturity: MATURITY.HARDENING,
    phase: '1H',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.PERFORMANCE,
    legacy: false,
    experimental: false,
    description: 'Tracker de cumplimiento Yango Loyalty / Oro por ciudad.',
    endpoints: ['/yango-loyalty/summary', '/yango-loyalty/kpis'],
  },

  // ═══════════════════════════════════════════════════════════════════
  // DRIVERS — Driver Operating System progresivo
  // ═══════════════════════════════════════════════════════════════════
  // Regla: visible ≠ productionReady. Todas las tabs visibles para mostrar el roadmap.
  // Solo Control Foundation tabs son productionReady en fase activa 1H.4.
  // Diagnostic / Reachability / Future son visibles pero gobernadas visualmente.
  // ═══════════════════════════════════════════════════════════════════
  drivers_supply: {
    maturity: MATURITY.HARDENING,
    phase: 'D1/D2',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Supply Overview — dinámicas de supply, segmentación y migración de conductores.',
    endpoints: ['/ops/supply/geo', '/ops/supply/series', '/ops/supply/summary'],
    statusLabel: 'Hardening',
    statusTone: 'amber',
    governanceReason: 'Control Foundation. Data real estable. Pendiente integración de actionable lists y serving facts unificados.',
    dependencies: ['serving.driver_identity_fact', 'serving.driver_activity_weekly_fact'],
    allowedInCurrentPhase: true,
  },
  drivers_lifecycle: {
    maturity: MATURITY.IN_CONSTRUCTION,
    phase: 'D3',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Ciclo de vida de conductores, cohorts, métricas base, retención.',
    endpoints: ['/ops/driver-lifecycle/weekly', '/ops/driver-lifecycle/monthly'],
    statusLabel: 'Under Construction',
    statusTone: 'purple',
    governanceReason: 'Control Foundation. KPIs de ciclo de vida funcionales. Drilldown sin enriquecimiento de identidad (sin phone, sin nombre en algunas queries). Pendiente fusión con risk list de Diagnóstico.',
    dependencies: ['serving.driver_lifecycle_fact', 'public.drivers_data.phone'],
    allowedInCurrentPhase: true,
  },
  drivers_action_queues: {
    maturity: MATURITY.HARDENING,
    phase: 'D4',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Action Queues — colas operacionales accionables con prioridad y evidencia.',
    endpoints: ['/drivers/actionable-list', '/drivers/actionable-summary'],
    statusLabel: 'Hardening',
    statusTone: 'amber',
    governanceReason: 'Control Foundation (D4). 5 queues operacionales con priority engine determinístico. Pendiente: workflow de asignación y gestión.',
    dependencies: ['driver_identity_service', 'driver_activity_service', 'driver_lifecycle_service'],
    allowedInCurrentPhase: true,
  },
  drivers_diagnostic: {
    maturity: MATURITY.IN_CONSTRUCTION,
    phase: 'D3/D6',
    engine: ENGINE_OWNER.DIAGNOSTIC,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Diagnóstico determinista de ciclo de vida, funnel y risk list.',
    endpoints: ['/driver-lifecycle/summary', '/driver-lifecycle/funnel'],
    statusLabel: 'Under Construction',
    statusTone: 'purple',
    governanceReason: 'Diagnostic Engine (Fase 2A.1). Risk list funcional pero sin phone/contacto. Motor Diagnostic no está ACTIVO (READY NEXT). Visible como preview. Se fusionará con Lifecycle en fase D5.',
    dependencies: ['serving.driver_lifecycle_fact', 'driver_identity_resolver (phone)'],
    allowedInCurrentPhase: false,
  },
  drivers_behavior_benchmarking: {
    maturity: MATURITY.READY_NEXT,
    phase: 'D6',
    engine: ENGINE_OWNER.DIAGNOSTIC,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Behavior Benchmarking — comparación TOP vs DECLINING vs AT_RISK entre grupos.',
    endpoints: ['/driver-behavior/summary', '/driver-behavior/group-benchmarks'],
    statusLabel: 'Diagnostic Engine · Ready Next',
    statusTone: 'blue',
    governanceReason: 'Diagnostic Engine (Fase 2A.2). Benchmarks agregados funcionales. Sin serving fact dedicado, fallback a trips_2026. Motor Diagnostic no está ACTIVO (READY NEXT).',
    dependencies: ['driver_daily_activity_fact (estabilizar)', 'Diagnostic Engine activation'],
    allowedInCurrentPhase: false,
  },
  drivers_behavioral_alerts: {
    maturity: MATURITY.READY_NEXT,
    phase: 'D6',
    engine: ENGINE_OWNER.DIAGNOSTIC,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Alertas de desviación conductual vs baseline semanal.',
    endpoints: ['/ops/behavior-alerts/summary', '/ops/behavior-alerts/drivers'],
    statusLabel: 'Ready Next',
    statusTone: 'blue',
    governanceReason: 'Diagnostic Engine (Fase 2A). Alertas de conducta con severity/risk funcionales. Depende de vista semanal. Motor Diagnostic no está ACTIVO.',
    dependencies: ['v_driver_behavior_alerts_weekly', 'Diagnostic Engine activation'],
    allowedInCurrentPhase: false,
  },
  drivers_fleet_leakage: {
    maturity: MATURITY.IN_CONSTRUCTION,
    phase: 'D6/D7',
    engine: ENGINE_OWNER.DIAGNOSTIC,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Fuga de flota — monitoreo de pérdida de conductores.',
    endpoints: ['/ops/leakage/summary', '/ops/leakage/drivers'],
    statusLabel: 'Under Construction',
    statusTone: 'purple',
    governanceReason: 'Diagnostic Engine. Fleet leakage snapshot funcional pero marcado "under_review" por el propio sistema. Requiere validación de estabilidad runtime antes de subir a READY NEXT.',
    dependencies: ['v_fleet_leakage_snapshot (validar)', 'Diagnostic Engine activation'],
    allowedInCurrentPhase: false,
  },
  drivers_behavioral_patterns: {
    maturity: MATURITY.READY_NEXT,
    phase: 'D6',
    engine: ENGINE_OWNER.DIAGNOSTIC,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Diagnóstico determinístico de patrones operativos diferenciales.',
    endpoints: ['/behavioral-patterns/summary', '/behavioral-patterns/patterns'],
    statusLabel: 'Ready Next',
    statusTone: 'blue',
    governanceReason: 'Diagnostic Engine (Fase 2A.3). Pattern detection funcional pero sin serving fact estable. Motor Diagnostic no está ACTIVO. READY NEXT — bloqueado hasta estabilizar Serving Governance Foundation.',
    dependencies: ['driver_daily_activity_fact', 'Diagnostic Engine activation', 'Serving Governance Foundation'],
    allowedInCurrentPhase: false,
  },
  drivers_operational_intelligence: {
    maturity: MATURITY.FUTURE,
    phase: 'FUTURE',
    engine: ENGINE_OWNER.DECISION_SUGGESTION,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Inteligencia operacional profunda con 7 sub-tabs. NO recomendaciones automáticas.',
    endpoints: ['/operational-intelligence/summary', '/operational-intelligence/efficiency'],
    statusLabel: 'Future',
    statusTone: 'gray',
    governanceReason: 'Decision / Suggestion (FUTURE). 7 sub-tabs con timeouts de 120s, raw api.get(), sin output accionable. Depende de estabilización de Control Foundation + Diagnostic Engine completos. Pertenece a motores no activos (BACKLOG).',
    dependencies: ['Control Foundation completo', 'Diagnostic Engine activo', 'Suggestion Engine'],
    allowedInCurrentPhase: false,
  },
  drivers_recoverability: {
    maturity: MATURITY.BLOCKED,
    phase: 'D7',
    engine: ENGINE_OWNER.REACHABILITY,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Recoverability Intelligence — scoring de recuperabilidad. Shadow mode.',
    endpoints: ['/recoverability/summary', '/recoverability/top-recoverable'],
    statusLabel: 'Blocked by Driver Lifecycle',
    statusTone: 'warning',
    governanceReason: 'Reachability Engine (BACKLOG). Shadow mode activo — calcula scores sin automatizar acciones. Motor Reachability no está activo. Bloqueado hasta que Driver Lifecycle (Control Foundation D3-D5) y Diagnostic Engine estén estables.',
    dependencies: ['Driver Lifecycle (D3-D5)', 'Diagnostic Engine', 'Reachability Engine activation', 'driver_identity_fact (phone)'],
    allowedInCurrentPhase: false,
  },

  // ═══════════════════════════════════════════════════════════════════
  // RIESGO
  // ═══════════════════════════════════════════════════════════════════
  riesgo_driver_behavior: {
    maturity: MATURITY.IN_CONSTRUCTION,
    phase: '2A',
    engine: ENGINE_OWNER.DIAGNOSTIC,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.RIESGO,
    legacy: false,
    experimental: false,
    description: 'Desviación de conductores por ventanas temporales.',
    endpoints: ['/ops/driver-behavior/summary', '/ops/driver-behavior/drivers'],
  },
  riesgo_action_engine: {
    maturity: MATURITY.DEPRECATED,
    phase: 'BACKLOG',
    engine: ENGINE_OWNER.ACTION,
    visible: false,
    navigationGroup: NAVIGATION_GROUP.RIESGO,
    legacy: false,
    experimental: false,
    featureFlag: null,
    description: 'Action Engine — requiere Decision Engine previo. NO activo.',
    endpoints: ['/ops/action-engine/summary'],
  },

  // ═══════════════════════════════════════════════════════════════════
  // OPERACIÓN
  // ═══════════════════════════════════════════════════════════════════
  operacion_omniview_matrix: {
    maturity: MATURITY.STABLE,
    phase: '1H',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.OPERACION,
    legacy: false,
    experimental: false,
    description: 'Vista canónica de verdad operacional. Centro de comando.',
    endpoints: ['/ops/business-slice/monthly', '/ops/business-slice/weekly'],
  },
  operacion_control_loop_pvr: {
    maturity: MATURITY.STABLE,
    phase: '1H',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.OPERACION,
    legacy: false,
    experimental: false,
    description: 'Control Loop Plan vs Real con proyección integrada.',
    endpoints: ['/ops/control-loop/plan-vs-real', '/ops/control-loop/plan-versions'],
  },
  operacion_reportes: {
    maturity: MATURITY.STABLE,
    phase: '1H',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.OPERACION,
    legacy: false,
    experimental: false,
    description: 'Reportes de Omniview.',
    endpoints: ['/ops/business-slice/fact-status'],
  },
  operacion_oportunidades: {
    maturity: MATURITY.IN_CONSTRUCTION,
    phase: '2B',
    engine: ENGINE_OWNER.DIAGNOSTIC,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.OPERACION,
    legacy: false,
    experimental: false,
    description: 'Oportunidades operativas detectadas por proyección.',
    endpoints: ['/ops/business-slice/omniview-projection'],
  },
  operacion_lob_drill: {
    maturity: MATURITY.STABLE,
    phase: '1H',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.OPERACION,
    legacy: false,
    experimental: false,
    description: 'Drill-down jerárquico por LOB, park y tipo de servicio.',
    endpoints: ['/ops/real-lob/drill', '/ops/real-lob/drill/children'],
  },

  // ── Legacy Operación ──
  operacion_omniview: {
    maturity: MATURITY.LEGACY,
    phase: '1H.3',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: false,
    navigationGroup: NAVIGATION_GROUP.LEGACY,
    legacy: true,
    experimental: false,
    description: 'Vista Omniview legacy — reemplazada por Omniview Matrix.',
    endpoints: ['/ops/business-slice/monthly', '/ops/business-slice/weekly'],
  },
  operacion_business_slice: {
    maturity: MATURITY.LEGACY,
    phase: '1H.3',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: false,
    navigationGroup: NAVIGATION_GROUP.LEGACY,
    legacy: true,
    experimental: false,
    description: 'Vista Business Slice legacy — reemplazada por Omniview Matrix.',
    endpoints: ['/ops/business-slice/monthly', '/ops/business-slice/weekly'],
  },

  // ═══════════════════════════════════════════════════════════════════
  // PLAN
  // ═══════════════════════════════════════════════════════════════════
  plan_acciones: {
    maturity: MATURITY.HARDENING,
    phase: '1H',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.PLAN,
    legacy: false,
    experimental: false,
    description: 'Seguimiento de acciones operativas. NO es Action Engine.',
    endpoints: ['/phase2b/actions', '/phase2c/scoreboard'],
  },
  plan_universo: {
    maturity: MATURITY.HARDENING,
    phase: '1H',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.PLAN,
    legacy: false,
    experimental: false,
    description: 'Universo LOB con mapeo Plan vs Real.',
    endpoints: ['/phase2c/lob-universe', '/phase2c/lob-universe/unmatched'],
  },
  plan_validacion: {
    maturity: MATURITY.HARDENING,
    phase: '1H',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.PLAN,
    legacy: false,
    experimental: false,
    description: 'Validación de plan (expansión, huecos).',
    endpoints: ['/plan/out_of_universe', '/plan/missing'],
  },

  // ═══════════════════════════════════════════════════════════════════
  // SYSTEM HEALTH
  // ═══════════════════════════════════════════════════════════════════
  system_health: {
    maturity: MATURITY.STABLE,
    phase: '1H',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.SYSTEM_HEALTH,
    legacy: false,
    experimental: false,
    description: 'Salud del sistema, integridad, freshness.',
    endpoints: ['/ops/system-health', '/ops/integrity-report'],
  },

  // ═══════════════════════════════════════════════════════════════════
  // LEGACY HIDDEN ROUTES
  // ═══════════════════════════════════════════════════════════════════
  en_revision_behavioral_alerts_legacy: {
    maturity: MATURITY.LEGACY,
    phase: '1H',
    engine: ENGINE_OWNER.DIAGNOSTIC,
    visible: false,
    navigationGroup: NAVIGATION_GROUP.LEGACY,
    legacy: true,
    experimental: false,
    description: 'Ruta legacy de alertas de conducta — movida a Drivers.',
    endpoints: ['/ops/behavior-alerts/summary'],
  },
  en_revision_fleet_leakage_legacy: {
    maturity: MATURITY.LEGACY,
    phase: '1H',
    engine: ENGINE_OWNER.DIAGNOSTIC,
    visible: false,
    navigationGroup: NAVIGATION_GROUP.LEGACY,
    legacy: true,
    experimental: false,
    description: 'Ruta legacy de fuga de flota — movida a Drivers.',
    endpoints: ['/ops/leakage/summary'],
  },

  // ═══════════════════════════════════════════════════════════════════
  // EXPERIMENTAL (BACKLOG ENGINES)
  // ═══════════════════════════════════════════════════════════════════
  real_vs_projection: {
    maturity: MATURITY.EXPERIMENTAL,
    phase: 'BACKLOG',
    engine: ENGINE_OWNER.FORECAST,
    visible: false,
    navigationGroup: NAVIGATION_GROUP.LEGACY,
    legacy: false,
    experimental: true,
    featureFlag: 'VITE_SHOW_FORECAST_EXPERIMENTAL',
    description: 'Proto-forecast: Real vs Proyección. Forecast Engine no activo.',
    endpoints: ['/ops/real-vs-projection/overview'],
  },
}

/**
 * Obtiene el estado de madurez de un módulo por su key.
 */
export function getMaturity (moduleKey) {
  return OPERATIONAL_MATURITY_REGISTRY[moduleKey]?.maturity || MATURITY.STABLE
}

/**
 * Devuelve true si el módulo debe ser visible en navegación.
 * Respeta maturity + visibilidad + feature flags.
 */
export function isModuleVisible (moduleKey) {
  const entry = OPERATIONAL_MATURITY_REGISTRY[moduleKey]
  if (!entry) return false
  if (!entry.visible) return false

  // Experimental modules require feature flag
  if (entry.experimental && entry.featureFlag) {
    const isDev = typeof import.meta !== 'undefined' && import.meta.env?.DEV
    const flagEnabled = typeof import.meta !== 'undefined' && import.meta.env?.[entry.featureFlag] === 'true'
    if (!isDev && !flagEnabled) return false
  }

  return true
}

/**
 * Devuelve el maturity badge info para UI.
 * Incluye nuevos niveles: ACTIVE, READY_NEXT, FUTURE, BLOCKED.
 */
export function getMaturityBadgeInfo (moduleKey) {
  const entry = OPERATIONAL_MATURITY_REGISTRY[moduleKey]
  if (!entry) return null

  switch (entry.maturity) {
    case MATURITY.ACTIVE:
      return { label: 'Active', color: 'bg-emerald-100 text-emerald-800 border-emerald-200' }
    case MATURITY.HARDENING:
      return { label: 'Hardening', color: 'bg-amber-100 text-amber-800 border-amber-200' }
    case MATURITY.READY_NEXT:
      return { label: 'Ready Next', color: 'bg-blue-100 text-blue-800 border-blue-200' }
    case MATURITY.IN_CONSTRUCTION:
      return { label: 'En construcción', color: 'bg-purple-100 text-purple-800 border-purple-200' }
    case MATURITY.EXPERIMENTAL:
      return { label: 'Experimental', color: 'bg-purple-100 text-purple-800 border-purple-200' }
    case MATURITY.FUTURE:
      return { label: 'Future', color: 'bg-gray-100 text-gray-600 border-gray-200' }
    case MATURITY.LEGACY:
      return { label: 'Legacy', color: 'bg-gray-100 text-gray-600 border-gray-200' }
    case MATURITY.DEPRECATED:
      return { label: 'Deprecated', color: 'bg-red-100 text-red-800 border-red-200' }
    case MATURITY.BLOCKED:
      return { label: 'Blocked', color: 'bg-orange-100 text-orange-800 border-orange-200' }
    default:
      return null
  }
}

/**
 * Devuelve metadata completa de capability governance para un módulo.
 * Usado por DriverCapabilityBadge y DriverCapabilityBanner.
 */
export function getCapabilityMeta (moduleKey) {
  const entry = OPERATIONAL_MATURITY_REGISTRY[moduleKey]
  if (!entry) return null

  return {
    moduleKey,
    maturity: entry.maturity,
    phase: entry.phase,
    engine: entry.engine,
    visible: entry.visible,
    legacy: entry.legacy || false,
    experimental: entry.experimental || false,
    productionReady: isProductionReady(moduleKey),
    statusLabel: entry.statusLabel || entry.maturity,
    statusTone: entry.statusTone || 'gray',
    governanceReason: entry.governanceReason || entry.description || '',
    dependencies: entry.dependencies || [],
    allowedInCurrentPhase: entry.allowedInCurrentPhase !== undefined ? entry.allowedInCurrentPhase : (entry.engine === ENGINE_OWNER.CONTROL_FOUNDATION),
    description: entry.description || '',
    endpoints: entry.endpoints || [],
  }
}

/**
 * Determina si un módulo está productionReady.
 * Control Foundation: STABLE, ACTIVE, o HARDENING.
 * Otros motores: solo STABLE/ACTIVE (ninguno — motores no activos).
 */
export function isProductionReady (moduleKey) {
  const meta = getCapabilityMeta(moduleKey)
  if (!meta) return false
  if (meta.maturity === MATURITY.STABLE || meta.maturity === MATURITY.ACTIVE) return true
  if (meta.maturity === MATURITY.HARDENING && meta.engine === ENGINE_OWNER.CONTROL_FOUNDATION) return true
  return false
}

/**
 * Agrupa entradas visibles por grupo de navegación.
 */
export function getModulesByGroup () {
  const groups = new Map()
  for (const [key, entry] of Object.entries(OPERATIONAL_MATURITY_REGISTRY)) {
    if (!isModuleVisible(key)) continue
    const group = entry.navigationGroup
    if (!groups.has(group)) groups.set(group, [])
    groups.get(group).push({ key, ...entry })
  }
  return groups
}

/**
 * Lista todos los módulos legacy.
 */
export function getLegacyModules () {
  return Object.entries(OPERATIONAL_MATURITY_REGISTRY)
    .filter(([, e]) => e.legacy)
    .map(([key, entry]) => ({ key, ...entry }))
}

/**
 * Lista todos los módulos experimentales.
 */
export function getExperimentalModules () {
  return Object.entries(OPERATIONAL_MATURITY_REGISTRY)
    .filter(([, e]) => e.experimental)
    .map(([key, entry]) => ({ key, ...entry }))
}

/**
 * Valida que no haya duplicados de key en el registry.
 */
export function validateRegistry () {
  const keys = Object.keys(OPERATIONAL_MATURITY_REGISTRY)
  const duplicates = keys.filter((k, i) => keys.indexOf(k) !== i)
  const legacyKeys = Object.entries(OPERATIONAL_MATURITY_REGISTRY)
    .filter(([, e]) => e.legacy)
    .map(([k]) => k)
  const experimentalKeys = Object.entries(OPERATIONAL_MATURITY_REGISTRY)
    .filter(([, e]) => e.experimental && e.visible)
    .map(([k]) => k)
  return {
    total: keys.length,
    duplicates: duplicates.length > 0 ? duplicates : null,
    legacyCount: legacyKeys.length,
    experimentalVisible: experimentalKeys,
  }
}
