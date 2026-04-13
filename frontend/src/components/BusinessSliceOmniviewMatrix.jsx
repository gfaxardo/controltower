/**
 * BusinessSliceOmniviewMatrix — vista BI premium con Insight & Action Engine.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  getBusinessSliceFilters,
  getBusinessSliceMonthly,
  getBusinessSliceWeekly,
  getBusinessSliceDaily,
  getDataFreshnessGlobal,
  getBusinessSliceCoverageSummary,
  getMatrixOperationalTrust,
} from '../services/api.js'
import {
  buildMatrix,
  computeDeltas as computeDeltasFn,
  computePeriodStates,
  mergePeriodStatesFromMeta,
  periodStateLabel,
  periodElapsedDays,
  periodTotalDays,
  PERIOD_STATES,
  MATRIX_KPIS,
  fmtValue,
  signalColorForKpi,
  signalArrow,
  fmtDelta,
  exportMatrixCsv,
  downloadCsv,
  loadPersistedState,
  persistState,
  SORT_OPTIONS,
  resolveMainIssueCellTarget,
} from './omniview/omniviewMatrixUtils.js'
import { INSIGHT_CONFIG } from './omniview/insightConfig.js'
import { detectInsights, buildInsightCellMap } from './omniview/insightEngine.js'
import { loadInsightUserPatch, mergeInsightRuntimeConfig } from './omniview/insightUserSettings.js'
import BusinessSliceOmniviewMatrixTable from './BusinessSliceOmniviewMatrixTable.jsx'
import BusinessSliceOmniviewInspector from './BusinessSliceOmniviewInspector.jsx'
import BusinessSliceInsightsPanel from './BusinessSliceInsightsPanel.jsx'
import BusinessSliceInsightSettings from './BusinessSliceInsightSettings.jsx'
import MatrixExecutiveBanner from './MatrixExecutiveBanner.jsx'
import FactStatusPanel from './FactStatusPanel.jsx'

const GRAINS = [
  { id: 'monthly', label: 'Mensual' },
  { id: 'weekly', label: 'Semanal' },
  { id: 'daily', label: 'Diario' },
]

const KPI_FOCUS_OPTIONS = [
  { id: 'trips_completed', label: 'Trips' },
  { id: 'revenue_yego_net', label: 'Revenue' },
  { id: 'active_drivers', label: 'Active drivers' },
  { id: 'avg_ticket', label: 'Avg ticket' },
  { id: 'trips_per_driver', label: 'Trips per driver' },
]

const btnCls = (active) =>
  `px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
    active ? 'bg-slate-900 text-white shadow-sm' : 'bg-white text-gray-600 border border-gray-200 hover:border-gray-300 hover:bg-gray-50'
  }`

const densityCls = (active) =>
  `px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
    active ? 'bg-slate-900 text-white shadow-sm' : 'bg-white text-gray-500 border border-gray-200 hover:border-gray-300 hover:bg-gray-50'
  }`

const modeCls = (active) =>
  `px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
    active ? 'bg-blue-600 text-white shadow-sm' : 'bg-white text-gray-500 border border-gray-200 hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50'
  }`

const selectCls = 'border border-gray-200 rounded-md text-sm px-2.5 py-1.5 bg-white focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none text-gray-700'
const miniSelectCls = 'border border-gray-200 rounded-md text-xs px-2 py-1 bg-white outline-none text-gray-600 focus:ring-1 focus:ring-blue-400'

/** Si true (p. ej. VITE_OMNIVIEW_MATRIX_MANUAL_LOAD en .env.development), no se llama a la API pesada hasta pulsar «Cargar datos». */
const MANUAL_LOAD = import.meta.env.VITE_OMNIVIEW_MATRIX_MANUAL_LOAD === 'true'

function toMetricMap (raw) {
  const out = new Map()
  if (!raw || typeof raw !== 'object') return out
  for (const [periodKey, metrics] of Object.entries(raw)) {
    if (!periodKey || !metrics || typeof metrics !== 'object') continue
    out.set(periodKey, metrics)
  }
  return out
}

export default function BusinessSliceOmniviewMatrix () {
  const saved = useMemo(() => loadPersistedState(), [])

  const [grain, setGrain] = useState(saved?.grain || 'monthly')
  const [compact, setCompact] = useState(saved?.compact ?? false)
  const [insightMode, setInsightMode] = useState(false)
  const [filtersMeta, setFiltersMeta] = useState(null)
  const [country, setCountry] = useState(saved?.country || '')
  const [city, setCity] = useState(saved?.city || '')
  const [businessSlice, setBusinessSlice] = useState(saved?.businessSlice || '')
  const [fleet, setFleet] = useState(saved?.fleet || '')
  const [showSubfleets, setShowSubfleets] = useState(saved?.showSubfleets ?? true)
  const [year, setYear] = useState(saved?.year ?? new Date().getFullYear())
  const [month, setMonth] = useState(saved?.month || '')
  const [sortKey, setSortKey] = useState(saved?.sortKey || 'alpha')
  const [focusedKpi, setFocusedKpi] = useState(saved?.focusedKpi || 'trips_completed')
  const [insightUserPatch, setInsightUserPatch] = useState(() => loadInsightUserPatch() ?? {})
  const [insightSettingsOpen, setInsightSettingsOpen] = useState(false)
  const [factStatusOpen, setFactStatusOpen] = useState(false)
  const prevInsightMode = useRef(insightMode)
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)
  const [selectedCell, setSelectedCell] = useState(null)
  const [selection, setSelection] = useState(null)

  const needsCountry = grain === 'weekly' || grain === 'daily'
  const blockedByCountry = needsCountry && !country

  useEffect(() => {
    persistState({ grain, compact, country, city, businessSlice, fleet, showSubfleets, year, month, sortKey, focusedKpi })
  }, [grain, compact, country, city, businessSlice, fleet, showSubfleets, year, month, sortKey, focusedKpi])

  const [freshnessInfo, setFreshnessInfo] = useState(null)
  const [sliceMaxTripDate, setSliceMaxTripDate] = useState(null)
  const [coverageSummary, setCoverageSummary] = useState(null)
  const [matrixMeta, setMatrixMeta] = useState(null)
  const [matrixTrust, setMatrixTrust] = useState(null)
  /** En modo manual, false hasta que el usuario pulse «Cargar datos» (evita consultas pesadas al montar la vista). */
  const [heavyQueriesEnabled, setHeavyQueriesEnabled] = useState(!MANUAL_LOAD)

  /**
   * Mapa de tareas activas: { taskKey: 'Etiqueta visible' }.
   * Una tarea aparece mientras su request está en vuelo; desaparece al completarse o cancelarse.
   */
  const [loadingTasks, setLoadingTasks] = useState({})
  const activeTasks = Object.values(loadingTasks).filter(Boolean)

  const trustAbortRef = useRef(null)
  const freshnessAbortRef = useRef(null)
  const filtersAbortRef = useRef(null)
  const trustStartDelayRef = useRef(null)
  const freshnessDelayRef = useRef(null)

  useEffect(() => {
    const ctrl = new AbortController()
    filtersAbortRef.current = ctrl
    getBusinessSliceFilters({ signal: ctrl.signal })
      .then(setFiltersMeta)
      .catch(() => {})
    return () => ctrl.abort('unmount')
  }, [])

  /** Retraso antes de trust/frescura para que /monthly tome pool y CPU primero (evita el “colgado” al abrir con todo en paralelo). */
  const SECONDARY_TRUST_DELAY_MS = 1500
  const SECONDARY_FRESHNESS_DELAY_MS = 2800

  const trustPollRef = useRef(null)
  useEffect(() => {
    if (!heavyQueriesEnabled) return
    let cancelled = false
    const ctrl = new AbortController()
    trustAbortRef.current = ctrl

    const fetchTrust = () => {
      setLoadingTasks((t) => ({ ...t, trust: 'Trust operativo' }))
      getMatrixOperationalTrust({ signal: ctrl.signal })
        .then((data) => {
          if (cancelled) return
          setMatrixTrust(data)
          // Si el backend todavía está computando, reintentamos en 5s
          if (data?.trust_status === 'loading') {
            trustPollRef.current = setTimeout(fetchTrust, 5000)
          } else {
            setLoadingTasks((t) => { const n = { ...t }; delete n.trust; return n })
          }
        })
        .catch((e) => {
          if (cancelled) return
          if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError' || e?.name === 'AbortError') return
          setMatrixTrust({
            trust_status: 'warning',
            message: 'No se pudo cargar el estado de confianza de la Matrix',
            operational_trust: { status: 'warning', message: 'Error de red' },
            operational_decision: {
              decision_mode: 'CAUTION',
              confidence: { score: 0, coverage: 0, freshness: 0, consistency: 0 },
            },
            trust_recommendations: [],
            trust_history_recent: [],
            global_insights_blocked: false,
            affected_period_keys: { monthly: [], weekly: [], daily: [] },
            executive: {
              status: 'WARNING',
              impact_pct: 0,
              priority_score: 0,
              main_issue: null,
              action: 'Error de red al cargar Data Trust.',
            },
          })
          setLoadingTasks((t) => { const n = { ...t }; delete n.trust; return n })
        })
    }

    trustStartDelayRef.current = setTimeout(() => {
      if (!cancelled) fetchTrust()
    }, SECONDARY_TRUST_DELAY_MS)

    return () => {
      cancelled = true
      clearTimeout(trustStartDelayRef.current)
      ctrl.abort('unmount')
      clearTimeout(trustPollRef.current)
    }
  }, [heavyQueriesEnabled])

  useEffect(() => {
    if (!heavyQueriesEnabled) return
    const ctrl = new AbortController()
    freshnessAbortRef.current = ctrl
    freshnessDelayRef.current = setTimeout(() => {
      setLoadingTasks((t) => ({ ...t, freshness: 'Frescura de datos' }))
      getDataFreshnessGlobal({ group: 'operational' }, { signal: ctrl.signal })
        .then(setFreshnessInfo)
        .catch(() => {})
        .finally(() => setLoadingTasks((t) => { const n = { ...t }; delete n.freshness; return n }))
    }, SECONDARY_FRESHNESS_DELAY_MS)
    return () => {
      clearTimeout(freshnessDelayRef.current)
      ctrl.abort('unmount')
    }
  }, [heavyQueriesEnabled])

  const countries = filtersMeta?.countries || []
  const allCities = filtersMeta?.cities || []
  const slices = filtersMeta?.business_slices || []
  const fleets = filtersMeta?.fleets || []

  const cityCountryRef = useRef(new Map())
  useEffect(() => {
    for (const r of rows) {
      if (r.country && r.city) cityCountryRef.current.set(r.city.toLowerCase(), r.country.toLowerCase())
    }
  }, [rows])

  const citiesForCountry = useMemo(() => {
    if (!country) return allCities
    const lc = country.toLowerCase()
    return allCities.filter((c) => { const m = cityCountryRef.current.get(c.toLowerCase()); return !m || m === lc })
  }, [allCities, country])

  useEffect(() => {
    if (country && city) {
      const m = cityCountryRef.current.get(city.toLowerCase())
      if (m && m !== country.toLowerCase()) setCity('')
    }
  }, [country]) // eslint-disable-line react-hooks/exhaustive-deps

  const abortRef = useRef(null)
  const debounceRef = useRef(null)

  // doLoad: ejecuta la carga real de la matriz + lanza coverage-summary DESPUÉS (con retraso).
  // Acepta un AbortController.signal para poder cancelar si el usuario cambia filtros mientras carga.
  const doLoad = useCallback(async (signal) => {
    if (blockedByCountry) {
      setRows([])
      setMatrixMeta(null)
      setSliceMaxTripDate(null)
      setErr(null)
      return
    }
    setLoading(true); setErr(null)
    setLoadingTasks((t) => ({ ...t, matrix: 'Matriz de datos' }))
    try {
      const params = {}
      if (country) params.country = country
      if (city) params.city = city
      if (businessSlice) params.business_slice = businessSlice
      if (year != null && year !== '') params.year = Number(year)
      if (month) params.month = Number(month)
      if (grain === 'monthly' && fleet) params.fleet = fleet
      let res
      if (grain === 'weekly') res = await getBusinessSliceWeekly(params, { signal })
      else if (grain === 'daily') res = await getBusinessSliceDaily(params, { signal })
      else res = await getBusinessSliceMonthly(params, { signal })
      let data = Array.isArray(res?.data) ? res.data : (Array.isArray(res) ? res : [])
      setMatrixMeta(res?.meta ?? null)
      setSliceMaxTripDate(res?.meta?.slice_max_trip_date ?? null)
      if (!showSubfleets) data = data.filter((r) => !r.is_subfleet)
      setRows(data)
      setLoadingTasks((t) => { const n = { ...t }; delete n.matrix; return n })

      // Coverage-summary se lanza DESPUÉS de que la matriz cargó, con 3s de retraso para no
      // competir con las queries principales de la BD.
      const coverageParams = {}
      if (country) coverageParams.country = country
      if (city) coverageParams.city = city
      if (year != null && year !== '') coverageParams.year = Number(year)
      if (month) coverageParams.month = Number(month)
      setLoadingTasks((t) => ({ ...t, coverage: 'Cobertura (en espera…)' }))
      await new Promise((resolve) => setTimeout(resolve, 3000))
      if (signal?.aborted) {
        setLoadingTasks((t) => { const n = { ...t }; delete n.coverage; return n })
        return
      }
      setLoadingTasks((t) => ({ ...t, coverage: 'Cobertura' }))
      getBusinessSliceCoverageSummary(coverageParams, { signal })
        .then(setCoverageSummary)
        .catch(() => setCoverageSummary(null))
        .finally(() => setLoadingTasks((t) => { const n = { ...t }; delete n.coverage; return n }))
    } catch (e) {
      setLoadingTasks((t) => { const n = { ...t }; delete n.matrix; delete n.coverage; return n })
      if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError' || e?.name === 'AbortError') return
      const detail = e?.response?.data?.detail
      const net =
        e?.code === 'ECONNABORTED' || e?.message?.includes?.('timeout')
          ? 'Tiempo de espera agotado: el servidor o la base de datos pueden estar lentos o no disponibles.'
          : null
      setErr(net || (typeof detail === 'string' ? detail : detail?.message) || e.message || 'Error cargando datos')
      setRows([])
      setMatrixMeta(null)
      setSliceMaxTripDate(null)
    } finally {
      setLoading(false)
      setLoadingTasks((t) => { const n = { ...t }; delete n.matrix; return n })
    }
  }, [grain, country, city, businessSlice, fleet, showSubfleets, year, month, blockedByCountry])

  // scheduledLoad: debounce de 600ms antes de lanzar doLoad. Cancela la request anterior si
  // el usuario cambia filtros antes de que termine.
  const scheduledLoad = useCallback(() => {
    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      abortRef.current?.abort('filter-change')
      abortRef.current = new AbortController()
      doLoad(abortRef.current.signal)
    }, 600)
  }, [doLoad])

  useEffect(() => {
    if (!heavyQueriesEnabled) return
    scheduledLoad()
    return () => {
      clearTimeout(debounceRef.current)
      abortRef.current?.abort('unmount')
    }
  }, [scheduledLoad, heavyQueriesEnabled])

  // loadData: función pública para refrescos manuales (botones, etc.) sin debounce.
  const loadData = useCallback(() => {
    abortRef.current?.abort('manual-reload')
    abortRef.current = new AbortController()
    doLoad(abortRef.current.signal)
  }, [doLoad])

  /** Cancela TODAS las requests en vuelo (incluido debounce pendiente). */
  const cancelAll = useCallback(() => {
    clearTimeout(debounceRef.current)
    clearTimeout(trustStartDelayRef.current)
    clearTimeout(freshnessDelayRef.current)
    abortRef.current?.abort('user-cancel')
    trustAbortRef.current?.abort('user-cancel')
    freshnessAbortRef.current?.abort('user-cancel')
    filtersAbortRef.current?.abort('user-cancel')
  }, [])

  const baseMatrix = useMemo(() => buildMatrix(rows, grain), [rows, grain])
  const backendTotals = useMemo(() => toMetricMap(matrixMeta?.period_totals), [matrixMeta?.period_totals])
  const backendComparisonTotals = useMemo(
    () => toMetricMap(matrixMeta?.comparison_period_totals),
    [matrixMeta?.comparison_period_totals]
  )
  const backendUnmappedTotals = useMemo(
    () => toMetricMap(matrixMeta?.unmapped_period_totals),
    [matrixMeta?.unmapped_period_totals]
  )
  const matrix = useMemo(() => ({
    ...baseMatrix,
    totals: backendTotals.size > 0 ? backendTotals : baseMatrix.totals,
    comparisonTotals: backendComparisonTotals.size > 0 ? backendComparisonTotals : baseMatrix.comparisonTotals,
  }), [baseMatrix, backendTotals, backendComparisonTotals])
  const execKpis = useMemo(() => {
    const periods = matrix.allPeriods || []
    const currPk = periods.length > 0 ? periods[periods.length - 1] : null
    const currTotals = currPk ? matrix.totals.get(currPk) : null
    const currUnmapped = currPk ? backendUnmappedTotals.get(currPk) : null
    const totalTripsVisible = (Number(currTotals?.trips_completed) || 0) + (Number(currTotals?.trips_cancelled) || 0)
    const unmappedTripsVolume = (Number(currUnmapped?.trips_completed) || 0) + (Number(currUnmapped?.trips_cancelled) || 0)
    return {
      ...(currTotals || {}),
      unmapped_trips_volume: unmappedTripsVolume,
      unmapped_share_of_trips: totalTripsVisible > 0 ? unmappedTripsVolume / totalTripsVisible : 0,
    }
  }, [matrix, backendUnmappedTotals])

  // Freshness para STALE: priorizar capa business_slice (day_fact) alineada a la matriz.
  const maxDataDate = sliceMaxTripDate || freshnessInfo?.derived_max_date || null
  const periodStates = useMemo(
    () => mergePeriodStatesFromMeta(
      computePeriodStates(matrix.allPeriods, grain, maxDataDate),
      matrixMeta?.period_states,
    ),
    [matrix.allPeriods, grain, maxDataDate, matrixMeta]
  )

  const bannerContextHints = useMemo(() => {
    const hints = []
    if (matrixMeta?.fact_layer?.status === 'empty') {
      hints.push(
        matrixMeta.fact_layer.message ||
          'Capa operativa (facts) sin datos para este filtro: revisar carga ETL.'
      )
    }
    const lp = matrix.allPeriods.length > 0 ? matrix.allPeriods[matrix.allPeriods.length - 1] : null
    const st = lp ? periodStates?.get(lp) : null
    if (st === PERIOD_STATES.STALE) {
      hints.push('Data desactualizada: el delta no es definitivo')
    }
    if (st === PERIOD_STATES.OPEN || st === PERIOD_STATES.PARTIAL) {
      hints.push(
        st === PERIOD_STATES.PARTIAL
          ? 'Carga incompleta: comparativos preliminares'
          : 'En curso: comparativos preliminares'
      )
    }
    const cp = coverageSummary?.coverage_pct
    if (cp != null && cp < 92) hints.push(`Cobertura mapeada ${cp}%`)
    const um = coverageSummary?.unmapped_trips
    if (um != null && um > 0) hints.push(`Sin mapear ${um.toLocaleString()} viajes`)
    return hints
  }, [matrix.allPeriods, periodStates, coverageSummary, matrixMeta])

  // ─── Insight Engine (memoized) ────────────────────────────────────────────
  const engineConfig = useMemo(
    () => mergeInsightRuntimeConfig(INSIGHT_CONFIG, insightUserPatch),
    [insightUserPatch]
  )
  const trustContext = useMemo(() => {
    if (!matrixTrust?.trust_status) return null
    const decisionMode = matrixTrust.operational_decision?.decision_mode ?? null
    return {
      trust_status: matrixTrust.trust_status,
      decision_mode: decisionMode,
      global_insights_blocked:
        !!matrixTrust.global_insights_blocked || decisionMode === 'BLOCKED',
      matrixTrust,
    }
  }, [matrixTrust])

  const execNavPendingRef = useRef(false)

  const executiveForBanner = useMemo(() => {
    if (!matrixTrust) return null
    if (matrixTrust.executive) return matrixTrust.executive
    const ts = matrixTrust.trust_status
    const status = ts === 'ok' ? 'OK' : ts === 'blocked' ? 'BLOCKED' : 'WARNING'
    const im = matrixTrust.impact_summary || {}
    const pi = matrixTrust.primary_issue
    return {
      status,
      impact_pct: Math.max(Number(im.pct_trips_affected) || 0, Number(im.pct_revenue_affected) || 0),
      priority_score: pi?.severity_weight ?? 0,
      main_issue: pi
        ? {
            code: pi.code,
            description: pi.message,
            city: pi.trace?.city ?? null,
            lob: pi.trace?.lob ?? null,
            period: pi.trace?.period ?? null,
            metric: Array.isArray(pi.trace?.metrics) ? pi.trace.metrics[0] : null,
          }
        : null,
      action: pi?.action_engine?.action || matrixTrust.message || '',
    }
  }, [matrixTrust])

  const handleExecutiveBannerActivate = useCallback(() => {
    const mi = executiveForBanner?.main_issue
    if (!mi) return
    execNavPendingRef.current = true
    if (mi.city) setCity(mi.city)
    if (mi.lob) setBusinessSlice(mi.lob)
    if (mi.period && grain === 'monthly') {
      const d = String(mi.period).slice(0, 10)
      const y = parseInt(d.slice(0, 4), 10)
      const mo = parseInt(d.slice(5, 7), 10)
      if (!Number.isNaN(y)) setYear(y)
      if (!Number.isNaN(mo)) setMonth(String(mo))
    }
  }, [executiveForBanner, grain])

  const insights = useMemo(
    () => detectInsights(matrix, grain, engineConfig, periodStates, trustContext),
    [matrix, grain, engineConfig, periodStates, trustContext]
  )
  const insightCellMap = useMemo(
    () => buildInsightCellMap(insights, engineConfig),
    [insights, engineConfig]
  )
  const lineImpactMap = useMemo(() => {
    const m = new Map()
    for (const ins of insights) {
      const k = `${ins.cityKey}::${ins.lineKey}`
      m.set(k, Math.max(m.get(k) ?? 0, ins.impactScore))
    }
    return m
  }, [insights])

  const refreshInsightPatch = useCallback(() => {
    setInsightUserPatch(loadInsightUserPatch() ?? {})
  }, [])

  const refreshMatrixTrust = useCallback(() => {
    getMatrixOperationalTrust()
      .then(setMatrixTrust)
      .catch(() => {})
  }, [])

  const sortSelectOptions = useMemo(() => {
    const impactOpt = SORT_OPTIONS.find((o) => o.id === 'impact_desc')
    const rest = SORT_OPTIONS.filter((o) => o.id !== 'impact_desc')
    if (insightMode) return [impactOpt, ...rest].filter(Boolean)
    return rest
  }, [insightMode])

  useEffect(() => {
    if (insightMode && !prevInsightMode.current && sortKey === 'alpha') {
      setSortKey('impact_desc')
    }
    prevInsightMode.current = insightMode
  }, [insightMode, sortKey])

  useEffect(() => {
    if (!insightMode && sortKey === 'impact_desc') setSortKey('alpha')
  }, [insightMode, sortKey])

  // Find insight for current selection
  const insightForSelection = useMemo(() => {
    if (!selection) return null
    const key = `${selection.cityKey}::${selection.lineKey}::${selection.period}`
    return insights.find((i) => `${i.cityKey}::${i.lineKey}::${i.period}` === key) || null
  }, [selection, insights])

  const handleCellClick = useCallback((cellInfo) => {
    setSelectedCell((prev) => (prev === cellInfo.id ? null : cellInfo.id))
    setSelection((prev) => (prev?.id === cellInfo.id ? null : cellInfo))
  }, [])

  useEffect(() => {
    if (!execNavPendingRef.current || loading || blockedByCountry || rows.length === 0) return
    const mi = executiveForBanner?.main_issue
    const resolved = mi && resolveMainIssueCellTarget(matrix, grain, mi, periodStates)
    if (resolved?.cellInfo) {
      handleCellClick(resolved.cellInfo)
      requestAnimationFrame(() => {
        const id = resolved.cellInfo.id
        const el = typeof CSS !== 'undefined' && CSS.escape
          ? document.querySelector(`[data-matrix-cell-id="${CSS.escape(id)}"]`)
          : document.querySelector(`[data-matrix-cell-id="${id.replace(/"/g, '')}"]`)
        el?.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' })
      })
    }
    execNavPendingRef.current = false
  }, [rows, matrix, loading, blockedByCountry, executiveForBanner, grain, periodStates, handleCellClick])

  const handleInsightClick = useCallback((insight) => {
    const lineData = matrix.cities.get(insight.cityKey)?.lines
    let foundLine = null, foundLineKey = null
    if (lineData) {
      for (const [lk, ld] of lineData) {
        if (ld.business_slice_name === insight.business_slice) { foundLine = ld; foundLineKey = lk; break }
      }
    }
    if (!foundLine) return
    const periodDeltas = {}
    const rawDeltas = computeDeltasFn(foundLine.periods, matrix.allPeriods, periodStates)
    const pd = rawDeltas.get(insight.period)
    if (pd) Object.assign(periodDeltas, pd)

    const cellId = `${insight.cityKey}::${foundLineKey}::${insight.period}::${insight.metric}`
    setSelectedCell(cellId)
    setSelection({
      id: cellId,
      cityKey: insight.cityKey,
      lineKey: foundLineKey,
      period: insight.period,
      kpiKey: insight.metric,
      lineData: foundLine,
      periodDeltas,
      raw: foundLine.periods.get(insight.period)?.raw,
    })
  }, [matrix, periodStates])

  const handleExport = useCallback(() => {
    const csv = exportMatrixCsv(matrix, grain)
    downloadCsv(csv, `omniview_matrix_${grain}_${new Date().toISOString().slice(0, 16).replace(/[:-]/g, '')}.csv`)
  }, [matrix, grain])

  return (
    <div className="relative" data-omniview-matrix-root style={{ width: '100vw', left: '50%', right: '50%', marginLeft: '-50vw', marginRight: '-50vw' }}>
      <div className="px-4 md:px-6 lg:px-8 space-y-3">
        {heavyQueriesEnabled && (
          <MatrixExecutiveBanner
            executive={executiveForBanner}
            decisionMode={matrixTrust?.operational_decision?.decision_mode}
            confidence={matrixTrust?.operational_decision?.confidence}
            recommendations={matrixTrust?.trust_recommendations}
            loading={!matrixTrust || matrixTrust?.trust_status === 'loading'}
            actionable={!blockedByCountry && rows.length > 0 && !loading}
            onActivate={handleExecutiveBannerActivate}
            contextHints={bannerContextHints}
          />
        )}

        {/* ── Controls ──────────────────────────────────────────── */}
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm divide-y divide-gray-100">

          {/* Fila 1: Filtros de datos */}
          <div className="px-4 py-3 flex flex-wrap items-end gap-x-4 gap-y-3">
            {/* Grano temporal */}
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Grano</span>
              <div className="flex gap-1">
                {GRAINS.map((g) => (
                  <button key={g.id} type="button" className={btnCls(grain === g.id)} onClick={() => setGrain(g.id)}>{g.label}</button>
                ))}
              </div>
            </div>

            {/* Separador vertical */}
            <div className="hidden sm:block self-stretch w-px bg-gray-100 mx-1" />

            {/* Filtros dimensionales */}
            <FilterSelect label="País" value={country} onChange={setCountry} options={countries} placeholder="Todos los países" required={needsCountry} />
            <FilterSelect label="Ciudad" value={city} onChange={setCity} options={citiesForCountry} placeholder="Todas las ciudades" />
            <FilterSelect label="Tajada" value={businessSlice} onChange={setBusinessSlice} options={slices} placeholder="Todas las tajadas" />
            {grain === 'monthly' && <FilterSelect label="Flota" value={fleet} onChange={setFleet} options={fleets} placeholder="Todas las flotas" />}

            {/* Separador vertical */}
            <div className="hidden sm:block self-stretch w-px bg-gray-100 mx-1" />

            {/* Periodo */}
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Año</span>
              <input type="number" className={selectCls + ' w-20'} value={year}
                onChange={(e) => setYear(e.target.value === '' ? '' : Number(e.target.value))} />
            </div>

            {(grain === 'monthly' || grain === 'daily') && (
              <div className="flex flex-col gap-1">
                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Mes</span>
                <select className={selectCls + ' w-24'} value={month} onChange={(e) => setMonth(e.target.value)}>
                  <option value="">Todos</option>
                  {['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic'].map((m, i) => (
                    <option key={i + 1} value={i + 1}>{m}</option>
                  ))}
                </select>
              </div>
            )}

            <label className="flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer select-none self-end pb-1.5">
              <input type="checkbox" checked={showSubfleets} onChange={(e) => setShowSubfleets(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 h-3.5 w-3.5" />
              Subflotas
            </label>
          </div>

          {/* Fila 2: Controles de visualización */}
          <div className="px-4 py-2 flex flex-wrap items-center gap-x-4 gap-y-2 bg-gray-50/60">
            {/* Modo Data / Insight */}
            <div className="flex items-center gap-1">
              <span className="text-[11px] font-medium text-gray-400 mr-1">Vista</span>
              <div className="flex gap-1">
                <button type="button" className={modeCls(!insightMode)} onClick={() => setInsightMode(false)}>Data</button>
                <button type="button" className={modeCls(insightMode)} onClick={() => setInsightMode(true)}>
                  Insight
                  {insights.length > 0 && (
                    <span className="ml-1.5 px-1.5 py-px rounded-full text-[9px] font-bold bg-red-500 text-white">{insights.length}</span>
                  )}
                </button>
              </div>
            </div>

            <div className="w-px h-4 bg-gray-200 hidden sm:block" />

            {/* Orden */}
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] font-medium text-gray-400">Orden</span>
              <select className={miniSelectCls} value={sortKey} onChange={(e) => setSortKey(e.target.value)}>
                {sortSelectOptions.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
              </select>
            </div>

            <div className="w-px h-4 bg-gray-200 hidden sm:block" />

            {/* Densidad */}
            <div className="flex items-center gap-1">
              <span className="text-[11px] font-medium text-gray-400 mr-1">Densidad</span>
              <div className="flex gap-1">
                <button type="button" className={densityCls(!compact)} onClick={() => setCompact(false)}>Cómodo</button>
                <button type="button" className={densityCls(compact)} onClick={() => setCompact(true)}>Compacto</button>
              </div>
            </div>

            <div className="ml-auto flex items-center gap-2">
              <button type="button"
                onClick={() => setFactStatusOpen((o) => !o)}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all border ${factStatusOpen ? 'bg-slate-800 text-white border-slate-800' : 'text-gray-500 bg-white border-gray-200 hover:border-gray-300 hover:bg-gray-50'}`}
                title="Ver estado de materialización de FACT tables">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 7v10c0 2 1 3 3 3h10c2 0 3-1 3-3V7M4 7c0-2 1-3 3-3h10c2 0 3 1 3 3M4 7h16" />
                </svg>
                FACT tables
              </button>
              {rows.length > 0 && (
                <>
                  <div className="w-px h-4 bg-gray-200" />
                  <button type="button" onClick={handleExport}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-gray-500 bg-white border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-all"
                    title="Exportar matriz a CSV">
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5m0 0l5-5m-5 5V3" />
                    </svg>
                    Exportar CSV
                  </button>
                </>
              )}
            </div>
          </div>

          {blockedByCountry && heavyQueriesEnabled && (
            <div className="px-4 py-2 text-xs text-amber-800 bg-amber-50 border-t border-amber-100 font-medium flex items-center gap-2">
              <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z" />
              </svg>
              Selecciona un <strong className="mx-0.5">país</strong> para habilitar el análisis semanal o diario.
            </div>
          )}

          {factStatusOpen && (
            <div className="mt-3">
              <FactStatusPanel onClose={() => setFactStatusOpen(false)} />
            </div>
          )}

          {MANUAL_LOAD && !heavyQueriesEnabled && (
            <div className="mt-3 rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white px-6 py-6 flex flex-col items-center gap-4 text-center shadow-sm">
              <div className="w-10 h-10 rounded-full bg-slate-100 flex items-center justify-center">
                <svg className="w-5 h-5 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5M9 11.25v1.5M12 9v3.75m3-6v6" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-800">Omniview Matrix — carga diferida</p>
                <p className="mt-1 text-xs text-slate-500 max-w-sm">
                  No se ejecutan consultas a la base de datos hasta que pulses el botón. Ajusta los filtros y carga cuando estés listo.
                </p>
                {blockedByCountry && (
                  <p className="mt-2 text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-1">
                    Selecciona un país para habilitar el grano semanal o diario.
                  </p>
                )}
              </div>
              <button
                type="button"
                disabled={blockedByCountry}
                onClick={() => setHeavyQueriesEnabled(true)}
                className="px-6 py-2 rounded-lg text-sm font-semibold bg-slate-900 text-white hover:bg-slate-700 transition-colors shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Cargar datos
              </button>
            </div>
          )}
        </div>

        {/* ── Barra de actividad: muestra qué requests están en vuelo + botón Detener ── */}
        {activeTasks.length > 0 && (
          <div className="mt-2 flex items-center gap-2.5 px-3 py-1.5 rounded-lg border border-blue-100 bg-blue-50 text-xs text-blue-700">
            <span className="inline-block w-3 h-3 border-[1.5px] border-blue-300 border-t-blue-600 rounded-full animate-spin flex-shrink-0" />
            <span className="flex-1 min-w-0 truncate font-medium">
              {activeTasks.join(' · ')}
            </span>
            <button
              type="button"
              onClick={cancelAll}
              className="flex-shrink-0 px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-100 hover:bg-red-100 hover:text-red-700 text-blue-700 border border-blue-200 hover:border-red-200 transition-colors"
              title="Cancelar todas las consultas en vuelo"
            >
              Detener
            </button>
          </div>
        )}

        {/* ── Context bar ───────────────────────────────────────── */}
        {heavyQueriesEnabled && !blockedByCountry && rows.length > 0 && (
          <OperationalContextBar
            grain={grain} periodStates={periodStates} allPeriods={matrix.allPeriods}
            comparisonMeta={matrix.comparisonMeta}
            freshnessInfo={freshnessInfo} sliceMaxTripDate={sliceMaxTripDate}
            coverageSummary={coverageSummary} compact={compact}
            matrixMeta={matrixMeta}
            execKpis={execKpis}
          />
        )}

        {/* ── KPI focus mode ────────────────────────────────────── */}
        {heavyQueriesEnabled && !blockedByCountry && rows.length > 0 && (
          <div className="rounded-xl border border-gray-200 bg-white px-4 py-3 shadow-sm">
            <div className="flex flex-wrap items-center gap-3">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-400">KPI focus mode</p>
                <p className="mt-1 text-xs text-gray-500">La matriz conserva la lectura temporal, pero muestra una sola métrica a la vez.</p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {KPI_FOCUS_OPTIONS.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => setFocusedKpi(option.id)}
                    className={btnCls(focusedKpi === option.id)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ── Insights Panel (additive, between focus and Matrix) ── */}
        {heavyQueriesEnabled && !blockedByCountry && insights.length > 0 && (
          <BusinessSliceInsightsPanel
            insights={insights}
            onInsightClick={handleInsightClick}
            compact={compact}
            transparency={engineConfig.transparency}
            defaultTopN={engineConfig.panelTopN ?? 10}
            onOpenSettings={() => setInsightSettingsOpen(true)}
            onUserPatchPersist={refreshInsightPatch}
          />
        )}

        <BusinessSliceInsightSettings
          open={insightSettingsOpen}
          onClose={() => setInsightSettingsOpen(false)}
          userPatch={insightUserPatch}
          onSaved={refreshInsightPatch}
        />

        {err && heavyQueriesEnabled && !blockedByCountry && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-xs text-red-800">{String(err)}</div>
        )}

        {loading && heavyQueriesEnabled && (
          <div className="flex items-center gap-2 text-xs text-gray-500 py-6 justify-center">
            <span className="inline-block w-3.5 h-3.5 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
            Cargando datos…
          </div>
        )}

        {/* ── Matrix + Inspector ─────────────────────────────────── */}
        {heavyQueriesEnabled && !loading && !blockedByCountry && rows.length > 0 && (
          <div className="flex gap-3 items-start">
            <div className="flex-1 min-w-0">
              <BusinessSliceOmniviewMatrixTable
                matrix={matrix} grain={grain} compact={compact} sortKey={sortKey}
                onCellClick={handleCellClick} selectedCell={selectedCell}
                insightCellMap={insightCellMap} insightMode={insightMode}
                lineImpactMap={lineImpactMap} periodStates={periodStates}
                matrixTrust={matrixTrust}
                focusedKpi={focusedKpi}
              />
            </div>
            <BusinessSliceOmniviewInspector
              selection={selection} grain={grain} compact={compact}
              onClose={() => { setSelection(null); setSelectedCell(null) }}
              insightForSelection={insightForSelection}
              insightTransparency={engineConfig.transparency}
              periodStates={periodStates} coverageSummary={coverageSummary}
              matrixTrust={matrixTrust}
              matrixMeta={matrixMeta}
              onTrustStateRefresh={refreshMatrixTrust}
            />
          </div>
        )}
      </div>
    </div>
  )
}

function OperationalContextBar ({ grain, periodStates, allPeriods, comparisonMeta, freshnessInfo, sliceMaxTripDate, coverageSummary, compact, matrixMeta, execKpis }) {
  const hasPartial = [...(periodStates?.values() || [])].some(
    (s) => s === PERIOD_STATES.PARTIAL || s === PERIOD_STATES.CURRENT_DAY || s === PERIOD_STATES.OPEN
  )
  const hasStale = [...(periodStates?.values() || [])].some((s) => s === PERIOD_STATES.STALE)
  const lastPeriod = allPeriods.length > 0 ? allPeriods[allPeriods.length - 1] : null
  const lastState = lastPeriod ? periodStates?.get(lastPeriod) : null
  const lastMeta = lastPeriod ? comparisonMeta?.get(lastPeriod) : null

  let compLabel = grain === 'weekly' ? 'Comparativo WoW cerrado'
    : grain === 'daily' ? 'Comparativo diario · mismo día semana anterior'
      : 'Comparativo MoM cerrado'
  if (lastMeta?.comparison_mode === 'weekly_partial_equivalent') {
    compLabel = 'Comparativo semanal parcial equivalente'
  } else if (lastMeta?.comparison_mode === 'monthly_partial_equivalent') {
    compLabel = 'Comparativo mensual parcial equivalente'
  } else if (lastMeta?.comparison_mode === 'daily_same_weekday') {
    compLabel = 'Comparativo diario · mismo día de semana'
  } else if (hasPartial) {
    compLabel = grain === 'weekly' ? 'Comparativo semanal · parcial vs cerrado'
      : grain === 'daily' ? 'Comparativo diario · mismo día semana anterior'
        : 'Comparativo mensual · parcial vs cerrado'
  }

  const elapsed = lastPeriod && (lastState === PERIOD_STATES.PARTIAL || lastState === PERIOD_STATES.CURRENT_DAY || lastState === PERIOD_STATES.OPEN)
    ? periodElapsedDays(lastPeriod, grain) : null
  const total = lastPeriod && elapsed ? periodTotalDays(lastPeriod, grain) : null

  const cov = coverageSummary
  const py = compact ? 'py-1' : 'py-1.5'

  return (
    <div className={`rounded-lg border border-slate-200 bg-slate-50 shadow-sm px-4 ${py} flex flex-wrap items-center gap-x-4 gap-y-1`}>
      <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Contexto</span>

      <span className="text-[10px] text-slate-600">
        {compLabel}
      </span>

      {lastMeta?.is_partial_equivalent && (
        <span className="text-[10px] text-blue-700">
          {lastMeta.current_range_start} → {lastMeta.current_cutoff_date} vs {lastMeta.previous_equivalent_range_start} → {lastMeta.previous_equivalent_cutoff_date}
        </span>
      )}

      {lastMeta?.comparison_mode === 'daily_same_weekday' && (
        <span className="text-[10px] text-blue-700">
          Base operativa: mismo día de semana anterior
          {lastMeta.is_preliminary && <span className="text-amber-700 ml-1">(día actual en curso)</span>}
        </span>
      )}

      {hasPartial && elapsed != null && total != null && (
        <span className="inline-flex items-center gap-1 text-[10px] text-blue-700 font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-500 inline-block" />
          Avance {elapsed}/{total} días
        </span>
      )}

      {hasStale && (
        <span className="inline-flex items-center gap-1 text-[10px] text-amber-700 font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 inline-block" />
          Periodo stale detectado
        </span>
      )}

      {freshnessInfo && (
        <span
          className="text-[10px] text-slate-500"
          title={sliceMaxTripDate ? `Business slice day_fact: ${sliceMaxTripDate}. ${freshnessInfo.message || ''}` : freshnessInfo.message}>
          Freshness: {sliceMaxTripDate || freshnessInfo.derived_max_date || '—'}
          {sliceMaxTripDate && <span className="text-slate-400 ml-1">(slice)</span>}
          {!sliceMaxTripDate && freshnessInfo.lag_days > 0 && (
            <span className="text-amber-600 ml-1">(lag {freshnessInfo.lag_days}d)</span>
          )}
        </span>
      )}

      {cov && (cov.total_trips_real_raw ?? cov.total_trips) > 0 && (
        <span className="text-[10px] text-slate-600 ml-auto flex items-center gap-2">
          <span title="Mapped / universo RAW (public.trips_unified)">
            Cobertura: <strong className={cov.coverage_pct >= 95 ? 'text-emerald-700' : cov.coverage_pct >= 80 ? 'text-amber-700' : 'text-red-700'}>{cov.coverage_pct}%</strong>
            <span className="text-slate-400 font-normal"> RAW {(cov.total_trips_real_raw ?? cov.total_trips).toLocaleString()}</span>
          </span>
          {cov.unmapped_trips > 0 && (
            <span className="text-slate-400">Sin mapear: {cov.unmapped_trips.toLocaleString()}</span>
          )}
          {cov.identity_check_ok === false && (
            <span className="text-amber-700" title="RAW vs resolved o conteos por estado">⚠ identidad</span>
          )}
        </span>
      )}

      {execKpis?.unmapped_trips_volume > 0 && (
        <span className="text-[10px] text-amber-800" title="Volumen en bucket UNMAPPED (calidad de mapeo, no LOB)">
          Sin mapear en vista: {execKpis.unmapped_trips_volume.toLocaleString()} viajes
          {execKpis.unmapped_share_of_trips != null && (
            <span className="text-slate-500"> ({(execKpis.unmapped_share_of_trips * 100).toFixed(1)}% del volumen mostrado)</span>
          )}
        </span>
      )}

      {matrixMeta?.period_states?.length > 0 && (
        <span className="text-[10px] text-slate-500 hidden lg:inline" title="State Engine: max por período en day_fact (no solo global)">
          Estados: backend · máx global {matrixMeta.slice_max_trip_date || '—'} · por período ✓
        </span>
      )}
    </div>
  )
}

function FilterSelect ({ label, value, onChange, options, placeholder, required }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
      </span>
      <select
        className={`border rounded-md text-sm px-2.5 py-1.5 bg-white focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none min-w-[130px] text-gray-700 transition-colors ${
          required && !value ? 'border-amber-400 bg-amber-50 text-amber-900' : 'border-gray-200 hover:border-gray-300'
        }`}
        value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{placeholder}</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  )
}

