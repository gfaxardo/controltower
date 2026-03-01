/**
 * Driver Lifecycle — Drilldown obligatorio por PARK.
 * Filtros: From/To, Park (multi-select), Weekly/Monthly.
 * Bloque KPI + tabla Desglose por Park; celdas clickeables abren modal con lista de drivers.
 */
import { useState, useEffect, useCallback } from 'react'
import {
  getDriverLifecycleWeekly,
  getDriverLifecycleMonthly,
  getDriverLifecycleDrilldown,
  getDriverLifecycleParksSummary,
  getDriverLifecycleParksList,
  getDriverLifecycleBaseMetrics,
  getDriverLifecycleBaseMetricsDrilldown,
  getDriverLifecycleCohorts,
  getDriverLifecycleCohortDrilldown
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
  return (num * 100).toFixed(2) + '%'
}

// Última semana (lunes) <= date; último mes (día 1) <= date
function lastWeekStart (d) {
  const date = new Date(d)
  const day = date.getDay()
  const diff = day === 0 ? 6 : day - 1
  const mon = new Date(date)
  mon.setDate(mon.getDate() - diff)
  return mon.toISOString().slice(0, 10)
}
function lastMonthStart (d) {
  return String(d).slice(0, 7) + '-01'
}

export default function DriverLifecycleView () {
  const today = new Date().toISOString().slice(0, 10)
  const defaultFrom = new Date()
  defaultFrom.setMonth(defaultFrom.getMonth() - 3)
  const fromDefault = defaultFrom.toISOString().slice(0, 10)

  const [from, setFrom] = useState(fromDefault)
  const [to, setTo] = useState(today)
  const [parkId, setParkId] = useState('') // optional filter; empty = global + breakdown
  const [periodType, setPeriodType] = useState('week') // 'week' | 'month'
  const [parksList, setParksList] = useState([])
  const [kpis, setKpis] = useState([])
  const [breakdownByPark, setBreakdownByPark] = useState([])
  const [parksSummary, setParksSummary] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const [modalOpen, setModalOpen] = useState(false)
  const [modalPayload, setModalPayload] = useState(null) // { type: 'kpi'|'cohort', park_id, period_start?, metric?, cohort_week?, horizon? }
  const [drilldownData, setDrilldownData] = useState({ drivers: [], total: 0, page: 1, page_size: 50 })
  const [drilldownLoading, setDrilldownLoading] = useState(false)

  const [baseMetrics, setBaseMetrics] = useState(null)
  const [cohortFrom, setCohortFrom] = useState(fromDefault)
  const [cohortTo, setCohortTo] = useState(today)
  const [cohortParkId, setCohortParkId] = useState('')
  const [cohorts, setCohorts] = useState([])
  const [cohortsLoading, setCohortsLoading] = useState(false)
  const [cohortsError, setCohortsError] = useState(null)

  const loadParksList = useCallback(async () => {
    try {
      const res = await getDriverLifecycleParksList()
      setParksList(res.parks || [])
    } catch (e) {
      console.error('Driver lifecycle parks list:', e)
    }
  }, [])

  useEffect(() => { loadParksList() }, [loadParksList])

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = { from, to }
      if (parkId && parkId.trim() !== '') {
        params.park_id = parkId
      }
      let data
      if (periodType === 'week') {
        data = await getDriverLifecycleWeekly(params)
      } else {
        data = await getDriverLifecycleMonthly(params)
      }
      setKpis(data.kpis || [])
      setBreakdownByPark(data.breakdown_by_park || [])

      const summaryRes = await getDriverLifecycleParksSummary({ from, to, period_type: periodType })
      setParksSummary(summaryRes.parks || [])

      const baseParams = { from, to }
      if (parkId && parkId.trim() !== '') baseParams.park_id = parkId
      try {
        const baseRes = await getDriverLifecycleBaseMetrics(baseParams)
        setBaseMetrics(baseRes)
      } catch (e) {
        setBaseMetrics(null)
      }
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || 'Error al cargar')
    } finally {
      setLoading(false)
    }
  }, [from, to, parkId, periodType])

  useEffect(() => { loadData() }, [loadData])

  const openDrilldown = (parkId, metric) => {
    const periodStart = periodType === 'week' ? lastWeekStart(to) : lastMonthStart(to)
    setModalPayload({ type: 'kpi', park_id: parkId, period_start: periodStart, metric })
    setModalOpen(true)
    setDrilldownData({ drivers: [], total: 0, page: 1, page_size: 50 })
  }

  const loadCohorts = useCallback(async () => {
    setCohortsLoading(true)
    setCohortsError(null)
    try {
      const params = { from_cohort_week: cohortFrom, to_cohort_week: cohortTo }
      if (cohortParkId && cohortParkId.trim() !== '') params.park_id = cohortParkId
      const res = await getDriverLifecycleCohorts(params)
      setCohorts(res.cohorts || [])
    } catch (e) {
      setCohortsError(e?.response?.data?.detail || e?.message || 'Error al cargar cohortes')
    } finally {
      setCohortsLoading(false)
    }
  }, [cohortFrom, cohortTo, cohortParkId])

  useEffect(() => { loadCohorts() }, [loadCohorts])

  const openBaseMetricsDrilldown = (metric) => {
    const pid = parkId && parkId.trim() !== '' ? parkId : (parksList[0] || '')
    if (!pid) return
    setModalPayload({ type: 'base_metrics', metric, park_id: pid, from, to })
    setModalOpen(true)
    setDrilldownData({ drivers: [], total: 0, page: 1, page_size: 50 })
  }

  const openCohortDrilldown = (cohortWeek, horizon, parkId) => {
    setModalPayload({ type: 'cohort', cohort_week: cohortWeek, horizon, park_id: parkId })
    setModalOpen(true)
    setDrilldownData({ drivers: [], total: 0, page: 1, page_size: 50 })
  }

  function displayParkId (pid) {
    if (pid == null || pid === '' || (typeof pid === 'string' && pid.trim() === '')) return 'PARK_DESCONOCIDO'
    return pid
  }

  function isParkDesconocido (pid) {
    return pid == null || pid === '' || (typeof pid === 'string' && pid.trim() === '')
  }

  useEffect(() => {
    if (!modalOpen || !modalPayload) return
    const fetchDrill = async () => {
      setDrilldownLoading(true)
      try {
        if (modalPayload.type === 'base_metrics') {
          const res = await getDriverLifecycleBaseMetricsDrilldown({
            from: modalPayload.from,
            to: modalPayload.to,
            park_id: modalPayload.park_id,
            metric: modalPayload.metric,
            page: 1,
            page_size: 100
          })
          setDrilldownData({
            drivers: res.drivers || [],
            total: res.total || 0,
            page: res.page || 1,
            page_size: res.page_size || 100
          })
        } else if (modalPayload.type === 'cohort') {
          const res = await getDriverLifecycleCohortDrilldown({
            cohort_week: modalPayload.cohort_week,
            horizon: modalPayload.horizon,
            park_id: modalPayload.park_id,
            page: 1,
            page_size: 100
          })
          setDrilldownData({
            drivers: res.drivers || [],
            total: res.total || 0,
            page: res.page || 1,
            page_size: res.page_size || 100
          })
        } else {
          const res = await getDriverLifecycleDrilldown({
            period_type: periodType,
            period_start: modalPayload.period_start,
            metric: modalPayload.metric,
            park_id: modalPayload.park_id,
            page: 1,
            page_size: 100
          })
          setDrilldownData({
            drivers: res.drivers || [],
            total: res.total || 0,
            page: res.page || 1,
            page_size: res.page_size || 100
          })
        }
      } catch (e) {
        console.error('Drilldown:', e)
      } finally {
        setDrilldownLoading(false)
      }
    }
    fetchDrill()
  }, [modalOpen, modalPayload, periodType])

  const exportDrilldownCsv = () => {
    const rows = drilldownData.drivers.map(d => d.driver_key + (d.activation_ts ? `,${d.activation_ts}` : '') + (d.last_completed_ts ? `,${d.last_completed_ts}` : ''))
    const header = 'driver_key' + (drilldownData.drivers[0]?.activation_ts ? ',activation_ts,last_completed_ts' : '')
    const csv = [header, ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const a = document.createElement('a')
    const suffix = modalPayload?.type === 'base_metrics'
      ? `base_${modalPayload?.metric}_${modalPayload?.park_id}`
      : modalPayload?.type === 'cohort'
        ? `cohort_${modalPayload?.cohort_week}_${modalPayload?.horizon}_${modalPayload?.park_id}`
        : `${modalPayload?.park_id}_${modalPayload?.metric}`
    a.href = URL.createObjectURL(blob)
    a.download = `driver_lifecycle_drilldown_${suffix}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const totalActivations = kpis.reduce((s, r) => s + (Number(r.activations) || 0), 0)
  const totalActive = kpis.length ? kpis[kpis.length - 1]?.active_drivers : null
  const totalChurned = periodType === 'week' ? kpis.reduce((s, r) => s + (Number(r.churned) || 0), 0) : null
  const totalReactivated = periodType === 'week' ? kpis.reduce((s, r) => s + (Number(r.reactivated) || 0), 0) : null

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-semibold text-gray-800 mb-4">Driver Lifecycle (por Park)</h2>

      <div className="flex flex-wrap gap-4 mb-4">
        <label className="flex items-center gap-2">
          <span className="text-sm text-gray-600">Desde</span>
          <input
            type="date"
            value={from}
            onChange={e => setFrom(e.target.value)}
            className="border rounded px-2 py-1 text-sm"
          />
        </label>
        <label className="flex items-center gap-2">
          <span className="text-sm text-gray-600">Hasta</span>
          <input
            type="date"
            value={to}
            onChange={e => setTo(e.target.value)}
            className="border rounded px-2 py-1 text-sm"
          />
        </label>
        <label className="flex items-center gap-2">
          <span className="text-sm text-gray-600">Park</span>
          <select
            value={parkId}
            onChange={e => setParkId(e.target.value)}
            className="border rounded px-2 py-1 text-sm min-w-[140px]"
          >
            <option value="">— Todos (global + desglose) —</option>
            {parksList.map(p => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </label>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">Periodo</span>
          <button
            onClick={() => setPeriodType('week')}
            className={`px-3 py-1 rounded text-sm ${periodType === 'week' ? 'bg-blue-500 text-white' : 'bg-gray-200'}`}
          >
            Semanal
          </button>
          <button
            onClick={() => setPeriodType('month')}
            className={`px-3 py-1 rounded text-sm ${periodType === 'month' ? 'bg-blue-500 text-white' : 'bg-gray-200'}`}
          >
            Mensual
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded mb-4">{error}</div>
      )}

      {loading && <div className="text-gray-500 py-2">Cargando...</div>}

      {!loading && !error && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-gray-50 rounded p-3">
              <div className="text-xs text-gray-500 uppercase">Activations (rango)</div>
              <div className="text-lg font-semibold">{formatNum(totalActivations)}</div>
            </div>
            {baseMetrics && (
              <>
                <div className="bg-gray-50 rounded p-3">
                  <div className="text-xs text-gray-500 uppercase">Time to first trip (avg días)</div>
                  <button
                    type="button"
                    onClick={() => parkId && openBaseMetricsDrilldown('time_to_first_trip')}
                    className={`text-lg font-semibold ${parkId ? 'text-blue-600 hover:underline' : ''}`}
                  >
                    {formatNum(baseMetrics.time_to_first_trip_avg)}
                  </button>
                  {parkId && <span className="text-xs text-gray-500 ml-1">(Drilldown)</span>}
                </div>
                <div className="bg-gray-50 rounded p-3">
                  <div className="text-xs text-gray-500 uppercase">Lifetime (avg días activos)</div>
                  <button
                    type="button"
                    onClick={() => parkId && openBaseMetricsDrilldown('lifetime_days')}
                    className={`text-lg font-semibold ${parkId ? 'text-blue-600 hover:underline' : ''}`}
                  >
                    {formatNum(baseMetrics.lifetime_days_avg)}
                  </button>
                  {parkId && <span className="text-xs text-gray-500 ml-1">(Drilldown)</span>}
                </div>
              </>
            )}
            <div className="bg-gray-50 rounded p-3">
              <div className="text-xs text-gray-500 uppercase">Active drivers (último periodo)</div>
              <div className="text-lg font-semibold">{formatNum(totalActive)}</div>
            </div>
            {periodType === 'week' && (
              <>
                <div className="bg-gray-50 rounded p-3">
                  <div className="text-xs text-gray-500 uppercase">Churned (rango)</div>
                  <div className="text-lg font-semibold">{formatNum(totalChurned)}</div>
                </div>
                <div className="bg-gray-50 rounded p-3">
                  <div className="text-xs text-gray-500 uppercase">Reactivated (rango)</div>
                  <div className="text-lg font-semibold">{formatNum(totalReactivated)}</div>
                </div>
              </>
            )}
          </div>

          <h3 className="text-lg font-medium text-gray-700 mb-2">Desglose por Park</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Park</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Activations</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Active Drivers</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Churn Rate</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Reactivation Rate</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Net Growth</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Mix FT/PT</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {parksSummary.map((row, idx) => (
                  <tr key={row.park_id || idx}>
                    <td className="px-4 py-2 text-sm text-gray-900">{row.park_id ?? '—'}</td>
                    <td className="px-4 py-2 text-sm text-right">
                      <button
                        type="button"
                        onClick={() => openDrilldown(row.park_id, 'activations')}
                        className="text-blue-600 hover:underline"
                      >
                        {formatNum(row.activations)}
                      </button>
                    </td>
                    <td className="px-4 py-2 text-sm text-right">
                      <button
                        type="button"
                        onClick={() => openDrilldown(row.park_id, 'active')}
                        className="text-blue-600 hover:underline"
                      >
                        {formatNum(row.active_drivers)}
                      </button>
                    </td>
                    <td className="px-4 py-2 text-sm text-right">
                      <button
                        type="button"
                        onClick={() => openDrilldown(row.park_id, 'churned')}
                        className="text-blue-600 hover:underline"
                      >
                        {formatPct(row.churn_rate)}
                      </button>
                    </td>
                    <td className="px-4 py-2 text-sm text-right">
                      <button
                        type="button"
                        onClick={() => openDrilldown(row.park_id, 'reactivated')}
                        className="text-blue-600 hover:underline"
                      >
                        {formatPct(row.reactivation_rate)}
                      </button>
                    </td>
                    <td className="px-4 py-2 text-sm text-right">{formatNum(row.net_growth)}</td>
                    <td className="px-4 py-2 text-sm text-gray-600">{row.mix_ft_pt ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {parksSummary.length === 0 && (
              <p className="text-gray-500 py-4 text-center">No hay datos por park en el rango seleccionado.</p>
            )}
          </div>

          <h3 className="text-lg font-medium text-gray-700 mb-2 mt-8">Cohortes por Park</h3>
          <div className="flex flex-wrap gap-4 mb-3">
            <label className="flex items-center gap-2">
              <span className="text-sm text-gray-600">Desde cohort</span>
              <input
                type="date"
                value={cohortFrom}
                onChange={e => setCohortFrom(e.target.value)}
                className="border rounded px-2 py-1 text-sm"
              />
            </label>
            <label className="flex items-center gap-2">
              <span className="text-sm text-gray-600">Hasta cohort</span>
              <input
                type="date"
                value={cohortTo}
                onChange={e => setCohortTo(e.target.value)}
                className="border rounded px-2 py-1 text-sm"
              />
            </label>
            <label className="flex items-center gap-2">
              <span className="text-sm text-gray-600">Park</span>
              <select
                value={cohortParkId}
                onChange={e => setCohortParkId(e.target.value)}
                className="border rounded px-2 py-1 text-sm min-w-[140px]"
              >
                <option value="">— Todos —</option>
                {parksList.map(p => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </label>
          </div>
          {cohortsError && (
            <div className="bg-amber-50 border border-amber-200 text-amber-800 px-4 py-2 rounded mb-3 text-sm">
              {cohortsError}
            </div>
          )}
          {cohortsLoading && <p className="text-gray-500 py-2">Cargando cohortes...</p>}
          {!cohortsLoading && (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Cohort Week</th>
                    <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Park</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Cohort Size</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Ret W1</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Ret W4</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Ret W8</th>
                    <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Ret W12</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {cohorts.map((row, idx) => (
                    <tr key={`${row.cohort_week}-${row.park_id ?? 'null'}-${idx}`} className={isParkDesconocido(row.park_id) ? 'bg-amber-50' : ''}>
                      <td className="px-4 py-2 text-sm text-gray-900">{row.cohort_week ?? '—'}</td>
                      <td className="px-4 py-2 text-sm font-medium">
                        <span className={isParkDesconocido(row.park_id) ? 'text-amber-700' : 'text-gray-900'}>
                          {displayParkId(row.park_id)}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-sm text-right">
                        <button
                          type="button"
                          onClick={() => openCohortDrilldown(row.cohort_week, 'base', displayParkId(row.park_id))}
                          className="text-blue-600 hover:underline"
                        >
                          {formatNum(row.cohort_size)}
                        </button>
                      </td>
                      <td className="px-4 py-2 text-sm text-right">
                        <button
                          type="button"
                          onClick={() => openCohortDrilldown(row.cohort_week, 'w1', displayParkId(row.park_id))}
                          className="text-blue-600 hover:underline"
                        >
                          {formatPct(row.retention_w1)}
                        </button>
                      </td>
                      <td className="px-4 py-2 text-sm text-right">
                        <button
                          type="button"
                          onClick={() => openCohortDrilldown(row.cohort_week, 'w4', displayParkId(row.park_id))}
                          className="text-blue-600 hover:underline"
                        >
                          {formatPct(row.retention_w4)}
                        </button>
                      </td>
                      <td className="px-4 py-2 text-sm text-right">
                        <button
                          type="button"
                          onClick={() => openCohortDrilldown(row.cohort_week, 'w8', displayParkId(row.park_id))}
                          className="text-blue-600 hover:underline"
                        >
                          {formatPct(row.retention_w8)}
                        </button>
                      </td>
                      <td className="px-4 py-2 text-sm text-right">
                        <button
                          type="button"
                          onClick={() => openCohortDrilldown(row.cohort_week, 'w12', displayParkId(row.park_id))}
                          className="text-blue-600 hover:underline"
                        >
                          {formatPct(row.retention_w12)}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {cohorts.length === 0 && (
                <p className="text-gray-500 py-4 text-center">No hay cohortes en el rango. Ejecuta apply_driver_lifecycle_v2 para crear MVs de cohortes.</p>
              )}
            </div>
          )}
        </>
      )}

      {modalOpen && modalPayload && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setModalOpen(false)}>
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden" onClick={e => e.stopPropagation()}>
            <div className="p-4 border-b flex justify-between items-center">
              <h4 className="font-semibold">
                {modalPayload.type === 'base_metrics'
                  ? `Drilldown: ${modalPayload.park_id} — ${modalPayload.metric}`
                  : modalPayload.type === 'cohort'
                    ? `Drilldown: ${modalPayload.park_id} — cohort ${modalPayload.cohort_week} (${modalPayload.horizon})`
                    : `Drilldown: ${modalPayload.park_id} — ${modalPayload.metric} (periodo ${modalPayload.period_start})`}
              </h4>
              <button type="button" onClick={() => setModalOpen(false)} className="text-gray-500 hover:text-black">✕</button>
            </div>
            <div className="p-4 overflow-auto max-h-[50vh]">
              {drilldownLoading && <p className="text-gray-500">Cargando...</p>}
              {!drilldownLoading && (
                <>
                  <p className="text-sm text-gray-600 mb-2">Total: {drilldownData.total} drivers</p>
                  <ul className="list-disc list-inside text-sm">
                    {drilldownData.drivers.map((d, i) => (
                      <li key={i}>
                        {d.driver_key}
                        {d.ttf_days_from_registered != null ? ` TTF: ${d.ttf_days_from_registered}d` : ''}
                        {d.lifetime_days != null ? ` Lifetime: ${d.lifetime_days}d` : ''}
                        {d.activation_ts != null && !d.ttf_days_from_registered && !d.lifetime_days ? ` (activation: ${d.activation_ts})` : ''}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
            <div className="p-4 border-t flex justify-end gap-2">
              <button
                type="button"
                onClick={exportDrilldownCsv}
                className="px-3 py-1 bg-gray-200 rounded text-sm hover:bg-gray-300"
              >
                Export CSV
              </button>
              <button type="button" onClick={() => setModalOpen(false)} className="px-3 py-1 bg-blue-500 text-white rounded text-sm">Cerrar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
