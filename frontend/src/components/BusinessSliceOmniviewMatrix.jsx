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
  aggregateExecutiveKpis,
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

const GRAINS = [
  { id: 'monthly', label: 'Mensual' },
  { id: 'weekly', label: 'Semanal' },
  { id: 'daily', label: 'Diario' },
]

const btnCls = (active) =>
  `px-2.5 py-1 rounded-md text-xs font-semibold transition-colors ${
    active ? 'bg-slate-800 text-white shadow-sm' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
  }`

const densityCls = (active) =>
  `px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
    active ? 'bg-slate-700 text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
  }`

const modeCls = (active) =>
  `px-2.5 py-0.5 rounded text-[11px] font-semibold transition-colors ${
    active ? 'bg-blue-600 text-white shadow-sm' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
  }`

const selectCls = 'border border-gray-300 rounded-md text-xs px-2 py-1 bg-white focus:ring-1 focus:ring-blue-400 focus:border-blue-400 outline-none'
const miniSelectCls = 'border border-gray-200 rounded text-[10px] px-1.5 py-0.5 bg-white outline-none text-gray-500'

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
  const [insightUserPatch, setInsightUserPatch] = useState(() => loadInsightUserPatch() ?? {})
  const [insightSettingsOpen, setInsightSettingsOpen] = useState(false)
  const prevInsightMode = useRef(insightMode)
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)
  const [selectedCell, setSelectedCell] = useState(null)
  const [selection, setSelection] = useState(null)

  const needsCountry = grain === 'weekly' || grain === 'daily'
  const blockedByCountry = needsCountry && !country

  useEffect(() => {
    persistState({ grain, compact, country, city, businessSlice, fleet, showSubfleets, year, month, sortKey })
  }, [grain, compact, country, city, businessSlice, fleet, showSubfleets, year, month, sortKey])

  const [freshnessInfo, setFreshnessInfo] = useState(null)
  const [sliceMaxTripDate, setSliceMaxTripDate] = useState(null)
  const [coverageSummary, setCoverageSummary] = useState(null)
  const [matrixMeta, setMatrixMeta] = useState(null)
  const [matrixTrust, setMatrixTrust] = useState(null)

  useEffect(() => { getBusinessSliceFilters().then(setFiltersMeta).catch(() => {}) }, [])
  useEffect(() => {
    getMatrixOperationalTrust()
      .then(setMatrixTrust)
      .catch(() => setMatrixTrust({
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
      }))
  }, [])
  useEffect(() => { getDataFreshnessGlobal({ group: 'operational' }).then(setFreshnessInfo).catch(() => {}) }, [])

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

  const loadData = useCallback(async () => {
    if (blockedByCountry) {
      setRows([])
      setMatrixMeta(null)
      setSliceMaxTripDate(null)
      setErr(null)
      return
    }
    setLoading(true); setErr(null)
    try {
      const params = {}
      if (country) params.country = country
      if (city) params.city = city
      if (businessSlice) params.business_slice = businessSlice
      if (year != null && year !== '') params.year = Number(year)
      if (month) params.month = Number(month)
      if (grain === 'monthly' && fleet) params.fleet = fleet
      let res
      if (grain === 'weekly') res = await getBusinessSliceWeekly(params)
      else if (grain === 'daily') res = await getBusinessSliceDaily(params)
      else res = await getBusinessSliceMonthly(params)
      let data = Array.isArray(res?.data) ? res.data : (Array.isArray(res) ? res : [])
      setMatrixMeta(res?.meta ?? null)
      setSliceMaxTripDate(res?.meta?.slice_max_trip_date ?? null)
      if (!showSubfleets) data = data.filter((r) => !r.is_subfleet)
      setRows(data)
    } catch (e) {
      const detail = e?.response?.data?.detail
      const net =
        e?.code === 'ECONNABORTED' || e?.message?.includes?.('timeout')
          ? 'Tiempo de espera agotado: el servidor o la base de datos pueden estar lentos o no disponibles.'
          : null
      setErr(net || (typeof detail === 'string' ? detail : detail?.message) || e.message || 'Error cargando datos')
      setRows([])
      setMatrixMeta(null)
      setSliceMaxTripDate(null)
    } finally { setLoading(false) }
  }, [grain, country, city, businessSlice, fleet, showSubfleets, year, month, blockedByCountry])

  useEffect(() => { loadData() }, [loadData])

  useEffect(() => {
    const params = {}
    if (country) params.country = country
    if (city) params.city = city
    if (year != null && year !== '') params.year = Number(year)
    if (month) params.month = Number(month)
    getBusinessSliceCoverageSummary(params).then(setCoverageSummary).catch(() => setCoverageSummary(null))
  }, [country, city, year, month])

  const matrix = useMemo(() => buildMatrix(rows, grain), [rows, grain])
  const execKpis = useMemo(() => aggregateExecutiveKpis(rows), [rows])

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

  const execCards = useMemo(() => {
    const cards = [
      { key: 'trips_completed', label: 'Viajes' },
      { key: 'revenue_yego_net', label: 'Revenue net' },
      { key: 'commission_pct', label: 'Comisión %' },
      { key: 'active_drivers', label: 'Conductores' },
      { key: 'cancel_rate_pct', label: 'Cancel %' },
      { key: 'trips_per_driver', label: 'Viajes / cond.' },
    ]
    const p = matrix.allPeriods
    const currPk = p.length > 0 ? p[p.length - 1] : null
    const prevPk = p.length > 1 ? p[p.length - 2] : null
    const currTotals = currPk ? matrix.totals.get(currPk) : null
    const currComparisonMeta = currPk ? matrix.comparisonMeta?.get(currPk) : null
    const prevTotals = currPk && currComparisonMeta && (currComparisonMeta.is_partial_equivalent || currComparisonMeta.is_operationally_aligned)
      ? matrix.comparisonTotals?.get(currPk)
      : (prevPk ? matrix.totals.get(prevPk) : null)
    const deltaLabel = currComparisonMeta?.comparison_mode === 'weekly_partial_equivalent'
      ? 'vs eq.'
      : currComparisonMeta?.comparison_mode === 'monthly_partial_equivalent'
        ? 'vs eq.'
        : currComparisonMeta?.comparison_mode === 'daily_same_weekday'
          ? 'vs DoW'
          : 'vs ant.'
    return cards.map((c) => {
      const val = execKpis[c.key]
      let delta = null, signal = 'neutral'
      if (currTotals && prevTotals) {
        const cv = currTotals[c.key], pv = prevTotals[c.key]
        if (cv != null && pv != null && pv !== 0) {
          const diff = cv - pv
          delta = {
            delta_pct: diff / Math.abs(pv),
            signal: diff > 0 ? 'up' : diff < 0 ? 'down' : 'neutral',
            isPartialComparison: false,
            is_equivalent_comparison: !!(currComparisonMeta && (currComparisonMeta.is_partial_equivalent || currComparisonMeta.is_operationally_aligned)),
          }
          signal = delta.signal
        }
      }
      return { ...c, val, delta, signal, deltaLabel }
    })
  }, [execKpis, matrix])

  const handleExport = useCallback(() => {
    const csv = exportMatrixCsv(matrix, grain)
    downloadCsv(csv, `omniview_matrix_${grain}_${new Date().toISOString().slice(0, 16).replace(/[:-]/g, '')}.csv`)
  }, [matrix, grain])

  return (
    <div className="relative" data-omniview-matrix-root style={{ width: '100vw', left: '50%', right: '50%', marginLeft: '-50vw', marginRight: '-50vw' }}>
      <div className="px-4 md:px-6 lg:px-8 space-y-3">
        <MatrixExecutiveBanner
          executive={executiveForBanner}
          decisionMode={matrixTrust?.operational_decision?.decision_mode}
          confidence={matrixTrust?.operational_decision?.confidence}
          recommendations={matrixTrust?.trust_recommendations}
          loading={!matrixTrust}
          actionable={!blockedByCountry && rows.length > 0 && !loading}
          onActivate={handleExecutiveBannerActivate}
          contextHints={bannerContextHints}
        />

        {/* ── Controls ──────────────────────────────────────────── */}
        <div className="rounded-lg border border-gray-200 bg-white shadow-sm px-4 py-2.5">
          <div className="flex flex-wrap items-end gap-x-3 gap-y-2">
            <div>
              <label className="block text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-0.5">Grano</label>
              <div className="flex gap-0.5">
                {GRAINS.map((g) => (
                  <button key={g.id} type="button" className={btnCls(grain === g.id)} onClick={() => setGrain(g.id)}>{g.label}</button>
                ))}
              </div>
            </div>

            <FilterSelect label="País" value={country} onChange={setCountry} options={countries} placeholder="Todos" required={needsCountry} />
            <FilterSelect label="Ciudad" value={city} onChange={setCity} options={citiesForCountry} placeholder="Todas" />
            <FilterSelect label="Tajada" value={businessSlice} onChange={setBusinessSlice} options={slices} placeholder="Todas" />
            {grain === 'monthly' && <FilterSelect label="Flota" value={fleet} onChange={setFleet} options={fleets} placeholder="Todas" />}

            <div>
              <label className="block text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-0.5">Año</label>
              <input type="number" className={selectCls + ' w-[68px]'} value={year}
                onChange={(e) => setYear(e.target.value === '' ? '' : Number(e.target.value))} />
            </div>

            {(grain === 'monthly' || grain === 'daily') && (
              <div>
                <label className="block text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-0.5">Mes</label>
                <select className={selectCls + ' w-[68px]'} value={month} onChange={(e) => setMonth(e.target.value)}>
                  <option value="">—</option>
                  {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
            )}

            <label className="flex items-center gap-1 text-[11px] text-gray-500 cursor-pointer select-none pb-0.5">
              <input type="checkbox" checked={showSubfleets} onChange={(e) => setShowSubfleets(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 h-3 w-3" />
              Subflotas
            </label>

            {/* ── Right controls ─────────────────────────────────── */}
            <div className="ml-auto flex items-end gap-2 pb-0.5">
              {/* Mode toggle: Data / Insight */}
              <div className="flex items-center gap-0.5">
                <span className="text-[10px] text-gray-400 mr-0.5">Modo</span>
                <button type="button" className={modeCls(!insightMode)} onClick={() => setInsightMode(false)}>Data</button>
                <button type="button" className={modeCls(insightMode)} onClick={() => setInsightMode(true)}>
                  Insight
                  {insights.length > 0 && (
                    <span className="ml-1 px-1 py-px rounded-full text-[8px] font-bold bg-red-500 text-white">{insights.length}</span>
                  )}
                </button>
              </div>

              <div className="flex items-center gap-1">
                <span className="text-[10px] text-gray-400">Orden</span>
                <select className={miniSelectCls} value={sortKey} onChange={(e) => setSortKey(e.target.value)}>
                  {sortSelectOptions.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
                </select>
              </div>

              <div className="flex items-center gap-1">
                <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Densidad</span>
                <button type="button" className={densityCls(!compact)} onClick={() => setCompact(false)}>Cómodo</button>
                <button type="button" className={densityCls(compact)} onClick={() => setCompact(true)}>Compacto</button>
              </div>

              {rows.length > 0 && (
                <button type="button" onClick={handleExport}
                  className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium text-gray-500 bg-gray-100 hover:bg-gray-200 transition-colors"
                  title="Exportar matriz a CSV">
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5m0 0l5-5m-5 5V3" />
                  </svg>CSV
                </button>
              )}
            </div>
          </div>

          {blockedByCountry && (
            <div className="mt-2 rounded border border-amber-300 bg-amber-50 px-3 py-1.5 text-[11px] text-amber-900 font-medium">
              Selecciona un <strong>país</strong> para habilitar análisis semanal o diario.
            </div>
          )}
        </div>

        {/* ── Context bar ───────────────────────────────────────── */}
        {!blockedByCountry && rows.length > 0 && (
          <OperationalContextBar
            grain={grain} periodStates={periodStates} allPeriods={matrix.allPeriods}
            comparisonMeta={matrix.comparisonMeta}
            freshnessInfo={freshnessInfo} sliceMaxTripDate={sliceMaxTripDate}
            coverageSummary={coverageSummary} compact={compact}
            matrixMeta={matrixMeta}
            execKpis={execKpis}
          />
        )}

        {/* ── KPI strip ─────────────────────────────────────────── */}
        {!blockedByCountry && rows.length > 0 && (
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
            {execCards.map((card) => (
              <div key={card.key} className={`rounded-lg border border-gray-200 bg-white shadow-sm ${compact ? 'px-3 py-1.5' : 'px-3 py-2'}`}>
                <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider leading-tight">{card.label}</p>
                <p className={`font-bold text-gray-900 leading-tight ${compact ? 'text-base' : 'text-lg'}`}>{fmtValue(card.val, card.key)}</p>
                {card.delta && (
                  <div className="flex items-baseline gap-1">
                    <span className="text-[11px] font-semibold" style={{ color: signalColorForKpi(card.signal, card.key) }}>{signalArrow(card.signal)} {fmtDelta(card.delta)}</span>
                    <span className="text-[9px] text-gray-400">{card.deltaLabel}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* ── Insights Panel (additive, between KPI strip and Matrix) ── */}
        {!blockedByCountry && insights.length > 0 && (
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

        {err && !blockedByCountry && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-xs text-red-800">{String(err)}</div>
        )}

        {loading && (
          <div className="flex items-center gap-2 text-xs text-gray-500 py-6 justify-center">
            <span className="inline-block w-3.5 h-3.5 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
            Cargando datos…
          </div>
        )}

        {/* ── Matrix + Inspector ─────────────────────────────────── */}
        {!loading && !blockedByCountry && (
          <div className="flex gap-3 items-start">
            <div className="flex-1 min-w-0">
              <BusinessSliceOmniviewMatrixTable
                matrix={matrix} grain={grain} compact={compact} sortKey={sortKey}
                onCellClick={handleCellClick} selectedCell={selectedCell}
                insightCellMap={insightCellMap} insightMode={insightMode}
                lineImpactMap={lineImpactMap} periodStates={periodStates}
                matrixTrust={matrixTrust}
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
    <div>
      <label className="block text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-0.5">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      <select
        className={`border rounded-md text-xs px-2 py-1 bg-white focus:ring-1 focus:ring-blue-400 focus:border-blue-400 outline-none min-w-[100px] ${
          required && !value ? 'border-amber-400 bg-amber-50' : 'border-gray-300'
        }`}
        value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{placeholder}</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  )
}

