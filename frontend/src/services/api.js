import axios from 'axios'

// En dev: usar proxy Vite (/api -> localhost:8000) para evitar CORS y Network Error
const baseURL = import.meta.env.DEV ? '/api' : (import.meta.env.VITE_API_URL || 'http://localhost:8000')

const api = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
})

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
  // #region agent log
  const t0 = Date.now()
  fetch('http://127.0.0.1:7243/ingest/d1353b8d-83b3-4a07-af72-66d85f06aec4',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'1c8c83'},body:JSON.stringify({sessionId:'1c8c83',location:'api.js:getRealLobDrillPro',message:'drill request started',data:{timeoutMs:REAL_DRILL_TIMEOUT_MS,params},timestamp:Date.now(),hypothesisId:'H1_H2'})}).catch(()=>{})
  // #endregion
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

// Control Tower Supply (REAL) — radar: geo, overview, segments, alerts, drilldown
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

export default api
