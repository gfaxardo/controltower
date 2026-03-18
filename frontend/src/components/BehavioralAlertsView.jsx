/**
 * Behavioral Alerts — Desviación de conductores vs su propia línea base histórica.
 * Filtros, KPIs, panel de insight, tabla de alertas, drilldown por conductor, panel semántico, export.
 */
import { useState, useEffect, useCallback } from 'react'
import {
  getSupplyGeo,
  getBehaviorAlertsSummary,
  getBehaviorAlertsInsight,
  getBehaviorAlertsDrivers,
  getBehaviorAlertsDriverDetail,
  getBehaviorAlertsExportUrl
} from '../services/api'
import {
  getBehaviorDirection,
  getPersistenceLabel,
  getDeltaPctColor,
  getDecisionContextLabel,
  BEHAVIOR_DIRECTION_COLORS,
  RISK_BAND_COLORS as SEMANTIC_RISK_BAND_COLORS,
  ALERT_COLORS as SEMANTIC_ALERT_COLORS
} from '../constants/explainabilitySemantics'
import { decisionColorClasses, severityToDecision } from '../theme/decisionColors'
import DataStateBadge from './DataStateBadge'

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

const ALERT_COLORS = SEMANTIC_ALERT_COLORS

const SEVERITY_ORDER = { critical: 0, moderate: 1, positive: 2, neutral: 3 }

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

function trendIcon (deltaPct) {
  if (deltaPct == null) return '→'
  if (Number(deltaPct) < -0.01) return '↓'
  if (Number(deltaPct) > 0.01) return '↑'
  return '→'
}

/** Last trip human-readable: Hoy, Hace N días, o — si no hay dato */
function formatLastTrip (lastTripDate) {
  if (!lastTripDate) return '—'
  const d = new Date(lastTripDate)
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  d.setHours(0, 0, 0, 0)
  const diffDays = Math.floor((today - d) / (24 * 60 * 60 * 1000))
  if (diffDays === 0) return 'Hoy'
  if (diffDays === 1) return 'Hace 1 día'
  if (diffDays <= 31) return `Hace ${diffDays} días`
  return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })
}

// Leyenda de segmentos (tipos de alerta) — on demand, no sobrecargar UI
const SEGMENT_LEGEND = [
  { type: 'Sudden Stop', short: 'Dejó de producir en la semana analizada (tenía actividad previa).', detail: 'Conductor con actividad en baseline que en la semana actual pasa a 0 viajes.' },
  { type: 'Critical Drop', short: 'Caída abrupta y severa vs baseline.', detail: 'Baseline ≥40 viajes/sem, delta ≤ -30%, al menos 4 semanas activas en ventana.' },
  { type: 'Moderate Drop', short: 'Caída relevante pero no extrema.', detail: 'Delta entre -30% y -15% vs baseline.' },
  { type: 'Silent Erosion', short: 'Deterioro progresivo sostenido.', detail: 'Al menos 3 semanas consecutivas en caída (sin ser Critical/Moderate Drop).' },
  { type: 'High Volatility', short: 'Comportamiento muy irregular entre semanas.', detail: 'Coeficiente de variación (stddev/avg) > 0,5 en baseline.' },
  { type: 'Strong Recovery', short: 'Recuperación clara vs baseline.', detail: 'Delta ≥ +30% y al menos 3 semanas activas en ventana.' },
  { type: 'Stable Performer', short: 'Estable dentro del rango esperado.', detail: 'No cumple ninguno de los criterios de alerta anteriores.' }
]

// Tooltips por columna (alineados al cálculo real del backend)
const COLUMN_TOOLTIPS = {
  Conductor: 'Nombre o ID del conductor.',
  País: 'País del park del conductor.',
  Ciudad: 'Ciudad del park.',
  Park: 'Nombre del park.',
  Segmento: 'Segmento de actividad en la semana analizada (p. ej. ELITE, FT) según viajes/semana.',
  'Viajes sem.': 'Viajes realizados en la semana analizada (trips_current_week).',
  'Base avg': 'Promedio de viajes del baseline (N semanas previas, excl. semana actual).',
  'Δ %': 'Variación porcentual entre semana analizada y baseline. Negativo = caída.',
  'Estado conductual': 'Resumen: Empeorando, Mejorando, En recuperación, Estable o Volátil (derivado de delta y alerta).',
  Persistencia: 'Semanas consecutivas en deterioro o en recuperación (weeks_declining/rising_consecutively).',
  Alerta: 'Clasificación operativa: Sudden Stop, Critical Drop, Moderate Drop, Silent Erosion, High Volatility, Strong Recovery, Stable Performer. Una sola por conductor (precedencia estricta).',
  Severidad: 'Nivel de urgencia: critical, moderate, positive, neutral.',
  'Risk Score': 'Puntaje compuesto 0-100 (comportamiento, migración, fragilidad, valor).',
  'Risk Band': 'Banda categórica: stable (0-24), monitor (25-49), medium risk (50-74), high risk (75-100).',
  'Last Trip': 'Fecha del último viaje del conductor. Ayuda a distinguir caída reciente vs abandono histórico.',
  'Último viaje': 'Fecha del último viaje del conductor. Ayuda a distinguir caída reciente vs abandono histórico.',
  Acción: 'Abre el detalle del conductor.'
}

/** Minimal line chart: trips over weeks (data ordered oldest first) */
function DriverTripsLineChart ({ data }) {
  if (!data || data.length === 0) return <div className="text-xs text-gray-500">Sin datos</div>
  const values = data.map((r) => Number(r.trips_current_week) || 0)
  const max = Math.max(1, ...values)
  const min = Math.min(0, ...values)
  const range = max - min || 1
  const w = 400
  const h = 120
  const pad = { top: 8, right: 8, bottom: 24, left: 28 }
  const xScale = (i) => pad.left + (i / Math.max(1, data.length - 1)) * (w - pad.left - pad.right)
  const yScale = (v) => pad.top + h - pad.top - pad.bottom - ((v - min) / range) * (h - pad.top - pad.bottom)
  const points = values.map((v, i) => `${xScale(i)},${yScale(v)}`).join(' ')
  const segLabels = data.map((r) => r.week_label || r.week_start || '').slice(0, 8)
  return (
    <div className="overflow-x-auto">
      <svg width={w} height={h} className="min-w-full" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="xMidYMid meet">
        <line x1={pad.left} y1={h - pad.bottom} x2={w - pad.right} y2={h - pad.bottom} stroke="#e5e7eb" strokeWidth={1} />
        <line x1={pad.left} y1={pad.top} x2={pad.left} y2={h - pad.bottom} stroke="#e5e7eb" strokeWidth={1} />
        <polyline fill="none" stroke="#3b82f6" strokeWidth={2} strokeLinejoin="round" points={points} />
        {values.map((v, i) => (
          <circle key={i} cx={xScale(i)} cy={yScale(v)} r={3} fill="#3b82f6" />
        ))}
        {segLabels.map((label, i) => (
          <text key={i} x={xScale(i)} y={h - 6} textAnchor="middle" className="fill-gray-500" style={{ fontSize: 9 }}>{String(label).slice(-5)}</text>
        ))}
      </svg>
      <div className="flex justify-between mt-1 text-xs text-gray-500">
        <span>Segmento por semana: {data.map((r) => r.segment_current).filter(Boolean).join(' → ') || '—'}</span>
      </div>
    </div>
  )
}

export default function BehavioralAlertsView () {
  const today = new Date().toISOString().slice(0, 10)
  const initialRange = applyTimeRangePreset('60', today) || { from: today, to: today }
  const [timeRangePreset, setTimeRangePreset] = useState('60')
  const [from, setFrom] = useState(initialRange.from)
  const [to, setTo] = useState(initialRange.to)
  const [baselineWindow, setBaselineWindow] = useState(6)
  const [country, setCountry] = useState('')
  const [city, setCity] = useState('')
  const [parkId, setParkId] = useState('')
  const [segmentCurrent, setSegmentCurrent] = useState('')
  const [movementType, setMovementType] = useState('')
  const [alertType, setAlertType] = useState('')
  const [severity, setSeverity] = useState('')
  const [riskBand, setRiskBand] = useState('')
  const [geo, setGeo] = useState({ countries: [], cities: [], parks: [] })
  const [summary, setSummary] = useState(null)
  const [insight, setInsight] = useState(null)
  const [drivers, setDrivers] = useState({ data: [], total: 0 })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [orderBy, setOrderBy] = useState('risk_score')
  const [orderDir, setOrderDir] = useState('desc')
  const [page, setPage] = useState(0)
  const pageSize = 50
  const [showGlossary, setShowGlossary] = useState(false)
  const [detailDriverKey, setDetailDriverKey] = useState(null)
  const [detailData, setDetailData] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)

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
    baseline_window: baselineWindow,
    country: country || undefined,
    city: city || undefined,
    park_id: parkId || undefined,
    segment_current: segmentCurrent || undefined,
    movement_type: movementType || undefined,
    alert_type: alertType || undefined,
    severity: severity || undefined,
    risk_band: riskBand || undefined
  }

  const loadSummary = useCallback(async () => {
    try {
      const s = await getBehaviorAlertsSummary({ ...filters, from, to })
      setSummary(s)
    } catch (e) {
      setSummary(null)
    }
  }, [from, to, country, city, parkId, segmentCurrent, movementType, alertType, severity, riskBand])

  const loadInsight = useCallback(async () => {
    try {
      const i = await getBehaviorAlertsInsight({ from, to, country, city, park_id: parkId, segment_current: segmentCurrent, movement_type: movementType, alert_type: alertType, severity, risk_band: riskBand })
      setInsight(i)
    } catch (e) {
      setInsight(null)
    }
  }, [from, to, country, city, parkId, segmentCurrent, movementType, alertType, severity, riskBand])

  const loadDrivers = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await getBehaviorAlertsDrivers({
        ...filters,
        from,
        to,
        limit: pageSize,
        offset: page * pageSize,
        order_by: orderBy,
        order_dir: orderDir
      })
      setDrivers({ data: r.data || [], total: r.total || 0 })
    } catch (e) {
      setError(e.message || 'Error al cargar alertas')
      setDrivers({ data: [], total: 0 })
    } finally {
      setLoading(false)
    }
  }, [from, to, country, city, parkId, segmentCurrent, movementType, alertType, severity, riskBand, page, orderBy, orderDir])

  useEffect(() => {
    loadSummary()
    loadInsight()
  }, [loadSummary, loadInsight])

  useEffect(() => {
    loadDrivers()
  }, [loadDrivers])

  const loadDriverDetail = useCallback(async (key) => {
    setDetailDriverKey(key)
    setDetailLoading(true)
    try {
      const r = await getBehaviorAlertsDriverDetail({
        driver_key: key,
        from,
        to,
        weeks: 8
      })
      setDetailData(r)
    } catch (e) {
      setDetailData(null)
    } finally {
      setDetailLoading(false)
    }
  }, [from, to])

  const segments = ['LEGEND', 'ELITE', 'FT', 'PT', 'CASUAL', 'OCCASIONAL', 'DORMANT']
  const movementTypes = ['upshift', 'downshift', 'stable', 'drop', 'new']
  // Precedencia: Sudden Stop, Critical Drop, Moderate Drop, Silent Erosion, High Volatility, Strong Recovery, Stable Performer
  const alertTypes = ['Sudden Stop', 'Critical Drop', 'Moderate Drop', 'Silent Erosion', 'High Volatility', 'Strong Recovery', 'Stable Performer']
  const severities = ['critical', 'moderate', 'positive', 'neutral']
  const riskBands = ['high risk', 'medium risk', 'monitor', 'stable']
  const RISK_BAND_COLORS = SEMANTIC_RISK_BAND_COLORS
  const [showSegmentLegend, setShowSegmentLegend] = useState(false)
  const columnToOrderKey = { Conductor: 'driver_name', País: 'country', Ciudad: 'city', Park: 'park_name', Segmento: 'segment_current', 'Viajes sem.': 'trips_current_week', 'Base avg': 'avg_trips_baseline', 'Δ %': 'delta_pct', Alerta: 'alert_type', Severidad: 'severity', 'Risk Score': 'risk_score', 'Risk Band': 'risk_band', 'Último viaje': 'last_trip_date' }
  const handleSort = (col) => {
    const key = columnToOrderKey[col]
    if (!key) return
    if (orderBy === key) setOrderDir((d) => (d === 'desc' ? 'asc' : 'desc'))
    else { setOrderBy(key); setOrderDir(key === 'risk_score' ? 'desc' : 'asc') }
    setPage(0)
  }
  const sortIcon = (col) => {
    const key = columnToOrderKey[col]
    if (!key || orderBy !== key) return <span className="opacity-50 ml-0.5" aria-hidden>↕</span>
    return orderDir === 'desc' ? <span className="text-blue-600 font-bold ml-0.5" aria-label="Orden descendente">↓</span> : <span className="text-blue-600 font-bold ml-0.5" aria-label="Orden ascendente">↑</span>
  }

  const totalPages = Math.max(1, Math.ceil(drivers.total / pageSize))

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold text-gray-800">Behavioral Alerts</h2>
        <DataStateBadge state="under_review" />
      </div>
      <p className="text-sm text-gray-600">
        Desviación de conductores respecto a su propia línea base histórica. No modifica Migration ni Driver Lifecycle.
      </p>
      <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">
        Pantalla en revisión. Los tiempos de carga pueden ser elevados; no considerar datos como definitivos.
      </p>

      {/* Filters */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Rango temporal</label>
            <select value={timeRangePreset} onChange={(e) => setTimeRangePreset(e.target.value)} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              {TIME_RANGE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          {timeRangePreset === 'custom' && (
            <>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Desde</label>
                <input type="date" value={from} onChange={(e) => handleFromChange(e.target.value)} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Hasta</label>
                <input type="date" value={to} onChange={(e) => handleToChange(e.target.value)} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" />
              </div>
            </>
          )}
          {timeRangePreset !== 'custom' && (
            <div className="flex items-end text-xs text-gray-500">
              {from} → {to}
            </div>
          )}
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Ventana baseline (semanas)</label>
            <select value={baselineWindow} onChange={(e) => setBaselineWindow(Number(e.target.value))} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              <option value={4}>4</option>
              <option value={6}>6</option>
              <option value={8}>8</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">País</label>
            <select value={country} onChange={(e) => { setCountry(e.target.value); setCity(''); setParkId(''); }} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              <option value="">Todos</option>
              {geo.countries?.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Ciudad</label>
            <select value={city} onChange={(e) => { setCity(e.target.value); setParkId(''); }} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              <option value="">Todas</option>
              {geo.cities?.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Park</label>
            <select value={parkId} onChange={(e) => setParkId(e.target.value)} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              <option value="">Todos</option>
              {geo.parks?.map((p) => <option key={p.park_id} value={p.park_id}>{p.park_name} — {p.city}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Segmento actual</label>
            <select value={segmentCurrent} onChange={(e) => setSegmentCurrent(e.target.value)} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              <option value="">Todos</option>
              {segments.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Tipo movimiento</label>
            <select value={movementType} onChange={(e) => setMovementType(e.target.value)} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              <option value="">Todos</option>
              {movementTypes.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div className="relative">
            <label className="block text-xs font-medium text-gray-500 mb-1">
              Tipo alerta
              <button type="button" onClick={() => setShowSegmentLegend((v) => !v)} className="ml-2 inline-flex items-center gap-1 px-2 py-0.5 rounded border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 text-xs font-medium" title="Leyenda de segmentos" aria-label="Leyenda de segmentos">
                <span aria-hidden>?</span> Leyenda
              </button>
            </label>
            {showSegmentLegend && (
              <div className="absolute left-0 top-full z-20 mt-1 w-[320px] max-w-[90vw] rounded-lg border border-gray-200 bg-white shadow-lg p-3 text-sm text-gray-700">
                <div className="font-medium text-gray-900 mb-2">Leyenda de alertas</div>
                <ul className="space-y-1.5">
                  {SEGMENT_LEGEND.map(({ type, short }) => (
                    <li key={type}><strong>{type}:</strong> {short}</li>
                  ))}
                </ul>
                <p className="mt-2 text-xs text-gray-500">Precedencia estricta: una sola clasificación por conductor.</p>
                <button type="button" onClick={() => setShowSegmentLegend(false)} className="mt-2 text-xs text-blue-600 hover:underline">Cerrar</button>
              </div>
            )}
            <select value={alertType} onChange={(e) => setAlertType(e.target.value)} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              <option value="">Todos</option>
              {alertTypes.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Severidad</label>
            <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              <option value="">Todas</option>
              {severities.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Banda de riesgo</label>
            <select value={riskBand} onChange={(e) => setRiskBand(e.target.value)} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              <option value="">Todas</option>
              {riskBands.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>
        </div>
      </div>

      {/* Risk counters / KPI cards — Total, por tipo de alerta (precedencia), riesgo. Máx 5 columnas para que no queden comprimidas. */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
        {[
          { key: 'drivers_monitored', label: 'Total en alertas', color: 'bg-blue-50 border-blue-200 text-blue-800' },
          { key: 'sudden_stop', label: 'Sudden Stop', color: 'bg-red-50 border-red-200 text-red-800' },
          { key: 'critical_drops', label: 'Caídas críticas', color: 'bg-red-50 border-red-200 text-red-800' },
          { key: 'moderate_drops', label: 'Caídas moderadas', color: 'bg-orange-50 border-orange-200 text-orange-800' },
          { key: 'silent_erosion', label: 'Erosión silenciosa', color: 'bg-yellow-50 border-yellow-200 text-yellow-800' },
          { key: 'strong_recoveries', label: 'Recuperaciones', color: 'bg-green-50 border-green-200 text-green-800' },
          { key: 'high_volatility', label: 'Alta volatilidad', color: 'bg-purple-50 border-purple-200 text-purple-800' },
          { key: 'stable_performer', label: 'Estables', color: 'bg-gray-50 border-gray-200 text-gray-800' },
          { key: 'high_risk_drivers', label: 'Alto riesgo', color: 'bg-red-50 border-red-200 text-red-800' },
          { key: 'medium_risk_drivers', label: 'Riesgo medio', color: 'bg-orange-50 border-orange-200 text-orange-800' }
        ].map(({ key, label, color }) => (
          <div key={key} className={`rounded-lg border p-3 ${color}`}>
            <div className="text-xs font-medium opacity-90">{label}</div>
            <div className="text-xl font-semibold mt-1">{formatNum(summary?.[key] ?? 0)}</div>
          </div>
        ))}
      </div>

      {/* Insight panel */}
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
        <div className="text-sm font-medium text-amber-900 mb-1">Resumen</div>
        <div className="text-sm text-amber-800">{insight?.insight_text ?? 'Cargando…'}</div>
      </div>

      {/* Help / Semantic panel */}
      <div>
        <button type="button" onClick={() => setShowGlossary(!showGlossary)} className="text-sm text-blue-600 hover:underline">
          {showGlossary ? 'Ocultar' : 'Ver'} explicación: Segmento, Baseline, Delta, Tendencia, Riesgo
        </button>
        {showGlossary && (
          <div className="mt-2 bg-gray-50 border border-gray-200 rounded p-4 text-sm text-gray-700 space-y-2">
            <p><strong>Segmento:</strong> Nivel de actividad según viajes de la última semana cerrada analizada.</p>
            <p><strong>Baseline:</strong> Promedio de viajes en las N semanas previas (ventana configurada). La comparación es &quot;última semana vs baseline&quot;.</p>
            <p><strong>Delta (Δ %):</strong> Diferencia en % entre la última semana cerrada y el baseline. Negativo = empeora; positivo = mejora.</p>
            <p><strong>Tendencia / Estado conductual:</strong> Dirección reciente: Empeorando, Mejorando, En recuperación, Estable o Volátil. Se deriva de delta, semanas consecutivas en caída/recuperación y tipo de alerta.</p>
            <p><strong>Persistencia:</strong> Cuántas semanas consecutivas el conductor lleva en deterioro o en recuperación.</p>
            <p><strong>Riesgo (Risk Score):</strong> Prioridad operativa 0-100. Bandas: stable (0-24), monitor (25-49), medium risk (50-74), high risk (75-100).</p>
            <p><strong>Behavioral Alerts:</strong> Evalúa desviaciones individuales respecto al patrón histórico del propio conductor.</p>
            <p><strong>Taxonomía de segmentos (viajes/semana):</strong> DORMANT 0, OCCASIONAL 1-4, CASUAL 5-19, PT 20-59, FT 60-119, ELITE 120-179, LEGEND 180+.</p>
          </div>
        )}
      </div>

      {/* Export — Recovery List: lista accionable para call center / recuperación. Visible y destacado. */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="text-xs font-medium text-gray-600 mb-2">Exportar datos</div>
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-gray-500 text-sm mr-1">Recovery List (recomendado):</span>
          <a href={getBehaviorAlertsExportUrl({ ...filters, from, to, format: 'csv' })} download="recovery_list_conductores.csv" className="inline-flex items-center px-4 py-2 rounded-md border-2 border-green-600 bg-green-50 text-green-800 text-sm font-semibold hover:bg-green-100">
            Export Recovery List (CSV)
          </a>
          <a href={getBehaviorAlertsExportUrl({ ...filters, from, to, format: 'excel' })} download="recovery_list_conductores.xlsx" className="inline-flex items-center px-4 py-2 rounded-md border-2 border-green-600 bg-green-50 text-green-800 text-sm font-semibold hover:bg-green-100">
            Export Recovery List (Excel)
          </a>
          <span className="text-gray-400 mx-2">|</span>
          <a href={getBehaviorAlertsExportUrl({ ...filters, from, to, format: 'csv' })} download="behavior_alerts.csv" className="inline-flex items-center px-3 py-1.5 rounded border border-gray-300 bg-white text-sm text-gray-700 hover:bg-gray-50">
            CSV genérico
          </a>
          <a href={getBehaviorAlertsExportUrl({ ...filters, from, to, format: 'excel' })} download="behavior_alerts.xlsx" className="inline-flex items-center px-3 py-1.5 rounded border border-gray-300 bg-white text-sm text-gray-700 hover:bg-gray-50">
            Excel genérico
          </a>
          <button
            type="button"
            onClick={() => {
              const rows = drivers.data || []
              const headers = ['driver_id', 'driver_name', 'park', 'segment', 'alert_type', 'severity', 'trips_last_week', 'trips_baseline', 'delta_percent', 'recommended_action']
              const toRow = (r) => [
                r.driver_key ?? '',
                (r.driver_name || r.driver_key) ?? '',
                r.park_name ?? r.park_id ?? '',
                r.segment_current ?? '',
                r.alert_type ?? '',
                r.severity ?? '',
                formatNum(r.trips_current_week),
                formatNum(r.avg_trips_baseline),
                r.delta_pct != null ? (Number(r.delta_pct) * 100).toFixed(1) : '',
                r.recommended_action ?? (r.alert_type ?? '')
              ]
              const csv = [headers.join(','), ...rows.map((r) => toRow(r).map((c) => `"${String(c).replace(/"/g, '""')}"`).join(','))].join('\r\n')
              const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url
              a.download = `conductores_alertas_${from}_${to}.csv`
              a.click()
              URL.revokeObjectURL(url)
            }}
            className="inline-flex items-center px-3 py-1.5 rounded border border-gray-300 bg-white text-sm text-gray-700 hover:bg-gray-50"
          >
            Exportar conductores (CSV filtrado)
          </button>
        </div>
      </div>

      {/* Time context */}
      <p className="text-xs text-gray-500">{getDecisionContextLabel(baselineWindow)} · Semana analizada: semana cerrada en el rango seleccionado.</p>

      {/* Alerts table — scroll horizontal en móvil/tablet para ver todas las columnas (incl. Último viaje). */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {error && <div className="p-4 bg-red-50 text-red-700 text-sm">{error}</div>}
        {loading && <div className="p-4 text-gray-500 text-sm">Cargando…</div>}
        <p className="px-4 py-1 text-xs text-gray-500 bg-gray-50 border-b border-gray-100">Desliza horizontalmente si no ves todas las columnas (p. ej. Último viaje).</p>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-100 border-b border-gray-200">
              <tr>
                {[
                  { label: 'Conductor', align: 'left', sortable: true },
                  { label: 'País', align: 'left', sortable: true },
                  { label: 'Ciudad', align: 'left', sortable: true },
                  { label: 'Park', align: 'left', sortable: true },
                  { label: 'Segmento', align: 'left', sortable: true },
                  { label: 'Viajes sem.', align: 'right', sortable: true },
                  { label: 'Base avg', align: 'right', sortable: true },
                  { label: 'Δ %', align: 'right', sortable: true },
                  { label: 'Estado conductual', align: 'left', sortable: false },
                  { label: 'Persistencia', align: 'left', sortable: false },
                  { label: 'Alerta', align: 'left', sortable: true },
                  { label: 'Severidad', align: 'left', sortable: true },
                  { label: 'Risk Score', align: 'right', sortable: true },
                  { label: 'Risk Band', align: 'left', sortable: true },
                  { label: 'Último viaje', align: 'left', sortable: true },
                  { label: 'Acción', align: 'left', sortable: false }
                ].map(({ label, align, sortable }) => (
                  <th
                    key={label}
                    className={`py-2 px-3 font-medium text-gray-700 ${align === 'right' ? 'text-right' : 'text-left'} ${sortable ? 'cursor-pointer hover:bg-gray-200 select-none' : ''} ${label === 'Último viaje' ? 'min-w-[7rem] whitespace-nowrap' : ''}`}
                    title={COLUMN_TOOLTIPS[label]}
                    onClick={sortable ? () => handleSort(label) : undefined}
                  >
                    {label}{sortable ? sortIcon(label) : ''}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {drivers.data.map((r) => (
                <tr
                  key={`${r.driver_key}-${r.week_start}`}
                  className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                  onClick={() => loadDriverDetail(r.driver_key)}
                >
                  <td className="py-2 px-3">{r.driver_name || r.driver_key}</td>
                  <td className="py-2 px-3">{r.country ?? '—'}</td>
                  <td className="py-2 px-3">{r.city ?? '—'}</td>
                  <td className="py-2 px-3">{r.park_name ?? '—'}</td>
                  <td className="py-2 px-3">{r.segment_current ?? '—'}</td>
                  <td className="py-2 px-3 text-right">{formatNum(r.trips_current_week)}</td>
                  <td className="py-2 px-3 text-right">{formatNum(r.avg_trips_baseline)}</td>
                  <td className={`py-2 px-3 text-right ${getDeltaPctColor(r.delta_pct)}`}>{formatPct(r.delta_pct)}</td>
                  <td className="py-2 px-3">
                    <span className={`inline-block px-2 py-0.5 rounded border text-xs ${BEHAVIOR_DIRECTION_COLORS[getBehaviorDirection(r)] || 'bg-gray-100'}`}>
                      {getBehaviorDirection(r)}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-xs text-gray-600">{getPersistenceLabel(r)}</td>
                  <td className="py-2 px-3">
                    <span className={`inline-block px-2 py-0.5 rounded border text-xs ${ALERT_COLORS[r.alert_type] || 'bg-gray-100'}`}>
                      {r.alert_type ?? '—'}
                    </span>
                  </td>
                  <td className="py-2 px-3">
                    <span className={`inline-block px-2 py-0.5 rounded border text-xs ${decisionColorClasses[severityToDecision[r.severity] || 'neutral']}`}>
                      {r.severity === 'critical' ? 'CRITICAL' : r.severity === 'moderate' ? 'WARNING' : (r.severity ? 'INFO' : '—')}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-right">{formatNum(r.risk_score)}</td>
                  <td className="py-2 px-3">
                    <span className={`inline-block px-2 py-0.5 rounded border text-xs ${RISK_BAND_COLORS[r.risk_band] || 'bg-gray-100'}`}>{r.risk_band ?? '—'}</span>
                  </td>
                  <td className="py-2 px-3 text-left min-w-[7rem]" title={r.last_trip_date ? new Date(r.last_trip_date).toLocaleString('es-ES') : ''}>{formatLastTrip(r.last_trip_date)}</td>
                  <td className="py-2 px-3">
                    <button type="button" className="text-blue-600 hover:underline text-xs" onClick={(ev) => { ev.stopPropagation(); loadDriverDetail(r.driver_key); }}>Ver detalle</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {drivers.data.length === 0 && !loading && <div className="p-4 text-gray-500 text-sm">Sin filas con los filtros actuales.</div>}
        {totalPages > 1 && (
          <div className="p-3 border-t border-gray-200 flex items-center justify-between">
            <span className="text-sm text-gray-600">Total: {drivers.total}</span>
            <div className="flex gap-2">
              <button type="button" disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="px-2 py-1 rounded border border-gray-300 text-sm disabled:opacity-50">Anterior</button>
              <span className="py-1 text-sm">Pág. {page + 1} de {totalPages}</span>
              <button type="button" disabled={page >= totalPages - 1} onClick={() => setPage((p) => p + 1)} className="px-2 py-1 rounded border border-gray-300 text-sm disabled:opacity-50">Siguiente</button>
            </div>
          </div>
        )}
      </div>

      {/* Driver drilldown modal */}
      {detailDriverKey != null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true" onClick={() => setDetailDriverKey(null)}>
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-800">Detalle conductor</h3>
              <button type="button" onClick={() => setDetailDriverKey(null)} className="text-gray-500 hover:text-gray-700 text-2xl leading-none">×</button>
            </div>
            {detailLoading && <div className="text-sm text-gray-500">Cargando…</div>}
            {!detailLoading && detailData?.data?.length > 0 && (
              <div className="space-y-4">
                <p className="text-sm text-gray-600">Conductor: {detailData.data[0].driver_name || detailData.driver_key} · {getDecisionContextLabel(baselineWindow)}</p>
                {/* Driver Behavior Timeline — Viajes últimas 8 semanas */}
                <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
                  <div className="text-xs font-medium text-gray-700 mb-2">Driver Behavior Timeline — Viajes últimas 8 semanas</div>
                  <DriverTripsLineChart data={[...(detailData.data || [])].reverse()} />
                </div>
                {(detailData.data[0].risk_score != null || detailData.risk_reasons?.length) && (
                  <div className="bg-amber-50 border border-amber-200 rounded p-3 text-sm">
                    <div className="font-medium text-amber-900 mb-1">Por qué se destaca este conductor</div>
                    {detailData.data[0].risk_score != null && (
                      <p>Risk Score: <strong>{detailData.data[0].risk_score}</strong> ({detailData.data[0].risk_band ?? '—'})</p>
                    )}
                    {detailData.data[0] && (
                      <p>Estado conductual: <span className={`inline-block px-1.5 py-0.5 rounded text-xs ${BEHAVIOR_DIRECTION_COLORS[getBehaviorDirection(detailData.data[0])] || ''}`}>{getBehaviorDirection(detailData.data[0])}</span> · Persistencia: {getPersistenceLabel(detailData.data[0])}</p>
                    )}
                    {detailData.risk_reasons?.length > 0 && (
                      <ul className="list-disc list-inside mt-1 text-amber-800">
                        {detailData.risk_reasons.map((reason, i) => <li key={i}>{reason}</li>)}
                      </ul>
                    )}
                  </div>
                )}
                <table className="min-w-full text-sm">
                  <thead className="bg-gray-100">
                    <tr>
                      <th className="text-left py-2 px-2">Semana</th>
                      <th className="text-right py-2 px-2">Viajes</th>
                      <th className="text-left py-2 px-2">Segmento</th>
                      <th className="text-right py-2 px-2">Base</th>
                      <th className="text-right py-2 px-2">Δ %</th>
                      <th className="text-left py-2 px-2">Estado</th>
                      <th className="text-left py-2 px-2">Persistencia</th>
                      <th className="text-left py-2 px-2">Alerta</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detailData.data.map((row) => (
                      <tr key={row.week_start} className="border-b border-gray-100">
                        <td className="py-2 px-2">{row.week_label ?? row.week_start}</td>
                        <td className="py-2 px-2 text-right">{formatNum(row.trips_current_week)}</td>
                        <td className="py-2 px-2">{row.segment_current ?? '—'}</td>
                        <td className="py-2 px-2 text-right">{formatNum(row.avg_trips_baseline)}</td>
                        <td className={`py-2 px-2 text-right ${getDeltaPctColor(row.delta_pct)}`}>{formatPct(row.delta_pct)}</td>
                        <td className="py-2 px-2"><span className={`px-1.5 py-0.5 rounded text-xs ${BEHAVIOR_DIRECTION_COLORS[getBehaviorDirection(row)] || ''}`}>{getBehaviorDirection(row)}</span></td>
                        <td className="py-2 px-2 text-xs">{getPersistenceLabel(row)}</td>
                        <td className="py-2 px-2"><span className={`px-1.5 py-0.5 rounded text-xs ${ALERT_COLORS[row.alert_type] || ''}`}>{row.alert_type ?? '—'}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {!detailLoading && (!detailData?.data?.length) && <p className="text-sm text-gray-500">Sin datos para este conductor en el rango.</p>}
          </div>
        </div>
      )}
    </div>
  )
}
