/**
 * Driver Lifecycle Diagnostic Engine Dashboard — Fase 2A.1
 *
 * Vista ejecutiva de fuga/leakage de conductores con estados determinísticos.
 * KPI cards + Leakage Funnel + Risk List + Cohorts básico.
 */
import { useCallback, useEffect, useState } from 'react'
import {
  getDriverLifecycleDiagnosticSummary,
  getDriverLifecycleDiagnosticFunnel,
  getDriverLifecycleDiagnosticRiskList,
  getDriverLifecycleDiagnosticCohortsBasic,
} from '../../services/api.js'

const STATE_LABELS = {
  CHURNED: 'Fugado',
  DORMANT: 'Dormido',
  REACTIVATED: 'Reactivado',
  NEW: 'Nuevo',
  AT_RISK: 'En riesgo',
  DECLINING: 'Declinando',
  GROWING: 'Creciendo',
  STABLE: 'Estable',
  ACTIVATING: 'Activando',
}

const STATE_COLORS = {
  CHURNED: 'bg-red-100 text-red-800 border-red-300',
  DORMANT: 'bg-orange-100 text-orange-800 border-orange-300',
  REACTIVATED: 'bg-green-100 text-green-800 border-green-300',
  NEW: 'bg-blue-100 text-blue-800 border-blue-300',
  AT_RISK: 'bg-red-50 text-red-700 border-red-200',
  DECLINING: 'bg-amber-100 text-amber-800 border-amber-300',
  GROWING: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  STABLE: 'bg-green-100 text-green-800 border-green-300',
  ACTIVATING: 'bg-sky-100 text-sky-800 border-sky-300',
}

const RISK_STYLES = {
  HIGH: { bg: 'bg-red-50', badge: 'bg-red-600 text-white', label: 'HIGH' },
  MEDIUM: { bg: 'bg-amber-50', badge: 'bg-amber-500 text-white', label: 'MEDIUM' },
  LOW: { bg: 'bg-green-50', badge: 'bg-green-600 text-white', label: 'LOW' },
}

const cardCls = 'bg-ct-card border border-ct-border rounded-lg p-4 shadow-sm'
const kpiValue = 'text-2xl font-bold text-ct-text'
const kpiLabel = 'text-xs text-ct-text2 mt-1'

export default function DriverLifecycleDashboard() {
  const [country, setCountry] = useState('')
  const [city, setCity] = useState('')
  const [riskFilter, setRiskFilter] = useState('')
  const [stateFilter, setStateFilter] = useState('')

  const [summary, setSummary] = useState(null)
  const [funnel, setFunnel] = useState(null)
  const [riskList, setRiskList] = useState([])
  const [cohorts, setCohorts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    const params = {}
    if (country) params.country = country
    if (city) params.city = city

    try {
      const [s, f, r, c] = await Promise.all([
        getDriverLifecycleDiagnosticSummary(params),
        getDriverLifecycleDiagnosticFunnel(params),
        getDriverLifecycleDiagnosticRiskList({
          ...params,
          risk_level: riskFilter || undefined,
          lifecycle_state: stateFilter || undefined,
          limit: 200,
        }),
        getDriverLifecycleDiagnosticCohortsBasic(params),
      ])
      setSummary(s)
      setFunnel(f)
      setRiskList(Array.isArray(r) ? r : [])
      setCohorts(Array.isArray(c) ? c : [])
    } catch (e) {
      setError(e?.message || 'Error loading diagnostic data')
    } finally {
      setLoading(false)
    }
  }, [country, city, riskFilter, stateFilter])

  useEffect(() => { loadData() }, [loadData])

  const fmtNum = (n) => n != null ? n.toLocaleString('es-ES') : '—'
  const fmtPct = (n) => n != null ? `${n}%` : '—'

  if (loading && !summary) {
    return <div className="p-6 text-ct-text2 text-sm">Cargando Driver Lifecycle Diagnostic Engine...</div>
  }

  return (
    <div className="p-4 space-y-5 max-w-full">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-ct-text">
            Driver Lifecycle Diagnostic Engine
          </h2>
          <p className="text-xs text-ct-text2">
            Diagnostico deterministico de ciclo de vida, riesgo y fuga de conductores
          </p>
        </div>
        <button
          type="button"
          onClick={loadData}
          className="px-3 py-1.5 text-xs font-medium rounded-md bg-ct-nav text-white hover:bg-blue-700 transition"
        >
          Refrescar
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-xs rounded-md px-3 py-2">
          {error}
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <select value={country} onChange={(e) => setCountry(e.target.value)} className="border border-ct-border rounded-md text-xs px-2.5 py-1.5 bg-ct-card text-ct-text">
          <option value="">Todos los paises</option>
          <option value="peru">Peru</option>
          <option value="colombia">Colombia</option>
        </select>
        <input
          type="text"
          placeholder="Ciudad..."
          value={city}
          onChange={(e) => setCity(e.target.value)}
          className="border border-ct-border rounded-md text-xs px-2.5 py-1.5 bg-ct-card text-ct-text w-32"
        />
        <select value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)} className="border border-ct-border rounded-md text-xs px-2.5 py-1.5 bg-ct-card text-ct-text">
          <option value="">Todos los riesgos</option>
          <option value="HIGH">HIGH</option>
          <option value="MEDIUM">MEDIUM</option>
          <option value="LOW">LOW</option>
        </select>
        <select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)} className="border border-ct-border rounded-md text-xs px-2.5 py-1.5 bg-ct-card text-ct-text">
          <option value="">Todos los estados</option>
          {Object.entries(STATE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
      </div>

      {/* KPI Cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
          {[
            { label: 'Active 7D', value: fmtNum(summary.active_7d), color: 'text-emerald-600' },
            { label: 'Active 28D', value: fmtNum(summary.active_28d), color: 'text-blue-600' },
            { label: 'New', value: fmtNum(summary.new_drivers), color: 'text-sky-600' },
            { label: 'At Risk', value: fmtNum(summary.at_risk_drivers), color: 'text-red-600' },
            { label: 'Dormant', value: fmtNum(summary.dormant_drivers), color: 'text-orange-600' },
            { label: 'Churned', value: fmtNum(summary.churned_drivers), color: 'text-red-700' },
            { label: 'Retention', value: fmtPct(summary.retention_rate), color: 'text-green-600' },
            { label: 'Leakage', value: fmtPct(summary.leakage_rate), color: 'text-red-600' },
          ].map((kpi) => (
            <div key={kpi.label} className={cardCls}>
              <div className={`${kpiValue} ${kpi.color}`}>{kpi.value}</div>
              <div className={kpiLabel}>{kpi.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Leakage Funnel / Driver Reservoir */}
      {funnel && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          {['input_layer', 'retained_layer', 'risk_layer', 'leakage_layer'].map((layer) => {
            const data = funnel[layer] || {}
            const colors = {
              input_layer: 'border-blue-300 bg-blue-50',
              retained_layer: 'border-green-300 bg-green-50',
              risk_layer: 'border-amber-300 bg-amber-50',
              leakage_layer: 'border-red-300 bg-red-50',
            }
            const titles = {
              input_layer: 'Entrada',
              retained_layer: 'Retenidos',
              risk_layer: 'Riesgo',
              leakage_layer: 'Fuga',
            }
            const entries = Object.entries(data).filter(([k]) => !k.startsWith('total_'))
            const totalKey = Object.keys(data).find(k => k.startsWith('total_'))
            return (
              <div key={layer} className={`${cardCls} border-l-4 ${colors[layer]}`}>
                <div className="text-xs font-semibold text-ct-text2 uppercase tracking-wide mb-2">
                  {titles[layer]}
                </div>
                {entries.map(([key, val]) => (
                  <div key={key} className="flex justify-between text-xs py-0.5">
                    <span className="text-ct-text2">{key.replace(/_/g, ' ')}</span>
                    <span className="font-semibold text-ct-text">{fmtNum(val)}</span>
                  </div>
                ))}
                {totalKey && (
                  <div className="flex justify-between text-xs py-1 mt-1 pt-1 border-t border-ct-border font-bold">
                    <span className="text-ct-text">Total</span>
                    <span className="text-ct-text">{fmtNum(data[totalKey])}</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Risk List (actionable) */}
      <div>
        <h3 className="text-sm font-semibold text-ct-text mb-2">
          Lista accionable ({riskList.length} conductores)
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs border-collapse">
            <thead>
              <tr className="text-left text-ct-text2 border-b border-ct-border">
                <th className="py-1.5 pr-2">Driver ID</th>
                <th className="py-1.5 pr-2">City</th>
                <th className="py-1.5 pr-2">State</th>
                <th className="py-1.5 pr-2">Risk</th>
                <th className="py-1.5 pr-2">Rule Reason</th>
                <th className="py-1.5 pr-2">Last Trip</th>
                <th className="py-1.5 pr-2">Days Since</th>
                <th className="py-1.5 pr-2">7D Trips</th>
                <th className="py-1.5 pr-2">28D Baseline</th>
                <th className="py-1.5 pr-2">Decline %</th>
              </tr>
            </thead>
            <tbody>
              {riskList.map((d, i) => {
                const riskStyle = RISK_STYLES[d.risk_level] || RISK_STYLES.LOW
                const stateColor = STATE_COLORS[d.lifecycle_state] || ''
                return (
                  <tr key={d.driver_id || i} className={`border-b border-ct-border/50 ${riskStyle.bg}`}>
                    <td className="py-1 pr-2 font-mono text-2xs">{String(d.driver_id || '').slice(0, 12)}...</td>
                    <td className="py-1 pr-2">{d.city}</td>
                    <td className="py-1 pr-2">
                      <span className={`px-1.5 py-0.5 rounded text-2xs border ${stateColor}`}>
                        {STATE_LABELS[d.lifecycle_state] || d.lifecycle_state}
                      </span>
                    </td>
                    <td className="py-1 pr-2">
                      <span className={`px-1.5 py-0.5 rounded text-2xs ${riskStyle.badge}`}>
                        {riskStyle.label}
                      </span>
                    </td>
                    <td className="py-1 pr-2 text-2xs text-ct-text2 max-w-[200px] truncate">{d.rule_reason}</td>
                    <td className="py-1 pr-2">{d.last_trip_date || '—'}</td>
                    <td className="py-1 pr-2 font-semibold">{d.days_since_last_trip ?? '—'}</td>
                    <td className="py-1 pr-2">{fmtNum(d.rolling_7d_trips)}</td>
                    <td className="py-1 pr-2">{fmtNum(d.baseline_trips_28d)}</td>
                    <td className="py-1 pr-2">{d.decline_pct != null ? `${d.decline_pct}%` : '—'}</td>
                  </tr>
                )
              })}
              {riskList.length === 0 && (
                <tr><td colSpan={10} className="py-4 text-center text-ct-text2">No hay conductores con los filtros seleccionados.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Cohorts Basic */}
      {cohorts.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-ct-text mb-2">Cohorts (por mes de primer viaje)</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="text-left text-ct-text2 border-b border-ct-border">
                  <th className="py-1.5 pr-2">Cohort</th>
                  <th className="py-1.5 pr-2">Started</th>
                  <th className="py-1.5 pr-2">Ret 7D</th>
                  <th className="py-1.5 pr-2">Ret 14D</th>
                  <th className="py-1.5 pr-2">Ret 30D</th>
                  <th className="py-1.5 pr-2">Ret 7D %</th>
                  <th className="py-1.5 pr-2">Ret 14D %</th>
                  <th className="py-1.5 pr-2">Ret 30D %</th>
                </tr>
              </thead>
              <tbody>
                {cohorts.map((c) => (
                  <tr key={c.cohort} className="border-b border-ct-border/50">
                    <td className="py-1 pr-2 font-semibold">{c.cohort}</td>
                    <td className="py-1 pr-2">{fmtNum(c.drivers_started)}</td>
                    <td className="py-1 pr-2">{fmtNum(c.retained_7d)}</td>
                    <td className="py-1 pr-2">{fmtNum(c.retained_14d)}</td>
                    <td className="py-1 pr-2">{fmtNum(c.retained_30d)}</td>
                    <td className="py-1 pr-2">{fmtPct(c.retention_7d_pct)}</td>
                    <td className="py-1 pr-2">{fmtPct(c.retention_14d_pct)}</td>
                    <td className="py-1 pr-2">{fmtPct(c.retention_30d_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
