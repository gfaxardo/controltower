/**
 * Fleet Leakage Monitor MVP — Vista de posible robo/fuga de conductores.
 * KPIs, filtros (país, ciudad, park, status, solo top performers), tabla y export.
 * No mezcla con Behavioral Alerts; fuentes propias (v_fleet_leakage_snapshot).
 */
import { useState, useEffect, useCallback } from 'react'
import { getSupplyGeo, getLeakageSummary, getLeakageDrivers, getLeakageExportUrl } from '../services/api'
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

const LEAKAGE_STATUS_LABELS = {
  stable_retained: 'Estable / Retenido',
  watchlist: 'En observación',
  progressive_leakage: 'Fuga progresiva',
  lost_driver: 'Perdido'
}

const LEAKAGE_STATUS_COLORS = {
  stable_retained: 'bg-gray-100 text-gray-800 border-gray-200',
  watchlist: 'bg-yellow-50 text-yellow-800 border-yellow-200',
  progressive_leakage: 'bg-orange-100 text-orange-800 border-orange-200',
  lost_driver: 'bg-red-100 text-red-800 border-red-200'
}

const pageSize = 50

export default function FleetLeakageView () {
  const [country, setCountry] = useState('')
  const [city, setCity] = useState('')
  const [parkId, setParkId] = useState('')
  const [leakageStatus, setLeakageStatus] = useState('')
  const [topPerformersOnly, setTopPerformersOnly] = useState(false)
  const [geo, setGeo] = useState({ countries: [], cities: [], parks: [] })
  const [summary, setSummary] = useState(null)
  const [drivers, setDrivers] = useState({ data: [], total: 0 })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(0)
  const [orderBy, setOrderBy] = useState('leakage_score')
  const [orderDir, setOrderDir] = useState('desc')

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
    country: country || undefined,
    city: city || undefined,
    park_id: parkId || undefined,
    leakage_status: leakageStatus || undefined,
    top_performers_only: topPerformersOnly || undefined
  }

  const loadSummary = useCallback(async () => {
    try {
      const s = await getLeakageSummary(filters)
      setSummary(s)
    } catch (e) {
      setSummary(null)
    }
  }, [country, city, parkId, leakageStatus, topPerformersOnly])

  const loadDrivers = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await getLeakageDrivers({
        ...filters,
        limit: pageSize,
        offset: page * pageSize,
        order_by: orderBy,
        order_dir: orderDir
      })
      setDrivers({ data: r.data || [], total: r.total || 0 })
    } catch (e) {
      setError(e.message || 'Error al cargar datos')
      setDrivers({ data: [], total: 0 })
    } finally {
      setLoading(false)
    }
  }, [country, city, parkId, leakageStatus, topPerformersOnly, page, orderBy, orderDir])

  useEffect(() => { loadSummary() }, [loadSummary])
  useEffect(() => { loadDrivers() }, [loadDrivers])

  const totalPages = Math.max(1, Math.ceil(drivers.total / pageSize))
  const columns = [
    { key: 'driver_name', label: 'Conductor', align: 'left', sortable: true },
    { key: 'country', label: 'País', align: 'left', sortable: true },
    { key: 'city', label: 'Ciudad', align: 'left', sortable: true },
    { key: 'park_name', label: 'Park', align: 'left', sortable: true },
    { key: 'baseline_trips_4w_avg', label: 'Base 4 sem', align: 'right', sortable: true },
    { key: 'trips_current_week', label: 'Viajes sem.', align: 'right', sortable: true },
    { key: 'delta_pct', label: 'Δ %', align: 'right', sortable: true },
    { key: 'last_trip_date', label: 'Último viaje', align: 'left', sortable: true },
    { key: 'days_since_last_trip', label: 'Días sin viaje', align: 'right', sortable: true },
    { key: 'leakage_status', label: 'Leakage status', align: 'left', sortable: true },
    { key: 'leakage_score', label: 'Score', align: 'right', sortable: true },
    { key: 'recovery_priority', label: 'Prioridad', align: 'left', sortable: true }
  ]

  const handleSort = (key) => {
    if (orderBy === key) setOrderDir((d) => (d === 'desc' ? 'asc' : 'desc'))
    else { setOrderBy(key); setOrderDir(key === 'leakage_score' ? 'desc' : 'asc') }
    setPage(0)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold text-gray-800">Fleet Leakage</h2>
        <DataStateBadge state="under_review" />
      </div>
      <p className="text-sm text-gray-600">
        Monitor de posible fuga/robo de conductores. Cohorte ancla 45 días. No sustituye Behavioral Alerts.
      </p>
      <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">
        Pantalla en revisión. Validar estabilidad en runtime antes de tomar decisiones.
      </p>

      {/* Filtros */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
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
            <label className="block text-xs font-medium text-gray-500 mb-1">Leakage status</label>
            <select value={leakageStatus} onChange={(e) => setLeakageStatus(e.target.value)} className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm">
              <option value="">Todos</option>
              {Object.entries(LEAKAGE_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={topPerformersOnly} onChange={(e) => setTopPerformersOnly(e.target.checked)} className="rounded border-gray-300" />
              <span className="text-sm text-gray-700">Solo top performers en riesgo</span>
            </label>
          </div>
        </div>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
        {[
          { key: 'drivers_under_watch', label: 'Under watch', color: 'bg-yellow-50 border-yellow-200 text-yellow-800' },
          { key: 'progressive_leakage', label: 'Fuga progresiva', color: 'bg-orange-50 border-orange-200 text-orange-800' },
          { key: 'lost_drivers', label: 'Perdidos', color: 'bg-red-50 border-red-200 text-red-800' },
          { key: 'top_performers_at_risk', label: 'Top en riesgo', color: 'bg-amber-50 border-amber-200 text-amber-800' },
          { key: 'cohort_retention_45d', label: 'Retención 45d', color: 'bg-blue-50 border-blue-200 text-blue-800' }
        ].map(({ key, label, color }) => (
          <div key={key} className={`rounded-lg border p-3 ${color}`}>
            <div className="text-xs font-medium opacity-90">{label}</div>
            <div className="text-xl font-semibold mt-1">{formatNum(summary?.[key] ?? 0)}</div>
          </div>
        ))}
      </div>

      {/* Export */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="text-xs font-medium text-gray-600 mb-2">Exportar Recovery Queue</div>
        <div className="flex flex-wrap gap-2 items-center">
          <a href={getLeakageExportUrl({ ...filters, format: 'csv' })} download="fleet_leakage.csv" className="inline-flex items-center px-4 py-2 rounded-md border-2 border-green-600 bg-green-50 text-green-800 text-sm font-semibold hover:bg-green-100">
            Export CSV
          </a>
          <a href={getLeakageExportUrl({ ...filters, format: 'excel' })} download="fleet_leakage.xlsx" className="inline-flex items-center px-4 py-2 rounded-md border-2 border-green-600 bg-green-50 text-green-800 text-sm font-semibold hover:bg-green-100">
            Export Excel
          </a>
        </div>
      </div>

      {/* Tabla */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        {error && <div className="p-4 bg-red-50 text-red-700 text-sm">{error}</div>}
        {loading && <div className="p-4 text-gray-500 text-sm">Cargando…</div>}
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-100 border-b border-gray-200">
              <tr>
                {columns.map(({ key, label, align, sortable }) => (
                  <th
                    key={key}
                    className={`py-2 px-3 font-medium text-gray-700 ${align === 'right' ? 'text-right' : 'text-left'} ${sortable ? 'cursor-pointer hover:bg-gray-200 select-none' : ''}`}
                    onClick={sortable ? () => handleSort(key) : undefined}
                  >
                    {label}
                    {sortable && (orderBy === key ? (orderDir === 'desc' ? ' ↓' : ' ↑') : ' ↕')}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {drivers.data.map((r) => (
                <tr key={r.driver_key} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="py-2 px-3">{r.driver_name ?? r.driver_key}</td>
                  <td className="py-2 px-3">{r.country ?? '—'}</td>
                  <td className="py-2 px-3">{r.city ?? '—'}</td>
                  <td className="py-2 px-3">{r.park_name ?? '—'}</td>
                  <td className="py-2 px-3 text-right">{formatNum(r.baseline_trips_4w_avg)}</td>
                  <td className="py-2 px-3 text-right">{formatNum(r.trips_current_week)}</td>
                  <td className={`py-2 px-3 text-right ${r.delta_pct != null && Number(r.delta_pct) < 0 ? 'text-red-600 font-medium' : ''}`}>{formatPct(r.delta_pct)}</td>
                  <td className="py-2 px-3">{formatLastTrip(r.last_trip_date)}</td>
                  <td className="py-2 px-3 text-right">{r.days_since_last_trip != null ? formatNum(r.days_since_last_trip) : '—'}</td>
                  <td className="py-2 px-3">
                    <span className={`inline-block px-2 py-0.5 rounded border text-xs ${LEAKAGE_STATUS_COLORS[r.leakage_status] || 'bg-gray-100'}`}>
                      {LEAKAGE_STATUS_LABELS[r.leakage_status] ?? r.leakage_status ?? '—'}
                    </span>
                  </td>
                  <td className="py-2 px-3 text-right">{formatNum(r.leakage_score)}</td>
                  <td className="py-2 px-3">
                    <span className="inline-block px-2 py-0.5 rounded border text-xs bg-gray-100 text-gray-800">{r.recovery_priority ?? '—'}</span>
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
    </div>
  )
}
