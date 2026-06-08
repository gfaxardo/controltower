import axios from 'axios'

// Dev: proxy Vite /api. Producción: VITE_API_URL si está definido, si no '/api' (mismo origen con nginx)
const apiBase = (import.meta.env.VITE_API_URL || '').trim()
const baseURL = import.meta.env.DEV ? '/api' : (apiBase || '/api')

const api = axios.create({
  baseURL,
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
})

function resolveFinalUrl (config) {
  try {
    const path = config?.url || ''
    if (/^https?:\/\//i.test(path)) return path
    const base = config?.baseURL || ''
    if (typeof window !== 'undefined') {
      return new URL(`${base}${path}`, window.location.origin).toString()
    }
    return `${base}${path}`
  } catch {
    return `${config?.baseURL || ''}${config?.url || ''}`
  }
}

const STORAGE_TOKEN = 'ct_integral_token'

api.interceptors.request.use((config) => {
  try {
    const token = typeof sessionStorage !== 'undefined' ? sessionStorage.getItem(STORAGE_TOKEN) : null
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
  } catch {
    /* ignore */
  }
  if (import.meta.env.DEV) {
    config._startTime = Date.now()
  }
  return config
})

if (import.meta.env.DEV) {
  api.interceptors.response.use(
    (response) => {
      const dur = response.config._startTime ? Date.now() - response.config._startTime : null
      console.info('[API]', response.config.method?.toUpperCase(), resolveFinalUrl(response.config), { status: response.status, duration_ms: dur, params: response.config.params, source: 'response' })
      return response
    },
    (error) => {
      const cfg = error.config || {}
      const dur = cfg._startTime ? Date.now() - cfg._startTime : null
      console.warn('[API:ERROR]', cfg.method?.toUpperCase(), resolveFinalUrl(cfg), { status: error.response?.status, duration_ms: dur, params: cfg.params, error: error.message, source: 'error' })
      return Promise.reject(error)
    }
  )
}

/**
 * Solo ruta relativa al mismo origen (nginx → FastAPI → api-int). Nunca https://api-int… en el bundle
 * (provoca CORS si el navegador llama directo a otro dominio).
 */
const CORPORATE_LOGIN_PATH = '/api/auth/login'

const loginHttp = axios.create({
  timeout: 30000,
  headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
})

/**
 * validateStatus acepta 401 para leer message en AuthContext.
 */
export const loginIntegral = (username, password) =>
  loginHttp.post(
    CORPORATE_LOGIN_PATH,
    { username, password },
    { validateStatus: (s) => s >= 200 && s < 600 }
  )

// Instrumentación (Fase 1): en dev, log de requests y duración para detectar duplicados
if (import.meta.env.DEV) {
  api.interceptors.request.use((config) => {
    config.metadata = { startTime: Date.now() }
    console.debug('[API FINAL]', config.method?.toUpperCase(), resolveFinalUrl(config))
    return config
  })
  api.interceptors.response.use(
    (response) => {
      const duration = response.config.metadata ? Date.now() - response.config.metadata.startTime : 0
      const url = response.config.url || ''
      const params = response.config.params ? `?${new URLSearchParams(response.config.params).toString()}` : ''
      console.debug('[API]', response.config.method?.toUpperCase(), url + params, `${duration}ms`)
      return response
    },
    (error) => {
      const duration = error.config?.metadata ? Date.now() - error.config.metadata.startTime : 0
      console.debug('[API]', error.config?.method?.toUpperCase(), error.config?.url, 'ERR', error.response?.status, `${duration}ms`)
      return Promise.reject(error)
    }
  )
}

export const uploadPlan = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await api.post('/plan/upload_simple', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

export const uploadPlanRuta27 = async (file, planVersion = null, replaceAll = false) => {
  const formData = new FormData()
  formData.append('file', file)
  
  let url = '/plan/upload_ruta27'
  const params = []
  if (planVersion) {
    params.push(`plan_version=${encodeURIComponent(planVersion)}`)
  }
  if (replaceAll) {
    params.push('replace_all=true')
  }
  if (params.length > 0) {
    url += `?${params.join('&')}`
  }
  
  const response = await api.post(url, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
  return response.data
}

/** Proyección agregada Control Loop (Excel TRIPS/REVENUE/DRIVERS o CSV). */
export const uploadControlLoopProjection = async (file, planVersion = null) => {
  const formData = new FormData()
  formData.append('file', file)
  let url = '/plan/upload_control_loop_projection'
  if (planVersion) {
    url += `?plan_version=${encodeURIComponent(planVersion)}`
  }
  const response = await api.post(url, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response.data
}

/** Lista versiones del plan desde ops.plan_trips_monthly. */
export const getPlanVersions = async () => {
  const response = await api.get('/plan/versions', { timeout: 10000 })
  return response.data
}

/** Actualiza display_name de una versión de proyección. */
export const patchPlanVersion = async (planVersionKey, displayName, description = null) => {
  const params = { display_name: displayName }
  if (description) params.description = description
  const response = await api.patch(`/plan/versions/${encodeURIComponent(planVersionKey)}`, null, { params })
  return response.data
}

/** Sube archivo CSV o Excel (Ruta 27) desde la UI. Genera versión con timestamp automático. */
export const uploadPlanRuta27UI = async (file) => {
  const formData = new FormData()
  formData.append('file', file)
  const response = await api.post('/plan/upload_ruta27_ui', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 600000, // 10 min — ingesta puede tardar ~2min en DB remota lenta
  })
  return response.data
}

export const getControlLoopPlanVsReal = async (params = {}) => {
  const response = await api.get('/ops/control-loop/plan-vs-real', { params })
  return response.data
}

export const getControlLoopPlanVersions = async () => {
  const response = await api.get('/ops/control-loop/plan-versions')
  return response.data
}

export const getOmniviewProjection = async (params = {}, { signal } = {}) => {
  const response = await api.get('/ops/business-slice/omniview-projection', { params, signal })
  return response.data
}

export const getOmniviewFreshnessGovernance = async ({ signal } = {}) => {
  const response = await api.get('/ops/omniview/freshness', { signal })
  return response.data
}

/** Refresh Remediation Control: ejecuta recarga day_fact + week_fact + month_fact. */
export const postOmniviewRefresh = async (force = true) => {
  const response = await api.post('/ops/omniview/refresh', null, { params: { force }, timeout: 300000 })
  return response.data
}

/**
 * FASE 1.1 — Ownership Serving Monthly.
 * Devuelve métricas plan vs real agrupadas por Jefe Producto.
 * Params: plan_version_key, country, city, jefe_producto, lob, period, ownership_assignment.
 */
export const getOwnershipServingMonthly = async (params = {}, { signal } = {}) => {
  const response = await api.get('/ops/ownership-serving/monthly', { params, signal })
  return response.data
}

/** Momentum drill series: DoD same-weekday, WoW, MoM. Usado en gráficos de drill de Omniview. */
export const getOmniviewMomentumDrill = async (params = {}) => {
  const response = await api.get('/ops/business-slice/omniview-momentum-drill', { params })
  return response.data
}

/** Behavioral Diagnosis MVP — diagnostico conductual individual (Fase 2A.3). */
export const getBehavioralDiagnosisMvp = async (params = {}) => {
  const response = await api.get('/ops/diagnostics/behavioral/mvp', { params, timeout: 15000 })
  return response.data
}

/** FASE 1G.3E — Plan versions materializadas en serving fact con metadata. */
export const getServingPlanVersions = async ({ signal } = {}) => {
  const response = await api.get('/ops/business-slice/omniview-projection/serving-plan-versions', { timeout: 15000, signal })
  return response.data
}

/** Frescura del REAL agregado (day/week/month facts) que alimenta Omniview semanal/diario. */
export const getBusinessSliceRealFreshness = async ({ signal } = {}) => {
  const response = await api.get('/ops/business-slice/real-freshness', { signal })
  return response.data
}

/**
 * FASE_KPI_CONSISTENCY: auditoría de consistencia KPI por grano (mes/semana/día).
 * Devuelve summary + rows con status: ok | expected_non_comparable | warning | fail.
 * Ejecuta el contrato de `kpi_aggregation_rules.py` (mismo motor que el script CLI).
 *
 * @param {{ month?: string, months?: number, country?: string, city?: string }} opts
 *   month en formato YYYY-MM o YYYY-MM-DD; months = nº de meses hacia atrás.
 */
export const fetchKpiConsistencyAudit = async ({
  month,
  months = 1,
  country,
  city,
} = {}, { signal } = {}) => {
  const params = { months }
  if (month) params.month = month
  if (country) params.country = country
  if (city) params.city = city
  const response = await api.get('/ops/kpi-consistency-audit', { params, signal })
  return response.data
}

/**
 * FASE_KPI_CONSISTENCY: diagnóstico fuerte de ROLLUP_MISMATCH para un mes.
 * Cada celda lleva `suspected_cause` (stale_month_fact, stale_day_fact,
 * duplication_or_mapping, filter_mismatch_vs_resolved, mapping_mismatch_*, negligible).
 *
 * @param {{ month: string, country?: string, city?: string, businessSlice?: string, includeResolved?: boolean }} opts
 */
export const fetchRollupMismatchAudit = async ({
  month,
  country,
  city,
  businessSlice,
  includeResolved = false,
} = {}, { signal } = {}) => {
  const params = { month, include_resolved: includeResolved }
  if (country) params.country = country
  if (city) params.city = city
  if (businessSlice) params.business_slice = businessSlice
  const response = await api.get('/ops/rollup-mismatch-audit', { params, signal })
  return response.data
}

/**
 * FASE_VALIDATION_FIX: reporte de decision readiness por KPI.
 * Devuelve { summary, rows } donde rows tiene decision_status por KPI:
 *   decision_ready | scope_only | formula_only | restricted
 * Es un endpoint estático (no depende de parámetros de filtro).
 */
export const fetchDecisionReadiness = async ({ signal } = {}) => {
  const response = await api.get('/ops/decision-readiness', { signal })
  return response.data
}

/** Auditoría completa de cobertura de mapeo del plan. */
export const getPlanMappingAudit = async (planVersion, { signal } = {}) => {
  const response = await api.get('/plan/mapping-audit', { params: { plan_version: planVersion }, signal })
  return response.data
}

export const getCoreMonthlySummary = async (filters = {}) => {
  const response = await api.get('/core/summary/monthly', { params: filters })
  return response.data
}

export const getPlanMonthlySummary = async (filters = {}) => {
  const response = await api.get('/plan/summary/monthly', { params: filters })
  return response.data
}

export const getRealMonthlySummary = async (filters = {}) => {
  const response = await api.get('/real/summary/monthly', { params: filters })
  return response.data
}

export const getPlanOutOfUniverse = async (filters = {}) => {
  const response = await api.get('/plan/out_of_universe', { params: filters })
  return response.data
}

export const getPlanMissing = async (filters = {}) => {
  const response = await api.get('/plan/missing', { params: filters })
  return response.data
}

export const getOpsUniverse = async () => {
  const response = await api.get('/ops/universe')
  return response.data
}

export const getIngestionStatus = async (datasetName = 'real_monthly_agg') => {
  const response = await api.get('/ingestion/status', { params: { dataset_name: datasetName } })
  return response.data
}

export const getPlanVsRealMonthly = async (filters = {}) => {
  const response = await api.get('/ops/plan-vs-real/monthly', { params: filters })
  return response.data
}

export const getPlanVsRealAlerts = async (filters = {}) => {
  const response = await api.get('/ops/plan-vs-real/alerts', { params: filters })
  return response.data
}

export const getRealMonthlySplit = async (filters = {}) => {
  const response = await api.get('/ops/real/monthly', { params: filters })
  return response.data
}

/** Real mensual desde cadena canónica (hourly-first). Solo para Resumen. Plan vs Real sigue con getRealMonthlySplit (legacy). */
export const getRealMonthlySplitCanonical = async (filters = {}) => {
  const response = await api.get('/ops/real/monthly', { params: { ...filters, source: 'canonical' } })
  return response.data
}

export const getPlanMonthlySplit = async (filters = {}) => {
  const response = await api.get('/ops/plan/monthly', { params: filters })
  return response.data
}

export const getOverlapMonthly = async (filters = {}) => {
  const response = await api.get('/ops/compare/overlap-monthly', { params: filters })
  return response.data
}

export const getPlanVsRealWeekly = async (filters = {}) => {
  const response = await api.get('/phase2b/weekly/plan-vs-real', { params: filters })
  return response.data
}

export const getWeeklyAlerts = async (filters = {}) => {
  const response = await api.get('/phase2b/weekly/alerts', { params: filters })
  return response.data
}

export const createPhase2BAction = async (actionData) => {
  const response = await api.post('/phase2b/actions', actionData)
  return response.data
}

export const getPhase2BActions = async (filters = {}) => {
  const response = await api.get('/phase2b/actions', { params: filters })
  return response.data
}

export const updatePhase2BAction = async (actionId, updateData) => {
  const response = await api.patch(`/phase2b/actions/${actionId}`, updateData)
  return response.data
}

export const getPhase2CScoreboard = async (filters = {}) => {
  const response = await api.get('/phase2c/scoreboard', { params: filters })
  return response.data
}

export const getPhase2CBacklog = async (filters = {}) => {
  const response = await api.get('/phase2c/backlog', { params: filters })
  return response.data
}

export const getPhase2CBreaches = async (filters = {}) => {
  const response = await api.get('/phase2c/breaches', { params: filters })
  return response.data
}

export const runPhase2CSnapshot = async () => {
  const response = await api.post('/phase2c/run-snapshot')
  return response.data
}

// Fase 2C+: Universo & LOB Mapping
export const getLobUniverse = async (filters = {}) => {
  const response = await api.get('/phase2c/lob-universe', { params: filters })
  return response.data
}

export const getUnmatchedTrips = async (filters = {}) => {
  const response = await api.get('/phase2c/lob-universe/unmatched', { params: filters })
  return response.data
}

// REAL LOB Observability (solo real, sin Plan). Timeout 15s para evitar loading infinito.
const REAL_LOB_TIMEOUT_MS = 15000
export const getRealLobMonthly = async (filters = {}) => {
  const response = await api.get('/ops/real-lob/monthly', { params: filters, timeout: REAL_LOB_TIMEOUT_MS })
  return response.data
}

export const getRealLobWeekly = async (filters = {}) => {
  const response = await api.get('/ops/real-lob/weekly', { params: filters, timeout: REAL_LOB_TIMEOUT_MS })
  return response.data
}

/** Solo en dev: max_month, max_week, count_month, count_week */
export const getRealLobDebug = async () => {
  const response = await api.get('/ops/real-lob/debug')
  return response.data
}

// Real LOB v2: country, city, park_id, lob_group, real_tipo_servicio, segment_tag (B2B/B2C)
export const getRealLobMonthlyV2 = async (filters = {}) => {
  const response = await api.get('/ops/real-lob/monthly-v2', { params: filters, timeout: REAL_LOB_TIMEOUT_MS })
  return response.data
}

export const getRealLobWeeklyV2 = async (filters = {}) => {
  const response = await api.get('/ops/real-lob/weekly-v2', { params: filters, timeout: REAL_LOB_TIMEOUT_MS })
  return response.data
}

// Real LOB v2: opciones para dropdowns (countries, cities, parks, lob_groups, tipo_servicio, segments, years)
export const getRealLobFilters = async (params = {}) => {
  const response = await api.get('/ops/real-lob/filters', { params, timeout: 10000 })
  return response.data
}

// Real LOB v2: datos con consolidación (agg_level) y totales
const REAL_LOB_DATA_TIMEOUT_MS = 20000
export const getRealLobV2Data = async (params = {}) => {
  const response = await api.get('/ops/real-lob/v2/data', { params, timeout: REAL_LOB_DATA_TIMEOUT_MS })
  return response.data
}

// Debe ser ≤ vite.config proxy timeout. Margen + weekly pueden pasar de 6 min (logs ~361s una sola query).
const LONG_HTTP_TIMEOUT_MS = 900000

// Real LOB Drill PRO y rutas igual de pesadas.
const REAL_DRILL_TIMEOUT_MS = LONG_HTTP_TIMEOUT_MS

// Business Slice weekly/daily/coverage: vistas resueltas pesadas.
const BUSINESS_SLICE_HEAVY_TIMEOUT_MS = LONG_HTTP_TIMEOUT_MS

// GET /ops/real-margin-quality: 2 consultas secuenciales sobre v_real_trip_fact_v2.
const REAL_MARGIN_QUALITY_CLIENT_TIMEOUT_MS = LONG_HTTP_TIMEOUT_MS

// Banner / shell: BD lenta pero sin full scan de hechos; más que 8s, menos que rutas “drill”.
const OPS_SHELL_TIMEOUT_MS = 120000
export const getRealLobDrillPro = async (params = {}) => {
  const { signal, ...queryParams } = params
  const config = { params: queryParams, timeout: REAL_DRILL_TIMEOUT_MS }
  if (signal) config.signal = signal
  const response = await api.get('/ops/real-lob/drill', config)
  return response.data
}
export const getRealLobDrillProChildren = async (params = {}) => {
  const { signal, ...queryParams } = params
  const config = { params: queryParams, timeout: REAL_DRILL_TIMEOUT_MS }
  if (signal) config.signal = signal
  const response = await api.get('/ops/real-lob/drill/children', config)
  return response.data
}

/** Parks para el filtro Park del drill. Fuente: misma que el drill (real_drill_dim_fact). Poblado siempre, independiente del desglose. */
export const getRealLobDrillParks = async (params = {}) => {
  const response = await api.get('/ops/real-lob/drill/parks', { params, timeout: 15000 })
  return response.data
}

// Period semantics: last_closed_week/month, current_open_week/month, labels para UI
export const getPeriodSemantics = async (params = {}) => {
  const response = await api.get('/ops/period-semantics', { params, timeout: 10000 })
  return response.data
}

// Comparativos oficiales WoW (semanas cerradas) y MoM (meses cerrados)
export const getRealLobComparativesWeekly = async (params = {}) => {
  const response = await api.get('/ops/real-lob/comparatives/weekly', { params, timeout: 15000 })
  return response.data
}
export const getRealLobComparativesMonthly = async (params = {}) => {
  const response = await api.get('/ops/real-lob/comparatives/monthly', { params, timeout: 15000 })
  return response.data
}

// Vista diaria Real LOB: summary, comparative (D-1 / same weekday / avg 4w), table
export const getRealLobDailySummary = async (params = {}) => {
  const response = await api.get('/ops/real-lob/daily/summary', { params, timeout: 15000 })
  return response.data
}
export const getRealLobDailyComparative = async (params = {}) => {
  const response = await api.get('/ops/real-lob/daily/comparative', { params, timeout: 15000 })
  return response.data
}
export const getRealLobDailyTable = async (params = {}) => {
  const response = await api.get('/ops/real-lob/daily/table', { params, timeout: 15000 })
  return response.data
}

// Real Operational (hourly-first): snapshot, day view, hourly view, cancellations, comparatives
const REAL_OPERATIONAL_TIMEOUT_MS = 30000
export const getRealOperationalSnapshot = async (params = {}) => {
  const response = await api.get('/ops/real-operational/snapshot', { params, timeout: REAL_OPERATIONAL_TIMEOUT_MS })
  return response.data
}
export const getRealOperationalDayView = async (params = {}) => {
  const response = await api.get('/ops/real-operational/day-view', { params, timeout: REAL_OPERATIONAL_TIMEOUT_MS })
  return response.data
}
export const getRealOperationalHourlyView = async (params = {}) => {
  const response = await api.get('/ops/real-operational/hourly-view', { params, timeout: REAL_OPERATIONAL_TIMEOUT_MS })
  return response.data
}
export const getRealOperationalCancellations = async (params = {}) => {
  const response = await api.get('/ops/real-operational/cancellations', { params, timeout: REAL_OPERATIONAL_TIMEOUT_MS })
  return response.data
}
export const getRealOperationalTodayVsYesterday = async (params = {}) => {
  const response = await api.get('/ops/real-operational/comparatives/today-vs-yesterday', { params, timeout: 15000 })
  return response.data
}
export const getRealOperationalTodayVsSameWeekday = async (params = {}) => {
  const response = await api.get('/ops/real-operational/comparatives/today-vs-same-weekday', { params, timeout: 15000 })
  return response.data
}
export const getRealOperationalCurrentHourVsHistorical = async (params = {}) => {
  const response = await api.get('/ops/real-operational/comparatives/current-hour-vs-historical', { params, timeout: 15000 })
  return response.data
}
export const getRealOperationalThisWeekVsComparable = async (params = {}) => {
  const response = await api.get('/ops/real-operational/comparatives/this-week-vs-comparable', { params, timeout: 15000 })
  return response.data
}

// Real LOB Drill-down: timeline por país, drill LOB/Park [legacy]
export const getRealDrillSummary = async (params = {}) => {
  const response = await api.get('/ops/real-drill/summary', { params, timeout: REAL_DRILL_TIMEOUT_MS })
  return response.data
}
export const getRealDrillByLob = async (params = {}) => {
  const response = await api.get('/ops/real-drill/by-lob', { params, timeout: REAL_DRILL_TIMEOUT_MS })
  return response.data
}
export const getRealDrillByPark = async (params = {}) => {
  const response = await api.get('/ops/real-drill/by-park', { params, timeout: REAL_DRILL_TIMEOUT_MS })
  return response.data
}
export const getRealDrillTotals = async (params = {}) => {
  const response = await api.get('/ops/real-drill/totals', { params, timeout: REAL_DRILL_TIMEOUT_MS })
  return response.data
}
export const getRealDrillCoverage = async () => {
  const response = await api.get('/ops/real-drill/coverage', { timeout: REAL_DRILL_TIMEOUT_MS })
  return response.data
}

// Real LOB Strategy (modo Ejecutivo): KPIs, forecast, rankings
const REAL_STRATEGY_TIMEOUT_MS = 20000
export const getRealStrategyCountry = async (params = {}) => {
  const response = await api.get('/ops/real-strategy/country', { params, timeout: REAL_STRATEGY_TIMEOUT_MS })
  return response.data
}
export const getRealStrategyLob = async (params = {}) => {
  const response = await api.get('/ops/real-strategy/lob', { params, timeout: REAL_STRATEGY_TIMEOUT_MS })
  return response.data
}
export const getRealStrategyCities = async (params = {}) => {
  const response = await api.get('/ops/real-strategy/cities', { params, timeout: REAL_STRATEGY_TIMEOUT_MS })
  return response.data
}

// Ops parks (dropdown: park_id + park_name, mismo criterio que Real LOB)
export const getOpsParks = async (params = {}) => {
  const response = await api.get('/ops/parks', { params, timeout: 10000 })
  return response.data
}

// Driver Lifecycle (drilldown por park)
const DRIVER_LIFECYCLE_TIMEOUT_MS = 30000
export const getDriverLifecycleWeekly = async (params = {}) => {
  const response = await api.get('/ops/driver-lifecycle/weekly', { params, timeout: DRIVER_LIFECYCLE_TIMEOUT_MS })
  return response.data
}
export const getDriverLifecycleMonthly = async (params = {}) => {
  const response = await api.get('/ops/driver-lifecycle/monthly', { params, timeout: DRIVER_LIFECYCLE_TIMEOUT_MS })
  return response.data
}
export const getDriverLifecycleSeries = async (params = {}) => {
  const response = await api.get('/ops/driver-lifecycle/series', { params, timeout: DRIVER_LIFECYCLE_TIMEOUT_MS })
  return response.data
}
export const getDriverLifecycleSummary = async (params = {}) => {
  const response = await api.get('/ops/driver-lifecycle/summary', { params, timeout: DRIVER_LIFECYCLE_TIMEOUT_MS })
  return response.data
}
export const getDriverLifecycleDrilldown = async (params = {}) => {
  const response = await api.get('/ops/driver-lifecycle/drilldown', { params, timeout: DRIVER_LIFECYCLE_TIMEOUT_MS })
  return response.data
}
export const getDriverLifecycleParksSummary = async (params = {}) => {
  const response = await api.get('/ops/driver-lifecycle/parks-summary', { params, timeout: DRIVER_LIFECYCLE_TIMEOUT_MS })
  return response.data
}
export const getDriverLifecycleParksList = async () => {
  const response = await api.get('/ops/driver-lifecycle/parks', { timeout: 10000 })
  return response.data
}
export const getDriverLifecycleBaseMetrics = async (params = {}) => {
  const response = await api.get('/ops/driver-lifecycle/base-metrics', { params, timeout: DRIVER_LIFECYCLE_TIMEOUT_MS })
  return response.data
}
export const getDriverLifecycleBaseMetricsDrilldown = async (params = {}) => {
  const response = await api.get('/ops/driver-lifecycle/base-metrics-drilldown', { params, timeout: DRIVER_LIFECYCLE_TIMEOUT_MS })
  return response.data
}
export const getDriverLifecycleCohorts = async (params = {}) => {
  const response = await api.get('/ops/driver-lifecycle/cohorts', { params, timeout: DRIVER_LIFECYCLE_TIMEOUT_MS })
  return response.data
}
export const getDriverLifecycleCohortDrilldown = async (params = {}) => {
  const response = await api.get('/ops/driver-lifecycle/cohort-drilldown', { params, timeout: DRIVER_LIFECYCLE_TIMEOUT_MS })
  return response.data
}

// Driver Lifecycle Diagnostic — Fase 2A.1 (deterministic lifecycle + risk)
export const getDriverLifecycleDiagnosticSummary = async (params = {}) => {
  const response = await api.get('/driver-lifecycle/summary', { params, timeout: 60000 })
  return response.data
}
export const getDriverLifecycleDiagnosticFunnel = async (params = {}) => {
  const response = await api.get('/driver-lifecycle/funnel', { params, timeout: 60000 })
  return response.data
}
export const getDriverLifecycleDiagnosticRiskList = async (params = {}) => {
  const response = await api.get('/driver-lifecycle/risk-list', { params, timeout: 60000 })
  return response.data
}
export const getDriverLifecycleDiagnosticCohortsBasic = async (params = {}) => {
  const response = await api.get('/driver-lifecycle/cohorts-basic', { params, timeout: 60000 })
  return response.data
}

// Driver Behavior Benchmarking — Fase 2A.2
export const getDriverBehaviorBenchmarkSummary = async (params = {}) => {
  const response = await api.get('/driver-behavior/summary', { params, timeout: 60000 })
  return response.data
}
export const getDriverBehaviorGroupBenchmarks = async (params = {}) => {
  const response = await api.get('/driver-behavior/group-benchmarks', { params, timeout: 60000 })
  return response.data
}
export const getDriverBehaviorTopVsRisk = async (params = {}) => {
  const response = await api.get('/driver-behavior/top-vs-risk', { params, timeout: 60000 })
  return response.data
}
export const getDriverBehaviorDistributions = async (params = {}) => {
  const response = await api.get('/driver-behavior/distributions', { params, timeout: 60000 })
  return response.data
}

// Driver Supply Dynamics — radar: geo, overview, composition, migration, alerts, drilldown
export const getSupplyGeo = async (params = {}) => {
  const response = await api.get('/ops/supply/geo', { params, timeout: 10000 })
  return response.data
}
export const getSupplyParks = async (params = {}) => {
  const response = await api.get('/ops/supply/parks', { params, timeout: 10000 })
  return response.data
}
export const getSupplySeries = async (params = {}) => {
  const response = await api.get('/ops/supply/series', { params, timeout: 30000 })
  return response.data
}
export const getSupplySummary = async (params = {}) => {
  const response = await api.get('/ops/supply/summary', { params, timeout: 15000 })
  return response.data
}
export const getSupplySegmentsSeries = async (params = {}) => {
  const response = await api.get('/ops/supply/segments/series', { params, timeout: 20000 })
  return response.data
}
export const getSupplyGlobalSeries = async (params = {}) => {
  const response = await api.get('/ops/supply/global/series', { params, timeout: 30000 })
  return response.data
}

export const getSupplyAlerts = async (params = {}) => {
  const response = await api.get('/ops/supply/alerts', { params, timeout: 15000 })
  return response.data
}
export const getSupplyAlertDrilldown = async (params = {}) => {
  const response = await api.get('/ops/supply/alerts/drilldown', { params, timeout: 15000 })
  return response.data
}
export const refreshSupplyAlerting = async () => {
  const response = await api.post('/ops/supply/refresh', {}, { timeout: 600000 })
  return response.data
}

// Driver Supply Dynamics — configuración de segmentos (ops.driver_segment_config)
export const getSupplySegmentConfig = async () => {
  const response = await api.get('/ops/supply/segments/config', { timeout: 5000 })
  return response.data?.data ?? []
}

// Driver Supply Dynamics — definiciones oficiales de métricas (tooltips, glosario)
export const getSupplyDefinitions = async () => {
  const response = await api.get('/ops/supply/definitions', { timeout: 5000 })
  return response.data
}

// SH3.5 — Fact-based endpoints (lean, no runtime)
export const getSupplyOverviewFact = async (params = {}) => {
  const response = await api.get('/drivers/supply-overview-fact', { params, timeout: 25000 })
  return response.data
}
export const getSegmentCompositionFact = async (params = {}) => {
  const response = await api.get('/drivers/segment-composition-fact', { params, timeout: 25000 })
  return response.data
}
export const getGeoOptions = async () => {
  const response = await api.get('/drivers/geo-options', { timeout: 20000 })
  return response.data
}
export const getServingFreshness = async (params = {}) => {
  const response = await api.get('/drivers/serving-freshness', { params, timeout: 10000 })
  return response.data
}
export const getSegmentMigrationFact = async (params = {}) => {
  const response = await api.get('/drivers/segment-migration', { params, timeout: 20000 })
  return response.data
}

// Driver Supply Dynamics — freshness (última semana, último refresh, estado)
export const getSupplyFreshness = async () => {
  const response = await api.get('/ops/supply/freshness', { timeout: 5000 })
  return response.data
}

// Freshness global (banner). group=operational para pestaña Real (no falla por datasets legacy).
export const getDataFreshnessGlobal = async (params = {}, { signal } = {}) => {
  const response = await api.get('/ops/data-freshness/global', { params: { group: params.group }, timeout: OPS_SHELL_TIMEOUT_MS, signal })
  return response.data
}

// Centro de observabilidad del pipeline: por dataset source_max_date, derived_max_date, lag_days, status
export const getDataPipelineHealth = async (latestOnly = true) => {
  const response = await api.get('/ops/data-pipeline-health', { params: { latest_only: latestOnly }, timeout: OPS_SHELL_TIMEOUT_MS })
  return response.data
}

// Calidad de margen en fuente REAL (ruta estable: /ops/real-margin-quality; /ops/real/margin-quality puede 404 en algunos despliegues)
export const getRealMarginQuality = async (params = {}) => {
  const response = await api.get('/ops/real-margin-quality', {
    params: { days_recent: params.days_recent ?? 90, findings_limit: params.findings_limit ?? 20 },
    timeout: REAL_MARGIN_QUALITY_CLIENT_TIMEOUT_MS,
  })
  return response.data
}

// Reporte de integridad (checks: TRIP LOSS, B2B, LOB MAPPING, DUPLICATES, MV STALE, JOIN LOSS, WEEKLY ANOMALY)
export const getIntegrityReport = async () => {
  const response = await api.get('/ops/integrity-report', { timeout: 15000 })
  return response.data
}

// System Health: integridad, freshness MVs, ingestión, última auditoría (dashboard observabilidad)
export const getSystemHealth = async () => {
  const response = await api.get('/ops/system-health', { timeout: 15000 })
  return response.data
}

// Ejecutar auditoría de integridad (persiste en ops.data_integrity_audit)
export const runIntegrityAudit = async () => {
  const response = await api.post('/ops/integrity-audit/run', {}, { timeout: 130000 })
  return response.data
}

// Fase 1 — Observabilidad E2E
export const getObservabilityOverview = async () => {
  const response = await api.get('/ops/observability/overview', { timeout: 10000 })
  return response.data
}
export const getObservabilityModules = async () => {
  const response = await api.get('/ops/observability/modules', { timeout: 10000 })
  return response.data
}
export const getObservabilityArtifacts = async () => {
  const response = await api.get('/ops/observability/artifacts', { timeout: 10000 })
  return response.data
}
export const getObservabilityLineage = async () => {
  const response = await api.get('/ops/observability/lineage', { timeout: 10000 })
  return response.data
}
export const getObservabilityFreshness = async () => {
  const response = await api.get('/ops/observability/freshness', { timeout: 10000 })
  return response.data
}

// Gobierno: estado de fuente REAL por pantalla (canonical | legacy | migrating)
export const getRealSourceStatus = async () => {
  const response = await api.get('/ops/real-source-status', { timeout: OPS_SHELL_TIMEOUT_MS })
  return response.data
}

// Data Trust Layer: estado de confianza por vista (ok | warning | blocked)
export const getDataTrustStatus = async (view) => {
  const response = await api.get('/ops/data-trust', { params: { view }, timeout: OPS_SHELL_TIMEOUT_MS })
  return response.data?.data_trust || { status: 'warning', message: 'Estado de data no disponible', last_update: null }
}

// Decision Layer: señal operativa por vista (action, priority, message, reason)
export const getDecisionSignal = async (view) => {
  const response = await api.get('/ops/decision-signal', { params: { view }, timeout: OPS_SHELL_TIMEOUT_MS })
  return response.data
}

// Resumen de decisiones por vista (view, action, priority)
export const getDecisionSignalSummary = async () => {
  const response = await api.get('/ops/decision-signal/summary', { timeout: OPS_SHELL_TIMEOUT_MS })
  return Array.isArray(response.data) ? response.data : []
}

// Driver Supply Dynamics — overview enriquecido (trips, shares, WoW, rolling, trend)
export const getSupplyOverviewEnhanced = async (params = {}) => {
  const response = await api.get('/ops/supply/overview-enhanced', { params, timeout: 20000 })
  return response.data
}

// Composición semanal por segmento con WoW
export const getSupplyComposition = async (params = {}) => {
  const response = await api.get('/ops/supply/composition', { params, timeout: 20000 })
  return response.data
}

// Migración entre segmentos (incluye summary: upgrades, downgrades, drops, revivals)
export const getSupplyMigration = async (params = {}) => {
  const response = await api.get('/ops/supply/migration', { params, timeout: 20000 })
  const data = response.data
  return { data: data?.data ?? data, summary: data?.summary ?? null }
}

// Drilldown de migración (drivers por semana y from/to segment)
export const getSupplyMigrationDrilldown = async (params = {}) => {
  const response = await api.get('/ops/supply/migration/drilldown', { params, timeout: 15000 })
  return response.data
}

// Time-first: resumen semanal por segmento (WoW, upgrades, downgrades)
export const getSupplyMigrationWeeklySummary = async (params = {}) => {
  const response = await api.get('/ops/supply/migration/weekly-summary', { params, timeout: 15000 })
  return response.data?.data ?? response.data ?? []
}

// Time-first: movimientos críticos (drivers > 100 o rate > 15%)
export const getSupplyMigrationCritical = async (params = {}) => {
  const response = await api.get('/ops/supply/migration/critical', { params, timeout: 15000 })
  return response.data?.data ?? response.data ?? []
}

// Behavioral Alerts (desviación vs línea base del conductor)
const BEHAVIOR_ALERTS_TIMEOUT_MS = 30000
export const getBehaviorAlertsSummary = async (params = {}) => {
  const response = await api.get('/ops/behavior-alerts/summary', { params, timeout: BEHAVIOR_ALERTS_TIMEOUT_MS })
  return response.data
}
export const getBehaviorAlertsInsight = async (params = {}) => {
  const response = await api.get('/ops/behavior-alerts/insight', { params, timeout: BEHAVIOR_ALERTS_TIMEOUT_MS })
  return response.data
}
export const getBehaviorAlertsDrivers = async (params = {}) => {
  const response = await api.get('/ops/behavior-alerts/drivers', { params, timeout: BEHAVIOR_ALERTS_TIMEOUT_MS })
  return response.data
}
export const getBehaviorAlertsDriverDetail = async (params = {}) => {
  const response = await api.get('/ops/behavior-alerts/driver-detail', { params, timeout: BEHAVIOR_ALERTS_TIMEOUT_MS })
  return response.data
}
export const getBehaviorAlertsExportUrl = (params = {}) => {
  const q = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v != null && v !== '') q.set(k, v) })
  const base = import.meta.env.DEV ? '/api' : (import.meta.env.VITE_API_URL || '/api')
  return `${base}/ops/behavior-alerts/export?${q.toString()}`
}

// --- Fleet Leakage Monitor MVP ---
const LEAKAGE_TIMEOUT_MS = 30000
export const getLeakageSummary = async (params = {}) => {
  const response = await api.get('/ops/leakage/summary', { params, timeout: LEAKAGE_TIMEOUT_MS })
  return response.data
}
export const getLeakageDrivers = async (params = {}) => {
  const response = await api.get('/ops/leakage/drivers', { params, timeout: LEAKAGE_TIMEOUT_MS })
  return response.data
}
export const getLeakageExportUrl = (params = {}) => {
  const q = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v != null && v !== '') q.set(k, v) })
  const base = import.meta.env.DEV ? '/api' : (import.meta.env.VITE_API_URL || '/api')
  return `${base}/ops/leakage/export?${q.toString()}`
}

// --- Driver Behavior (deviation engine: time windows, days_since_last_trip) ---
export const getDriverBehaviorSummary = async (params = {}) => {
  const response = await api.get('/ops/driver-behavior/summary', { params })
  return response.data
}
export const getDriverBehaviorDrivers = async (params = {}) => {
  const response = await api.get('/ops/driver-behavior/drivers', { params })
  return response.data
}
export const getDriverBehaviorDriverDetail = async (params = {}) => {
  const response = await api.get('/ops/driver-behavior/driver-detail', { params })
  return response.data
}
export const getDriverBehaviorExportUrl = (params = {}) => {
  const q = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v != null && v !== '') q.set(k, v) })
  const base = import.meta.env.DEV ? '/api' : (import.meta.env.VITE_API_URL || '/api')
  return `${base}/ops/driver-behavior/export?${q.toString()}`
}

// --- Action Engine (cohorts + recommended actions) ---
export const getActionEngineSummary = async (params = {}) => {
  const response = await api.get('/ops/action-engine/summary', { params })
  return response.data
}
export const getActionEngineCohorts = async (params = {}) => {
  const response = await api.get('/ops/action-engine/cohorts', { params })
  return response.data
}
export const getActionEngineCohortDetail = async (params = {}) => {
  const response = await api.get('/ops/action-engine/cohort-detail', { params })
  return response.data
}
export const getActionEngineRecommendations = async (params = {}) => {
  const response = await api.get('/ops/action-engine/recommendations', { params })
  return response.data
}
export const getActionEngineExportUrl = (params = {}) => {
  const q = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v != null && v !== '') q.set(k, v) })
  const base = import.meta.env.DEV ? '/api' : (import.meta.env.VITE_API_URL || '/api')
  return `${base}/ops/action-engine/export?${q.toString()}`
}

// --- Top Driver Behavior ---
export const getTopDriverBehaviorSummary = async (params = {}) => {
  const response = await api.get('/ops/top-driver-behavior/summary', { params })
  return response.data
}
export const getTopDriverBehaviorBenchmarks = async (params = {}) => {
  const response = await api.get('/ops/top-driver-behavior/benchmarks', { params })
  return response.data
}
export const getTopDriverBehaviorPatterns = async (params = {}) => {
  const response = await api.get('/ops/top-driver-behavior/patterns', { params })
  return response.data
}
export const getTopDriverBehaviorPlaybookInsights = async (params = {}) => {
  const response = await api.get('/ops/top-driver-behavior/playbook-insights', { params })
  return response.data
}
export const getTopDriverBehaviorExportUrl = (params = {}) => {
  const q = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v != null && v !== '') q.set(k, v) })
  const base = import.meta.env.DEV ? '/api' : (import.meta.env.VITE_API_URL || '/api')
  return `${base}/ops/top-driver-behavior/export?${q.toString()}`
}

// --- Business Slice (REAL, capa ejecutiva) ---
export const getBusinessSliceFilters = async ({ signal } = {}) => {
  const response = await api.get('/ops/business-slice/filters', { timeout: OPS_SHELL_TIMEOUT_MS, signal })
  return response.data
}
export const getBusinessSliceMonthly = async (params = {}, { signal } = {}) => {
  // Misma ventana que weekly/daily: año completo + unmapped + meta State Engine puede superar 2 min (BD remota/lenta).
  const response = await api.get('/ops/business-slice/monthly', { params, timeout: BUSINESS_SLICE_HEAVY_TIMEOUT_MS, signal })
  return response.data
}
export const getBusinessSliceCoverage = async (params = {}, { signal } = {}) => {
  const response = await api.get('/ops/business-slice/coverage', { params, timeout: BUSINESS_SLICE_HEAVY_TIMEOUT_MS, signal })
  return response.data
}
export const getBusinessSliceCoverageSummary = async (params = {}, { signal } = {}) => {
  const response = await api.get('/ops/business-slice/coverage-summary', { params, timeout: BUSINESS_SLICE_HEAVY_TIMEOUT_MS, signal })
  return response.data
}
export const getBusinessSliceUnmatched = async (params = {}, { signal } = {}) => {
  const response = await api.get('/ops/business-slice/unmatched', { params, signal })
  return response.data
}
export const getBusinessSliceConflicts = async (params = {}, { signal } = {}) => {
  const response = await api.get('/ops/business-slice/conflicts', { params, signal })
  return response.data
}
export const getBusinessSliceSubfleets = async ({ signal } = {}) => {
  const response = await api.get('/ops/business-slice/subfleets', { signal })
  return response.data
}
export const getBusinessSliceWeekly = async (params = {}, { signal } = {}) => {
  const response = await api.get('/ops/business-slice/weekly', { params, timeout: BUSINESS_SLICE_HEAVY_TIMEOUT_MS, signal })
  return response.data
}
export const getBusinessSliceDaily = async (params = {}, { signal } = {}) => {
  const response = await api.get('/ops/business-slice/daily', { params, timeout: BUSINESS_SLICE_HEAVY_TIMEOUT_MS, signal })
  return response.data
}
/** Omniview: unifica monthly / weekly / daily según `grain` (no se envía al backend). */
export const getBusinessSliceOmniview = async (params = {}, opts = {}) => {
  const { grain = 'monthly', ...rest } = params
  if (grain === 'weekly') {
    return getBusinessSliceWeekly(rest, opts)
  }
  if (grain === 'daily') {
    return getBusinessSliceDaily(rest, opts)
  }
  return getBusinessSliceMonthly(rest, opts)
}

/** Estado de materialización de las 3 FACT tables (qué meses están cargados). */
export const getFactStatus = async ({ signal } = {}) => {
  const response = await api.get('/ops/business-slice/fact-status', { timeout: 10000, signal })
  return response.data
}

/** Progreso en tiempo real del backfill activo (chunk a chunk). */
export const getBackfillProgress = async ({ signal } = {}) => {
  const response = await api.get('/ops/business-slice/backfill-progress', { timeout: 5000, signal })
  return response.data
}

/** Dispara un backfill. from_date/to_date en formato "YYYY-MM". */
export const startBackfill = async ({ from_date, to_date, with_week = true }) => {
  const response = await api.post('/ops/business-slice/backfill', { from_date, to_date, with_week }, { timeout: 10000 })
  return response.data
}

/** Cancela el backfill en curso. */
export const cancelBackfill = async () => {
  const response = await api.post('/ops/business-slice/backfill-cancel', {}, { timeout: 5000 })
  return response.data
}

/** Trust operativo Matrix (integridad: gaps, freshness, rollup, revenue). */
export const getMatrixOperationalTrust = async ({ signal } = {}) => {
  const response = await api.get('/ops/business-slice/matrix-operational-trust', { timeout: BUSINESS_SLICE_HEAVY_TIMEOUT_MS, signal })
  return response.data
}

export const logMatrixIssueAction = async (payload) => {
  const response = await api.post('/ops/business-slice/matrix-issue-action', payload, {
    timeout: BUSINESS_SLICE_HEAVY_TIMEOUT_MS,
  })
  return response.data
}

// --- Behavioral Pattern Diagnosis (Fase 2A.3) ---
export const getBehavioralPatternsSummary = async (params = {}) => {
  const response = await api.get('/behavioral-patterns/summary', { params, timeout: 60000 })
  return response.data
}
export const getBehavioralPatterns = async (params = {}) => {
  const response = await api.get('/behavioral-patterns/patterns', { params, timeout: 60000 })
  return response.data
}
export const getBehavioralGroupProfile = async (params = {}) => {
  const response = await api.get('/behavioral-patterns/group-profile', { params, timeout: 60000 })
  return response.data
}
export const getBehavioralDeclineSignals = async (params = {}) => {
  const response = await api.get('/behavioral-patterns/decline-signals', { params, timeout: 60000 })
  return response.data
}

// Fase 2C.1 — Recoverability Intelligence (Shadow Mode)
export const getRecoverabilitySummary = async (params = {}) => {
  const response = await api.get('/recoverability/summary', { params, timeout: 60000 })
  return response.data
}
export const getRecoverabilityTop = async (params = {}) => {
  const response = await api.get('/recoverability/top-recoverable', { params, timeout: 60000 })
  return response.data
}
export const getRecoverabilityDistribution = async (params = {}) => {
  const response = await api.get('/recoverability/distribution', { params, timeout: 60000 })
  return response.data
}
export const getDriverRecoverability = async (driverId, params = {}) => {
  const response = await api.get(`/recoverability/driver/${driverId}`, { params, timeout: 60000 })
  return response.data
}
export const getRecoverabilityShadowPriority = async (params = {}) => {
  const response = await api.get('/recoverability/shadow-priority', { params, timeout: 60000 })
  return response.data
}
export const getRecoverabilitySegments = async (params = {}) => {
  const response = await api.get('/recoverability/segments', { params, timeout: 60000 })
  return response.data
}
export const getRecoverabilityExplainability = async (driverId, params = {}) => {
  const response = await api.get(`/recoverability/explainability/${driverId}`, { params, timeout: 60000 })
  return response.data
}
export const getRecoverabilityRiskDistribution = async (params = {}) => {
  const response = await api.get('/recoverability/risk-distribution', { params, timeout: 60000 })
  return response.data
}

// --- Yango Loyalty / Oro Tracker ---
export const getYangoLoyaltySummary = async () => {
  const response = await api.get('/yango-loyalty/summary', { timeout: 60000 })
  return response.data
}
export const getYangoLoyaltyKpis = async (params = {}) => {
  const response = await api.get('/yango-loyalty/kpis', { params, timeout: 60000 })
  return response.data
}
export const postYangoLoyaltyManualKpi = async (payload) => {
  const response = await api.post('/yango-loyalty/manual-kpi', payload)
  return response.data
}
export const postYangoLoyaltyTarget = async (payload) => {
  const response = await api.post('/yango-loyalty/target', payload)
  return response.data
}
export const getYangoLoyaltyPerformance = async (params = {}) => {
  const response = await api.get('/yango-loyalty/performance', { params, timeout: 15000 })
  return response.data
}
export const getYangoLoyaltyHistory = async (params = {}) => {
  const response = await api.get('/yango-loyalty/history', { params, timeout: 30000 })
  return response.data
}
export const getYangoLoyaltyCityComparison = async (params = {}) => {
  const response = await api.get('/yango-loyalty/city-comparison', { params, timeout: 30000 })
  return response.data
}

// --- Fleet Project > Yego Pro > Profitability (P2) ---
const PROFITABILITY_TIMEOUT_MS = 60000
export const getYegoProProfitabilityOverview = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/overview', { params, timeout: PROFITABILITY_TIMEOUT_MS })
  return response.data
}
export const getYegoProProfitabilityWeekly = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/weekly', { params, timeout: PROFITABILITY_TIMEOUT_MS })
  return response.data
}
export const getYegoProProfitabilityDaily = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/daily', { params, timeout: PROFITABILITY_TIMEOUT_MS })
  return response.data
}
export const getYegoProProfitabilityDrivers = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/drivers', { params, timeout: PROFITABILITY_TIMEOUT_MS })
  return response.data
}
export const getYegoProProfitabilityVehicles = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/vehicles', { params, timeout: PROFITABILITY_TIMEOUT_MS })
  return response.data
}
export const getYegoProProfitabilityShifts = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/shifts', { params, timeout: PROFITABILITY_TIMEOUT_MS })
  return response.data
}
export const getYegoProProfitabilityInputMapping = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/input-mapping', { params, timeout: PROFITABILITY_TIMEOUT_MS })
  return response.data
}
export const getYegoProProfitabilityQuality = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/quality', { params, timeout: PROFITABILITY_TIMEOUT_MS })
  return response.data
}
export const getYegoProProfitabilityRootCause = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/root-cause', { params, timeout: PROFITABILITY_TIMEOUT_MS })
  return response.data
}
export const getYegoProDiagnosticsDrivers = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/diagnostics/drivers', { params, timeout: PROFITABILITY_TIMEOUT_MS })
  return response.data
}
export const getYegoProDiagnosticsVehicles = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/diagnostics/vehicles', { params, timeout: PROFITABILITY_TIMEOUT_MS })
  return response.data
}
export const getYegoProDiagnosticsShifts = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/diagnostics/shifts', { params, timeout: PROFITABILITY_TIMEOUT_MS })
  return response.data
}
export const getYegoProDiagnosticsPortfolio = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/diagnostics/portfolio', { params, timeout: PROFITABILITY_TIMEOUT_MS })
  return response.data
}

export const runYegoProSimulator = async (payload) => {
  const response = await api.post('/fleet-project/yego-pro/profitability/simulator/run', payload, { timeout: PROFITABILITY_TIMEOUT_MS })
  return response.data
}

export const getYegoProSimulatorDefaults = async () => {
  const response = await api.get('/fleet-project/yego-pro/profitability/simulator/defaults', { timeout: 15000 })
  return response.data
}

export const getYegoProBonusConfig = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/simulator/bonus-config', { params, timeout: 15000 })
  return response.data
}

export const saveYegoProBonusConfig = async (payload) => {
  const response = await api.post('/fleet-project/yego-pro/profitability/simulator/bonus-config', payload, { timeout: 15000 })
  return response.data
}

export const resetYegoProBonusConfig = async (payload = {}) => {
  const response = await api.post('/fleet-project/yego-pro/profitability/simulator/bonus-config/reset', payload, { timeout: 15000 })
  return response.data
}

export const getYegoProBaseline = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/simulator/baseline', { params, timeout: 30000 })
  return response.data
}

export const getYegoProScenarios = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/simulator/scenarios', { params, timeout: 15000 })
  return response.data
}

export const saveYegoProScenario = async (payload) => {
  const response = await api.post('/fleet-project/yego-pro/profitability/simulator/scenarios', payload, { timeout: 15000 })
  return response.data
}

export const updateYegoProScenario = async (id, payload) => {
  const response = await api.patch(`/fleet-project/yego-pro/profitability/simulator/scenarios/${id}`, payload, { timeout: 15000 })
  return response.data
}

export const duplicateYegoProScenario = async (id, payload = {}) => {
  const response = await api.post(`/fleet-project/yego-pro/profitability/simulator/scenarios/${id}/duplicate`, payload, { timeout: 15000 })
  return response.data
}

export const archiveYegoProScenario = async (id) => {
  const response = await api.post(`/fleet-project/yego-pro/profitability/simulator/scenarios/${id}/archive`, {}, { timeout: 15000 })
  return response.data
}

export const getYegoProOperationalBaseline = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/simulator/operational-baseline', { params, timeout: 30000 })
  return response.data
}

export const getYegoProOperationalReferences = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/simulator/operational-references', { params, timeout: 30000 })
  return response.data
}

export const getYegoProKpiExplainability = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/kpi-explainability', { params, timeout: 30000 })
  return response.data
}

export const getYegoProDriverDrill = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/driver-drill', { params, timeout: 30000 })
  return response.data
}

export const getYegoProVehicleDrill = async (params = {}) => {
  const response = await api.get('/fleet-project/yego-pro/profitability/vehicle-drill', { params, timeout: 30000 })
  return response.data
}

// ── Lima Growth ──

export const getLimaGrowthPrioritizedOpportunities = async (params = {}) => {
  const response = await api.get('/yego-lima-growth/policy/prioritized-opportunities', { params, timeout: 30000 })
  return response.data
}

export const getLoopControlConfig = async () => {
  const response = await api.get('/yego-lima-growth/loopcontrol/config', { timeout: 15000 })
  return response.data
}

export const getLoopControlExports = async (params = {}) => {
  const response = await api.get('/yego-lima-growth/loopcontrol/exports', { params, timeout: 15000 })
  return response.data
}

export const getLoopControlExportDetail = async (exportId) => {
  const response = await api.get(`/yego-lima-growth/loopcontrol/exports/${exportId}`, { timeout: 15000 })
  return response.data
}

// ── Lima Growth — Daily Capacity (LG-2.2B) ──

export const getLimaGrowthCapacityConfig = async (date = null) => {
  const params = {}
  if (date) params.date = date
  const response = await api.get('/yego-lima-growth/capacity/config', { params, timeout: 15000 })
  return response.data
}

export const getLimaGrowthCapacitySummary = async (date = null, actionableCount = 0) => {
  const params = { actionable_count: actionableCount }
  if (date) params.date = date
  const response = await api.get('/yego-lima-growth/capacity/summary', { params, timeout: 15000 })
  return response.data
}

export const updateLimaGrowthCapacityConfig = async (payload) => {
  const response = await api.put('/yego-lima-growth/capacity/config', payload, { timeout: 15000 })
  return response.data
}

// ── Lima Growth — Priority Allocation (LG-2.3) ──

export const getLimaGrowthPriorityAllocation = async (date) => {
  const response = await api.get('/yego-lima-growth/priority-allocation', { params: { date }, timeout: 15000 })
  return response.data
}

// ── Lima Growth — Channel Allocation (LG-2.4) ──

export const getLimaGrowthChannelAllocation = async (date) => {
  const response = await api.get('/yego-lima-growth/channel-allocation', { params: { date }, timeout: 15000 })
  return response.data
}

// ── Lima Growth — Opportunity Worklist (LG-2.5A) ──

export const getLimaGrowthOpportunityWorklist = async (params = {}) => {
  const response = await api.get('/yego-lima-growth/opportunity-worklist', { params, timeout: 30000 })
  return response.data
}

// ── Lima Growth — Assignment Queue (LG-2.5B) ──

export const buildLimaGrowthAssignmentQueue = async (date, filters = {}) => {
  const params = { date }
  if (filters.program) params.program = filters.program
  if (filters.channel) params.channel = filters.channel
  if (filters.city) params.city = filters.city
  const response = await api.post('/yego-lima-growth/assignment-queue/build', null, { params, timeout: 60000 })
  return response.data
}

export const getLimaGrowthAssignmentQueue = async (params = {}) => {
  const response = await api.get('/yego-lima-growth/assignment-queue', { params, timeout: 30000 })
  return response.data
}

// ── Lima Growth — Today's Action Plan (LG-UX-R2.6) ──

export const getLimaGrowthTodayActionPlan = async (date) => {
  const response = await api.get('/yego-lima-growth/today-action-plan', { params: { date }, timeout: 30000 })
  return response.data
}

export const getLimaGrowthAllocationTrace = async (date) => {
  const response = await api.get('/yego-lima-growth/capacity/allocation-trace', { params: { date }, timeout: 30000 })
  return response.data
}

export const getLimaGrowthProgramCapacityPolicy = async (date) => {
  const response = await api.get('/yego-lima-growth/program-capacity-policy', { params: { date }, timeout: 30000 })
  return response.data
}

export const simulateLimaGrowthProgramCapacityPolicy = async (date, programs) => {
  const response = await api.post('/yego-lima-growth/program-capacity-policy/simulate', { date, programs }, { timeout: 30000 })
  return response.data
}

// ── Lima Growth — Operational Summary (LG-C1.4-P0) ──

export const getLimaGrowthOperationalSummary = async (date) => {
  const response = await api.get('/yego-lima-growth/operational-summary', { params: { date }, timeout: 30000 })
  return response.data
}

export const getLimaGrowthDriverStateSummary = async (date) => {
  const response = await api.get('/yego-lima-growth/driver-state/summary', { params: { date }, timeout: 30000 })
  return response.data
}

export const getLimaGrowthProgramsSummary = async (date) => {
  const response = await api.get('/yego-lima-growth/programs/summary', { params: { date }, timeout: 60000 })
  return response.data
}

export const getLimaGrowthQueueSummary = async (date) => {
  const response = await api.get('/yego-lima-growth/assignment-queue/summary', { params: { date }, timeout: 30000 })
  return response.data
}

export const exportLimaGrowthAssignmentQueue = async (date, filters = {}) => {
  const params = { date }
  if (filters.program) params.program = filters.program
  if (filters.channel) params.channel = filters.channel
  if (filters.limit) params.limit = filters.limit
  const response = await api.post('/yego-lima-growth/assignment-queue/export', null, { params, timeout: 60000 })
  return response.data
}

// ── Lima Growth — LoopControl Result Sync (LC-2A) ──

export const syncLimaGrowthLoopControlResults = async (payload) => {
  const response = await api.post('/yego-lima-growth/loopcontrol/results/sync', payload, { timeout: 30000 })
  return response.data
}

export const getLimaGrowthLoopControlResultsSummary = async (filters = {}) => {
  const params = {}
  if (filters.date) params.date = filters.date
  if (filters.campaign_id_external) params.campaign_id_external = filters.campaign_id_external
  const response = await api.get('/yego-lima-growth/loopcontrol/results/summary', { params, timeout: 15000 })
  return response.data
}

export const getLimaGrowthLoopControlResults = async (filters = {}) => {
  const params = {}
  if (filters.date) params.date = filters.date
  if (filters.campaign_id_external) params.campaign_id_external = filters.campaign_id_external
  if (filters.status) params.status = filters.status
  if (filters.disposition) params.disposition = filters.disposition
  if (filters.limit) params.limit = filters.limit
  const response = await api.get('/yego-lima-growth/loopcontrol/results', { params, timeout: 15000 })
  return response.data
}

// ── Lima Growth — Executive Risk Panel (LG-2.6) ──

export const getLimaGrowthRiskPanel = async (date) => {
  const response = await api.get('/yego-lima-growth/risk-panel', { params: { date }, timeout: 15000 })
  return response.data
}

// ── Lima Growth — Impact Tracking (IF-1) ──

export const getLimaGrowthImpactSummary = async (filters = {}) => {
  const params = {}
  if (filters.date) params.date = filters.date
  if (filters.campaign_id_external) params.campaign_id_external = filters.campaign_id_external
  const response = await api.get('/yego-lima-growth/impact/summary', { params, timeout: 15000 })
  return response.data
}

export const getLimaGrowthImpactRecords = async (filters = {}) => {
  const params = {}
  if (filters.date) params.date = filters.date
  if (filters.campaign_id_external) params.campaign_id_external = filters.campaign_id_external
  if (filters.impact_status) params.impact_status = filters.impact_status
  if (filters.limit) params.limit = filters.limit
  const response = await api.get('/yego-lima-growth/impact/records', { params, timeout: 15000 })
  return response.data
}

export const rebuildLimaGrowthImpact = async (payload) => {
  const response = await api.post('/yego-lima-growth/impact/rebuild', payload, { timeout: 60000 })
  return response.data
}

// ── Lima Growth — Impact Dashboard (IF-2) ──

export const getLimaGrowthImpactDashboardSummary = async (date) => {
  const params = {}
  if (date) params.date = date
  const response = await api.get('/yego-lima-growth/impact-dashboard/summary', { params, timeout: 15000 })
  return response.data
}

export const getLimaGrowthImpactDashboardPrograms = async (date) => {
  const params = {}
  if (date) params.date = date
  const response = await api.get('/yego-lima-growth/impact-dashboard/programs', { params, timeout: 15000 })
  return response.data
}

export const getLimaGrowthImpactDashboardCampaigns = async (date) => {
  const params = {}
  if (date) params.date = date
  const response = await api.get('/yego-lima-growth/impact-dashboard/campaigns', { params, timeout: 15000 })
  return response.data
}

export const getLimaGrowthImpactDashboardChannels = async (date) => {
  const params = {}
  if (date) params.date = date
  const response = await api.get('/yego-lima-growth/impact-dashboard/channels', { params, timeout: 15000 })
  return response.data
}

// ── Lima Growth — Movement Engine (ME-1) ──

export const rebuildLimaGrowthMovement = async (payload) => {
  const response = await api.post('/yego-lima-growth/movement/rebuild', payload, { timeout: 60000 })
  return response.data
}

export const getLimaGrowthMovementSummary = async (filters = {}) => {
  const params = {}
  if (filters.date) params.date = filters.date
  if (filters.campaign_id_external) params.campaign_id_external = filters.campaign_id_external
  const response = await api.get('/yego-lima-growth/movement/summary', { params, timeout: 15000 })
  return response.data
}

export const getLimaGrowthMovementRecords = async (filters = {}) => {
  const params = {}
  if (filters.date) params.date = filters.date
  if (filters.campaign_id_external) params.campaign_id_external = filters.campaign_id_external
  if (filters.movement_direction) params.movement_direction = filters.movement_direction
  if (filters.limit) params.limit = filters.limit
  const response = await api.get('/yego-lima-growth/movement/records', { params, timeout: 15000 })
  return response.data
}

export const getLimaGrowthMovementTransitions = async (date) => {
  const params = {}
  if (date) params.date = date
  const response = await api.get('/yego-lima-growth/movement/transitions', { params, timeout: 15000 })
  return response.data
}

// ── Lima Growth — Attribution Candidates (AE-1) ──

export const rebuildLimaGrowthAttribution = async (payload) => {
  const response = await api.post('/yego-lima-growth/attribution/rebuild', payload, { timeout: 60000 })
  return response.data
}

export const getLimaGrowthAttributionSummary = async (date) => {
  const params = {}
  if (date) params.date = date
  const response = await api.get('/yego-lima-growth/attribution/summary', { params, timeout: 15000 })
  return response.data
}

export const getLimaGrowthAttributionPrograms = async (date) => {
  const params = {}
  if (date) params.date = date
  const response = await api.get('/yego-lima-growth/attribution/programs', { params, timeout: 15000 })
  return response.data
}

export const getLimaGrowthAttributionCampaigns = async (date) => {
  const params = {}
  if (date) params.date = date
  const response = await api.get('/yego-lima-growth/attribution/campaigns', { params, timeout: 15000 })
  return response.data
}

export const getLimaGrowthAttributionChannels = async (date) => {
  const params = {}
  if (date) params.date = date
  const response = await api.get('/yego-lima-growth/attribution/channels', { params, timeout: 15000 })
  return response.data
}

// ── Lima Growth — Operational Truth (LG-UX-R2.1) ──

export const getLimaGrowthOperationalTruth = async (date) => {
  const params = {}
  if (date) params.date = date
  const response = await api.get('/yego-lima-growth/operational-truth', { params, timeout: 15000 })
  return response.data
}

// ── Lima Growth — Intraday Signals (LG-INFRA-R1.3) ──

export const getLimaGrowthIntradaySignalsSummary = async (date) => {
  const params = {}
  if (date) params.date = date
  const response = await api.get('/yego-lima-growth/intraday-signals/summary', { params, timeout: 15000 })
  return response.data
}

export const getLimaGrowthIntradaySignalsByCampaign = async (date) => {
  const params = {}
  if (date) params.date = date
  const response = await api.get('/yego-lima-growth/intraday-signals/by-campaign', { params, timeout: 15000 })
  return response.data
}

export const getLimaGrowthIntradaySignalsByProgram = async (date) => {
  const params = {}
  if (date) params.date = date
  const response = await api.get('/yego-lima-growth/intraday-signals/by-program', { params, timeout: 15000 })
  return response.data
}

export const buildLimaGrowthIntradaySignals = async (date) => {
  const params = {}
  if (date) params.date = date
  const response = await api.post('/yego-lima-growth/intraday-signals/build', null, { params, timeout: 60000 })
  return response.data
}

// ═══════════════════════════════════════════════════════════════
// Omniview V2 Shadow
// ═══════════════════════════════════════════════════════════════

export const getOmniviewV2Shell = async (params = {}, { signal } = {}) => {
  const response = await api.get('/ops/omniview-v2/shell', { params, signal, timeout: 10000 })
  return response.data
}

export const getOmniviewV2Sources = async ({ signal } = {}) => {
  const response = await api.get('/ops/omniview-v2/sources', { signal, timeout: 10000 })
  return response.data
}

export const getOmniviewV2Compare = async (params = {}, { signal } = {}) => {
  const response = await api.get('/ops/omniview-v2/compare', { params, signal, timeout: 20000 })
  return response.data
}

export const getOmniviewV2Matrix = async (params = {}, { signal } = {}) => {
  const response = await api.get('/ops/omniview-v2/matrix', { params, signal, timeout: 10000 })
  return response.data
}

export const getOmniviewV2OperatingDate = async (params = {}, { signal } = {}) => {
  const response = await api.get('/ops/omniview-v2/operating-date', { params, signal, timeout: 5000 })
  return response.data
}

export const getOmniviewV2PlanRealMonthly = async (params = {}, { signal } = {}) => {
  const response = await api.get('/ops/omniview-v2/plan-real/monthly', { params, signal, timeout: 10000 })
  return response.data
}

export const getOmniviewV2DrillCell = async (params = {}, { signal } = {}) => {
  const response = await api.get('/ops/omniview-v2/drill/cell', { params, signal, timeout: 8000 })
  return response.data
}

export default api
