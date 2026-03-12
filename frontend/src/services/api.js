import axios from 'axios'

// Dev: proxy Vite /api. Producción: VITE_API_URL si está definido, si no '/api' (mismo origen con nginx)
const apiBase = (import.meta.env.VITE_API_URL || '').trim()
const baseURL = import.meta.env.DEV ? '/api' : (apiBase || '/api')

const api = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Instrumentación (Fase 1): en dev, log de requests y duración para detectar duplicados
if (import.meta.env.DEV) {
  api.interceptors.request.use((config) => {
    config.metadata = { startTime: Date.now() }
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

// Real LOB Drill PRO. BD tiene statement_timeout 300s → cliente debe esperar más (6 min).
const REAL_DRILL_TIMEOUT_MS = 360000
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

// Driver Supply Dynamics — freshness (última semana, último refresh, estado)
export const getSupplyFreshness = async () => {
  const response = await api.get('/ops/supply/freshness', { timeout: 5000 })
  return response.data
}

// Freshness global (banner): estado único para toda la app (fresca / parcial_esperada / atrasada / falta_data / sin_datos)
export const getDataFreshnessGlobal = async () => {
  const response = await api.get('/ops/data-freshness/global', { timeout: 8000 })
  return response.data
}

// Centro de observabilidad del pipeline: por dataset source_max_date, derived_max_date, lag_days, status
export const getDataPipelineHealth = async (latestOnly = true) => {
  const response = await api.get('/ops/data-pipeline-health', { params: { latest_only: latestOnly }, timeout: 10000 })
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

export default api
