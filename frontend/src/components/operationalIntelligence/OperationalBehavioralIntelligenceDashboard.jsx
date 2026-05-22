/**
 * Operational Behavioral Intelligence Dashboard — Fase 2B
 * Análisis operacional profundo de conductores.
 * NO genera recomendaciones automáticas. Solo diagnóstico.
 *
 * Secciones:
 *   1. KPI Cards de eficiencia
 *   2. Archetypes
 *   3. Session Analytics
 *   4. Time Patterns
 *   5. Zone Behavior
 *   6. Pre-Churn Signals
 *   7. Top vs Churned
 *   8. Missing Metrics Banner
 */
import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'

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

function formatMinutes (min) {
  if (min == null || min === '') return '—'
  const m = Number(min)
  if (Number.isNaN(m)) return '—'
  if (m < 60) return Math.round(m) + ' min'
  const h = Math.floor(m / 60)
  const remainder = Math.round(m % 60)
  return h + 'h ' + remainder + 'm'
}

const SEVERITY_COLORS = {
  EARLY_WARNING: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  MODERATE_DEGRADATION: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  STRONG_DEGRADATION: 'bg-red-500/20 text-red-400 border-red-500/30',
}

const ARCHETYPE_COLORS = {
  FULLTIMER: '#3b82f6',
  PART_TIMER: '#8b5cf6',
  WEEKEND_SPECIALIST: '#f59e0b',
  PEAK_HOUR_SPECIALIST: '#ef4444',
  HIGH_EFFICIENCY: '#10b981',
  HIGH_VOLUME_LOW_EFFICIENCY: '#f97316',
  CONSISTENT_OPERATOR: '#06b6d4',
  INCONSISTENT_OPERATOR: '#6b7280',
  BURNOUT_PATTERN: '#dc2626',
  UNCLASSIFIED: '#6b7280',
}

export default function OperationalBehavioralIntelligenceDashboard () {
  const [country, setCountry] = useState('')
  const [city, setCity] = useState('')
  const [periodDays, setPeriodDays] = useState(28)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const [summary, setSummary] = useState(null)
  const [efficiency, setEfficiency] = useState(null)
  const [sessions, setSessions] = useState(null)
  const [zones, setZones] = useState(null)
  const [timePatterns, setTimePatterns] = useState(null)
  const [preChurn, setPreChurn] = useState(null)
  const [archetypes, setArchetypes] = useState(null)
  const [topVsChurned, setTopVsChurned] = useState(null)

  const [activeSection, setActiveSection] = useState('efficiency')

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = { period_days: periodDays }
      if (country) params.country = country
      if (city) params.city = city

      const [sum, eff, sess, zon, timeP, churn, arch, tvc] = await Promise.all([
        api.get('/operational-intelligence/summary', { params, timeout: 120000 }).then(r => r.data),
        api.get('/operational-intelligence/efficiency', { params, timeout: 120000 }).then(r => r.data),
        api.get('/operational-intelligence/sessions', { params, timeout: 120000 }).then(r => r.data),
        api.get('/operational-intelligence/zones', { params, timeout: 120000 }).then(r => r.data),
        api.get('/operational-intelligence/time-patterns', { params, timeout: 120000 }).then(r => r.data),
        api.get('/operational-intelligence/pre-churn-signals', { params, timeout: 120000 }).then(r => r.data),
        api.get('/operational-intelligence/archetypes', { params, timeout: 120000 }).then(r => r.data),
        api.get('/operational-intelligence/top-vs-churned', { params, timeout: 120000 }).then(r => r.data),
      ])
      setSummary(sum)
      setEfficiency(eff)
      setSessions(sess)
      setZones(zon)
      setTimePatterns(timeP)
      setPreChurn(churn)
      setArchetypes(arch)
      setTopVsChurned(tvc)
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Error al cargar datos')
    } finally {
      setLoading(false)
    }
  }, [country, city, periodDays])

  useEffect(() => { loadData() }, [loadData])

  const missingMetrics = []
  if (efficiency?.unavailable_kpis) {
    Object.entries(efficiency.unavailable_kpis).forEach(([k, v]) => missingMetrics.push(v))
  }

  const sections = [
    { key: 'efficiency', label: 'Eficiencia', count: efficiency?.kpis?.drivers_in_sample },
    { key: 'sessions', label: 'Sesiones', count: sessions?.sessions?.drivers_with_sessions },
    { key: 'archetypes', label: 'Arquetipos', count: archetypes?.total_drivers_classified },
    { key: 'time', label: 'Horarios', count: timePatterns?.hourly_distribution?.length },
    { key: 'zones', label: 'Zonas', count: zones?.zones?.length },
    { key: 'prechurn', label: 'Pre-Churn', count: preChurn?.total_drivers_with_signals },
    { key: 'comparison', label: 'Top vs Churned', count: topVsChurned?.comparison?.length },
  ]

  return (
    <div className="space-y-3">
      {/* ── Header ── */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold text-ct-text">Operational Intelligence</h1>
          <p className="text-2xs text-ct-text2">Análisis operacional profundo de conductores</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={periodDays}
            onChange={e => setPeriodDays(Number(e.target.value))}
            className="bg-ct-surface border border-ct-border rounded px-2 py-1 text-2xs text-ct-text"
          >
            <option value={7}>7 días</option>
            <option value={14}>14 días</option>
            <option value={28}>28 días</option>
            <option value={56}>56 días</option>
            <option value={90}>90 días</option>
          </select>
          <button
            type="button"
            onClick={loadData}
            disabled={loading}
            className="px-3 py-1 rounded text-2xs bg-ct-accent text-white hover:opacity-90 disabled:opacity-50"
          >
            {loading ? 'Cargando...' : 'Actualizar'}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/15 border border-red-500/30 rounded px-3 py-2 text-2xs text-red-400">
          {error}
        </div>
      )}

      {/* ── Missing Metrics Banner ── */}
      {missingMetrics.length > 0 && (
        <div className="bg-yellow-500/10 border border-yellow-500/20 rounded px-3 py-2">
          <p className="text-2xs font-medium text-yellow-400 mb-1">Métricas no disponibles</p>
          <ul className="text-2xs text-yellow-400/80 space-y-0.5">
            {missingMetrics.map((m, i) => <li key={i}>- {m}</li>)}
          </ul>
        </div>
      )}

      {/* ── KPI Cards de Eficiencia ── */}
      {efficiency?.kpis && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
          {[
            { label: 'Revenue/hora', value: formatCurrency(efficiency.kpis.avg_revenue_per_hour) },
            { label: 'Revenue/km', value: formatCurrency(efficiency.kpis.avg_revenue_per_km) },
            { label: 'Viajes/hora', value: formatNum(efficiency.kpis.avg_trips_per_hour) },
            { label: 'Viajes/día', value: formatNum(efficiency.kpis.avg_trips_per_day) },
            { label: 'Revenue/viaje', value: formatCurrency(efficiency.kpis.avg_revenue_per_trip) },
            { label: 'Peak share', value: formatPct(efficiency.kpis.avg_peak_hour_share) },
            { label: 'Weekend share', value: formatPct(efficiency.kpis.avg_weekend_share) },
            { label: 'Zone conc.', value: formatNum(efficiency.kpis.avg_zone_concentration) },
            { label: 'Km/viaje', value: formatNum(efficiency.kpis.avg_km_per_trip) },
            { label: 'Muestra', value: efficiency.kpis.drivers_in_sample?.toLocaleString() + ' drivers' },
          ].map((kpi, i) => (
            <div key={i} className="bg-ct-card border border-ct-border rounded-lg p-3">
              <p className="text-2xs text-ct-text3">{kpi.label}</p>
              <p className="text-sm font-semibold text-ct-text mt-0.5">{kpi.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* ── Section Tabs ── */}
      <div className="flex flex-wrap gap-1.5">
        {sections.map(({ key, label, count }) => (
          <button
            key={key}
            type="button"
            onClick={() => setActiveSection(key)}
            className={`px-3 py-1.5 rounded text-2xs font-medium transition-all ${
              activeSection === key
                ? 'bg-ct-accent text-white shadow-sm'
                : 'text-ct-text2 hover:text-ct-text hover:bg-ct-border'
            }`}
          >
            {label}
            {count != null && <span className="ml-1 opacity-60">({count})</span>}
          </button>
        ))}
      </div>

      {/* ── SECTION: Eficiencia (percentiles) ── */}
      {activeSection === 'efficiency' && efficiency?.percentiles && (
        <div className="bg-ct-card border border-ct-border rounded-lg p-4">
          <h3 className="text-xs font-semibold text-ct-text mb-3">Distribución Revenue/Hora</h3>
          <div className="grid grid-cols-5 gap-2">
            {['p10', 'p25', 'p50', 'p75', 'p90'].map(p => (
              <div key={p} className="text-center">
                <p className="text-2xs text-ct-text3 uppercase">{p}</p>
                <p className="text-sm font-semibold text-ct-text">
                  {formatCurrency(efficiency.percentiles.revenue_per_hour?.[p])}
                </p>
              </div>
            ))}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-2xs text-ct-text2">
            <p>Mediana viajes: {efficiency.percentiles.completed_trips_p50}</p>
            <p>Mediana días activos: {efficiency.percentiles.active_days_p50}</p>
          </div>
        </div>
      )}

      {/* ── SECTION: Archetypes ── */}
      {activeSection === 'archetypes' && archetypes?.distribution && (
        <div className="space-y-3">
          <div className="bg-ct-card border border-ct-border rounded-lg p-4">
            <h3 className="text-xs font-semibold text-ct-text mb-3">Distribución de Arquetipos</h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
              {Object.entries(archetypes.distribution).map(([arch, count]) => (
                <div key={arch} className="flex items-center gap-2 p-2 rounded bg-ct-surface">
                  <div
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{ backgroundColor: ARCHETYPE_COLORS[arch] || '#6b7280' }}
                  />
                  <div className="min-w-0">
                    <p className="text-2xs text-ct-text truncate">{arch.replace(/_/g, ' ')}</p>
                    <p className="text-xs font-semibold text-ct-text">{count}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
          {archetypes.reference_thresholds && (
            <div className="bg-ct-card border border-ct-border rounded-lg p-4">
              <h3 className="text-xs font-semibold text-ct-text mb-2">Umbrales de Referencia (P50)</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-2xs">
                {Object.entries(archetypes.reference_thresholds).map(([k, v]) => (
                  <div key={k}>
                    <span className="text-ct-text3">{k.replace(/_/g, ' ')}: </span>
                    <span className="text-ct-text font-medium">{typeof v === 'number' ? formatNum(v) : v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {archetypes?.classification_rules && (
            <div className="bg-ct-card border border-ct-border rounded-lg p-4">
              <h3 className="text-xs font-semibold text-ct-text mb-2">Reglas de Clasificación</h3>
              <div className="text-2xs text-ct-text2 space-y-1 max-h-48 overflow-y-auto">
                {Object.entries(archetypes.classification_rules).map(([arch, rule]) => (
                  <p key={arch}>
                    <span className="font-medium text-ct-text">{arch.replace(/_/g, ' ')}: </span>
                    {rule}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── SECTION: Sessions ── */}
      {activeSection === 'sessions' && sessions && (
        <div className="space-y-3">
          {!sessions.available ? (
            <div className="bg-yellow-500/10 border border-yellow-500/20 rounded px-3 py-2 text-2xs text-yellow-400">
              {sessions.reason}
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                {[
                  { label: 'Drivers c/sesiones', value: sessions.sessions?.drivers_with_sessions },
                  { label: 'Sesiones/driver', value: formatNum(sessions.sessions?.avg_sessions_per_driver) },
                  { label: 'Trips/driver', value: formatNum(sessions.sessions?.avg_trips_per_driver) },
                  { label: 'Duración sesión', value: formatMinutes(sessions.sessions?.avg_session_duration_min) },
                  { label: 'Trips/sesión', value: formatNum(sessions.sessions?.avg_trips_per_session) },
                  { label: 'Trips/hora (sesión)', value: formatNum(sessions.sessions?.avg_trips_per_hour_in_session) },
                  { label: 'Revenue/sesión', value: formatCurrency(sessions.sessions?.avg_revenue_per_session) },
                  { label: 'Revenue/hora (sesión)', value: formatCurrency(sessions.sessions?.avg_revenue_per_hour_in_session) },
                  { label: 'Idle/sesión', value: formatMinutes(sessions.sessions?.avg_idle_time_per_session_min) },
                  { label: 'Idle entre viajes', value: formatMinutes(sessions.sessions?.avg_idle_between_trips_min) },
                  { label: 'Idle ratio', value: formatPct(sessions.sessions?.avg_idle_ratio) },
                  { label: 'Duración viaje', value: formatMinutes(sessions.sessions?.avg_trip_duration_min) },
                  { label: 'Ticket promedio', value: formatCurrency(sessions.sessions?.avg_ticket_per_trip) },
                  { label: 'Volat. trips sesión', value: formatNum(sessions.sessions?.session_trips_volatility) },
                ].map((kpi, i) => (
                  <div key={i} className="bg-ct-card border border-ct-border rounded-lg p-3">
                    <p className="text-2xs text-ct-text3">{kpi.label}</p>
                    <p className="text-sm font-semibold text-ct-text mt-0.5">{kpi.value}</p>
                  </div>
                ))}
              </div>
              {sessions.distribution_by_trips?.length > 0 && (
                <div className="bg-ct-card border border-ct-border rounded-lg p-4 max-h-64 overflow-y-auto">
                  <h3 className="text-xs font-semibold text-ct-text mb-2">Distribución por Trips/Sesión</h3>
                  <table className="w-full text-2xs">
                    <thead>
                      <tr className="text-ct-text3 border-b border-ct-border">
                        <th className="text-left py-1">Trips</th>
                        <th className="text-right py-1">Sesiones</th>
                        <th className="text-right py-1">Duración media</th>
                        <th className="text-right py-1">Revenue medio</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sessions.distribution_by_trips.map((r, i) => (
                        <tr key={i} className="border-b border-ct-border/30">
                          <td className="py-1 text-ct-text">{r.trips_in_session}</td>
                          <td className="py-1 text-right text-ct-text">{r.session_count}</td>
                          <td className="py-1 text-right text-ct-text">{formatMinutes(r.avg_duration)}</td>
                          <td className="py-1 text-right text-ct-text">{formatCurrency(r.avg_revenue)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* ── SECTION: Time Patterns ── */}
      {activeSection === 'time' && timePatterns?.hourly_distribution && (
        <div className="space-y-3">
          <div className="bg-ct-card border border-ct-border rounded-lg p-4">
            <h3 className="text-xs font-semibold text-ct-text mb-3">Distribución por Hora del Día</h3>
            <div className="max-h-64 overflow-y-auto">
              <div className="space-y-1">
                {timePatterns.hourly_distribution.map((h, i) => {
                  const maxTrips = Math.max(...timePatterns.hourly_distribution.map(d => d.trips || 0))
                  const pct = maxTrips > 0 ? ((h.trips || 0) / maxTrips * 100) : 0
                  return (
                    <div key={i} className="flex items-center gap-2 text-2xs">
                      <span className="w-8 text-right text-ct-text3">{h.trip_hour}h</span>
                      <div className="flex-1 bg-ct-surface rounded h-4 relative overflow-hidden">
                        <div
                          className="absolute inset-y-0 left-0 bg-ct-accent/60 rounded"
                          style={{ width: pct + '%' }}
                        />
                      </div>
                      <span className="w-16 text-right text-ct-text">{h.trips?.toLocaleString()}</span>
                      <span className="w-24 text-right text-ct-text2">{formatCurrency(h.avg_revenue)}</span>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
          {timePatterns.peak_vs_offpeak && (
            <div className="grid grid-cols-2 gap-2">
              {timePatterns.peak_vs_offpeak.map((p, i) => (
                <div key={i} className="bg-ct-card border border-ct-border rounded-lg p-3">
                  <p className="text-xs font-semibold text-ct-text capitalize">
                    {p.period_type === 'peak' ? 'Hora Pico' : 'Fuera de Pico'}
                  </p>
                  <p className="text-2xs text-ct-text2">Viajes: {p.trips?.toLocaleString()}</p>
                  <p className="text-2xs text-ct-text2">Drivers: {p.unique_drivers?.toLocaleString()}</p>
                  <p className="text-2xs text-ct-text2">Revenue/viaje: {formatCurrency(p.avg_revenue)}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── SECTION: Zones ── */}
      {activeSection === 'zones' && zones?.zones && (
        <div className="space-y-3">
          {zones.concentration && (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {[
                { label: 'Zonas/driver', value: formatNum(zones.concentration.avg_zones_per_driver) },
                { label: 'Conc. zona top', value: formatPct(zones.concentration.avg_top_zone_concentration) },
                { label: '1 sola zona', value: zones.concentration.single_zone_drivers + ' drivers' },
                { label: '5+ zonas', value: zones.concentration.multi_zone_drivers + ' drivers' },
                { label: 'Total drivers', value: zones.concentration.total_drivers?.toLocaleString() },
              ].map((kpi, i) => (
                <div key={i} className="bg-ct-card border border-ct-border rounded-lg p-3">
                  <p className="text-2xs text-ct-text3">{kpi.label}</p>
                  <p className="text-sm font-semibold text-ct-text mt-0.5">{kpi.value}</p>
                </div>
              ))}
            </div>
          )}
          <div className="bg-ct-card border border-ct-border rounded-lg p-4 max-h-80 overflow-y-auto">
            <h3 className="text-xs font-semibold text-ct-text mb-2">Top Zonas (Park)</h3>
            <table className="w-full text-2xs">
              <thead>
                <tr className="text-ct-text3 border-b border-ct-border">
                  <th className="text-left py-1">Zona</th>
                  <th className="text-right py-1">Drivers</th>
                  <th className="text-right py-1">Viajes</th>
                  <th className="text-right py-1">Revenue</th>
                  <th className="text-right py-1">Peak%</th>
                  <th className="text-right py-1">W-end%</th>
                </tr>
              </thead>
              <tbody>
                {zones.zones.slice(0, 20).map((z, i) => (
                  <tr key={i} className="border-b border-ct-border/30">
                    <td className="py-1 text-ct-text max-w-[120px] truncate" title={z.park_id}>
                      {z.city || z.park_id?.slice(0, 12) || '—'}
                    </td>
                    <td className="py-1 text-right text-ct-text">{z.unique_drivers}</td>
                    <td className="py-1 text-right text-ct-text">{z.total_trips?.toLocaleString()}</td>
                    <td className="py-1 text-right text-ct-text">{formatCurrency(z.total_revenue)}</td>
                    <td className="py-1 text-right text-ct-text">{formatPct(z.peak_hour_share)}</td>
                    <td className="py-1 text-right text-ct-text">{formatPct(z.weekend_share)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── SECTION: Pre-Churn Signals ── */}
      {activeSection === 'prechurn' && preChurn && (
        <div className="space-y-3">
          {preChurn.severity_summary && (
            <div className="grid grid-cols-3 gap-2">
              {[
                { label: 'Early Warning', key: 'EARLY_WARNING', cls: 'border-yellow-500/30 bg-yellow-500/10' },
                { label: 'Moderate', key: 'MODERATE_DEGRADATION', cls: 'border-orange-500/30 bg-orange-500/10' },
                { label: 'Strong', key: 'STRONG_DEGRADATION', cls: 'border-red-500/30 bg-red-500/10' },
              ].map(({ label, key, cls }) => (
                <div key={key} className={`rounded-lg p-3 border ${cls}`}>
                  <p className="text-2xs text-ct-text2">{label}</p>
                  <p className="text-lg font-bold text-ct-text">{preChurn.severity_summary[key]}</p>
                  <p className="text-2xs text-ct-text3">drivers</p>
                </div>
              ))}
            </div>
          )}
          {preChurn.signals?.length > 0 && (
            <div className="bg-ct-card border border-ct-border rounded-lg p-4 max-h-80 overflow-y-auto">
              <h3 className="text-xs font-semibold text-ct-text mb-2">
                Drivers con Señales ({preChurn.total_drivers_with_signals})
              </h3>
              {preChurn.signals.slice(0, 50).map((s, i) => (
                <div key={i} className="border-b border-ct-border/30 py-2 text-2xs">
                  <div className="flex items-center gap-2">
                    <span className="text-ct-text font-mono text-2xs">{s.driver_id?.slice(0, 12)}</span>
                    <span className={`px-1.5 py-0.5 rounded border text-2xs ${SEVERITY_COLORS[s.max_severity] || ''}`}>
                      {s.max_severity?.replace(/_/g, ' ') || '—'}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {s.signals?.map((sig, j) => (
                      <span key={j} className={`px-1 py-0.5 rounded border text-2xs ${SEVERITY_COLORS[sig.severity] || ''}`}>
                        {sig.type?.replace(/_/g, ' ')}: {sig.change_pct}%
                      </span>
                    ))}
                  </div>
                  <div className="flex gap-3 mt-1 text-ct-text3">
                    <span>P1: {s.first_half?.trips} trips, {formatCurrency(s.first_half?.revenue)}</span>
                    <span>P2: {s.second_half?.trips} trips, {formatCurrency(s.second_half?.revenue)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ── SECTION: Top vs Churned ── */}
      {activeSection === 'comparison' && topVsChurned?.comparison && (
        <div className="bg-ct-card border border-ct-border rounded-lg p-4">
          <h3 className="text-xs font-semibold text-ct-text mb-3">TOP vs CHURNED</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-2xs">
              <thead>
                <tr className="text-ct-text3 border-b border-ct-border">
                  <th className="text-left py-1">Métrica</th>
                  {topVsChurned.comparison.map((c, i) => (
                    <th key={i} className="text-right py-1">
                      {c.segment === 'TOP_PERFORMER' ? 'TOP' : c.segment === 'RECENTLY_CHURNED' ? 'CHURNED' : 'OTHER'}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[
                  { label: 'Drivers', key: 'drivers' },
                  { label: 'Revenue', key: 'avg_revenue', format: formatCurrency },
                  { label: 'Viajes', key: 'avg_trips', format: formatNum },
                  { label: 'Días activos', key: 'avg_active_days', format: formatNum },
                  { label: 'Revenue/h', key: 'avg_revenue_per_hour', format: formatCurrency },
                  { label: 'Revenue/km', key: 'avg_revenue_per_km', format: formatCurrency },
                  { label: 'Km/h', key: 'avg_km_per_hour', format: formatNum },
                  { label: 'Peak share', key: 'avg_peak_hour_share', format: formatPct },
                  { label: 'W-end share', key: 'avg_weekend_share', format: formatPct },
                  { label: 'Zonas usadas', key: 'avg_zones_used', format: formatNum },
                ].map(({ label, key, format }) => (
                  <tr key={label} className="border-b border-ct-border/30">
                    <td className="py-1 text-ct-text2">{label}</td>
                    {topVsChurned.comparison.map((c, i) => (
                      <td key={i} className="py-1 text-right text-ct-text">
                        {format ? format(c[key]) : c[key]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Data Source Info ── */}
      {summary?.source && (
        <div className="bg-ct-surface border border-ct-border rounded px-3 py-2 text-2xs text-ct-text3">
          Fuente: {summary.source.data_source} ({summary.source.source_type})
          {summary.source.source_warning && (
            <span className="text-yellow-400 ml-1">{summary.source.source_warning}</span>
          )}
        </div>
      )}
    </div>
  )
}
