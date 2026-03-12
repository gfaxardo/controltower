/**
 * Driver Behavior — Desviación por conductor (ventanas reciente vs baseline).
 * Additive module: no reemplaza Behavioral Alerts ni Action Engine.
 * Filtros, KPIs, tabla accionable, drilldown con timeline, ayuda, export.
 */
import { useState, useEffect, useCallback } from 'react'
import {
  getSupplyGeo,
  getDriverBehaviorSummary,
  getDriverBehaviorDrivers,
  getDriverBehaviorDriverDetail,
  getDriverBehaviorExportUrl
} from '../services/api'
import {
  getDeltaPctColor,
  BEHAVIOR_DIRECTION_COLORS as BASE_BEHAVIOR_COLORS,
  RISK_BAND_COLORS
} from '../constants/explainabilitySemantics'
import { decisionColorClasses, severityToDecision } from '../theme/decisionColors'

const BEHAVIOR_DIRECTION_COLORS = {
  ...BASE_BEHAVIOR_COLORS,
  Recuperando: 'bg-green-100 text-green-800 border-green-200'
}

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

function persistenceLabel (r) {
  if (!r) return '—'
  const dec = (r.declining_weeks_consecutive ?? 0) | 0
  const ris = (r.rising_weeks_consecutive ?? 0) | 0
  if (dec >= 1) return `${dec} sem. empeorando`
  if (ris >= 1) return `${ris} sem. recuperando`
  return '—'
}

/** Compact line chart: trips per week (weekly = [{ week_label, trips }]) */
function DriverTripsLineChart ({ data }) {
  if (!data || data.length === 0) return <div className="text-xs text-gray-500">Sin datos</div>
  const values = data.map((r) => Number(r.trips) ?? 0)
  const max = Math.max(1, ...values)
  const min = Math.min(0, ...values)
  const range = max - min || 1
  const w = 400
  const h = 120
  const pad = { top: 8, right: 8, bottom: 24, left: 28 }
  const xScale = (i) => pad.left + (i / Math.max(1, data.length - 1)) * (w - pad.left - pad.right)
  const yScale = (v) => pad.top + h - pad.top - pad.bottom - ((v - min) / range) * (h - pad.top - pad.bottom)
  const points = values.map((v, i) => `${xScale(i)},${yScale(v)}`).join(' ')
  const labels = data.map((r) => r.week_label || r.week_start || '').slice(-8)
  return (
    <div className="overflow-x-auto">
      <svg width={w} height={h} className="min-w-full" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="xMidYMid meet">
        <line x1={pad.left} y1={h - pad.bottom} x2={w - pad.right} y2={h - pad.bottom} stroke="#e5e7eb" strokeWidth={1} />
        <line x1={pad.left} y1={pad.top} x2={pad.left} y2={h - pad.bottom} stroke="#e5e7eb" strokeWidth={1} />
        <polyline fill="none" stroke="#3b82f6" strokeWidth={2} strokeLinejoin="round" points={points} />
        {values.map((v, i) => (
          <circle key={i} cx={xScale(i)} cy={yScale(v)} r={3} fill="#3b82f6" />
        ))}
        {labels.map((label, i) => (
          <text key={i} x={xScale(i)} y={h - 6} textAnchor="middle" className="fill-gray-500" style={{ fontSize: 9 }}>{String(label).slice(-5)}</text>
        ))}
      </svg>
    </div>
  )
}

const WINDOW_OPTIONS = [4, 8, 16, 32]
const ALERT_TYPES = ['Sharp Degradation', 'Moderate Degradation', 'Sustained Degradation', 'Recovery', 'Dormant Risk', 'Churn Risk', 'High Volatility', 'Stable']
const SEVERITIES = ['critical', 'moderate', 'positive', 'neutral']
const RISK_BANDS = ['stable', 'monitor', 'medium risk', 'high risk']
const INACTIVITY_OPTIONS = [
  { value: 'active', label: 'Activo (0–3 días)' },
  { value: 'cooling', label: 'Enfriando (4–7 días)' },
  { value: 'dormant_risk', label: 'Riesgo dormido (8–14 días)' },
  { value: 'churn_risk', label: 'Riesgo churn (15+ días)' }
]
const SEGMENTS = ['LEGEND', 'ELITE', 'FT', 'PT', 'CASUAL', 'OCCASIONAL', 'DORMANT']

const ALERT_COLORS = {
  'Sharp Degradation': 'bg-red-100 text-red-800 border-red-200',
  'Moderate Degradation': 'bg-amber-100 text-amber-800 border-amber-200',
  'Sustained Degradation': 'bg-orange-100 text-orange-800 border-orange-200',
  Recovery: 'bg-green-100 text-green-800 border-green-200',
  'Dormant Risk': 'bg-red-100 text-red-800 border-red-200',
  'Churn Risk': 'bg-red-100 text-red-900 border-red-300',
  'High Volatility': 'bg-purple-100 text-purple-800 border-purple-200',
  Stable: 'bg-gray-100 text-gray-700 border-gray-200'
}

const INACTIVITY_COLORS = {
  active: 'bg-green-100 text-green-800 border-green-200',
  cooling: 'bg-amber-100 text-amber-800 border-amber-200',
  dormant_risk: 'bg-red-100 text-red-800 border-red-200',
  churn_risk: 'bg-red-100 text-red-900 border-red-300'
}

export default function DriverBehaviorView () {
  const [recentWeeks, setRecentWeeks] = useState(4)
  const [baselineWeeks, setBaselineWeeks] = useState(16)
  const [asOfWeek, setAsOfWeek] = useState('')
  const [country, setCountry] = useState('')
  const [city, setCity] = useState('')
  const [parkId, setParkId] = useState('')
  const [segmentCurrent, setSegmentCurrent] = useState('')
  const [alertType, setAlertType] = useState('')
  const [severity, setSeverity] = useState('')
  const [riskBand, setRiskBand] = useState('')
  const [inactivityStatus, setInactivityStatus] = useState('')
  const [minBaselineTrips, setMinBaselineTrips] = useState('')
  const [geo, setGeo] = useState({ countries: [], cities: [], parks: [] })
  const [summary, setSummary] = useState(null)
  const [drivers, setDrivers] = useState({ data: [], total: 0 })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [orderBy, setOrderBy] = useState('risk_score')
  const [orderDir, setOrderDir] = useState('desc')
  const [page, setPage] = useState(0)
  const pageSize = 50
  const [showHelp, setShowHelp] = useState(false)
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

  const filters = {
    recent_weeks: recentWeeks,
    baseline_weeks: baselineWeeks,
    ...(asOfWeek ? { as_of_week: asOfWeek } : {}),
    ...(country ? { country } : {}),
    ...(city ? { city } : {}),
    ...(parkId ? { park_id: parkId } : {}),
    ...(segmentCurrent ? { segment_current: segmentCurrent } : {}),
    ...(alertType ? { alert_type: alertType } : {}),
    ...(severity ? { severity } : {}),
    ...(riskBand ? { risk_band: riskBand } : {}),
    ...(inactivityStatus ? { inactivity_status: inactivityStatus } : {}),
    ...(minBaselineTrips !== '' && minBaselineTrips !== undefined ? { min_baseline_trips: Number(minBaselineTrips) } : {})
  }

  const loadSummary = useCallback(async () => {
    try {
      const s = await getDriverBehaviorSummary(filters)
      setSummary(s)
    } catch (e) {
      setSummary(null)
    }
  }, [recentWeeks, baselineWeeks, asOfWeek, country, city, parkId, segmentCurrent, alertType, severity, riskBand, inactivityStatus, minBaselineTrips])

  const loadDrivers = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await getDriverBehaviorDrivers({
        ...filters,
        limit: pageSize,
        offset: page * pageSize,
        order_by: orderBy,
        order_dir: orderDir
      })
      setDrivers({ data: r.data || [], total: r.total || 0 })
    } catch (e) {
      setError(e.message || 'Error al cargar conductores')
      setDrivers({ data: [], total: 0 })
    } finally {
      setLoading(false)
    }
  }, [recentWeeks, baselineWeeks, asOfWeek, country, city, parkId, segmentCurrent, alertType, severity, riskBand, inactivityStatus, minBaselineTrips, page, orderBy, orderDir])

  useEffect(() => { loadSummary() }, [loadSummary])
  useEffect(() => { loadDrivers() }, [loadDrivers])

  const loadDriverDetail = useCallback(async (key) => {
    setDetailDriverKey(key)
    setDetailLoading(true)
    try {
      const r = await getDriverBehaviorDriverDetail({
        driver_key: key,
        recent_weeks: recentWeeks,
        baseline_weeks: baselineWeeks,
        ...(asOfWeek ? { as_of_week: asOfWeek } : {})
      })
      setDetailData(r)
    } catch (e) {
      setDetailData(null)
    } finally {
      setDetailLoading(false)
    }
  }, [recentWeeks, baselineWeeks, asOfWeek])

  const totalPages = Math.max(1, Math.ceil(drivers.total / pageSize))

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-gray-800">Driver Behavior</h2>
      <p className="text-sm text-gray-600">
        Desviación individual por conductor: ventana reciente vs baseline histórica. Días desde último viaje, urgencia y acción sugerida. No sustituye Behavioral Alerts ni Action Engine.
      </p>

      {/* Filters */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Ventana reciente (semanas)</label>
            <select value={recentWeeks} onChange={(e) => setRecentWeeks(Number(e.target.value))} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              {WINDOW_OPTIONS.map((w) => <option key={w} value={w}>{w}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Ventana baseline (semanas)</label>
            <select value={baselineWeeks} onChange={(e) => setBaselineWeeks(Number(e.target.value))} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              {WINDOW_OPTIONS.map((w) => <option key={w} value={w}>{w}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Semana referencia (opcional)</label>
            <input type="date" value={asOfWeek} onChange={(e) => setAsOfWeek(e.target.value)} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" placeholder="Vacío = última" />
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
              {SEGMENTS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Tipo alerta</label>
            <select value={alertType} onChange={(e) => setAlertType(e.target.value)} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              <option value="">Todos</option>
              {ALERT_TYPES.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Severidad</label>
            <select value={severity} onChange={(e) => setSeverity(e.target.value)} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              <option value="">Todas</option>
              {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Banda riesgo</label>
            <select value={riskBand} onChange={(e) => setRiskBand(e.target.value)} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              <option value="">Todas</option>
              {RISK_BANDS.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Estado inactividad</label>
            <select value={inactivityStatus} onChange={(e) => setInactivityStatus(e.target.value)} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              <option value="">Todos</option>
              {INACTIVITY_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-500 mb-1">Mín. viajes baseline (opc.)</label>
            <input type="number" min={0} step={1} value={minBaselineTrips} onChange={(e) => setMinBaselineTrips(e.target.value)} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm" placeholder="—" />
          </div>
        </div>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-4">
        {[
          { key: 'drivers_monitored', label: 'Conductores monitoreados', color: 'bg-blue-50 border-blue-200 text-blue-800' },
          { key: 'sharp_degradation', label: 'Degradación fuerte', color: 'bg-red-50 border-red-200 text-red-800' },
          { key: 'sustained_degradation', label: 'Degradación sostenida', color: 'bg-orange-50 border-orange-200 text-orange-800' },
          { key: 'recovery_cases', label: 'Recuperación', color: 'bg-green-50 border-green-200 text-green-800' },
          { key: 'dormant_risk_cases', label: 'Riesgo dormido/churn', color: 'bg-red-50 border-red-200 text-red-800' },
          { key: 'high_value_at_risk', label: 'Alto valor en riesgo', color: 'bg-amber-50 border-amber-200 text-amber-800' },
          { key: 'avg_days_since_last_trip', label: 'Prom. días sin viaje', color: 'bg-gray-50 border-gray-200 text-gray-800' }
        ].map(({ key, label, color }) => (
          <div key={key} className={`rounded-lg border p-3 ${color}`}>
            <div className="text-xs font-medium opacity-90">{label}</div>
            <div className="text-xl font-semibold mt-1">
              {key === 'avg_days_since_last_trip'
                ? (summary?.[key] != null ? formatNum(summary[key]) : '—')
                : formatNum(summary?.[key] ?? 0)}
            </div>
          </div>
        ))}
      </div>

      {/* Help panel */}
      <div>
        <button type="button" onClick={() => setShowHelp(!showHelp)} className="text-sm text-blue-600 hover:underline">
          {showHelp ? 'Ocultar' : 'Ver'} explicación: Ventanas, Delta, Días sin viaje, Riesgo, Acción
        </button>
        {showHelp && (
          <div className="mt-2 bg-gray-50 border border-gray-200 rounded p-4 text-sm text-gray-700 space-y-2">
            <p><strong>Ventana reciente:</strong> Semanas usadas para medir el comportamiento actual del conductor.</p>
            <p><strong>Ventana baseline:</strong> Semanas anteriores (excluyendo la reciente) para establecer la línea base histórica. No se solapan.</p>
            <p><strong>Delta %:</strong> (Promedio reciente − promedio baseline) / promedio baseline. Negativo = empeora; positivo = mejora.</p>
            <p><strong>Días desde último viaje:</strong> Días desde el último viaje completado. Activo 0–3, Enfriando 4–7, Riesgo dormido 8–14, Riesgo churn 15+.</p>
            <p><strong>Estado conductual:</strong> Empeorando, Recuperando, Mejorando, Estable, Volátil. Deriva de delta, rachas y inactividad.</p>
            <p><strong>Tipo alerta:</strong> Sharp/Moderate/Sustained Degradation, Recovery, Dormant Risk, Churn Risk, High Volatility, Stable.</p>
            <p><strong>Risk Score (0–100):</strong> Estable 0–24, Monitor 25–49, Medium risk 50–74, High risk 75–100. Explicable por desviación, persistencia e inactividad.</p>
            <p><strong>Acción sugerida:</strong> Reactivación, Retención prioritaria, Contacto lealtad, Refuerzo recuperación o Solo seguimiento.</p>
            <p><strong>Diferencia con otros módulos:</strong> Los módulos semanales (Behavioral Alerts, Action Engine) miden evolución macro por semana/cohorte. Este módulo mide desviación individual por ventanas de tiempo y prioriza intervención por conductor.</p>
          </div>
        )}
      </div>

      {/* Export */}
      <div className="flex flex-wrap gap-2 items-center">
        <a href={getDriverBehaviorExportUrl(filters)} download className="inline-flex items-center px-3 py-1.5 rounded border border-gray-300 bg-white text-sm text-gray-700 hover:bg-gray-50">
          Exportar CSV (filtros activos)
        </a>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {error && <div className="p-4 bg-red-50 text-red-700 text-sm">{error}</div>}
        {loading && <div className="p-4 text-gray-500 text-sm">Cargando…</div>}
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-100 border-b border-gray-200">
              <tr>
                <th className="text-left py-2 px-3 font-medium text-gray-700">Conductor</th>
                <th className="text-left py-2 px-3 font-medium text-gray-700">País</th>
                <th className="text-left py-2 px-3 font-medium text-gray-700">Ciudad</th>
                <th className="text-left py-2 px-3 font-medium text-gray-700">Park</th>
                <th className="text-left py-2 px-3 font-medium text-gray-700">Segmento</th>
                <th className="text-right py-2 px-3 font-medium text-gray-700">Recent avg</th>
                <th className="text-right py-2 px-3 font-medium text-gray-700">Baseline avg</th>
                <th className="text-right py-2 px-3 font-medium text-gray-700">Δ %</th>
                <th className="text-left py-2 px-3 font-medium text-gray-700">Estado</th>
                <th className="text-right py-2 px-3 font-medium text-gray-700">Días sin viaje</th>
                <th className="text-left py-2 px-3 font-medium text-gray-700">Persistencia</th>
                <th className="text-left py-2 px-3 font-medium text-gray-700">Alerta</th>
                <th className="text-right py-2 px-3 font-medium text-gray-700">Risk</th>
                <th className="text-left py-2 px-3 font-medium text-gray-700">Banda</th>
                <th className="text-left py-2 px-3 font-medium text-gray-700">Acción sugerida</th>
                <th className="text-left py-2 px-3 font-medium text-gray-700">Acción</th>
              </tr>
            </thead>
            <tbody>
              {drivers.data.map((r) => (
                <tr
                  key={r.driver_key}
                  className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                  onClick={() => loadDriverDetail(r.driver_key)}
                >
                  <td className="py-2 px-3">{r.driver_name || r.driver_key}</td>
                  <td className="py-2 px-3">{r.country ?? '—'}</td>
                  <td className="py-2 px-3">{r.city ?? '—'}</td>
                  <td className="py-2 px-3">{r.park_name ?? '—'}</td>
                  <td className="py-2 px-3">{r.current_segment ?? '—'}</td>
                  <td className="py-2 px-3 text-right">{formatNum(r.recent_avg_weekly_trips)}</td>
                  <td className="py-2 px-3 text-right">{formatNum(r.baseline_avg_weekly_trips)}</td>
                  <td className={`py-2 px-3 text-right ${getDeltaPctColor(r.delta_pct)}`}>{formatPct(r.delta_pct)}</td>
                  <td className="py-2 px-3">
                    <span className={`inline-block px-2 py-0.5 rounded border text-xs ${BEHAVIOR_DIRECTION_COLORS[r.behavior_direction] || 'bg-gray-100'}`}>
                      {r.behavior_direction ?? '—'}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-right">
                    <span className={`inline-block px-2 py-0.5 rounded border text-xs ${INACTIVITY_COLORS[r.inactivity_status] || 'bg-gray-100'}`}>
                      {r.days_since_last_trip != null ? r.days_since_last_trip : '—'}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-xs text-gray-600">{persistenceLabel(r)}</td>
                  <td className="py-2 px-3">
                    <span className={`inline-block px-2 py-0.5 rounded border text-xs ${ALERT_COLORS[r.alert_type] || 'bg-gray-100'}`}>
                      {r.alert_type ?? '—'}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-right">{formatNum(r.risk_score)}</td>
                  <td className="py-2 px-3">
                    <span className={`inline-block px-2 py-0.5 rounded border text-xs ${RISK_BAND_COLORS[r.risk_band] || 'bg-gray-100'}`}>{r.risk_band ?? '—'}</span>
                  </td>
                  <td className="py-2 px-3 text-xs">{r.suggested_action ?? '—'}</td>
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

      {/* Driver detail modal */}
      {detailDriverKey != null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true" onClick={() => setDetailDriverKey(null)}>
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-800">Detalle conductor</h3>
              <button type="button" onClick={() => setDetailDriverKey(null)} className="text-gray-500 hover:text-gray-700 text-2xl leading-none">×</button>
            </div>
            {detailLoading && <div className="text-sm text-gray-500">Cargando…</div>}
            {!detailLoading && detailData?.data && (
              <div className="space-y-4">
                <p className="text-sm text-gray-600">
                  {detailData.data.driver_name || detailData.driver_key} · Ventana reciente {detailData.recent_window_weeks} sem., baseline {detailData.baseline_window_weeks} sem.
                </p>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>Recent avg viajes/sem:</div>
                  <div className="font-medium">{formatNum(detailData.data.recent_avg_weekly_trips)}</div>
                  <div>Baseline avg viajes/sem:</div>
                  <div className="font-medium">{formatNum(detailData.data.baseline_avg_weekly_trips)}</div>
                  <div>Delta %:</div>
                  <div className={getDeltaPctColor(detailData.data.delta_pct)}>{formatPct(detailData.data.delta_pct)}</div>
                  <div>Días desde último viaje:</div>
                  <div className="font-medium">{detailData.data.days_since_last_trip ?? '—'}</div>
                  <div>Estado conductual:</div>
                  <div>
                    <span className={`inline-block px-2 py-0.5 rounded border text-xs ${BEHAVIOR_DIRECTION_COLORS[detailData.data.behavior_direction] || ''}`}>
                      {detailData.data.behavior_direction ?? '—'}
                    </span>
                  </div>
                  <div>Risk score / Banda:</div>
                  <div>{detailData.data.risk_score ?? '—'} · {detailData.data.risk_band ?? '—'}</div>
                  <div>Acción sugerida:</div>
                  <div>{detailData.data.suggested_action ?? '—'}</div>
                  <div className="col-span-2">Rationale:</div>
                  <div className="col-span-2 text-gray-600">{detailData.data.rationale_short ?? '—'}</div>
                </div>
                {detailData.weekly?.length > 0 && (
                  <div className="bg-gray-50 rounded-lg p-3 border border-gray-200">
                    <div className="text-xs font-medium text-gray-700 mb-2">Viajes por semana (reciente + baseline)</div>
                    <DriverTripsLineChart data={detailData.weekly.map((w) => ({ week_label: w.week_label, trips: w.trips }))} />
                  </div>
                )}
              </div>
            )}
            {!detailLoading && !detailData?.data && <p className="text-sm text-gray-500">Sin datos para este conductor.</p>}
          </div>
        </div>
      )}
    </div>
  )
}
