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
  STABLE: 'stable',
  HARDENING: 'hardening',
  IN_CONSTRUCTION: 'in_construction',
  EXPERIMENTAL: 'experimental',
  LEGACY: 'legacy',
  DEPRECATED: 'deprecated',
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
  // DRIVERS
  // ═══════════════════════════════════════════════════════════════════
  drivers_supply: {
    maturity: MATURITY.STABLE,
    phase: '1H',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Dinámicas de supply, segmentación y migración de conductores.',
    endpoints: ['/ops/supply/geo', '/ops/supply/series', '/ops/supply/summary'],
  },
  drivers_lifecycle: {
    maturity: MATURITY.HARDENING,
    phase: '1H',
    engine: ENGINE_OWNER.CONTROL_FOUNDATION,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Ciclo de vida de conductores, cohorts, métricas base.',
    endpoints: ['/ops/driver-lifecycle/weekly', '/ops/driver-lifecycle/monthly'],
  },
  drivers_diagnostic: {
    maturity: MATURITY.IN_CONSTRUCTION,
    phase: '2A.1',
    engine: ENGINE_OWNER.DIAGNOSTIC,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Diagnóstico determinista de ciclo de vida, riesgo y leakage.',
    endpoints: ['/driver-lifecycle/summary', '/driver-lifecycle/funnel'],
  },
  drivers_behavior_benchmarking: {
    maturity: MATURITY.IN_CONSTRUCTION,
    phase: '2A.2',
    engine: ENGINE_OWNER.DIAGNOSTIC,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Benchmarking comparativo de patrones operativos entre grupos.',
    endpoints: ['/driver-behavior/summary', '/driver-behavior/group-benchmarks'],
  },
  drivers_behavioral_alerts: {
    maturity: MATURITY.IN_CONSTRUCTION,
    phase: '2A',
    engine: ENGINE_OWNER.DIAGNOSTIC,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Alertas de desviación conductual vs baseline.',
    endpoints: ['/ops/behavior-alerts/summary', '/ops/behavior-alerts/drivers'],
  },
  drivers_fleet_leakage: {
    maturity: MATURITY.IN_CONSTRUCTION,
    phase: '2A',
    engine: ENGINE_OWNER.DIAGNOSTIC,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Monitoreo de fuga de flota y pérdida de conductores.',
    endpoints: ['/ops/leakage/summary', '/ops/leakage/drivers'],
  },
  drivers_behavioral_patterns: {
    maturity: MATURITY.IN_CONSTRUCTION,
    phase: '2A.3',
    engine: ENGINE_OWNER.DIAGNOSTIC,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Diagnóstico determinístico de patrones operativos diferenciales.',
    endpoints: ['/behavioral-patterns/summary', '/behavioral-patterns/patterns'],
  },
  drivers_operational_intelligence: {
    maturity: MATURITY.IN_CONSTRUCTION,
    phase: '2B',
    engine: ENGINE_OWNER.DIAGNOSTIC,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Inteligencia operacional profunda. NO recomendaciones automáticas.',
    endpoints: ['/operational-intelligence/summary', '/operational-intelligence/efficiency'],
  },
  drivers_recoverability: {
    maturity: MATURITY.IN_CONSTRUCTION,
    phase: '2C.1',
    engine: ENGINE_OWNER.DIAGNOSTIC,
    visible: true,
    navigationGroup: NAVIGATION_GROUP.DRIVERS,
    legacy: false,
    experimental: false,
    description: 'Recoverability intelligence. Shadow mode. NO acciones automáticas.',
    endpoints: ['/recoverability/summary', '/recoverability/top-recoverable'],
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
 */
export function getMaturityBadgeInfo (moduleKey) {
  const entry = OPERATIONAL_MATURITY_REGISTRY[moduleKey]
  if (!entry) return null

  switch (entry.maturity) {
    case MATURITY.HARDENING:
      return { label: 'Hardening', color: 'bg-amber-100 text-amber-800 border-amber-200' }
    case MATURITY.IN_CONSTRUCTION:
      return { label: `En construcción — ${entry.phase}`, color: 'bg-blue-100 text-blue-800 border-blue-200' }
    case MATURITY.EXPERIMENTAL:
      return { label: 'Experimental', color: 'bg-purple-100 text-purple-800 border-purple-200' }
    case MATURITY.LEGACY:
      return { label: 'Legacy', color: 'bg-gray-100 text-gray-600 border-gray-200' }
    case MATURITY.DEPRECATED:
      return { label: 'Deprecated', color: 'bg-red-100 text-red-800 border-red-200' }
    default:
      return null
  }
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
