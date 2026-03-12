/**
 * Action Engine — Cohortes accionables y recomendaciones.
 * Sub-tabs: Cohorts (KPIs, acciones recomendadas, tabla, drilldown) y Top Driver Behavior (benchmarks, patrones, playbook).
 */
import { useState, useEffect, useCallback } from 'react'
import {
  getSupplyGeo,
  getActionEngineSummary,
  getActionEngineCohorts,
  getActionEngineCohortDetail,
  getActionEngineRecommendations,
  getActionEngineExportUrl,
  getTopDriverBehaviorSummary,
  getTopDriverBehaviorBenchmarks,
  getTopDriverBehaviorPatterns,
  getTopDriverBehaviorPlaybookInsights,
  getTopDriverBehaviorExportUrl
} from '../services/api'
import {
  getBehaviorDirection,
  getPersistenceLabel,
  getDeltaPctColor,
  getDecisionContextLabel,
  BEHAVIOR_DIRECTION_COLORS,
  RISK_BAND_COLORS as SEMANTIC_RISK_BAND_COLORS,
  ALERT_COLORS as SEMANTIC_ALERT_COLORS,
  COHORT_RATIONALE
} from '../constants/explainabilitySemantics'
import {
  decisionColorClasses,
  conversionRateDecision,
  reactivationRateDecision,
  downgradeRateDecision,
  priorityScoreDecision
} from '../theme/decisionColors'

function formatNum (n) {
  if (n == null || n === '') return '—'
  const num = Number(n)
  if (Number.isNaN(num)) return '—'
  return num.toLocaleString('es-ES', { maximumFractionDigits: 2 })
}

function formatPct (n) {
  if (n == null || n === '') return '—'
  const num = Number(n)
  if (Number.isNaN(num)) return '—'
  return (num * 100).toFixed(1) + '%'
}

const COHORT_LABELS = {
  high_value_deteriorating: 'Alto valor en deterioro',
  silent_erosion: 'Erosión silenciosa',
  recoverable_mid_performers: 'Recuperables (mid)',
  near_upgrade_opportunity: 'Cerca de subir segmento',
  near_drop_risk: 'Riesgo de bajada',
  volatile_drivers: 'Volátiles',
  high_value_recovery_candidates: 'Alto valor recuperables'
}

const PRIORITY_LABELS = { high: 'Alta', medium: 'Media', low: 'Baja' }
const BASELINE_WEEKS = 6

const TIME_RANGE_OPTIONS = [
  { value: '7', label: '7 días' },
  { value: '14', label: '14 días' },
  { value: '30', label: '30 días' },
  { value: '60', label: '60 días' },
  { value: 'custom', label: 'Rango personalizado' }
]

function applyTimeRangePreset (preset, toDate) {
  if (preset === 'custom') return null
  const d = new Date(toDate || new Date().toISOString().slice(0, 10))
  const days = Math.max(1, parseInt(preset, 10) || 30)
  const from = new Date(d)
  from.setDate(from.getDate() - days)
  return { from: from.toISOString().slice(0, 10), to: d.toISOString().slice(0, 10) }
}

/** Derive priority score 0-100 for display (high=85, medium=55, low=25) */
function cohortPriorityScore (c) {
  const p = (c && c.suggested_priority) || ''
  if (p === 'high') return 85
  if (p === 'medium') return 55
  if (p === 'low') return 25
  return c && c.priority_score != null ? Number(c.priority_score) : 50
}

export default function ActionEngineView () {
  const today = new Date().toISOString().slice(0, 10)
  const initialRange = applyTimeRangePreset('60', today) || { from: today, to: today }
  const [subTab, setSubTab] = useState('cohorts')
  const [timeRangePreset, setTimeRangePreset] = useState('60')
  const [from, setFrom] = useState(initialRange.from)
  const [to, setTo] = useState(initialRange.to)
  const [country, setCountry] = useState('')
  const [city, setCity] = useState('')
  const [parkId, setParkId] = useState('')
  const [segmentCurrent, setSegmentCurrent] = useState('')
  const [cohortType, setCohortType] = useState('')
  const [priority, setPriority] = useState('')
  const [geo, setGeo] = useState({ countries: [], cities: [], parks: [] })
  const [summary, setSummary] = useState(null)
  const [recommendations, setRecommendations] = useState({ data: [] })
  const [cohorts, setCohorts] = useState({ data: [], total: 0 })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [cohortPage, setCohortPage] = useState(0)
  const cohortPageSize = 20
  const [drillCohort, setDrillCohort] = useState(null)
  const [drillData, setDrillData] = useState({ data: [], total: 0 })
  const [drillLoading, setDrillLoading] = useState(false)
  const [showHelp, setShowHelp] = useState(false)

  const [tdbSummary, setTdbSummary] = useState(null)
  const [tdbBenchmarks, setTdbBenchmarks] = useState({ data: [] })
  const [tdbPatterns, setTdbPatterns] = useState({ data: [] })
  const [tdbInsights, setTdbInsights] = useState([])
  const [tdbLoading, setTdbLoading] = useState(false)

  const loadGeo = useCallback(async () => {
    try {
      const g = await getSupplyGeo({ country, city })
      setGeo(g)
    } catch (e) {
      console.error('Geo:', e)
    }
  }, [country, city])
  useEffect(() => { loadGeo() }, [loadGeo])

  useEffect(() => {
    if (timeRangePreset !== 'custom') {
      const next = applyTimeRangePreset(timeRangePreset, to)
      if (next) {
        setFrom(next.from)
        setTo(next.to)
      }
    }
  }, [timeRangePreset])

  const handleFromChange = (v) => { setFrom(v); setTimeRangePreset('custom') }
  const handleToChange = (v) => { setTo(v); setTimeRangePreset('custom') }

  const filters = {
    from,
    to,
    country: country || undefined,
    city: city || undefined,
    park_id: parkId || undefined,
    segment_current: segmentCurrent || undefined,
    cohort_type: cohortType || undefined,
    priority: priority || undefined
  }

  const loadSummary = useCallback(async () => {
    try {
      const s = await getActionEngineSummary({ ...filters, from, to })
      setSummary(s)
    } catch (e) {
      setSummary(null)
    }
  }, [from, to, country, city, parkId, segmentCurrent, cohortType, priority])

  const loadRecommendations = useCallback(async () => {
    try {
      const r = await getActionEngineRecommendations({
        from, to, country, city, park_id: parkId, segment_current: segmentCurrent,
        top_n: 5
      })
      setRecommendations(r)
    } catch (e) {
      setRecommendations({ data: [] })
    }
  }, [from, to, country, city, parkId, segmentCurrent])

  const loadCohorts = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await getActionEngineCohorts({
        ...filters, from, to,
        limit: cohortPageSize,
        offset: cohortPage * cohortPageSize
      })
      setCohorts({ data: r.data || [], total: r.total || 0 })
    } catch (e) {
      setError(e.message || 'Error al cargar cohortes')
      setCohorts({ data: [], total: 0 })
    } finally {
      setLoading(false)
    }
  }, [from, to, country, city, parkId, segmentCurrent, cohortType, priority, cohortPage])

  useEffect(() => {
    loadSummary()
    loadRecommendations()
  }, [loadSummary, loadRecommendations])

  useEffect(() => {
    loadCohorts()
  }, [loadCohorts])

  const loadCohortDetail = useCallback(async (ct, weekStart) => {
    setDrillCohort({ cohort_type: ct, week_start: weekStart })
    setDrillLoading(true)
    try {
      const r = await getActionEngineCohortDetail({
        cohort_type: ct,
        week_start: weekStart,
        country: country || undefined,
        city: city || undefined,
        park_id: parkId || undefined,
        limit: 500,
        offset: 0
      })
      setDrillData({ data: r.data || [], total: r.total || 0 })
    } catch (e) {
      setDrillData({ data: [], total: 0 })
    } finally {
      setDrillLoading(false)
    }
  }, [country, city, parkId])

  const loadTdb = useCallback(async () => {
    setTdbLoading(true)
    try {
      const [s, b, p, i] = await Promise.all([
        getTopDriverBehaviorSummary({ from, to, country: country || undefined, city: city || undefined, park_id: parkId || undefined }),
        getTopDriverBehaviorBenchmarks({}),
        getTopDriverBehaviorPatterns({ segment_current: segmentCurrent || undefined, limit: 100 }),
        getTopDriverBehaviorPlaybookInsights({ country: country || undefined, city: city || undefined })
      ])
      setTdbSummary(s)
      setTdbBenchmarks(b)
      setTdbPatterns(p)
      setTdbInsights((i && i.data) ? i.data : [])
    } catch (e) {
      setTdbSummary(null)
      setTdbBenchmarks({ data: [] })
      setTdbPatterns({ data: [] })
      setTdbInsights([])
    } finally {
      setTdbLoading(false)
    }
  }, [from, to, country, city, parkId, segmentCurrent])

  useEffect(() => {
    if (subTab === 'top_driver_behavior') loadTdb()
  }, [subTab, loadTdb])

  const totalCohortPages = Math.max(1, Math.ceil(cohorts.total / cohortPageSize))
  const segments = ['LEGEND', 'ELITE', 'FT', 'PT', 'CASUAL', 'OCCASIONAL', 'DORMANT']

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 border-b border-gray-200 pb-2">
        <button
          onClick={() => setSubTab('cohorts')}
          className={`px-3 py-1.5 rounded text-sm ${subTab === 'cohorts' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
        >
          Cohortes y acciones
        </button>
        <button
          onClick={() => setSubTab('top_driver_behavior')}
          className={`px-3 py-1.5 rounded text-sm ${subTab === 'top_driver_behavior' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
        >
          Top Driver Behavior
        </button>
      </div>

      {/* Filters */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2">
        <div>
          <label className="block text-xs text-gray-500">Rango temporal</label>
          <select value={timeRangePreset} onChange={(e) => setTimeRangePreset(e.target.value)} className="w-full border rounded px-2 py-1 text-sm">
            {TIME_RANGE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        {timeRangePreset === 'custom' && (
          <>
            <div>
              <label className="block text-xs text-gray-500">Desde</label>
              <input type="date" value={from} onChange={(e) => handleFromChange(e.target.value)} className="w-full border rounded px-2 py-1 text-sm" />
            </div>
            <div>
              <label className="block text-xs text-gray-500">Hasta</label>
              <input type="date" value={to} onChange={(e) => handleToChange(e.target.value)} className="w-full border rounded px-2 py-1 text-sm" />
            </div>
          </>
        )}
        {timeRangePreset !== 'custom' && (
          <div className="col-span-2 flex items-end gap-1 text-xs text-gray-500">
            {from} → {to}
          </div>
        )}
        <div>
          <label className="block text-xs text-gray-500">País</label>
          <select value={country} onChange={(e) => setCountry(e.target.value)} className="w-full border rounded px-2 py-1 text-sm">
            <option value="">Todos</option>
            {(geo.countries || []).map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500">Ciudad</label>
          <select value={city} onChange={(e) => setCity(e.target.value)} className="w-full border rounded px-2 py-1 text-sm">
            <option value="">Todas</option>
            {(geo.cities || []).map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500">Parque</label>
          <select value={parkId} onChange={(e) => setParkId(e.target.value)} className="w-full border rounded px-2 py-1 text-sm">
            <option value="">Todos</option>
            {(geo.parks || []).map((p) => <option key={p.park_id} value={p.park_id}>{p.park_name || p.park_id}</option>)}
          </select>
        </div>
        {subTab === 'cohorts' && (
          <>
            <div>
              <label className="block text-xs text-gray-500">Segmento</label>
              <select value={segmentCurrent} onChange={(e) => setSegmentCurrent(e.target.value)} className="w-full border rounded px-2 py-1 text-sm">
                <option value="">Todos</option>
                {segments.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500">Prioridad</label>
              <select value={priority} onChange={(e) => setPriority(e.target.value)} className="w-full border rounded px-2 py-1 text-sm">
                <option value="">Todas</option>
                <option value="high">Alta</option>
                <option value="medium">Media</option>
                <option value="low">Baja</option>
              </select>
            </div>
          </>
        )}
        {subTab === 'top_driver_behavior' && (
          <div>
            <label className="block text-xs text-gray-500">Segmento</label>
            <select value={segmentCurrent} onChange={(e) => setSegmentCurrent(e.target.value)} className="w-full border rounded px-2 py-1 text-sm">
              <option value="">Todos</option>
              <option value="ELITE">ELITE</option>
              <option value="LEGEND">LEGEND</option>
              <option value="FT">FT</option>
            </select>
          </div>
        )}
      </div>

      {subTab === 'cohorts' && (
        <>
          {/* KPI cards — decision colors and derived rates */}
          {(() => {
            const act = Number(summary?.actionable_drivers) || 0
            const convPct = act > 0 ? ((Number(summary?.near_upgrade_opportunities) || 0) / act) * 100 : null
            const reactPct = act > 0 ? ((Number(summary?.recoverable_drivers) || 0) / act) * 100 : null
            const downgPct = act > 0 ? ((Number(summary?.high_value_at_risk) || 0) / act) * 100 : null
            const convDec = conversionRateDecision(convPct)
            const reactDec = reactivationRateDecision(reactPct)
            const downgDec = downgradeRateDecision(downgPct)
            return (
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                <div className="bg-white rounded border p-3 shadow-sm">
                  <div className="text-xs text-gray-500">Conductores accionables</div>
                  <div className="text-xl font-semibold">{formatNum(summary?.actionable_drivers)}</div>
                </div>
                <div className="bg-white rounded border p-3 shadow-sm">
                  <div className="text-xs text-gray-500">Cohortes detectados</div>
                  <div className="text-xl font-semibold">{formatNum(summary?.cohorts_detected)}</div>
                </div>
                <div className={`bg-white rounded border p-3 shadow-sm border-l-4 ${summary?.high_priority_cohorts > 0 ? 'border-l-red-500' : 'border-l-gray-200'}`}>
                  <div className="text-xs text-gray-500">Cohortes alta prioridad</div>
                  <div className={`text-xl font-semibold ${summary?.high_priority_cohorts > 0 ? 'text-red-600' : 'text-gray-700'}`}>
                    {formatNum(summary?.high_priority_cohorts)}
                  </div>
                  <div className="text-xs text-gray-400">—</div>
                </div>
                <div className={`rounded border p-3 shadow-sm ${decisionColorClasses[reactDec]}`}>
                  <div className="text-xs opacity-90">Tasa reactivación</div>
                  <div className="text-xl font-semibold">{convPct != null ? (reactPct ?? 0).toFixed(1) + '%' : '—'}</div>
                  <div className="text-xs">↑ —</div>
                </div>
                <div className={`rounded border p-3 shadow-sm ${decisionColorClasses[convDec]}`}>
                  <div className="text-xs opacity-90">Tasa conversión (cerca subir)</div>
                  <div className="text-xl font-semibold">{convPct != null ? (convPct ?? 0).toFixed(1) + '%' : '—'}</div>
                  <div className="text-xs">↑ —</div>
                </div>
                <div className={`rounded border p-3 shadow-sm ${decisionColorClasses[downgDec]}`}>
                  <div className="text-xs opacity-90">Riesgo bajada (% cohorte)</div>
                  <div className="text-xl font-semibold">{downgPct != null ? (downgPct ?? 0).toFixed(1) + '%' : '—'}</div>
                  <div className="text-xs">↓ —</div>
                </div>
              </div>
            )
          })()}

          {/* Time context */}
          <p className="text-xs text-gray-500">{getDecisionContextLabel(BASELINE_WEEKS)} · Cada cohorte corresponde a una semana cerrada en el rango.</p>

          {/* Recommended actions panel */}
          <div className="bg-white rounded border p-4 shadow-sm">
            <h3 className="font-semibold text-gray-800 mb-2">Acciones recomendadas</h3>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {(recommendations.data || []).slice(0, 6).map((rec, i) => (
                <div key={i} className="border rounded p-3 bg-gray-50">
                  <div className="font-medium text-gray-800">{rec.action_name}</div>
                  <div className="text-xs text-gray-500 mt-1">
                    {COHORT_LABELS[rec.cohort_type] || rec.cohort_type} · {rec.cohort_size} conductores · {rec.week_label || rec.week_start}
                  </div>
                  <div className="text-xs text-gray-600 mt-1">Base: {getDecisionContextLabel(BASELINE_WEEKS)} · Cambio promedio: {formatPct(rec.avg_delta_pct)}</div>
                  <div className="text-sm text-gray-700 mt-1">{COHORT_RATIONALE[rec.cohort_type] || rec.action_objective}</div>
                  <div className="flex items-center gap-2 mt-2 flex-wrap">
                    <span className={`text-xs px-1.5 py-0.5 rounded ${rec.suggested_priority === 'high' ? 'bg-red-100 text-red-800' : 'bg-gray-200 text-gray-700'}`}>
                      {PRIORITY_LABELS[rec.suggested_priority] || rec.suggested_priority}
                    </span>
                    <span className="text-xs text-gray-500">{rec.suggested_channel}</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => loadCohortDetail(rec.cohort_type, rec.week_start)}
                    className="mt-2 text-sm text-blue-600 hover:underline"
                  >
                    Ver cohorte
                  </button>
                </div>
              ))}
            </div>
            {(recommendations.data || []).length === 0 && (
              <p className="text-gray-500 text-sm">No hay recomendaciones para el rango seleccionado.</p>
            )}
          </div>

          {/* Cohort table */}
          <div className="bg-white rounded border shadow-sm overflow-x-auto">
            <div className="p-2 flex justify-between items-center border-b">
              <h3 className="font-semibold text-gray-800">Cohortes</h3>
              <a href={getActionEngineExportUrl(filters)} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:underline">
                Exportar CSV
              </a>
            </div>
            {error && <p className="p-2 text-red-600 text-sm">{error}</p>}
            {loading ? (
              <p className="p-4 text-gray-500">Cargando…</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-100 border-b">
                    <th colSpan={4} className="text-left p-2 font-medium text-gray-700">Cohort info</th>
                    <th colSpan={2} className="text-right p-2 font-medium text-gray-700">Comportamiento</th>
                    <th colSpan={5} className="text-left p-2 font-medium text-gray-700">Acciones</th>
                  </tr>
                  <tr className="bg-gray-50 border-b">
                    <th className="text-left p-2">Cohorte</th>
                    <th className="text-right p-2">Semana</th>
                    <th className="text-right p-2">Tamaño</th>
                    <th className="text-right p-2">Segmento dom.</th>
                    <th className="text-right p-2">Riesgo avg</th>
                    <th className="text-right p-2">Delta %</th>
                    <th className="text-right p-2">Prioridad</th>
                    <th className="text-right p-2">Score</th>
                    <th className="text-left p-2">Canal</th>
                    <th className="text-left p-2">Objetivo / Rationale</th>
                    <th className="text-left p-2">Acción</th>
                  </tr>
                </thead>
                <tbody>
                  {(cohorts.data || []).map((c, i) => {
                    const score = cohortPriorityScore(c)
                    const scoreDec = priorityScoreDecision(score)
                    return (
                      <tr key={i} className="border-b hover:bg-gray-50">
                        <td className="py-3 px-2">{COHORT_LABELS[c.cohort_type] || c.cohort_type}</td>
                        <td className="py-3 px-2 text-right">{c.week_label || c.week_start}</td>
                        <td className="py-3 px-2 text-right">{formatNum(c.cohort_size)}</td>
                        <td className="py-3 px-2 text-right">{c.dominant_segment}</td>
                        <td className="py-3 px-2 text-right">{formatNum(c.avg_risk_score)}</td>
                        <td className={`py-3 px-2 text-right ${getDeltaPctColor(c.avg_delta_pct)}`}>{formatPct(c.avg_delta_pct)}</td>
                        <td className="py-3 px-2 text-right">{PRIORITY_LABELS[c.suggested_priority] || c.suggested_priority}</td>
                        <td className="py-3 px-2 text-right">
                          <span className={`inline-block px-1.5 py-0.5 rounded text-xs ${decisionColorClasses[scoreDec]}`}>{score}</span>
                        </td>
                        <td className="py-3 px-2">{c.suggested_channel}</td>
                        <td className="py-3 px-2 text-xs">{COHORT_RATIONALE[c.cohort_type] || c.action_objective}</td>
                        <td className="py-3 px-2">
                          <button
                            type="button"
                            onClick={() => loadCohortDetail(c.cohort_type, c.week_start)}
                            className="text-blue-600 hover:underline"
                          >
                            Ver
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}
            {totalCohortPages > 1 && (
              <div className="p-2 flex justify-between items-center border-t">
                <span className="text-sm text-gray-500">
                  {cohorts.total} cohortes
                </span>
                <div className="flex gap-1">
                  <button type="button" onClick={() => setCohortPage((p) => Math.max(0, p - 1))} disabled={cohortPage === 0} className="px-2 py-1 border rounded text-sm disabled:opacity-50">Anterior</button>
                  <span className="px-2 py-1 text-sm">{cohortPage + 1} / {totalCohortPages}</span>
                  <button type="button" onClick={() => setCohortPage((p) => p + 1)} disabled={cohortPage >= totalCohortPages - 1} className="px-2 py-1 border rounded text-sm disabled:opacity-50">Siguiente</button>
                </div>
              </div>
            )}
          </div>

          {/* Cohort drilldown modal */}
          {drillCohort && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true">
              <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
                <div className="p-4 border-b flex justify-between items-center">
                  <h3 className="font-semibold">
                    {COHORT_LABELS[drillCohort.cohort_type] || drillCohort.cohort_type} — {drillCohort.week_start}
                  </h3>
                  <button type="button" onClick={() => { setDrillCohort(null); setDrillData({ data: [], total: 0 }) }} className="text-gray-500 hover:text-gray-700 text-2xl leading-none">×</button>
                </div>
                <div className="px-4 pt-2 pb-2 border-b bg-gray-50 text-xs text-gray-600">
                  {getDecisionContextLabel(BASELINE_WEEKS)} · Acción sugerida: {COHORT_RATIONALE[drillCohort.cohort_type] || '—'}
                </div>
                <div className="p-4 overflow-auto flex-1">
                  {drillLoading ? (
                    <p className="text-gray-500">Cargando…</p>
                  ) : (
                    <>
                      <p className="text-sm text-gray-600 mb-2">{drillData.total} conductores en esta cohorte</p>
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="bg-gray-50 border-b">
                            <th className="text-left p-2">Conductor</th>
                            <th className="text-right p-2">Segmento</th>
                            <th className="text-right p-2">Viajes sem.</th>
                            <th className="text-right p-2">Baseline</th>
                            <th className="text-right p-2">Delta %</th>
                            <th className="text-left p-2">Estado conductual</th>
                            <th className="text-left p-2">Persistencia</th>
                            <th className="text-right p-2">Riesgo</th>
                            <th className="text-left p-2">Alerta</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(drillData.data || []).map((d, i) => (
                            <tr key={i} className="border-b hover:bg-gray-50">
                              <td className="p-2">{d.driver_name || d.driver_key}</td>
                              <td className="p-2 text-right">{d.segment_current}</td>
                              <td className="p-2 text-right">{formatNum(d.trips_current_week)}</td>
                              <td className="p-2 text-right">{formatNum(d.avg_trips_baseline)}</td>
                              <td className={`p-2 text-right ${getDeltaPctColor(d.delta_pct)}`}>{formatPct(d.delta_pct)}</td>
                              <td className="p-2">
                                <span className={`inline-block px-1.5 py-0.5 rounded text-xs ${BEHAVIOR_DIRECTION_COLORS[getBehaviorDirection(d)] || 'bg-gray-100'}`}>{getBehaviorDirection(d)}</span>
                              </td>
                              <td className="p-2 text-xs">{getPersistenceLabel(d)}</td>
                              <td className="p-2 text-right">{formatNum(d.risk_score)}</td>
                              <td className="p-2"><span className={`px-1.5 py-0.5 rounded text-xs ${SEMANTIC_ALERT_COLORS[d.alert_type] || 'bg-gray-100'}`}>{d.alert_type ?? '—'}</span></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </>
                  )}
                </div>
                <div className="p-4 border-t">
                  <a
                    href={getActionEngineExportUrl({ ...filters, cohort_type: drillCohort.cohort_type, week_start: drillCohort.week_start })}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-600 hover:underline"
                  >
                    Exportar esta cohorte
                  </a>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {subTab === 'top_driver_behavior' && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-white rounded border p-3 shadow-sm">
              <div className="text-xs text-gray-500">Elite</div>
              <div className="text-xl font-semibold">{formatNum(tdbSummary?.elite_drivers)}</div>
            </div>
            <div className="bg-white rounded border p-3 shadow-sm">
              <div className="text-xs text-gray-500">Legend</div>
              <div className="text-xl font-semibold">{formatNum(tdbSummary?.legend_drivers)}</div>
            </div>
            <div className="bg-white rounded border p-3 shadow-sm">
              <div className="text-xs text-gray-500">FT</div>
              <div className="text-xl font-semibold">{formatNum(tdbSummary?.ft_drivers)}</div>
            </div>
          </div>
          <div className="bg-white rounded border p-4 shadow-sm">
            <h3 className="font-semibold text-gray-800 mb-2">Benchmarks</h3>
            {tdbLoading ? (
              <p className="text-gray-500">Cargando…</p>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b">
                    <th className="text-left p-2">Segmento</th>
                    <th className="text-right p-2">Conductores</th>
                    <th className="text-right p-2">Viajes/sem avg</th>
                    <th className="text-right p-2">Consistencia avg</th>
                    <th className="text-right p-2">Semanas activas avg</th>
                  </tr>
                </thead>
                <tbody>
                  {(tdbBenchmarks.data || []).map((b, i) => (
                    <tr key={i} className="border-b">
                      <td className="p-2">{b.segment_current}</td>
                      <td className="p-2 text-right">{formatNum(b.driver_count)}</td>
                      <td className="p-2 text-right">{formatNum(b.avg_weekly_trips)}</td>
                      <td className="p-2 text-right">{formatNum(b.consistency_score_avg)}</td>
                      <td className="p-2 text-right">{formatNum(b.active_weeks_avg)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="bg-white rounded border p-4 shadow-sm">
            <h3 className="font-semibold text-gray-800 mb-2">Insights (playbook)</h3>
            <ul className="list-disc list-inside space-y-1 text-sm text-gray-700">
              {(tdbInsights || []).map((ins, i) => (
                <li key={i}><strong>{ins.title}:</strong> {ins.text}</li>
              ))}
            </ul>
          </div>
          <div className="bg-white rounded border p-4 shadow-sm">
            <h3 className="font-semibold text-gray-800 mb-2">Patrones (ciudad/parque)</h3>
            {tdbLoading ? (
              <p className="text-gray-500">Cargando…</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b">
                      <th className="text-left p-2">Segmento</th>
                      <th className="text-left p-2">País</th>
                      <th className="text-left p-2">Ciudad</th>
                      <th className="text-left p-2">Parque</th>
                      <th className="text-right p-2">Conductores</th>
                      <th className="text-right p-2">% segmento</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(tdbPatterns.data || []).slice(0, 50).map((p, i) => (
                      <tr key={i} className="border-b">
                        <td className="p-2">{p.segment_current}</td>
                        <td className="p-2">{p.country}</td>
                        <td className="p-2">{p.city}</td>
                        <td className="p-2">{p.park_name || p.park_id}</td>
                        <td className="p-2 text-right">{formatNum(p.driver_count)}</td>
                        <td className="p-2 text-right">{formatNum(p.pct_of_segment)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
          <div className="flex justify-end">
            <a href={getTopDriverBehaviorExportUrl({ from, to, country: country || undefined, city: city || undefined, park_id: parkId || undefined, segment_current: segmentCurrent || undefined })} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:underline">
              Exportar Top Driver Behavior
            </a>
          </div>
        </>
      )}

      {/* Help panel */}
      <div className="border rounded bg-gray-50 p-4">
        <button type="button" onClick={() => setShowHelp(!showHelp)} className="font-medium text-gray-800">
          {showHelp ? '▼' : '▶'} Ayuda — Segmento, Baseline, Delta, Tendencia, Riesgo, Action Engine
        </button>
        {showHelp && (
          <div className="mt-2 text-sm text-gray-600 space-y-2">
            <p><strong>Segmento:</strong> Nivel de actividad según viajes de la última semana cerrada.</p>
            <p><strong>Baseline:</strong> Promedio del comportamiento en las semanas previas configuradas (ej. 6).</p>
            <p><strong>Delta:</strong> Diferencia entre la última semana cerrada y el baseline. Negativo = empeora; positivo = mejora.</p>
            <p><strong>Tendencia / Estado conductual:</strong> Dirección reciente: Empeorando, Mejorando, En recuperación, Estable o Volátil.</p>
            <p><strong>Riesgo:</strong> Prioridad operativa del caso o cohorte (Risk Score y banda).</p>
            <p><strong>Action Engine:</strong> Agrupa conductores en cohortes accionables según su comportamiento y riesgo. Cada cohorte tiene una acción y canal sugeridos.</p>
            <p><strong>Behavioral Alerts:</strong> Evalúa desviaciones individuales respecto al patrón histórico del conductor.</p>
            <p><strong>Top Driver Behavior:</strong> Analiza patrones de Elite y Legend (y FT) para benchmarks replicables.</p>
          </div>
        )}
      </div>
    </div>
  )
}
