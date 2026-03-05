/**
 * Control Tower Supply (Real) — Radar: Overview, Segments, Alerts, Drilldown.
 * Filtros cascada country → city → park (park obligatorio). No cargar datos hasta elegir park.
 * Siempre mostrar park_name, city, country (nunca solo IDs).
 */
import { useState, useEffect, useCallback } from 'react'
import {
  getSupplyGeo,
  getSupplySeries,
  getSupplySummary,
  getSupplySegmentsSeries,
  getSupplyAlerts,
  getSupplyAlertDrilldown,
  refreshSupplyAlerting
} from '../services/api'

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

const TABS = { overview: 'Overview', segments: 'Segments', alerts: 'Alerts' }

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

  const [series, setSeries] = useState([])
  const [summary, setSummary] = useState(null)
  const [segments, setSegments] = useState([])
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(false)
  const [segmentsLoading, setSegmentsLoading] = useState(false)
  const [alertsLoading, setAlertsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [refreshMvsLoading, setRefreshMvsLoading] = useState(false)

  const [drilldownAlert, setDrilldownAlert] = useState(null)
  const [drilldownRows, setDrilldownRows] = useState([])
  const [drilldownLoading, setDrilldownLoading] = useState(false)

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
      setSeries([])
      setSummary(null)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const [seriesRes, summaryRes] = await Promise.all([
        getSupplySeries({ park_id: parkId, from, to, grain }),
        getSupplySummary({ park_id: parkId, from, to, grain })
      ])
      setSeries(Array.isArray(seriesRes) ? seriesRes : (seriesRes?.data ?? []))
      setSummary(summaryRes)
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || 'Error al cargar')
      setSeries([])
      setSummary(null)
    } finally {
      setLoading(false)
    }
  }, [parkId, from, to, grain])

  const loadSegments = useCallback(async () => {
    if (!parkId?.trim()) {
      setSegments([])
      return
    }
    setSegmentsLoading(true)
    try {
      const res = await getSupplySegmentsSeries({ park_id: parkId, from, to })
      setSegments(Array.isArray(res) ? res : (res?.data ?? []))
    } catch (e) {
      console.error('Supply segments:', e)
      setSegments([])
    } finally {
      setSegmentsLoading(false)
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
      setAlerts(Array.isArray(res?.data) ? res.data : [])
    } catch (e) {
      console.error('Supply alerts:', e)
      setAlerts([])
    } finally {
      setAlertsLoading(false)
    }
  }, [parkId, from, to])

  useEffect(() => {
    loadOverview()
  }, [loadOverview])

  useEffect(() => {
    if (activeTab === TABS.segments) loadSegments()
  }, [activeTab, loadSegments])

  useEffect(() => {
    if (activeTab === TABS.alerts) loadAlerts()
  }, [activeTab, loadAlerts])

  const handleRefreshMvs = useCallback(async () => {
    if (!window.confirm('¿Refrescar MVs de Supply Alerting? Puede tardar unos minutos.')) return
    setRefreshMvsLoading(true)
    try {
      await refreshSupplyAlerting()
      await loadAlerts()
      if (drilldownAlert) await loadDrilldown(drilldownAlert)
      window.alert('Refresh completado.')
    } catch (e) {
      window.alert('Error: ' + (e?.response?.data?.detail || e?.message))
    } finally {
      setRefreshMvsLoading(false)
    }
  }, [loadAlerts, drilldownAlert])

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
    const base = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    return `${base}/ops/supply/alerts/drilldown?${q}`
  }

  const segmentsCsvUrl = () => {
    if (!parkId) return null
    const q = new URLSearchParams({ park_id: parkId, from, to, format: 'csv' })
    if (import.meta.env.DEV) return `/api/ops/supply/segments/series?${q}`
    const base = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    return `${base}/ops/supply/segments/series?${q}`
  }

  const alertsCsvUrl = () => {
    if (!parkId) return null
    const q = new URLSearchParams({ park_id: parkId, from, to, format: 'csv' })
    if (import.meta.env.DEV) return `/api/ops/supply/alerts?${q}`
    const base = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    return `${base}/ops/supply/alerts?${q}`
  }

  const overviewCsvUrl = () => {
    if (!parkId) return null
    const q = new URLSearchParams({ park_id: parkId, from, to, grain, format: 'csv' })
    if (import.meta.env.DEV) return `/api/ops/supply/series?${q}`
    const base = import.meta.env.VITE_API_URL || 'http://localhost:8000'
    return `${base}/ops/supply/series?${q}`
  }

  const severityClass = (s) => {
    if (s === 'P0') return 'bg-red-600 text-white'
    if (s === 'P1') return 'bg-orange-500 text-white'
    if (s === 'P2') return 'bg-amber-500 text-white'
    if (s === 'P3') return 'bg-blue-500 text-white'
    return 'bg-gray-400 text-white'
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-gray-800">Supply (Real) — Radar</h2>
      <p className="text-gray-600 text-sm">Overview, segmentos y alertas por park. Elige país → ciudad → park para cargar datos.</p>

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

      {!parkId && geo.parks?.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded p-4 text-amber-800">
          Selecciona un park para cargar Overview, Segments y Alerts.
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
              {summary && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Activations (sum)</div><div className="font-semibold">{formatNum(summary.activations_sum)}</div></div>
                  <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Churned (sum)</div><div className="font-semibold">{formatNum(summary.churned_sum)}</div></div>
                  <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Reactivated (sum)</div><div className="font-semibold">{formatNum(summary.reactivated_sum)}</div></div>
                  <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Net growth (sum)</div><div className="font-semibold">{formatNum(summary.net_growth_sum)}</div></div>
                  <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Active drivers (último)</div><div className="font-semibold">{formatNum(summary.active_drivers_last_period)}</div></div>
                  <div className="bg-white p-3 rounded shadow"><div className="text-xs text-gray-500">Churn rate (pond.)</div><div className="font-semibold">{summary.churn_rate_weighted != null ? Number(summary.churn_rate_weighted).toFixed(2) + '%' : '—'}</div></div>
                </div>
              )}
              <div className="bg-white rounded-lg shadow overflow-hidden">
                <div className="px-4 py-2 bg-gray-50 font-medium flex justify-between items-center">
                  <span>Serie por periodo (más reciente arriba)</span>
                  {overviewCsvUrl() && (
                    <a href={overviewCsvUrl()} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:underline">Download CSV</a>
                  )}
                </div>
                {loading ? (
                  <div className="p-8 text-center text-gray-500">Cargando…</div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Periodo</th>
                          <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Activations</th>
                          <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Active drivers</th>
                          <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Churned</th>
                          <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Reactivated</th>
                          <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Net growth</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-200">
                        {series.map((row, i) => (
                          <tr key={i} className="hover:bg-gray-50">
                            <td className="px-4 py-2 text-sm">{String(row.period_start || '').slice(0, 10)}</td>
                            <td className="px-4 py-2 text-sm text-right">{formatNum(row.activations)}</td>
                            <td className="px-4 py-2 text-sm text-right">{formatNum(row.active_drivers)}</td>
                            <td className="px-4 py-2 text-sm text-right">{formatNum(row.churned)}</td>
                            <td className="px-4 py-2 text-sm text-right">{formatNum(row.reactivated)}</td>
                            <td className="px-4 py-2 text-sm text-right">{formatNum(row.net_growth)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {!loading && series.length === 0 && <div className="p-6 text-center text-gray-500">Sin datos en el rango.</div>}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Tab: Segments */}
          {activeTab === TABS.segments && (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <div className="px-4 py-2 bg-gray-50 font-medium flex justify-between items-center">
                <span>Evolución por segmento (FT / PT / CASUAL / OCC / DORMANT) — week_start DESC</span>
                {segmentsCsvUrl() && <a href={segmentsCsvUrl()} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:underline">Download CSV</a>}
              </div>
              {segmentsLoading ? (
                <div className="p-8 text-center text-gray-500">Cargando…</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Semana</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Segmento</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Drivers</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Trips</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Share activos</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {segments.map((row, i) => (
                        <tr key={i} className="hover:bg-gray-50">
                          <td className="px-3 py-2 text-sm">{String(row.week_start || '').slice(0, 10)}</td>
                          <td className="px-3 py-2 text-sm font-medium">{row.segment_week || '—'}</td>
                          <td className="px-3 py-2 text-sm text-right">{formatNum(row.drivers_count)}</td>
                          <td className="px-3 py-2 text-sm text-right">{formatNum(row.trips_sum)}</td>
                          <td className="px-3 py-2 text-sm text-right">{row.share_of_active != null ? Number(row.share_of_active).toFixed(1) + '%' : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!segmentsLoading && segments.length === 0 && <div className="p-6 text-center text-gray-500">Sin datos de segmentos en el rango.</div>}
                </div>
              )}
            </div>
          )}

          {/* Tab: Alerts */}
          {activeTab === TABS.alerts && (
            <div className="bg-white rounded-lg shadow overflow-hidden">
              <div className="px-4 py-2 bg-gray-50 font-medium flex justify-between items-center">
                <span>Alertas (P0..P3) — segment_drop / segment_spike</span>
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
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Semana</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Severidad</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Tipo</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Segmento</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Baseline</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Actual</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Δ%</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Mensaje</th>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Acción</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-200">
                      {alerts.map((row, i) => (
                        <tr key={i} className="hover:bg-gray-50">
                          <td className="px-3 py-2 text-sm">{String(row.week_start || '').slice(0, 10)}</td>
                          <td className="px-3 py-2"><span className={`px-2 py-0.5 rounded text-xs font-medium ${severityClass(row.severity)}`}>{row.severity || '—'}</span></td>
                          <td className="px-3 py-2 text-sm">{row.alert_type === 'segment_drop' ? 'Caída' : 'Spike'}</td>
                          <td className="px-3 py-2 text-sm">{row.segment_week || '—'}</td>
                          <td className="px-3 py-2 text-sm text-right">{formatNum(row.baseline_avg)}</td>
                          <td className="px-3 py-2 text-sm text-right">{formatNum(row.current_value)}</td>
                          <td className="px-3 py-2 text-sm text-right">{row.delta_pct != null ? formatPct(row.delta_pct) : '—'}</td>
                          <td className="px-3 py-2 text-sm max-w-xs truncate" title={row.message_short}>{row.message_short || '—'}</td>
                          <td className="px-3 py-2 text-sm">
                            <button type="button" onClick={() => openDrilldown(row)} className="text-blue-600 hover:underline mr-2">Ver drivers</button>
                            <a href={drilldownCsvUrl(row)} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline text-xs">CSV</a>
                          </td>
                        </tr>
                      ))}
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

      {!parkId && geo.parks?.length === 0 && (
        <div className="bg-gray-50 rounded p-4 text-gray-600">Cargando geo… (dim.v_geo_park)</div>
      )}
    </div>
  )
}
