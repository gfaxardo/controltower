/**
 * Driver Supply Dynamics — Radar: Overview, Composition, Migration, Alerts, Drilldown.
 * Filtros cascada country → city → park (park obligatorio). No cargar datos hasta elegir park.
 * Siempre mostrar park_name, city, country (nunca solo IDs).
 */
import { useState, useEffect, useCallback } from 'react'
import {
  getSupplyGeo,
  getSupplyOverviewEnhanced,
  getSupplyComposition,
  getSupplyMigration,
  getSupplyMigrationDrilldown,
  getSupplyAlerts,
  getSupplyAlertDrilldown,
  refreshSupplyAlerting,
  getSupplyFreshness,
  getSupplyDefinitions,
  getSupplySegmentConfig
} from '../services/api'
import DriverSupplyGlossary from './DriverSupplyGlossary'

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

/** Convierte week_start (YYYY-MM-DD) a formato S{week}-{year}. Ej: 2026-02-03 → S6-2026 */
function formatIsoWeek (weekStart) {
  if (weekStart == null || weekStart === '') return '—'
  const s = String(weekStart).slice(0, 10)
  const d = new Date(s + 'T12:00:00')
  if (Number.isNaN(d.getTime())) return s
  d.setDate(d.getDate() + 4 - (d.getDay() || 7))
  const yearStart = new Date(d.getFullYear(), 0, 1)
  const weekNo = Math.ceil((((d - yearStart) / 86400000) + 1) / 7)
  return `S${weekNo}-${d.getFullYear()}`
}

/** Agrupa filas por mes (period_start o week_start YYYY-MM). Devuelve { '2026-02': [rows], ... } */
function groupByMonth (rows, dateKey = 'period_start') {
  const byMonth = {}
  for (const r of rows || []) {
    const v = r[dateKey] ?? r.week_start
    const month = v ? String(v).slice(0, 7) : ''
    if (!byMonth[month]) byMonth[month] = []
    byMonth[month].push(r)
  }
  return byMonth
}

/** Formato mes para agrupación: "2026-02" → "Feb 2026" */
function monthLabel (yyyyMm) {
  if (!yyyyMm || yyyyMm.length < 7) return yyyyMm
  const [y, m] = yyyyMm.split('-')
  const months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
  const i = parseInt(m, 10) - 1
  return `${months[i] || m} ${y}`
}

/** Agrupa filas por mes y luego por semana. Devuelve { monthKey: { weekKey: [rows] } }. monthKey = YYYY-MM, weekKey = Sx-YYYY. */
function groupByMonthAndWeek (rows, getWeekKey = (r) => r.week_display || formatIsoWeek(r.week_start) || String(r.week_start || '').slice(0, 10), getMonthKey = (r) => String(r.week_start || r.period_start || '').slice(0, 7)) {
  const byMonth = {}
  for (const r of rows || []) {
    const month = getMonthKey(r) || 'unknown'
    const week = getWeekKey(r) || 'unknown'
    if (!byMonth[month]) byMonth[month] = {}
    if (!byMonth[month][week]) byMonth[month][week] = []
    byMonth[month][week].push(r)
  }
  return byMonth
}

const TABS = { overview: 'Overview', composition: 'Composition', migration: 'Migration', alerts: 'Alerts' }

// Fallback si el backend no devuelve segment config
const SEGMENT_CRITERIA_FALLBACK = [
  { seg: 'FT', desc: '60+ viajes/semana' },
  { seg: 'PT', desc: '20–59' },
  { seg: 'CASUAL', desc: '5–19' },
  { seg: 'OCCASIONAL', desc: '1–4' },
  { seg: 'DORMANT', desc: '0' }
]

export default function SupplyView () {
  const today = new Date().toISOString().slice(0, 10)
  const defaultFrom = new Date()
  defaultFrom.setDate(defaultFrom.getDate() - 90)
  const fromDefault = defaultFrom.toISOString().slice(0, 10)

  const [country, setCountry] = useState('')
  const [city, setCity] = useState('')
  const [parkId, setParkId] = useState('')
  const [geo, setGeo] = useState({ countries: [], cities: [], parks: [] })
  const [from, setFrom] = useState(fromDefault)
  const [to, setTo] = useState(today)
  const [grain, setGrain] = useState('weekly')
  const [activeTab, setActiveTab] = useState(TABS.overview)

  const [overviewData, setOverviewData] = useState({ summary: {}, series: [], series_with_wow: [] })
  const [composition, setComposition] = useState([])
  const [migration, setMigration] = useState([])
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(false)
  const [compositionLoading, setCompositionLoading] = useState(false)
  const [migrationLoading, setMigrationLoading] = useState(false)
  const [alertsLoading, setAlertsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [refreshMvsLoading, setRefreshMvsLoading] = useState(false)

  const [freshness, setFreshness] = useState({ last_week_available: null, last_refresh: null, status: 'unknown' })
  const [definitions, setDefinitions] = useState({})
  const [segmentConfig, setSegmentConfig] = useState([])
  const [migrationSummary, setMigrationSummary] = useState(null)
  const [drilldownAlert, setDrilldownAlert] = useState(null)
  const [drilldownRows, setDrilldownRows] = useState([])
  const [drilldownLoading, setDrilldownLoading] = useState(false)
  const [migrationDrilldown, setMigrationDrilldown] = useState(null)
  const [migrationDrilldownRows, setMigrationDrilldownRows] = useState([])
  const [migrationDrilldownLoading, setMigrationDrilldownLoading] = useState(false)

  const selectedPark = geo.parks.find(p => p.park_id === parkId)
  const parkLabel = selectedPark ? [selectedPark.park_name, selectedPark.city, selectedPark.country].filter(Boolean).join(' · ') : ''

  const loadGeo = useCallback(async () => {
    try {
      const res = await getSupplyGeo({ country: country || undefined, city: city || undefined })
      setGeo({
        countries: res.countries || [],
        cities: res.cities || [],
        parks: res.parks || []
      })
      if (parkId && !(res.parks || []).some(p => p.park_id === parkId)) setParkId('')
    } catch (e) {
      console.error('Supply geo:', e)
      setGeo({ countries: [], cities: [], parks: [] })
    }
  }, [country, city, parkId])

  useEffect(() => { loadGeo() }, [loadGeo])

  const loadOverview = useCallback(async () => {
    if (!parkId?.trim()) {
      setOverviewData({ summary: {}, series: [], series_with_wow: [] })
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await getSupplyOverviewEnhanced({ park_id: parkId, from, to, grain })
      setOverviewData({
        summary: res.summary || {},
        series: res.series || [],
        series_with_wow: res.series_with_wow || res.series || []
      })
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || 'Error al cargar')
      setOverviewData({ summary: {}, series: [], series_with_wow: [] })
    } finally {
      setLoading(false)
    }
  }, [parkId, from, to, grain])

  const loadComposition = useCallback(async () => {
    if (!parkId?.trim()) {
      setComposition([])
      return
    }
    setCompositionLoading(true)
    try {
      const res = await getSupplyComposition({ park_id: parkId, from, to })
      setComposition(Array.isArray(res?.data) ? res.data : (Array.isArray(res) ? res : []))
    } catch (e) {
      console.error('Supply composition:', e)
      setComposition([])
    } finally {
      setCompositionLoading(false)
    }
  }, [parkId, from, to])

  const loadMigration = useCallback(async () => {
    if (!parkId?.trim()) {
      setMigration([])
      return
    }
    setMigrationLoading(true)
    try {
      const res = await getSupplyMigration({ park_id: parkId, from, to })
      setMigration(Array.isArray(res?.data) ? res.data : (Array.isArray(res) ? res : []))
      setMigrationSummary(res?.summary ?? null)
    } catch (e) {
      console.error('Supply migration:', e)
      setMigration([])
    } finally {
      setMigrationLoading(false)
    }
  }, [parkId, from, to])

  const loadAlerts = useCallback(async () => {
    if (!parkId?.trim()) {
      setAlerts([])
      return
    }
    setAlertsLoading(true)
    try {
      const res = await getSupplyAlerts({ park_id: parkId, from, to, limit: 100 })
      setAlerts(Array.isArray(res?.data) ? res.data : Array.isArray(res) ? res : [])
    } catch (e) {
      console.error('Supply alerts:', e)
      setAlerts([])
    } finally {
      setAlertsLoading(false)
    }
  }, [parkId, from, to])

  const loadFreshness = useCallback(async () => {
    try {
      const res = await getSupplyFreshness()
      setFreshness({
        last_week_available: res?.last_week_available ?? null,
        last_refresh: res?.last_refresh ?? null,
        status: res?.status ?? 'unknown'
      })
    } catch (e) {
      setFreshness({ last_week_available: null, last_refresh: null, status: 'unknown' })
    }
  }, [])

  useEffect(() => {
    loadOverview()
  }, [loadOverview])

  useEffect(() => {
    if (activeTab === TABS.composition) loadComposition()
  }, [activeTab, loadComposition])

  useEffect(() => {
    if (activeTab === TABS.migration) loadMigration()
  }, [activeTab, loadMigration])

  useEffect(() => {
    if (activeTab === TABS.alerts) loadAlerts()
  }, [activeTab, loadAlerts])

  useEffect(() => {
    loadFreshness()
  }, [loadFreshness])

  useEffect(() => {
    getSupplyDefinitions().then(setDefinitions).catch(() => setDefinitions({}))
    getSupplySegmentConfig().then(setSegmentConfig).catch(() => setSegmentConfig([]))
  }, [])

  const handleRefreshMvs = useCallback(async () => {
    if (!window.confirm('¿Refrescar MVs de Supply Alerting? Puede tardar unos minutos.')) return
    setRefreshMvsLoading(true)
    try {
      await refreshSupplyAlerting()
      await loadFreshness()
      await loadAlerts()
      if (drilldownAlert) await loadDrilldown(drilldownAlert)
      window.alert('Refresh completado.')
    } catch (e) {
      window.alert('Error: ' + (e?.response?.data?.detail || e?.message))
    } finally {
      setRefreshMvsLoading(false)
    }
  }, [loadFreshness, loadAlerts, drilldownAlert])

  const loadMigrationDrilldown = useCallback(async (row) => {
    if (!row?.week_start || !row?.park_id) return
    setMigrationDrilldownLoading(true)
    try {
      const res = await getSupplyMigrationDrilldown({
        park_id: row.park_id,
        week_start: row.week_start,
        from_segment: row.from_segment || undefined,
        to_segment: row.to_segment || undefined
      })
      setMigrationDrilldownRows(Array.isArray(res?.data) ? res.data : [])
    } catch (e) {
      setMigrationDrilldownRows([])
    } finally {
      setMigrationDrilldownLoading(false)
    }
  }, [])

  const openMigrationDrilldown = useCallback((row) => {
    setMigrationDrilldown(row)
    setMigrationDrilldownRows([])
    loadMigrationDrilldown(row)
  }, [loadMigrationDrilldown])

  const loadDrilldown = useCallback(async (alert) => {
    if (!alert?.week_start || !alert?.park_id) return
    setDrilldownLoading(true)
    try {
      const res = await getSupplyAlertDrilldown({
        park_id: alert.park_id,
        week_start: alert.week_start,
        segment_week: alert.segment_week,
        alert_type: alert.alert_type
      })
      setDrilldownRows(Array.isArray(res?.data) ? res.data : [])
    } catch (e) {
      setDrilldownRows([])
    } finally {
      setDrilldownLoading(false)
    }
  }, [])

  const openDrilldown = useCallback((alert) => {
    setDrilldownAlert(alert)
    setDrilldownRows([])
    loadDrilldown(alert)
  }, [loadDrilldown])

  const drilldownCsvUrl = (alert) => {
    if (!alert?.week_start || !alert?.park_id) return '#'
    const q = new URLSearchParams({
      park_id: alert.park_id,
      week_start: alert.week_start,
      format: 'csv'
    })
    if (alert.segment_week) q.set('segment_week', alert.segment_week)
    if (alert.alert_type) q.set('alert_type', alert.alert_type)
    if (import.meta.env.DEV) return `/api/ops/supply/alerts/drilldown?${q}`
    const base = (import.meta.env.VITE_API_URL || '').trim() || '/api'
    return `${base}/ops/supply/alerts/drilldown?${q}`
  }

  const compositionCsvUrl = () => {
    if (!parkId) return null
    const q = new URLSearchParams({ park_id: parkId, from, to, format: 'csv' })
    if (import.meta.env.DEV) return `/api/ops/supply/segments/series?${q}`
    const base = (import.meta.env.VITE_API_URL || '').trim() || '/api'
    return `${base}/ops/supply/segments/series?${q}`
  }

  const migrationCsvUrl = () => {
    if (!parkId) return null
    const q = new URLSearchParams({ park_id: parkId, from, to, format: 'csv' })
    if (import.meta.env.DEV) return `/api/ops/supply/migration?${q}`
    const base = (import.meta.env.VITE_API_URL || '').trim() || '/api'
    return `${base}/ops/supply/migration?${q}`
  }

  const overviewCsvUrlEnhanced = () => {
    if (!parkId) return null
    const q = new URLSearchParams({ park_id: parkId, from, to, grain, format: 'csv' })
    if (import.meta.env.DEV) return `/api/ops/supply/series?${q}`
    const base = (import.meta.env.VITE_API_URL || '').trim() || '/api'
    return `${base}/ops/supply/series?${q}`
  }

  const alertsCsvUrl = () => {
    if (!parkId) return null
    const q = new URLSearchParams({ park_id: parkId, from, to, format: 'csv' })
    if (import.meta.env.DEV) return `/api/ops/supply/alerts?${q}`
    const base = (import.meta.env.VITE_API_URL || '').trim() || '/api'
    return `${base}/ops/supply/alerts?${q}`
  }

  const overviewCsvUrl = () => {
    if (!parkId) return null
    const q = new URLSearchParams({ park_id: parkId, from, to, grain, format: 'csv' })
    if (import.meta.env.DEV) return `/api/ops/supply/series?${q}`
    const base = (import.meta.env.VITE_API_URL || '').trim() || '/api'
    return `${base}/ops/supply/series?${q}`
  }

  const severityClass = (s) => {
    if (s === 'P0') return 'bg-red-600 text-white'
    if (s === 'P1') return 'bg-orange-500 text-white'
    if (s === 'P2') return 'bg-amber-500 text-white'
    if (s === 'P3') return 'bg-blue-500 text-white'
    return 'bg-gray-400 text-white'
  }

  const periodLabel = overviewData.summary?.period_label
    ? `Periodo analizado: ${overviewData.summary.period_label}`
    : overviewData.summary?.period_weeks_count
      ? `Últimas ${overviewData.summary.period_weeks_count} semanas`
      : null

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <h2 className="text-xl font-semibold text-gray-800">Driver Supply Dynamics</h2>
        <DriverSupplyGlossary />
      </div>
      <p className="text-gray-600 text-sm">Overview, composición, migración y alertas por park. Elige país → ciudad → park para cargar datos.</p>
      {periodLabel && parkId && (
        <p className="text-sm font-medium text-slate-700 bg-slate-100 px-3 py-1.5 rounded inline-block">
          {periodLabel}
        </p>
      )}

      {/* Filtros cascada */}
      <div className="flex flex-wrap gap-4 items-end bg-white p-4 rounded-lg shadow">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">País</label>
          <select
            value={country}
            onChange={(e) => { setCountry(e.target.value); setCity(''); setParkId('') }}
            className="border border-gray-300 rounded px-3 py-2 min-w-[140px]"
          >
            <option value="">Todos</option>
            {(geo.countries || []).map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Ciudad</label>
          <select
            value={city}
            onChange={(e) => { setCity(e.target.value); setParkId('') }}
            className="border border-gray-300 rounded px-3 py-2 min-w-[140px]"
          >
            <option value="">Todas</option>
            {(geo.cities || []).map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Park (obligatorio)</label>
          <select
            value={parkId}
            onChange={(e) => setParkId(e.target.value)}
            className="border border-gray-300 rounded px-3 py-2 min-w-[220px]"
          >
            <option value="">Selecciona park</option>
            {(geo.parks || []).map(p => (
              <option key={p.park_id} value={p.park_id}>
                {[p.park_name, p.city, p.country].filter(Boolean).join(' · ') || p.park_id}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Granularidad (Overview)</label>
          <select
            value={grain}
            onChange={(e) => setGrain(e.target.value)}
            className="border border-gray-300 rounded px-3 py-2"
          >
            <option value="weekly">Semanal (ISO)</option>
            <option value="monthly">Mensual</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Desde</label>
          <input
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            className="border border-gray-300 rounded px-3 py-2"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Hasta</label>
          <input
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            className="border border-gray-300 rounded px-3 py-2"
          />
        </div>
        <button
          type="button"
          onClick={handleRefreshMvs}
          disabled={refreshMvsLoading || !parkId}
          className="px-3 py-2 text-sm bg-amber-500 text-white rounded hover:bg-amber-600 disabled:opacity-50"
        >
          {refreshMvsLoading ? 'Refrescando…' : 'Refrescar MVs'}
        </button>
      </div>

      {/* Freshness strip */}
      <div className="flex flex-wrap items-center gap-4 bg-slate-100 border border-slate-200 rounded px-4 py-2 text-sm">
        <span className="text-slate-600">Última semana:</span>
        <span className="font-medium">{freshness.last_week_available ?? '—'}</span>
        <span className="text-slate-600">Último refresh:</span>
        <span className="font-medium">{freshness.last_refresh ?? '—'}</span>
        <span className="text-slate-600">Estado:</span>
        <span className={`font-medium px-2 py-0.5 rounded ${freshness.status === 'fresh' ? 'bg-green-100 text-green-800' : freshness.status === 'stale' ? 'bg-amber-100 text-amber-800' : 'bg-gray-200 text-gray-700'}`}>
          {freshness.status === 'fresh' ? 'Fresh' : freshness.status === 'stale' ? 'Stale' : 'Unknown'}
        </span>
      </div>

      {!parkId && geo.parks?.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded p-4 text-amber-800">
          Selecciona un park para cargar Overview, Composition, Migration y Alerts.
        </div>
      )}

      {parkId && (
        <>
          <p className="text-sm text-gray-600">
            Park: <strong>{parkLabel || parkId}</strong>
          </p>

          {/* Tabs */}
          <div className="flex gap-2 border-b border-gray-200">
            {Object.entries(TABS).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setActiveTab(label)}
                className={`px-4 py-2 rounded-t font-medium text-sm ${activeTab === label ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Tab: Overview */}
          {activeTab === TABS.overview && (
            <div className="space-y-4">
              {error && <div className="bg-red-50 text-red-700 px-4 py-2 rounded">{error}</div>}
              {overviewData.summary && Object.keys(overviewData.summary).length > 0 && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <div className="bg-white p-3 rounded shadow" title={definitions.activations}><div className="text-xs text-gray-500">Activations (sum)</div><div className="font-semibold">{formatNum(overviewData.summary.activations_sum)}</div></div>
                  <div className="bg-white p-3 rounded shadow" title={definitions.churned}><div className="text-xs text-gray-500">Churned (sum)</div><div className="font-semibold">{formatNum(overviewData.summary.churned_sum)}</div></div>
                  <div className="bg-white p-3 rounded shadow" title={definitions.reactivated}><div className="text-xs text-gray-500">Reactivated (sum)</div><div className="font-semibold">{formatNum(overviewData.summary.reactivated_sum)}</div></div>
                  <div className="bg-white p-3 rounded shadow" title={definitions.net_growth}><div className="text-xs text-gray-500">Net growth (sum)</div><div className="font-semibold">{formatNum(overviewData.summary.net_growth_sum)}</div></div>
                  <div className="bg-white p-3 rounded shadow" title={definitions.active_drivers || definitions.active_supply}><div className="text-xs text-gray-500">Active drivers (último)</div><div className="font-semibold">{formatNum(overviewData.summary.active_drivers_last_period)}</div></div>
                  <div className="bg-white p-3 rounded shadow" title={definitions.churned}><div className="text-xs text-gray-500">Churn rate (pond.)</div><div className="font-semibold">{overviewData.summary.churn_rate_weighted != null ? Number(overviewData.summary.churn_rate_weighted).toFixed(2) + '%' : '—'}</div></div>
                  <div className="bg-white p-3 rounded shadow" title={definitions.week_supply}><div className="text-xs text-gray-500">Trips (último)</div><div className="font-semibold">{formatNum(overviewData.summary.trips)}</div></div>
                  <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Avg trips/driver</div><div className="font-semibold">{overviewData.summary.avg_trips_per_driver != null ? Number(overviewData.summary.avg_trips_per_driver).toFixed(1) : '—'}</div></div>
                  <div className="bg-white p-3 rounded shadow" title={definitions.segments}><div className="text-xs text-gray-500">FT share %</div><div className="font-semibold">{overviewData.summary.FT_share != null ? Number(overviewData.summary.FT_share).toFixed(1) + '%' : '—'}</div></div>
                  <div className="bg-white p-3 rounded shadow" title={definitions.segments}><div className="text-xs text-gray-500">PT share %</div><div className="font-semibold">{overviewData.summary.PT_share != null ? Number(overviewData.summary.PT_share).toFixed(1) + '%' : '—'}</div></div>
                  <div className="bg-white p-3 rounded shadow" title={definitions.segments}><div className="text-xs text-gray-500">Weak supply %</div><div className="font-semibold">{overviewData.summary.weak_supply_share != null ? Number(overviewData.summary.weak_supply_share).toFixed(1) + '%' : '—'}</div></div>
                  {overviewData.summary.growth_rate != null && (
                    <div className="bg-white p-3 rounded shadow" title={definitions.growth_rate}><div className="text-xs text-gray-500">Growth rate (WoW)</div><div className="font-semibold">{(Number(overviewData.summary.growth_rate) * 100).toFixed(2)}%</div></div>
                  )}
                  {grain === 'weekly' && (
                    <>
                      <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Rolling 4w active drivers</div><div className="font-semibold">{overviewData.summary.rolling_4w_active_drivers != null ? formatNum(Math.round(overviewData.summary.rolling_4w_active_drivers)) : '—'}</div></div>
                      <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Rolling 8w active drivers</div><div className="font-semibold">{overviewData.summary.rolling_8w_active_drivers != null ? formatNum(Math.round(overviewData.summary.rolling_8w_active_drivers)) : '—'}</div></div>
                      <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Rolling 4w trips</div><div className="font-semibold">{overviewData.summary.rolling_4w_trips != null ? formatNum(Math.round(overviewData.summary.rolling_4w_trips)) : '—'}</div></div>
                      <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Rolling 8w trips</div><div className="font-semibold">{overviewData.summary.rolling_8w_trips != null ? formatNum(Math.round(overviewData.summary.rolling_8w_trips)) : '—'}</div></div>
                      <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Rolling 4w FT share</div><div className="font-semibold">{overviewData.summary.rolling_4w_FT_share != null ? Number(overviewData.summary.rolling_4w_FT_share).toFixed(1) + '%' : '—'}</div></div>
                      <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Rolling 8w FT share</div><div className="font-semibold">{overviewData.summary.rolling_8w_FT_share != null ? Number(overviewData.summary.rolling_8w_FT_share).toFixed(1) + '%' : '—'}</div></div>
                      <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Rolling 4w weak supply %</div><div className="font-semibold">{overviewData.summary.rolling_4w_weak_supply_share != null ? Number(overviewData.summary.rolling_4w_weak_supply_share).toFixed(1) + '%' : '—'}</div></div>
                      <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Rolling 8w weak supply %</div><div className="font-semibold">{overviewData.summary.rolling_8w_weak_supply_share != null ? Number(overviewData.summary.rolling_8w_weak_supply_share).toFixed(1) + '%' : '—'}</div></div>
                      <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Trend</div><div className="font-semibold"><span className={`px-2 py-0.5 rounded text-xs ${overviewData.summary.trend_direction === 'up' ? 'bg-green-100 text-green-800' : overviewData.summary.trend_direction === 'down' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-700'}`}>{overviewData.summary.trend_direction ?? '—'}</span></div></div>
                    </>
                  )}
                </div>
              )}
              <div className="bg-white rounded-lg shadow overflow-hidden">
                <div className="px-4 py-2 bg-gray-50 font-medium flex justify-between items-center">
                  <span>Serie por periodo (más reciente arriba){grain === 'weekly' ? ' — con WoW' : ''}</span>
                  {overviewCsvUrlEnhanced() && (
                    <a href={overviewCsvUrlEnhanced()} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:underline">Download CSV</a>
                  )}
                </div>
                {loading ? (
                  <div className="p-8 text-center text-gray-500">Cargando…</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Periodo (Sx-YYYY)</th>
                          <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Activations</th>
                          <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Active drivers</th>
                          {grain === 'weekly' && <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Drivers WoW %</th>}
                          <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Trips</th>
                          {grain === 'weekly' && <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Trips WoW %</th>}
                          <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Churned</th>
                          <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Reactivated</th>
                          <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Net growth</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200">
                        {(() => {
                          const series = overviewData.series_with_wow || overviewData.series || []
                          if (grain !== 'weekly' || series.length === 0) {
                            return series.map((row, i) => (
                              <tr key={i} className="hover:bg-gray-50">
                                <td className="px-4 py-2 text-sm" title={String(row.period_start || '').slice(0, 10)}>{row.period_display || formatIsoWeek(row.period_start) || String(row.period_start || '').slice(0, 10)}</td>
                                <td className="px-4 py-2 text-sm text-right">{formatNum(row.activations)}</td>
                                <td className="px-4 py-2 text-sm text-right">{formatNum(row.active_drivers)}</td>
                                {grain === 'weekly' && <td className="px-4 py-2 text-sm text-right">{row.drivers_wow_pct != null ? Number(row.drivers_wow_pct).toFixed(1) + '%' : '—'}</td>}
                                <td className="px-4 py-2 text-sm text-right">{formatNum(row.trips)}</td>
                                {grain === 'weekly' && <td className="px-4 py-2 text-sm text-right">{row.trips_wow_pct != null ? Number(row.trips_wow_pct).toFixed(1) + '%' : '—'}</td>}
                                <td className="px-4 py-2 text-sm text-right">{formatNum(row.churned)}</td>
                                <td className="px-4 py-2 text-sm text-right">{formatNum(row.reactivated)}</td>
                                <td className="px-4 py-2 text-sm text-right">{formatNum(row.net_growth)}</td>
                              </tr>
                            ))
                          }
                          const byMonth = groupByMonth(series, 'period_start')
                          const monthKeys = Object.keys(byMonth).sort().reverse()
                          const colCount = 9 + (grain === 'weekly' ? 2 : 0)
                          return monthKeys.flatMap(monthKey => [
                            <tr key={`m-${monthKey}`} className="bg-slate-100 border-t border-slate-200">
                              <td colSpan={colCount} className="px-4 py-1.5 text-xs font-semibold text-slate-700">{monthLabel(monthKey)}</td>
                            </tr>,
                            ...byMonth[monthKey].map((row, i) => (
                              <tr key={`${monthKey}-${i}`} className="hover:bg-gray-50">
                                <td className="px-4 py-2 text-sm pl-6" title={String(row.period_start || '').slice(0, 10)}>{row.period_display || formatIsoWeek(row.period_start) || String(row.period_start || '').slice(0, 10)}</td>
                                <td className="px-4 py-2 text-sm text-right">{formatNum(row.activations)}</td>
                                <td className="px-4 py-2 text-sm text-right">{formatNum(row.active_drivers)}</td>
                                {grain === 'weekly' && <td className="px-4 py-2 text-sm text-right">{row.drivers_wow_pct != null ? Number(row.drivers_wow_pct).toFixed(1) + '%' : '—'}</td>}
                                <td className="px-4 py-2 text-sm text-right">{formatNum(row.trips)}</td>
                                {grain === 'weekly' && <td className="px-4 py-2 text-sm text-right">{row.trips_wow_pct != null ? Number(row.trips_wow_pct).toFixed(1) + '%' : '—'}</td>}
                                <td className="px-4 py-2 text-sm text-right">{formatNum(row.churned)}</td>
                                <td className="px-4 py-2 text-sm text-right">{formatNum(row.reactivated)}</td>
                                <td className="px-4 py-2 text-sm text-right">{formatNum(row.net_growth)}</td>
                              </tr>
                            ))
                          ])
                        })()}
                      </tbody>
                    </table>
                    {!loading && (overviewData.series_with_wow || overviewData.series || []).length === 0 && <div className="p-6 text-center text-gray-500">Sin datos en el rango.</div>}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tab: Composition */}
          {activeTab === TABS.composition && (
            <div className="space-y-4">
              <div className="bg-slate-50 border border-slate-200 rounded px-3 py-2 text-sm text-slate-700 flex flex-wrap items-center gap-x-4 gap-y-1">
                <span className="font-medium">Criterio de segmentación (ops.driver_segment_config):</span>
                {(segmentConfig.length ? segmentConfig.map(c => ({ seg: c.segment, desc: c.min_trips != null && c.max_trips != null ? `${c.min_trips}–${c.max_trips}` : c.min_trips != null ? `${c.min_trips}+` : '0' })) : SEGMENT_CRITERIA_FALLBACK).map(({ seg, desc }) => (
                  <span key={seg} className="text-slate-600">{seg} {desc}</span>
                ))}
              </div>
              <div className="bg-white rounded-lg shadow overflow-hidden">
                <div className="px-4 py-2 bg-gray-50 font-medium flex justify-between items-center">
                  <span>Composición por semana y segmento (week_start DESC)</span>
                  {compositionCsvUrl() && <a href={compositionCsvUrl()} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:underline">Download CSV</a>}
                </div>
                {compositionLoading ? (
                  <div className="p-8 text-center text-gray-500">Cargando…</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Semana (Sx-YYYY)</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Segmento</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Drivers</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Δ drivers</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Trips</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Share activos</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Δ share pp</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Supply contrib %</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Avg trips/driver</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Drivers WoW %</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Trips WoW %</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Share WoW pp</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Rolling 4w</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Rolling 8w</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Trend</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200">
                        {(() => {
                          const colCount = 15
                          const byMonthWeek = groupByMonthAndWeek(composition)
                          const monthKeys = Object.keys(byMonthWeek).sort().reverse()
                          if (monthKeys.length === 0) return null
                          return monthKeys.flatMap(monthKey => {
                            const byWeek = byMonthWeek[monthKey]
                            const weekKeys = Object.keys(byWeek).sort((a, b) => {
                              const tA = byWeek[a][0]?.week_start ? new Date(byWeek[a][0].week_start).getTime() : 0
                              const tB = byWeek[b][0]?.week_start ? new Date(byWeek[b][0].week_start).getTime() : 0
                              return tB - tA
                            })
                            return [
                              <tr key={`m-${monthKey}`} className="bg-slate-200 border-t-2 border-slate-300">
                                <td colSpan={colCount} className="px-4 py-2 text-sm font-semibold text-slate-800">{monthLabel(monthKey)}</td>
                              </tr>,
                              ...weekKeys.flatMap(weekKey => {
                                const rows = byWeek[weekKey]
                                return [
                                  <tr key={`w-${monthKey}-${weekKey}`} className="bg-slate-100 border-t border-slate-200">
                                    <td className="px-3 py-1.5 text-sm font-medium text-slate-800">{weekKey}</td>
                                    <td colSpan={colCount - 1} className="px-3 py-1.5" />
                                  </tr>,
                                  ...rows.map((row, i) => (
                                    <tr key={`${monthKey}-${weekKey}-${i}`} className="hover:bg-gray-50">
                                      <td className="px-3 py-2 text-sm pl-6 text-slate-400">—</td>
                                      <td className="px-3 py-2 text-sm font-medium">{row.segment_week || '—'}</td>
                                      <td className="px-3 py-2 text-sm text-right">{formatNum(row.drivers_count)}</td>
                                      <td className="px-3 py-2 text-sm text-right">{row.delta_drivers != null ? (row.delta_drivers >= 0 ? '+' : '') + formatNum(row.delta_drivers) : '—'}</td>
                                      <td className="px-3 py-2 text-sm text-right">{formatNum(row.trips_sum)}</td>
                                      <td className="px-3 py-2 text-sm text-right">{row.share_of_active != null ? Number(row.share_of_active).toFixed(1) + '%' : '—'}</td>
                                      <td className="px-3 py-2 text-sm text-right">{row.delta_share != null ? (row.delta_share >= 0 ? '+' : '') + Number(row.delta_share).toFixed(1) + ' pp' : '—'}</td>
                                      <td className="px-3 py-2 text-sm text-right">{row.supply_contribution != null ? Number(row.supply_contribution).toFixed(1) + '%' : '—'}</td>
                                      <td className="px-3 py-2 text-sm text-right">{row.avg_trips_per_driver != null ? Number(row.avg_trips_per_driver).toFixed(1) : '—'}</td>
                                      <td className="px-3 py-2 text-sm text-right">{row.drivers_wow_pct != null ? Number(row.drivers_wow_pct).toFixed(1) + '%' : '—'}</td>
                                      <td className="px-3 py-2 text-sm text-right">{row.trips_wow_pct != null ? Number(row.trips_wow_pct).toFixed(1) + '%' : '—'}</td>
                                      <td className="px-3 py-2 text-sm text-right">{row.share_wow_pp != null ? Number(row.share_wow_pp).toFixed(1) + ' pp' : '—'}</td>
                                      <td className="px-3 py-2 text-sm text-right">{row.rolling_4w_drivers_count != null ? formatNum(Math.round(row.rolling_4w_drivers_count)) : '—'}</td>
                                      <td className="px-3 py-2 text-sm text-right">{row.rolling_8w_drivers_count != null ? formatNum(Math.round(row.rolling_8w_drivers_count)) : '—'}</td>
                                      <td className="px-3 py-2 text-sm"><span className={`px-1.5 py-0.5 rounded text-xs ${row.trend_direction === 'up' ? 'bg-green-100 text-green-800' : row.trend_direction === 'down' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-600'}`}>{row.trend_direction ?? '—'}</span></td>
                                    </tr>
                                  ))
                                ]
                              })
                            ]
                          })
                        })()}
                      </tbody>
                    </table>
                    {!compositionLoading && composition.length === 0 && <div className="p-6 text-center text-gray-500">Sin datos de composición en el rango.</div>}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tab: Migration */}
          {activeTab === TABS.migration && (
            <div className="space-y-4">
              {(migration.length > 0 || migrationSummary) && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <div className="bg-white p-3 rounded shadow" title={definitions.migration}><div className="text-xs text-gray-500">Upgrades</div><div className="font-semibold">{formatNum(migrationSummary?.upgrades ?? migration.filter(r => r.migration_type === 'upgrade').reduce((s, r) => s + (r.drivers_migrated || 0), 0))}</div></div>
                  <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Downgrades</div><div className="font-semibold">{formatNum(migrationSummary?.downgrades ?? migration.filter(r => r.migration_type === 'downgrade').reduce((s, r) => s + (r.drivers_migrated || 0), 0))}</div></div>
                  <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Revivals</div><div className="font-semibold">{formatNum(migrationSummary?.revivals ?? migration.filter(r => r.migration_type === 'revival').reduce((s, r) => s + (r.drivers_migrated || 0), 0))}</div></div>
                  <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Drops</div><div className="font-semibold">{formatNum(migrationSummary?.drops ?? migration.filter(r => r.migration_type === 'drop').reduce((s, r) => s + (r.drivers_migrated || 0), 0))}</div></div>
                </div>
              )}
              <div className="bg-white rounded-lg shadow overflow-hidden">
                <div className="px-4 py-2 bg-gray-50 font-medium flex justify-between items-center">
                  <span>Migración entre segmentos (from → to)</span>
                  {migrationCsvUrl() && <a href={migrationCsvUrl()} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:underline">Download CSV</a>}
                </div>
                {migrationLoading ? (
                  <div className="p-8 text-center text-gray-500">Cargando…</div>
                ) : migration.length === 0 ? (
                  <div className="p-6 text-center text-gray-500">Sin datos de migración en el rango.</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Semana (Sx-YYYY)</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">From</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">To</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Tipo</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Drivers</th>
                          <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Migration rate</th>
                          <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Acción</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200">
                        {(() => {
                          const byMonthWeek = groupByMonthAndWeek(migration)
                          const monthKeys = Object.keys(byMonthWeek).sort().reverse()
                          if (monthKeys.length === 0) return null
                          return monthKeys.flatMap(monthKey => {
                            const byWeek = byMonthWeek[monthKey]
                            const weekKeys = Object.keys(byWeek).sort((a, b) => {
                              const tA = byWeek[a][0]?.week_start ? new Date(byWeek[a][0].week_start).getTime() : 0
                              const tB = byWeek[b][0]?.week_start ? new Date(byWeek[b][0].week_start).getTime() : 0
                              return tB - tA
                            })
                            return [
                              <tr key={`m-${monthKey}`} className="bg-slate-200 border-t-2 border-slate-300">
                                <td colSpan={7} className="px-4 py-2 text-sm font-semibold text-slate-800">{monthLabel(monthKey)}</td>
                              </tr>,
                              ...weekKeys.flatMap(weekKey => {
                                const rows = byWeek[weekKey]
                                return [
                                  <tr key={`w-${monthKey}-${weekKey}`} className="bg-slate-100 border-t border-slate-200">
                                    <td className="px-3 py-1.5 text-sm font-medium text-slate-800">{weekKey}</td>
                                    <td colSpan={6} className="px-3 py-1.5" />
                                  </tr>,
                                  ...rows.map((row, i) => (
                                    <tr key={`${monthKey}-${weekKey}-${i}`} className="hover:bg-gray-50">
                                      <td className="px-3 py-2 text-sm pl-6 text-slate-400">—</td>
                                      <td className="px-3 py-2 text-sm">{row.from_segment ?? '—'}</td>
                                      <td className="px-3 py-2 text-sm font-medium">{row.to_segment ?? '—'}</td>
                                      <td className="px-3 py-2 text-sm">
                                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${row.migration_type === 'upgrade' ? 'bg-green-100 text-green-800' : row.migration_type === 'downgrade' ? 'bg-amber-100 text-amber-800' : row.migration_type === 'drop' ? 'bg-red-100 text-red-800' : row.migration_type === 'revival' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-700'}`}>{row.migration_type ?? '—'}</span>
                                      </td>
                                      <td className="px-3 py-2 text-sm text-right">{formatNum(row.drivers_migrated)}</td>
                                      <td className="px-3 py-2 text-sm text-right">{row.migration_rate != null ? (Number(row.migration_rate) * 100).toFixed(2) + '%' : '—'}</td>
                                      <td className="px-3 py-2 text-sm">
                                        <button type="button" onClick={() => openMigrationDrilldown(row)} className="text-blue-600 hover:underline">Ver drivers</button>
                                      </td>
                                    </tr>
                                  ))
                                ]
                              })
                            ]
                          })
                        })()}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tab: Alerts */}
          {activeTab === TABS.alerts && (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <div className="px-4 py-2 bg-gray-50 font-medium flex justify-between items-center">
                <span>Alertas (P0..P3) — Prioridad High / Medium / Low — segment_drop / segment_spike</span>
                {alertsCsvUrl() && <a href={alertsCsvUrl()} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:underline">Download CSV</a>}
              </div>
              {alertsLoading ? (
                <div className="p-8 text-center text-gray-500">Cargando…</div>
              ) : alerts.length === 0 ? (
                <div className="p-6 text-center text-gray-500">No hay alertas en el rango para este park.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Semana (Sx-YYYY)</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Prioridad</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Severidad</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Tipo</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Segmento</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Baseline mean (8w)</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Baseline std</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">z-score</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Actual</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Δ%</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Trend context</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Mensaje</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Acción recomendada</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Acción</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {(() => {
                        const byMonthWeek = groupByMonthAndWeek(alerts)
                        const monthKeys = Object.keys(byMonthWeek).sort().reverse()
                        if (monthKeys.length === 0) return null
                        return monthKeys.flatMap(monthKey => {
                          const byWeek = byMonthWeek[monthKey]
                          const weekKeys = Object.keys(byWeek).sort((a, b) => {
                            const tA = byWeek[a][0]?.week_start ? new Date(byWeek[a][0].week_start).getTime() : 0
                            const tB = byWeek[b][0]?.week_start ? new Date(byWeek[b][0].week_start).getTime() : 0
                            return tB - tA
                          })
                          const alertColCount = 14
                          return [
                            <tr key={`m-${monthKey}`} className="bg-slate-200 border-t-2 border-slate-300">
                              <td colSpan={alertColCount} className="px-4 py-2 text-sm font-semibold text-slate-800">{monthLabel(monthKey)}</td>
                            </tr>,
                            ...weekKeys.flatMap(weekKey => {
                              const rows = byWeek[weekKey]
                              return [
                                <tr key={`w-${monthKey}-${weekKey}`} className="bg-slate-100 border-t border-slate-200">
                                  <td className="px-3 py-1.5 text-sm font-medium text-slate-800">{weekKey}</td>
                                  <td colSpan={alertColCount - 1} className="px-3 py-1.5" />
                                </tr>,
                                ...rows.map((row, i) => (
                                  <tr key={`${monthKey}-${weekKey}-${i}`} className="hover:bg-gray-50">
                                    <td className="px-3 py-2 text-sm pl-6 text-slate-400">—</td>
                                    <td className="px-3 py-2"><span className={`px-2 py-0.5 rounded text-xs font-medium ${row.priority_label === 'High' ? 'bg-red-100 text-red-800' : row.priority_label === 'Medium' ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-700'}`}>{row.priority_label || '—'}</span></td>
                                    <td className="px-3 py-2"><span className={`px-2 py-0.5 rounded text-xs font-medium ${severityClass(row.severity)}`}>{row.severity || '—'}</span></td>
                                    <td className="px-3 py-2 text-sm">{row.alert_type === 'segment_drop' ? 'Caída' : 'Spike'}</td>
                                    <td className="px-3 py-2 text-sm">{row.segment_week || '—'}</td>
                                    <td className="px-3 py-2 text-sm text-right">{formatNum(row.baseline_mean ?? row.baseline_avg)}</td>
                                    <td className="px-3 py-2 text-sm text-right">{row.baseline_std != null ? Number(row.baseline_std).toFixed(2) : '—'}</td>
                                    <td className="px-3 py-2 text-sm text-right">{row.z_score != null ? Number(row.z_score).toFixed(2) : '—'}</td>
                                    <td className="px-3 py-2 text-sm text-right font-medium">{formatNum(row.current_value)}</td>
                                    <td className="px-3 py-2 text-sm text-right">{row.delta_pct != null ? formatPct(row.delta_pct) : '—'}</td>
                                    <td className="px-3 py-2 text-sm"><span className="text-gray-700">{row.trend_context ?? '—'}</span></td>
                                    <td className="px-3 py-2 text-sm max-w-xs truncate" title={row.message_short}>{row.message_short || '—'}</td>
                                    <td className="px-3 py-2 text-sm max-w-xs truncate" title={row.recommended_action}>{row.recommended_action || '—'}</td>
                                    <td className="px-3 py-2 text-sm">
                                      <button type="button" onClick={() => openDrilldown(row)} className="text-blue-600 hover:underline mr-2">Ver drivers</button>
                                      <a href={drilldownCsvUrl(row)} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline text-xs">CSV</a>
                                    </td>
                                  </tr>
                                ))
                              ]
                            })
                          ]
                        })
                      })()}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* Modal Drilldown */}
      {drilldownAlert && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setDrilldownAlert(null)}>
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col m-4" onClick={e => e.stopPropagation()}>
            <div className="px-4 py-3 bg-gray-100 font-medium flex justify-between items-center">
              <span>Drilldown: {drilldownAlert.segment_week} — {String(drilldownAlert.week_start).slice(0, 10)} · {drilldownAlert.park_name || drilldownAlert.park_id} · {drilldownAlert.city} · {drilldownAlert.country}</span>
              <div className="flex gap-2">
                <a href={drilldownCsvUrl(drilldownAlert)} target="_blank" rel="noopener noreferrer" className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700">Export CSV</a>
                <button type="button" className="px-3 py-1 text-sm bg-gray-400 text-white rounded hover:bg-gray-500" onClick={() => setDrilldownAlert(null)}>Cerrar</button>
              </div>
            </div>
            <div className="p-4 overflow-auto flex-1">
              {drilldownLoading ? (
                <div className="py-8 text-center text-gray-500">Cargando conductores…</div>
              ) : (
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Driver</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Segmento prev</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Segmento actual</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Trips semana</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Baseline 4w</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Cambio</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {drilldownRows.map((row, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-3 py-2 text-sm">{row.driver_key ?? '—'}</td>
                        <td className="px-3 py-2 text-sm">{row.prev_segment_week ?? '—'}</td>
                        <td className="px-3 py-2 text-sm">{row.segment_week_current ?? '—'}</td>
                        <td className="px-3 py-2 text-sm text-right">{formatNum(row.trips_completed_week)}</td>
                        <td className="px-3 py-2 text-sm text-right">{formatNum(row.baseline_trips_4w_avg)}</td>
                        <td className="px-3 py-2 text-sm">{row.segment_change_type ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {!drilldownLoading && drilldownRows.length === 0 && <div className="py-6 text-center text-gray-500">Ningún conductor en drilldown para esta alerta.</div>}
            </div>
            <div className="px-4 py-2 bg-gray-50 border-t text-sm text-gray-500 flex justify-between">
              <span>{drilldownRows.length} conductores</span>
              <button type="button" className="text-gray-400 hover:text-gray-600" disabled>Enviar a equipo ops (próximamente)</button>
            </div>
          </div>
        </div>
      )}

      {/* Modal Migration Drilldown */}
      {migrationDrilldown && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setMigrationDrilldown(null)}>
          <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col m-4" onClick={e => e.stopPropagation()}>
            <div className="px-4 py-3 bg-gray-100 font-medium flex justify-between items-center">
              <span>Migración: {migrationDrilldown.from_segment ?? '—'} → {migrationDrilldown.to_segment ?? '—'} · {String(migrationDrilldown.week_start).slice(0, 10)} · Park {migrationDrilldown.park_id}</span>
              <button type="button" className="px-3 py-1 text-sm bg-gray-400 text-white rounded hover:bg-gray-500" onClick={() => setMigrationDrilldown(null)}>Cerrar</button>
            </div>
            <div className="p-4 overflow-auto flex-1">
              {migrationDrilldownLoading ? (
                <div className="py-8 text-center text-gray-500">Cargando conductores…</div>
              ) : (
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Driver</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">From</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">To</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Tipo</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Trips semana</th>
                      <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Baseline 4w</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {migrationDrilldownRows.map((row, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-3 py-2 text-sm">{row.driver_key ?? '—'}</td>
                        <td className="px-3 py-2 text-sm">{row.from_segment ?? '—'}</td>
                        <td className="px-3 py-2 text-sm">{row.to_segment ?? '—'}</td>
                        <td className="px-3 py-2 text-sm">{row.migration_type ?? '—'}</td>
                        <td className="px-3 py-2 text-sm text-right">{formatNum(row.trips_completed_week)}</td>
                        <td className="px-3 py-2 text-sm text-right">{formatNum(row.baseline_trips_4w_avg)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {!migrationDrilldownLoading && migrationDrilldownRows.length === 0 && <div className="py-6 text-center text-gray-500">Ningún conductor en este tramo de migración.</div>}
            </div>
            <div className="px-4 py-2 bg-gray-50 border-t text-sm text-gray-500">
              {migrationDrilldownRows.length} conductores
            </div>
          </div>
        </div>
      )}

      {!parkId && geo.parks?.length === 0 && (
        <div className="bg-gray-50 rounded p-4 text-gray-600">Cargando geo… (dim.v_geo_park)</div>
      )}
    </div>
  )
}
