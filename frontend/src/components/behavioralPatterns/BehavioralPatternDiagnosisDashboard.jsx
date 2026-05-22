/**
 * Behavioral Pattern Diagnosis Dashboard — Fase 2A.3
 * Explica patrones operativos diferenciales entre grupos de conductores.
 * Diagnóstico determinístico. NO recomendaciones automáticas.
 */
import { useState, useEffect, useCallback } from 'react'
import {
  getBehavioralPatternsSummary,
  getBehavioralPatterns,
  getBehavioralGroupProfile,
  getBehavioralDeclineSignals,
} from '../../services/api'

const LIFECYCLE_GROUPS = [
  'TOP_PERFORMER', 'STABLE', 'GROWING', 'DECLINING',
  'AT_RISK', 'DORMANT', 'CHURNED', 'REACTIVATED',
]

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
  if (Math.abs(num) < 1 && num !== 0) return (num * 100).toFixed(1) + '%'
  return num.toFixed(1) + '%'
}

function formatCurrency (n) {
  if (n == null || n === '') return '—'
  const num = Number(n)
  if (Number.isNaN(num)) return '—'
  return num.toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function strengthBadge (s) {
  const colors = {
    HIGH: 'bg-red-100 text-red-700 border-red-200',
    MEDIUM: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    LOW: 'bg-blue-100 text-blue-700 border-blue-200',
  }
  return (
    <span className={`px-1.5 py-0.5 rounded text-2xs font-medium border ${colors[s] || 'bg-gray-100 text-gray-600'}`}>
      {s}
    </span>
  )
}

export default function BehavioralPatternDiagnosisDashboard () {
  const [country, setCountry] = useState('')
  const [city, setCity] = useState('')
  const [periodDays, setPeriodDays] = useState(28)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const [summary, setSummary] = useState(null)
  const [patterns, setPatterns] = useState([])
  const [declineSignals, setDeclineSignals] = useState([])
  const [selectedGroup, setSelectedGroup] = useState('TOP_PERFORMER')
  const [groupProfile, setGroupProfile] = useState(null)
  const [profileLoading, setProfileLoading] = useState(false)

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = { period_days: periodDays }
      if (country) params.country = country
      if (city) params.city = city

      const [sum, pats, sigs] = await Promise.all([
        getBehavioralPatternsSummary(params),
        getBehavioralPatterns(params),
        getBehavioralDeclineSignals(params),
      ])
      setSummary(sum)
      setPatterns(pats.patterns || [])
      setDeclineSignals(sigs.signals || [])
    } catch (e) {
      console.error('Behavioral Patterns:', e)
      setError(e.response?.data?.detail || e.message || 'Error')
    } finally {
      setLoading(false)
    }
  }, [country, city, periodDays])

  const loadProfile = useCallback(async (group) => {
    setProfileLoading(true)
    try {
      const params = { group_name: group, period_days: periodDays }
      if (country) params.country = country
      if (city) params.city = city
      const prof = await getBehavioralGroupProfile(params)
      setGroupProfile(prof)
    } catch (e) {
      console.error('Group profile:', e)
    } finally {
      setProfileLoading(false)
    }
  }, [country, city, periodDays])

  useEffect(() => { loadData() }, [loadData])
  useEffect(() => { loadProfile(selectedGroup) }, [selectedGroup, loadProfile])

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
        <h2 className="text-lg font-bold text-ct-text">Behavioral Pattern Diagnosis</h2>
        <p className="text-xs text-ct-text3 mt-1">
          Diagnóstico determinístico de patrones operativos diferenciales. No genera recomendaciones automáticas.
        </p>
      </div>

      {/* Filtros */}
      <div className="bg-ct-card border border-ct-border rounded-lg px-4 py-3 flex flex-wrap items-end gap-3">
        <div>
          <label className="block text-2xs text-ct-text3 mb-0.5">País</label>
          <input type="text" value={country} onChange={(e) => setCountry(e.target.value)} placeholder="Todos"
            className="w-28 px-2 py-1 rounded bg-ct-bg border border-ct-border text-xs text-ct-text focus:border-ct-accent focus:outline-none" />
        </div>
        <div>
          <label className="block text-2xs text-ct-text3 mb-0.5">Ciudad</label>
          <input type="text" value={city} onChange={(e) => setCity(e.target.value)} placeholder="Todas"
            className="w-28 px-2 py-1 rounded bg-ct-bg border border-ct-border text-xs text-ct-text focus:border-ct-accent focus:outline-none" />
        </div>
        <div>
          <label className="block text-2xs text-ct-text3 mb-0.5">Ventana (días)</label>
          <select value={periodDays} onChange={(e) => setPeriodDays(Number(e.target.value))}
            className="w-24 px-2 py-1 rounded bg-ct-bg border border-ct-border text-xs text-ct-text focus:border-ct-accent focus:outline-none">
            <option value={7}>7</option>
            <option value={14}>14</option>
            <option value={28}>28</option>
            <option value={60}>60</option>
            <option value={90}>90</option>
          </select>
        </div>
        <button type="button" onClick={loadData} disabled={loading}
          className="px-3 py-1.5 rounded bg-ct-accent text-white text-xs font-medium hover:opacity-90 disabled:opacity-50">
          {loading ? 'Cargando...' : 'Actualizar'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-xs text-red-700">{error}</div>
      )}

      {/* KPI Cards */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
          {kpiCard('Patrones detectados', summary.total_patterns_detected)}
          {kpiCard('HIGH', summary.high_strength_patterns, 'red-500')}
          {kpiCard('MEDIUM', summary.medium_strength_patterns, 'yellow-500')}
          {kpiCard('LOW', summary.low_strength_patterns, 'blue-500')}
          {kpiCard('Dimensiones disponibles', summary.dimensions_available?.length || 0)}
          {kpiCard('Dimensiones faltantes', summary.dimensions_missing?.length || 0, 'yellow-500')}
        </div>
      )}

      {/* Source info */}
      {summary && (
        <div className="bg-ct-card border border-ct-border rounded-lg px-4 py-2 text-2xs text-ct-text3 flex flex-wrap gap-x-4">
          <span>Fuente: <code className="text-ct-accent">{summary.data_source}</code></span>
          <span>Modo: <code className="text-ct-accent">{summary.diagnostic_mode}</code></span>
          <span>Rango: {summary.date_range?.from} → {summary.date_range?.to}</span>
        </div>
      )}

      {/* Detected Patterns */}
      <div className="bg-ct-card border border-ct-border rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-ct-border flex justify-between items-center">
          <h3 className="text-sm font-semibold text-ct-text">
            Patrones Detectados ({patterns.length})
          </h3>
        </div>
        {patterns.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-ct-bg text-ct-text3 uppercase tracking-wide">
                  <th className="text-left px-3 py-2 font-medium">Dimensión</th>
                  <th className="text-left px-3 py-2 font-medium">Título</th>
                  <th className="text-center px-3 py-2 font-medium">Fuerza</th>
                  <th className="text-center px-3 py-2 font-medium">Comparación</th>
                  <th className="text-right px-3 py-2 font-medium">Gap %</th>
                  <th className="text-left px-3 py-2 font-medium">Interpretación</th>
                </tr>
              </thead>
              <tbody>
                {patterns.map((p, i) => (
                  <tr key={i} className="border-b border-ct-border hover:bg-ct-bg/50">
                    <td className="px-3 py-2 text-ct-text2">{p.dimension}</td>
                    <td className="px-3 py-2 font-medium text-ct-text">{p.title}</td>
                    <td className="px-3 py-2 text-center">{strengthBadge(p.strength)}</td>
                    <td className="px-3 py-2 text-center text-ct-text2">{p.comparison_groups}</td>
                    <td className="px-3 py-2 text-right font-medium">{formatPct(p.gap_pct)}</td>
                    <td className="px-3 py-2 text-ct-text2 italic max-w-xs">{p.interpretation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="px-4 py-8 text-center text-xs text-ct-text3">No se detectaron patrones con la fuerza mínima.</div>
        )}
      </div>

      {/* Group Profiles */}
      <div className="bg-ct-card border border-ct-border rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-ct-border flex flex-wrap items-center gap-3">
          <h3 className="text-sm font-semibold text-ct-text">Group Profile</h3>
          <select value={selectedGroup} onChange={(e) => setSelectedGroup(e.target.value)}
            className="px-2 py-1 rounded bg-ct-bg border border-ct-border text-xs text-ct-text">
            {LIFECYCLE_GROUPS.map((g) => (
              <option key={g} value={g}>{g}</option>
            ))}
          </select>
          {profileLoading && <span className="text-2xs text-ct-text3">Cargando...</span>}
        </div>
        {groupProfile && groupProfile.available !== false ? (
          <div className="p-4 space-y-3">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                ['Drivers', groupProfile.drivers_count],
                ['Viajes totales', groupProfile.total_trips],
                ['Viajes/driver', groupProfile.avg_trips_per_driver],
                ['Días activos', groupProfile.avg_active_days],
                ['Viajes/día activo', groupProfile.trips_per_active_day],
                ['Consistencia', formatPct(groupProfile.consistency_score)],
                ['Fin de semana', groupProfile.weekend_share != null ? formatPct(groupProfile.weekend_share) : '—'],
                ['Ticket promedio', groupProfile.avg_ticket != null ? formatCurrency(groupProfile.avg_ticket) : '—'],
              ].map(([label, val]) => (
                <div key={label} className="bg-ct-bg rounded-lg px-3 py-2">
                  <div className="text-2xs text-ct-text3">{label}</div>
                  <div className="text-sm font-semibold text-ct-text">{val}</div>
                </div>
              ))}
            </div>

            {groupProfile.top_cities && groupProfile.top_cities.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-ct-text mb-1">Top Ciudades</h4>
                <div className="flex flex-wrap gap-2">
                  {groupProfile.top_cities.map((c, i) => (
                    <span key={i} className="px-2 py-0.5 rounded bg-ct-bg border border-ct-border text-2xs text-ct-text2">
                      {c.label} ({c.trips} viajes, {c.driver_count} drivers)
                    </span>
                  ))}
                </div>
              </div>
            )}

            {groupProfile.top_parks && groupProfile.top_parks.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-ct-text mb-1">Top Parks</h4>
                <div className="flex flex-wrap gap-2">
                  {groupProfile.top_parks.slice(0, 5).map((p, i) => (
                    <span key={i} className="px-2 py-0.5 rounded bg-ct-bg border border-ct-border text-2xs text-ct-text2">
                      {p.label} ({p.trips} viajes)
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="px-4 py-6 text-center text-xs text-ct-text3">
            {groupProfile?.reason || 'Grupo sin datos en el periodo.'}
          </div>
        )}
      </div>

      {/* Decline Signals */}
      <div className="bg-ct-card border border-ct-border rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-ct-border">
          <h3 className="text-sm font-semibold text-ct-text">
            Señales de Deterioro ({declineSignals.length})
          </h3>
          <p className="text-2xs text-ct-text3 mt-0.5">
            Comparación STABLE vs DECLINING / AT_RISK. Diagnóstico, no recomendaciones.
          </p>
        </div>
        {declineSignals.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-ct-bg text-ct-text3 uppercase tracking-wide">
                  <th className="text-left px-3 py-2 font-medium">Señal</th>
                  <th className="text-right px-3 py-2 font-medium">STABLE</th>
                  <th className="text-right px-3 py-2 font-medium">DECLINING</th>
                  <th className="text-right px-3 py-2 font-medium">AT RISK</th>
                  <th className="text-right px-3 py-2 font-medium">Gap %</th>
                  <th className="text-center px-3 py-2 font-medium">Fuerza</th>
                  <th className="text-left px-3 py-2 font-medium">Interpretación</th>
                </tr>
              </thead>
              <tbody>
                {declineSignals.map((s, i) => (
                  <tr key={i} className="border-b border-ct-border hover:bg-ct-bg/50">
                    <td className="px-3 py-2 font-medium text-ct-text">{s.signal_name}</td>
                    <td className="text-right px-3 py-2">{formatNum(s.stable_value)}</td>
                    <td className="text-right px-3 py-2 text-yellow-600">{formatNum(s.declining_value)}</td>
                    <td className="text-right px-3 py-2 text-red-600">{formatNum(s.at_risk_value)}</td>
                    <td className="text-right px-3 py-2 font-medium text-red-600">{formatPct(s.max_gap_pct)}</td>
                    <td className="px-3 py-2 text-center">{strengthBadge(s.strength)}</td>
                    <td className="px-3 py-2 text-ct-text2 italic max-w-xs">{s.interpretation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="px-4 py-8 text-center text-xs text-ct-text3">No se detectaron señales de deterioro significativas.</div>
        )}
      </div>

      {/* Banner de limitaciones */}
      {summary && summary.missing_metrics && summary.missing_metrics.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-4 py-3">
          <h4 className="text-xs font-semibold text-yellow-800 mb-1">Limitaciones</h4>
          <ul className="mt-1 space-y-0.5">
            <li className="text-2xs text-yellow-700">
              Métricas no disponibles: <strong>{summary.missing_metrics.join(', ')}</strong>
            </li>
            <li className="text-2xs text-yellow-700">
              <strong>enrich_from_trips=false</strong> por defecto (revenue, hour, distance no disponibles)
            </li>
            <li className="text-2xs text-yellow-700">
              No se generan recomendaciones automáticas. Solo diagnóstico determinístico.
            </li>
          </ul>
        </div>
      )}
    </div>
  )
}
