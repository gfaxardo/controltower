import { useState, useEffect, useCallback } from 'react'
import {
  getYangoLoyaltySummary,
  getYangoLoyaltyKpis,
  postYangoLoyaltyGoals,
  postYangoLoyaltyManualResults,
  getYangoLoyaltyCompleteness,
  getYangoLoyaltyFreshness,
  getYangoLoyaltyDailySnapshot,
  getYangoLoyaltyHistorical,
  postYangoLoyaltyCopyGoals,
  postYangoLoyaltyBulkManualResults,
} from '../services/api'

const CITIES = ['Lima', 'Trujillo', 'Arequipa']
const MANUAL_KPIS = ['SH', 'CALLS', 'CONV_NEW', 'CONV_REA', 'UFC', 'COMMS', 'SUPPORT', 'SOCIAL']

// ═══════════ COLORS ═══════════

const FRESHNESS_COLORS = {
  FRESH: 'text-green-400', WARNING: 'text-amber-400', STALE: 'text-red-400', MISSING: 'text-gray-500',
}
const FRESHNESS_BG = {
  FRESH: 'bg-green-500/10 border-green-500/30', WARNING: 'bg-amber-500/10 border-amber-500/30',
  STALE: 'bg-red-500/10 border-red-500/30', MISSING: 'bg-gray-500/10 border-gray-500/30',
}
const SEMAPHORE = { green: 'text-green-400', amber: 'text-amber-400', red: 'text-red-400', gray: 'text-gray-400' }

function formatNum(n) {
  if (n == null || isNaN(n)) return '—'
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + 'M'
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K'
  return Number(n).toFixed(2)
}
function formatPct(n) {
  if (n == null || isNaN(n)) return '—'
  return Number(n).toFixed(1) + '%'
}

const Btn = ({ onClick, children, variant = 'default', small = false, ...p }) => (
  <button type="button" onClick={onClick} disabled={p.disabled}
    className={`${small ? 'px-2 py-0.5 text-2xs' : 'px-3 py-1 text-xs'} rounded font-medium transition-all ${
      variant === 'primary' ? 'bg-ct-accent text-white hover:brightness-110' :
      variant === 'danger' ? 'bg-red-500/20 text-red-300 hover:bg-red-500/30 border border-red-500/30' :
      variant === 'ghost' ? 'text-ct-text3 hover:text-ct-text hover:bg-ct-border' :
      'bg-ct-surface border border-ct-border text-ct-text hover:bg-ct-border'
    } ${p.disabled ? 'opacity-40 cursor-not-allowed' : ''}`} {...p}>{children}</button>
)

const Input = ({ label, value, onChange, type = 'text', placeholder, min, max, step, error }) => (
  <div>
    {label && <label className="block text-2xs text-ct-text3 mb-0.5">{label}</label>}
    <input type={type} value={value} onChange={onChange} placeholder={placeholder}
      min={min} max={max} step={step}
      className={`w-full bg-ct-card border ${error ? 'border-red-400' : 'border-ct-border'} rounded px-2 py-1 text-xs text-ct-text focus:outline-none focus:border-ct-accent`} />
    {error && <span className="text-2xs text-red-400">{error}</span>}
  </div>
)

// ═══════════ GOAL MANAGEMENT ═══════════

export function GoalManagementTable() {
  const [month, setMonth] = useState('')
  const [goals, setGoals] = useState({})   // { "city|kpi_code": value }
  const [kpis, setKpis] = useState([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState(null)
  const [copyFrom, setCopyFrom] = useState('')
  const [copyTo, setCopyTo] = useState('')
  const [errors, setErrors] = useState({})

  useEffect(() => {
    getYangoLoyaltyKpis().then(r => setKpis(r?.kpis || []))
  }, [])

  const loadGoals = useCallback(async (m) => {
    if (!m) return
    setLoading(true)
    try {
      const res = await getYangoLoyaltySummary({ month: m })
      const map = {}
      for (const k of (res?.kpis || [])) {
        if (k.target_value != null) map[`${k.city}|${k.kpi_code}`] = String(k.target_value)
      }
      setGoals(map)
    } catch (e) { setMsg({ type: 'error', text: e.message }) }
    finally { setLoading(false) }
  }, [])

  const handleSave = async () => {
    if (!month) { setMsg({ type: 'error', text: 'Selecciona un mes' }); return }
    setSaving(true)
    setErrors({})
    const payload = []
    const errs = {}
    for (const [key, val] of Object.entries(goals)) {
      if (val === '' || val == null) continue
      const [city, code] = key.split('|')
      const v = parseFloat(val)
      if (isNaN(v)) { errs[key] = 'Número inválido'; continue }
      if (v < 0) { errs[key] = 'No puede ser negativo'; continue }
      payload.push({ month, country: 'PE', city, kpi_code: code, target_value: v })
    }
    if (Object.keys(errs).length > 0) { setErrors(errs); return }
    try {
      const res = await postYangoLoyaltyGoals(payload)
      if (res.errors?.length) setMsg({ type: 'error', text: `${res.errors.length} errores de validación` })
      else setMsg({ type: 'success', text: `${res.updated || res.total} metas guardadas` })
    } catch (e) { setMsg({ type: 'error', text: e.message }) }
    finally { setSaving(false) }
  }

  const handleCopy = async () => {
    if (!copyFrom || !copyTo) { setMsg({ type: 'error', text: 'Selecciona mes origen y destino' }); return }
    try {
      const res = await postYangoLoyaltyCopyGoals({ from_month: copyFrom, to_month: copyTo })
      setMsg({ type: 'success', text: `${res.copied} metas copiadas a ${copyTo}` })
      if (copyTo === month) loadGoals(month)
    } catch (e) { setMsg({ type: 'error', text: e.message }) }
  }

  const setGoalVal = (city, kpi, val) => {
    setGoals(prev => ({ ...prev, [`${city}|${kpi}`]: val }))
    setErrors(prev => { const n = { ...prev }; delete n[`${city}|${kpi}`]; return n })
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label className="block text-2xs text-ct-text3 mb-0.5">Mes</label>
          <input type="month" value={month} onChange={e => { setMonth(e.target.value + '-01' !== e.target.value ? e.target.value : e.target.value); loadGoals(e.target.value) }}
            className="bg-ct-card border border-ct-border rounded px-2 py-1 text-xs text-ct-text" />
        </div>
        <Btn onClick={handleSave} variant="primary" disabled={saving}>{saving ? 'Guardando...' : 'Guardar metas'}</Btn>
        {msg && <span className={`text-xs ${msg.type === 'error' ? 'text-red-400' : 'text-green-400'}`}>{msg.text}</span>}
      </div>

      {/* Copy goals */}
      <div className="bg-ct-card border border-ct-border rounded-lg p-3">
        <div className="text-xs font-semibold text-ct-text mb-2">Copiar metas de mes anterior</div>
        <div className="flex flex-wrap items-end gap-2">
          <div>
            <label className="block text-2xs text-ct-text3 mb-0.5">Origen</label>
            <input type="month" value={copyFrom} onChange={e => setCopyFrom(e.target.value)}
              className="bg-ct-card border border-ct-border rounded px-2 py-1 text-xs text-ct-text" />
          </div>
          <div>
            <label className="block text-2xs text-ct-text3 mb-0.5">Destino</label>
            <input type="month" value={copyTo} onChange={e => setCopyTo(e.target.value)}
              className="bg-ct-card border border-ct-border rounded px-2 py-1 text-xs text-ct-text" />
          </div>
          <Btn onClick={handleCopy} variant="ghost" small>Copiar</Btn>
        </div>
      </div>

      {/* Thresholds reference */}
      <details className="bg-ct-card border border-ct-border rounded-lg p-2">
        <summary className="text-2xs text-ct-text3 cursor-pointer">Thresholds Oro / Plata / Bronce</summary>
        <div className="mt-1 overflow-x-auto">
          <table className="w-full text-2xs text-ct-text3">
            <thead><tr className="border-b border-ct-border">
              <th className="py-1 px-1 text-left">KPI</th><th className="py-1 px-1 text-center">Oro ≥</th>
              <th className="py-1 px-1 text-center">Plata ≥</th><th className="py-1 px-1 text-center">Bronce ≥</th>
            </tr></thead>
            <tbody>
              {kpis.map(k => (
                <tr key={k.kpi_code} className="border-b border-ct-border/30">
                  <td className="py-1 px-1 font-medium text-ct-text">{k.kpi_name}</td>
                  <td className="py-1 px-1 text-center text-yellow-400">{k.gold_threshold}%</td>
                  <td className="py-1 px-1 text-center text-slate-400">{k.silver_threshold}%</td>
                  <td className="py-1 px-1 text-center text-amber-600">{k.bronze_threshold}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      {/* Goals table */}
      {month && (
        <div className="bg-ct-card border border-ct-border rounded-lg overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-ct-border bg-ct-surface/50">
                <th className="py-2 px-2 text-2xs text-ct-text3 uppercase">KPI</th>
                {CITIES.map(c => <th key={c} className="py-2 px-2 text-2xs text-ct-text3 uppercase text-center">{c}</th>)}
              </tr>
            </thead>
            <tbody>
              {kpis.map(k => (
                <tr key={k.kpi_code} className="border-b border-ct-border hover:bg-ct-surface/30">
                  <td className="py-1 px-2 text-xs text-ct-text">
                    <div className="font-medium">{k.kpi_name}</div>
                    <div className="text-2xs text-ct-text3">{k.unit} · {k.source_type}</div>
                  </td>
                  {CITIES.map(c => (
                    <td key={c} className="py-1 px-1 text-center">
                      <input type="number" min="0" step="any"
                        value={goals[`${c}|${k.kpi_code}`] || ''}
                        onChange={e => setGoalVal(c, k.kpi_code, e.target.value)}
                        placeholder="—"
                        className={`w-20 bg-ct-surface border ${errors[`${c}|${k.kpi_code}`] ? 'border-red-400' : 'border-ct-border'} rounded px-1 py-0.5 text-xs text-ct-text text-center focus:outline-none focus:border-ct-accent`} />
                      {errors[`${c}|${k.kpi_code}`] && <div className="text-2xs text-red-400 mt-0.5">{errors[`${c}|${k.kpi_code}`]}</div>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ═══════════ MANUAL KPI INPUT ═══════════

export function ManualKpiInputForm() {
  const [month, setMonth] = useState('')
  const [values, setValues] = useState({}) // { "city|kpi_code": value }
  const [freshness, setFreshness] = useState(null)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState(null)

  const loadExisting = useCallback(async (m) => {
    if (!m) return
    try {
      const [sumRes, freshRes] = await Promise.all([
        getYangoLoyaltySummary({ month: m }),
        getYangoLoyaltyFreshness({ month: m }),
      ])
      const map = {}
      for (const k of (sumRes?.kpis || [])) {
        if (k.real_value != null && MANUAL_KPIS.includes(k.kpi_code)) {
          map[`${k.city}|${k.kpi_code}`] = String(k.real_value)
        }
      }
      setValues(map)
      setFreshness(freshRes)
    } catch (e) { setMsg({ type: 'error', text: e.message }) }
  }, [])

  const handleSave = async () => {
    if (!month) { setMsg({ type: 'error', text: 'Selecciona un mes' }); return }
    setSaving(true)
    const payload = []
    for (const [key, val] of Object.entries(values)) {
      if (val === '' || val == null) continue
      const [city, code] = key.split('|')
      const v = parseFloat(val)
      if (isNaN(v) || v < 0) continue
      if ((['CONV_NEW', 'CONV_REA', 'UFC', 'COMMS', 'SUPPORT', 'SOCIAL'].includes(code)) && (v < 0 || v > 100)) continue
      payload.push({ month, country: 'PE', city, kpi_code: code, real_value: v })
    }
    try {
      const res = await postYangoLoyaltyManualResults(payload)
      if (res.errors?.length) setMsg({ type: 'error', text: `${res.errors.length} errores` })
      else { setMsg({ type: 'success', text: `${res.updated || res.total} KPIs guardados` }); loadExisting(month) }
    } catch (e) { setMsg({ type: 'error', text: e.message }) }
    finally { setSaving(false) }
  }

  const setVal = (city, kpi, val) => setValues(prev => ({ ...prev, [`${city}|${kpi}`]: val }))

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label className="block text-2xs text-ct-text3 mb-0.5">Mes</label>
          <input type="month" value={month} onChange={e => { setMonth(e.target.value); loadExisting(e.target.value) }}
            className="bg-ct-card border border-ct-border rounded px-2 py-1 text-xs text-ct-text" />
        </div>
        <Btn onClick={handleSave} variant="primary" disabled={saving}>{saving ? 'Guardando...' : 'Guardar resultados'}</Btn>
        {msg && <span className={`text-xs ${msg.type === 'error' ? 'text-red-400' : 'text-green-400'}`}>{msg.text}</span>}
      </div>

      {/* Freshness panel */}
      {freshness && (
        <div className="bg-ct-card border border-ct-border rounded-lg p-2">
          <div className="text-xs font-semibold text-ct-text mb-1">Freshness de KPIs Manuales</div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(freshness.freshness_distribution || {}).map(([status, count]) => (
              <span key={status} className={`inline-block px-1.5 py-0.5 rounded text-2xs border ${FRESHNESS_COLORS[status] || ''} ${FRESHNESS_BG[status] || ''}`}>
                {status}: <strong className="text-ct-text">{count}</strong>
              </span>
            ))}
          </div>
          {freshness.warning_count > 0 && (
            <div className="mt-1 text-2xs text-amber-400">{freshness.warning_count} KPIs necesitan actualización</div>
          )}
        </div>
      )}

      {/* Input table */}
      {month && (
        <div className="bg-ct-card border border-ct-border rounded-lg overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-ct-border bg-ct-surface/50">
                <th className="py-2 px-2 text-2xs text-ct-text3 uppercase">KPI</th>
                <th className="py-2 px-2 text-2xs text-ct-text3 uppercase text-center">Unidad</th>
                {CITIES.map(c => <th key={c} className="py-2 px-2 text-2xs text-ct-text3 uppercase text-center">{c}</th>)}
                <th className="py-2 px-2 text-2xs text-ct-text3 uppercase text-center">Último update</th>
              </tr>
            </thead>
            <tbody>
              {MANUAL_KPIS.map(code => (
                <tr key={code} className="border-b border-ct-border hover:bg-ct-surface/30">
                  <td className="py-1 px-2 text-xs text-ct-text font-medium">{code}</td>
                  <td className="py-1 px-2 text-center text-2xs text-ct-text3">
                    {['CONV_NEW', 'CONV_REA', 'UFC'].includes(code) ? '%' : ['COMMS', 'SUPPORT', 'SOCIAL'].includes(code) ? 'score' : ['SH'].includes(code) ? 'hrs' : '#'}
                  </td>
                  {CITIES.map(c => (
                    <td key={c} className="py-1 px-1 text-center">
                      <input type="number" min="0" max={['CONV_NEW', 'CONV_REA', 'UFC', 'COMMS', 'SUPPORT', 'SOCIAL'].includes(code) ? 100 : undefined} step="any"
                        value={values[`${c}|${code}`] || ''}
                        onChange={e => setVal(c, code, e.target.value)}
                        placeholder="—"
                        className={`w-20 bg-ct-surface border border-ct-border rounded px-1 py-0.5 text-xs text-ct-text text-center focus:outline-none focus:border-ct-accent`} />
                    </td>
                  ))}
                  <td className="py-1 px-2 text-center text-2xs text-ct-text3">
                    {(freshness?.items || []).filter(i => i.kpi_code === code).map(i => (
                      <div key={i.city} className="flex items-center justify-center gap-1">
                        <span className={FRESHNESS_COLORS[i.freshness_status] || ''}>{i.city.slice(0,1)}</span>
                      </div>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ═══════════ DAILY SNAPSHOT ═══════════

export function DailySnapshotCard() {
  const [snap, setSnap] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try { setSnap(await getYangoLoyaltyDailySnapshot()) }
    catch (e) { /* silent */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) return <div className="text-xs text-ct-text3 py-4">Cargando snapshot diario...</div>
  if (!snap) return null

  return (
    <div className="space-y-3">
      {/* Metric pills */}
      <div className="flex flex-wrap gap-2">
        {[
          { label: 'On Track', val: snap.on_track_count, color: 'green' },
          { label: 'Ahead', val: snap.ahead_count, color: 'green' },
          { label: 'Behind', val: snap.behind_count, color: 'amber' },
          { label: 'At Risk', val: snap.at_risk_count, color: 'red' },
        ].map(m => (
          <div key={m.label} className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border bg-${m.color}-500/10 border-${m.color}-500/30`}>
            <span className={`text-xs font-bold ${SEMAPHORE[m.color]}`}>{m.val}</span>
            <span className="text-2xs text-ct-text3">{m.label}</span>
          </div>
        ))}
      </div>

      {/* Snapshot table */}
      <div className="bg-ct-card border border-ct-border rounded-lg overflow-x-auto">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-ct-border bg-ct-surface/50">
              <th className="py-2 px-2 text-2xs text-ct-text3 uppercase">KPI</th>
              <th className="py-2 px-2 text-2xs text-ct-text3 uppercase text-center">Ciudad</th>
              <th className="py-2 px-2 text-2xs text-ct-text3 uppercase text-center">Esperado hoy</th>
              <th className="py-2 px-2 text-2xs text-ct-text3 uppercase text-center">Real</th>
              <th className="py-2 px-2 text-2xs text-ct-text3 uppercase text-center">Gap</th>
              <th className="py-2 px-2 text-2xs text-ct-text3 uppercase text-center">Attainment</th>
              <th className="py-2 px-2 text-2xs text-ct-text3 uppercase text-center">Status</th>
            </tr>
          </thead>
          <tbody>
            {(snap.items || []).map((item, idx) => (
              <tr key={idx} className="border-b border-ct-border hover:bg-ct-surface/30">
                <td className="py-1 px-2 text-xs text-ct-text font-medium">{item.kpi_name}</td>
                <td className="py-1 px-2 text-xs text-center text-ct-text3">{item.city}</td>
                <td className="py-1 px-2 text-xs text-center text-ct-text3">{formatNum(item.expected_value_today)}</td>
                <td className="py-1 px-2 text-xs text-center text-ct-text">{formatNum(item.real_value)}</td>
                <td className="py-1 px-2 text-xs text-center">
                  <span className={item.gap_abs != null && item.gap_abs < 0 ? 'text-red-400' : 'text-green-400'}>
                    {item.gap_pct != null ? (item.gap_pct >= 0 ? '+' : '') + formatPct(item.gap_pct) : '—'}
                  </span>
                </td>
                <td className="py-1 px-2 text-xs text-center text-ct-text">{formatPct(item.attainment_pct)}</td>
                <td className="py-1 px-2 text-xs text-center">
                  <span className={`inline-block w-2.5 h-2.5 rounded-full bg-${item.semaphore_color}-500`} title={item.reachability_status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ═══════════ HISTORICAL ═══════════

export function HistoricalTable() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [monthsBack, setMonthsBack] = useState(6)
  const [filterKpi, setFilterKpi] = useState('')
  const [filterCity, setFilterCity] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { months_back: monthsBack }
      if (filterKpi) params.kpi_code = filterKpi
      if (filterCity) params.city = filterCity
      setData(await getYangoLoyaltyHistorical(params))
    } catch (e) { /* silent */ }
    finally { setLoading(false) }
  }, [monthsBack, filterKpi, filterCity])

  useEffect(() => { load() }, [load])

  // Build pivot: months as columns, rows = city|kpi_code
  const buildPivot = () => {
    if (!data?.historical?.length) return { months: [], rows: [] }
    const items = data.historical
    const months = [...new Set(items.map(i => i.month))].sort()
    const rowKeys = [...new Set(items.map(i => `${i.city}|${i.kpi_code}`))]
    const rows = rowKeys.map(rk => {
      const [city, code] = rk.split('|')
      const vals = {}
      let name = ''
      for (const m of months) {
        const item = items.find(i => i.month === m && i.city === city && i.kpi_code === code)
        vals[m] = item || null
        if (!name && item) name = item.kpi_name
      }
      return { key: rk, city, kpi_code: code, kpi_name: name, values: vals }
    })
    return { months, rows }
  }

  const { months, rows } = buildPivot()

  if (loading) return <div className="text-xs text-ct-text3 py-4">Cargando histórico...</div>

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label className="block text-2xs text-ct-text3 mb-0.5">Meses atrás</label>
          <select value={monthsBack} onChange={e => setMonthsBack(Number(e.target.value))}
            className="bg-ct-card border border-ct-border rounded px-2 py-1 text-xs text-ct-text">
            {[3, 6, 12, 24].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-2xs text-ct-text3 mb-0.5">KPI</label>
          <select value={filterKpi} onChange={e => setFilterKpi(e.target.value)}
            className="bg-ct-card border border-ct-border rounded px-2 py-1 text-xs text-ct-text">
            <option value="">Todos</option>
            {['AD', 'SH', 'N_R', 'CALLS', 'CONV_NEW', 'CONV_REA', 'UFC', 'COMMS', 'SUPPORT', 'SOCIAL'].map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-2xs text-ct-text3 mb-0.5">Ciudad</label>
          <select value={filterCity} onChange={e => setFilterCity(e.target.value)}
            className="bg-ct-card border border-ct-border rounded px-2 py-1 text-xs text-ct-text">
            <option value="">Todas</option>
            {CITIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>

      {months.length === 0 ? (
        <div className="text-xs text-ct-text3 py-4">Sin datos históricos para los filtros seleccionados.</div>
      ) : (
        <div className="bg-ct-card border border-ct-border rounded-lg overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-ct-border bg-ct-surface/50">
                <th className="py-2 px-2 text-2xs text-ct-text3 uppercase">Ciudad</th>
                <th className="py-2 px-2 text-2xs text-ct-text3 uppercase">KPI</th>
                {months.map(m => <th key={m} className="py-2 px-1 text-2xs text-ct-text3 uppercase text-center">{m.slice(2)}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.key} className="border-b border-ct-border hover:bg-ct-surface/30">
                  <td className="py-1 px-2 text-xs text-ct-text3">{r.city}</td>
                  <td className="py-1 px-2 text-xs text-ct-text font-medium">{r.kpi_code}</td>
                  {months.map(m => {
                    const v = r.values[m]
                    if (!v || v.attainment_pct == null) return <td key={m} className="py-1 px-1 text-center text-2xs text-ct-text3">—</td>
                    const color = v.current_category === 'ORO' ? 'text-yellow-400' :
                      v.current_category === 'PLATA' ? 'text-slate-300' :
                      v.current_category === 'BRONCE' ? 'text-amber-600' : 'text-red-400'
                    return (
                      <td key={m} className="py-1 px-1 text-center">
                        <span className={`text-2xs font-semibold ${color}`} title={`${v.current_category}: ${formatPct(v.attainment_pct)}`}>
                          {v.current_category?.charAt(0) || '—'}
                        </span>
                      </td>
                    )
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ═══════════ COMPLETENESS PANEL ═══════════

export function CompletenessPanel() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try { setData(await getYangoLoyaltyCompleteness()) }
    catch (e) { /* silent */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) return <div className="text-xs text-ct-text3 py-4">Cargando completitud...</div>
  if (!data) return null

  return (
    <div className="space-y-3">
      {/* Global bar */}
      <div className="bg-ct-card border border-ct-border rounded-lg p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-ct-text">Completitud Global</span>
          <span className={`text-lg font-bold ${data.global_completeness_pct >= 80 ? 'text-green-400' : data.global_completeness_pct >= 50 ? 'text-amber-400' : 'text-red-400'}`}>
            {formatPct(data.global_completeness_pct)}
          </span>
        </div>
        <div className="w-full h-2 bg-ct-border rounded-full overflow-hidden">
          <div className={`h-full rounded-full transition-all ${data.global_completeness_pct >= 80 ? 'bg-green-500' : data.global_completeness_pct >= 50 ? 'bg-amber-500' : 'bg-red-500'}`}
            style={{ width: `${Math.min(100, data.global_completeness_pct)}%` }} />
        </div>
        <div className="mt-2 flex flex-wrap gap-2 text-2xs text-ct-text3">
          {Object.entries(data.global_states || {}).map(([s, c]) => (
            <span key={s}>{s}: <strong className="text-ct-text">{c}</strong></span>
          ))}
        </div>
      </div>

      {/* City breakdown */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        {CITIES.map(c => {
          const cc = data.city_completeness?.[c]
          if (!cc) return <div key={c} className="bg-ct-card border border-ct-border rounded-lg p-2"><span className="text-2xs text-ct-text3">{c}: sin datos</span></div>
          return (
            <div key={c} className="bg-ct-card border border-ct-border rounded-lg p-2">
              <div className="text-xs font-semibold text-ct-text mb-1">{c}</div>
              <div className={`text-lg font-bold ${cc.completeness_pct >= 80 ? 'text-green-400' : 'text-amber-400'}`}>{formatPct(cc.completeness_pct)}</div>
              <div className="text-2xs text-ct-text3 mt-1">
                {cc.complete_count}/{cc.total_kpis} completos
              </div>
              <div className="w-full h-1.5 bg-ct-border rounded-full mt-1 overflow-hidden">
                <div className={`h-full rounded-full ${cc.completeness_pct >= 80 ? 'bg-green-500' : 'bg-amber-500'}`}
                  style={{ width: `${Math.min(100, cc.completeness_pct)}%` }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
