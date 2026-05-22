/**
 * Driver Behavior Benchmarking Dashboard — Fase 2A.2
 * Comparación diagnóstica de patrones operativos: TOP vs DECLINING/AT-RISK.
 * No genera recomendaciones automáticas. Solo diagnóstico.
 */
import { useState, useEffect, useCallback } from 'react'
import {
  getDriverBehaviorBenchmarkSummary,
  getDriverBehaviorGroupBenchmarks,
  getDriverBehaviorTopVsRisk,
  getDriverBehaviorDistributions,
} from '../../services/api'

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

function formatCurrency (n) {
  if (n == null || n === '') return '—'
  const num = Number(n)
  if (Number.isNaN(num)) return '—'
  return num.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function formatGap (n, unit) {
  if (n == null || n === '') return '—'
  const num = Number(n)
  if (Number.isNaN(num)) return '—'
  if (unit === 'ratio') return (num * 100).toFixed(1) + ' pp'
  if (unit === 'currency') return num.toLocaleString('es-ES', { signDisplay: 'always', minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return num.toLocaleString('es-ES', { signDisplay: 'always', maximumFractionDigits: 2 })
}

const DIMENSION_OPTIONS = [
  { value: 'city', label: 'Ciudad' },
  { value: 'park', label: 'Park' },
  { value: 'lob', label: 'Línea de negocio' },
  { value: 'day_of_week', label: 'Día de la semana' },
  { value: 'hour', label: 'Hora del día' },
]

export default function DriverBehaviorBenchmarkingDashboard () {
  const [country, setCountry] = useState('')
  const [city, setCity] = useState('')
  const [periodDays, setPeriodDays] = useState(28)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const [summary, setSummary] = useState(null)
  const [groups, setGroups] = useState([])
  const [topVsRisk, setTopVsRisk] = useState(null)

  const [distDimension, setDistDimension] = useState('city')
  const [distGroup, setDistGroup] = useState('')
  const [distributions, setDistributions] = useState(null)
  const [distLoading, setDistLoading] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = { period_days: periodDays }
      if (country) params.country = country
      if (city) params.city = city

      const [sum, grp, cmp] = await Promise.all([
        getDriverBehaviorBenchmarkSummary(params),
        getDriverBehaviorGroupBenchmarks(params),
        getDriverBehaviorTopVsRisk(params),
      ])
      setSummary(sum)
      setGroups(grp?.groups || [])
      setTopVsRisk(cmp)
    } catch (e) {
      console.error('Driver Behavior Benchmarking:', e)
      setError(e.response?.data?.detail || e.message || 'Error al cargar datos')
    } finally {
      setLoading(false)
    }
  }, [country, city, periodDays])

  const loadDistributions = useCallback(async () => {
    setDistLoading(true)
    try {
      const params = {
        dimension: distDimension,
        period_days: periodDays,
      }
      if (country) params.country = country
      if (city) params.city = city
      if (distGroup) params.group_name = distGroup

      const result = await getDriverBehaviorDistributions(params)
      setDistributions(result ?? { available: false, reason: 'No data' })
    } catch (e) {
      console.error('Distributions:', e)
    } finally {
      setDistLoading(false)
    }
  }, [distDimension, distGroup, country, city, periodDays])

  useEffect(() => { loadData() }, [loadData])
  useEffect(() => { loadDistributions() }, [loadDistributions])

  const kpiCard = (label, value, color = 'ct-accent') => (
    <div className="bg-ct-card border border-ct-border rounded-lg px-4 py-3">
      <div className="text-2xs text-ct-text3 uppercase tracking-wide">{label}</div>
      <div className={`text-xl font-bold text-${color} mt-0.5`}>{formatNum(value)}</div>
    </div>
  )

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="bg-ct-card border border-ct-border rounded-xl px-5 py-4">
        <h2 className="text-lg font-bold text-ct-text">Driver Behavior Benchmarking</h2>
        <p className="text-xs text-ct-text3 mt-1">
          Comparación diagnóstica de patrones operativos. No genera recomendaciones automáticas.
        </p>
      </div>

      {/* Filtros */}
      <div className="bg-ct-card border border-ct-border rounded-lg px-4 py-3 flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-2xs text-ct-text3 mb-0.5">País</label>
          <input
            type="text"
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            placeholder="Todos"
            className="w-28 px-2 py-1 rounded bg-ct-bg border border-ct-border text-xs text-ct-text focus:border-ct-accent focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-2xs text-ct-text3 mb-0.5">Ciudad</label>
          <input
            type="text"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            placeholder="Todas"
            className="w-28 px-2 py-1 rounded bg-ct-bg border border-ct-border text-xs text-ct-text focus:border-ct-accent focus:outline-none"
          />
        </div>
        <div>
          <label className="block text-2xs text-ct-text3 mb-0.5">Ventana (días)</label>
          <select
            value={periodDays}
            onChange={(e) => setPeriodDays(Number(e.target.value))}
            className="w-24 px-2 py-1 rounded bg-ct-bg border border-ct-border text-xs text-ct-text focus:border-ct-accent focus:outline-none"
          >
            <option value={7}>7</option>
            <option value={14}>14</option>
            <option value={28}>28</option>
            <option value={60}>60</option>
            <option value={90}>90</option>
          </select>
        </div>
        <button
          type="button"
          onClick={loadData}
          disabled={loading}
          className="px-3 py-1.5 rounded bg-ct-accent text-white text-xs font-medium hover:opacity-90 disabled:opacity-50"
        >
          {loading ? 'Cargando...' : 'Actualizar'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-xs text-red-700">{error}</div>
      )}

      {/* KPI Cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
          {kpiCard('Conductores analizados', summary.total_drivers_analyzed)}
          {kpiCard('Top Performers', summary.top_performer_count, 'green-500')}
          {kpiCard('Declining', summary.declining_count, 'yellow-500')}
          {kpiCard('At Risk', summary.at_risk_count, 'red-500')}
          {kpiCard('Métricas disponibles', summary.available_metrics?.length || 0)}
          {kpiCard('Métricas faltantes', summary.missing_metrics?.length || 0, 'yellow-500')}
        </div>
      )}

      {/* Fuente de datos y rango */}
      {summary && (
        <div className="bg-ct-card border border-ct-border rounded-lg px-4 py-2 text-2xs text-ct-text3 flex flex-wrap gap-x-4">
          <span>Fuente: <code className="text-ct-accent">{summary.data_source}</code></span>
          <span>Rango: {summary.date_range?.from} → {summary.date_range?.to}</span>
          <span>Grupos detectados: {summary.groups_count}</span>
        </div>
      )}

      {/* Group Benchmarks Table */}
      {groups.length > 0 && (
        <div className="bg-ct-card border border-ct-border rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-ct-border">
            <h3 className="text-sm font-semibold text-ct-text">Group Benchmarks</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-ct-bg text-ct-text3 uppercase tracking-wide">
                  <th className="text-left px-3 py-2 font-medium">Grupo</th>
                  <th className="text-right px-3 py-2 font-medium">Drivers</th>
                  <th className="text-right px-3 py-2 font-medium">Viajes totales</th>
                  <th className="text-right px-3 py-2 font-medium">Viajes/driver</th>
                  <th className="text-right px-3 py-2 font-medium">Días activos</th>
                  <th className="text-right px-3 py-2 font-medium">Viajes/día activo</th>
                  <th className="text-right px-3 py-2 font-medium">Consistencia</th>
                  <th className="text-right px-3 py-2 font-medium">Ticket promedio</th>
                  <th className="text-right px-3 py-2 font-medium">Revenue/driver</th>
                  <th className="text-right px-3 py-2 font-medium">Horas pico</th>
                  <th className="text-right px-3 py-2 font-medium">Fin de semana</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((g) => (
                  <tr key={g.group_name} className="border-b border-ct-border hover:bg-ct-bg/50">
                    <td className="px-3 py-2 font-medium text-ct-text">
                      <span className={
                        g.group_name === 'TOP_PERFORMER' ? 'text-green-600' :
                        g.group_name === 'DECLINING' ? 'text-yellow-600' :
                        g.group_name === 'AT_RISK' ? 'text-red-600' :
                        g.group_name === 'DORMANT' || g.group_name === 'CHURNED' ? 'text-ct-text3' :
                        ''
                      }>{g.group_name}</span>
                    </td>
                    <td className="text-right px-3 py-2">{formatNum(g.drivers_count)}</td>
                    <td className="text-right px-3 py-2">{formatNum(g.total_trips)}</td>
                    <td className="text-right px-3 py-2">{formatNum(g.avg_trips_per_driver)}</td>
                    <td className="text-right px-3 py-2">{formatNum(g.avg_active_days)}</td>
                    <td className="text-right px-3 py-2">{formatNum(g.trips_per_active_day)}</td>
                    <td className="text-right px-3 py-2">{formatPct(g.consistency_score)}</td>
                    <td className="text-right px-3 py-2">{g.avg_ticket != null ? formatCurrency(g.avg_ticket) : '—'}</td>
                    <td className="text-right px-3 py-2">{g.revenue_per_driver != null ? formatCurrency(g.revenue_per_driver) : '—'}</td>
                    <td className="text-right px-3 py-2">{g.peak_hour_share != null ? formatPct(g.peak_hour_share) : '—'}</td>
                    <td className="text-right px-3 py-2">{g.weekend_share != null ? formatPct(g.weekend_share) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {groups.length === 0 && (
            <div className="px-4 py-8 text-center text-xs text-ct-text3">Sin datos de grupos disponibles.</div>
          )}
        </div>
      )}

      {/* Top vs Risk Comparison */}
      {topVsRisk && topVsRisk.comparisons && topVsRisk.comparisons.length > 0 && (
        <div className="bg-ct-card border border-ct-border rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-ct-border">
            <h3 className="text-sm font-semibold text-ct-text">
              Comparación TOP vs Declining / At-Risk
            </h3>
            <div className="text-2xs text-ct-text3 mt-0.5">
              TOP: {topVsRisk.group_counts?.top_performer || 0} drivers |
              DECLINING: {topVsRisk.group_counts?.declining || 0} drivers |
              AT_RISK: {topVsRisk.group_counts?.at_risk || 0} drivers
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-ct-bg text-ct-text3 uppercase tracking-wide">
                  <th className="text-left px-3 py-2 font-medium">Métrica</th>
                  <th className="text-right px-3 py-2 font-medium">TOP</th>
                  <th className="text-right px-3 py-2 font-medium">DECLINING</th>
                  <th className="text-right px-3 py-2 font-medium">AT RISK</th>
                  <th className="text-right px-3 py-2 font-medium">Gap TOP-DECL</th>
                  <th className="text-right px-3 py-2 font-medium">Gap TOP-RISK</th>
                  <th className="text-left px-3 py-2 font-medium">Interpretación</th>
                </tr>
              </thead>
              <tbody>
                {topVsRisk.comparisons.map((row, i) => (
                  <tr key={i} className="border-b border-ct-border hover:bg-ct-bg/50">
                    <td className="px-3 py-2 font-medium text-ct-text">{row.metric_label}</td>
                    <td className="text-right px-3 py-2">
                      {row.unit === 'currency' ? formatCurrency(row.top_performer_value) :
                       row.unit === 'ratio' ? formatPct(row.top_performer_value) :
                       formatNum(row.top_performer_value)}
                    </td>
                    <td className="text-right px-3 py-2">
                      {row.declining_value != null
                        ? (row.unit === 'currency' ? formatCurrency(row.declining_value) :
                           row.unit === 'ratio' ? formatPct(row.declining_value) :
                           formatNum(row.declining_value))
                        : '—'}
                    </td>
                    <td className="text-right px-3 py-2">
                      {row.at_risk_value != null
                        ? (row.unit === 'currency' ? formatCurrency(row.at_risk_value) :
                           row.unit === 'ratio' ? formatPct(row.at_risk_value) :
                           formatNum(row.at_risk_value))
                        : '—'}
                    </td>
                    <td className={`text-right px-3 py-2 ${row.gap_top_vs_declining > 0 ? 'text-green-600' : row.gap_top_vs_declining < 0 ? 'text-red-500' : ''}`}>
                      {row.gap_top_vs_declining != null ? formatGap(row.gap_top_vs_declining, row.unit) : '—'}
                    </td>
                    <td className={`text-right px-3 py-2 ${row.gap_top_vs_at_risk > 0 ? 'text-green-600' : row.gap_top_vs_at_risk < 0 ? 'text-red-500' : ''}`}>
                      {row.gap_top_vs_at_risk != null ? formatGap(row.gap_top_vs_at_risk, row.unit) : '—'}
                    </td>
                    <td className="px-3 py-2 text-ct-text2 italic">{row.interpretation || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Distributions */}
      {distributions && (
        <div className="bg-ct-card border border-ct-border rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-ct-border flex flex-wrap items-center gap-3">
            <h3 className="text-sm font-semibold text-ct-text">Distribuciones</h3>
            <div className="flex items-center gap-2">
              <label className="text-2xs text-ct-text3">Dimensión:</label>
              <select
                value={distDimension}
                onChange={(e) => setDistDimension(e.target.value)}
                className="px-2 py-1 rounded bg-ct-bg border border-ct-border text-xs text-ct-text"
              >
                {DIMENSION_OPTIONS.map((d) => (
                  <option key={d.value} value={d.value}>{d.label}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-2xs text-ct-text3">Grupo:</label>
              <select
                value={distGroup}
                onChange={(e) => setDistGroup(e.target.value)}
                className="px-2 py-1 rounded bg-ct-bg border border-ct-border text-xs text-ct-text"
              >
                <option value="">Todos</option>
                {groups.map((g) => (
                  <option key={g.group_name} value={g.group_name}>{g.group_name}</option>
                ))}
              </select>
            </div>
          </div>
          {distributions.available === false ? (
            <div className="px-4 py-6 text-center text-xs text-ct-text3">
              {distributions.reason}
            </div>
          ) : (
            <div className="overflow-x-auto">
              {distributions.distributions?.map((dist) => (
                <div key={dist.group_name}>
                  <div className="px-4 py-2 bg-ct-bg/50 text-2xs text-ct-text3 uppercase tracking-wide">
                    {dist.group_name} ({dist.drivers_count} drivers)
                  </div>
                  {dist.data && dist.data.length > 0 ? (
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="text-ct-text3 uppercase">
                          <th className="text-left px-3 py-1.5 font-medium">{distDimension === 'hour' ? 'Hora' : distDimension === 'day_of_week' ? 'Día' : 'Valor'}</th>
                          <th className="text-right px-3 py-1.5 font-medium">Viajes</th>
                          <th className="text-right px-3 py-1.5 font-medium">Conductores</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dist.data.map((row, i) => (
                          <tr key={i} className="border-b border-ct-border/50 hover:bg-ct-bg/30">
                            <td className="px-3 py-1.5 text-ct-text">{row.label || '—'}</td>
                            <td className="text-right px-3 py-1.5">{formatNum(row.trips)}</td>
                            <td className="text-right px-3 py-1.5">{formatNum(row.driver_count)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : (
                    <div className="px-4 py-3 text-xs text-ct-text3">Sin datos para esta dimensión.</div>
                  )}
                </div>
              ))}
            </div>
          )}
          {distLoading && (
            <div className="px-4 py-6 text-center text-xs text-ct-text3">Cargando distribuciones...</div>
          )}
        </div>
      )}

      {/* Banner de limitaciones */}
      {summary && summary.missing_metrics && summary.missing_metrics.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3">
          <h4 className="text-xs font-semibold text-yellow-800 mb-1">Métricas no disponibles</h4>
          <p className="text-2xs text-yellow-700">
            Las siguientes métricas no están disponibles por falta de columnas en la fuente de datos:
          </p>
          <ul className="mt-1 space-y-0.5">
            {summary.missing_metrics.map((m) => (
              <li key={m} className="text-2xs text-yellow-700">
                <strong>{m}</strong>: no existe en {summary.data_source || 'la fuente de datos'}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
