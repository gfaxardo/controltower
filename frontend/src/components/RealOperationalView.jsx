/**
 * RealOperationalView — Vista operativa REAL (hourly-first).
 * Hoy / Ayer / Esta semana, por día, por hora, cancelaciones y comparativos.
 * Fuente: ops.mv_real_lob_day_v2, ops.mv_real_lob_hour_v2.
 */
import { useState, useEffect } from 'react'
import {
  getRealOperationalSnapshot,
  getRealOperationalDayView,
  getRealOperationalHourlyView,
  getRealOperationalCancellations,
  getRealOperationalTodayVsYesterday,
  getRealOperationalTodayVsSameWeekday,
  getRealOperationalCurrentHourVsHistorical,
  getRealOperationalThisWeekVsComparable
} from '../services/api'
import DataStateBadge from './DataStateBadge'

const SUB_VIEWS = [
  { id: 'snapshot', label: 'Hoy / Ayer / Semana' },
  { id: 'comparatives', label: 'Comparativos' },
  { id: 'day', label: 'Por día' },
  { id: 'hourly', label: 'Por hora' },
  { id: 'cancellations', label: 'Cancelaciones' }
]

function formatNum (n) {
  if (n == null || n === '') return '—'
  const x = Number(n)
  if (Number.isNaN(x)) return '—'
  return x.toLocaleString('es-ES', { maximumFractionDigits: 2 })
}

function pctClass (pct) {
  if (pct == null) return ''
  if (pct > 0) return 'text-green-600'
  if (pct < 0) return 'text-red-600'
  return 'text-gray-600'
}

// Etiquetas claras para comparativos: Δ% = variación porcentual, Δpp = puntos porcentuales
const COMPARATIVE_LABELS = {
  requested_trips_pct: 'Pedidos (Δ%)',
  completed_trips_pct: 'Completados (Δ%)',
  cancelled_trips_pct: 'Cancelados (Δ%)',
  gross_revenue_pct: 'Revenue (Δ%)',
  margin_total_pct: 'Margen (Δ%)',
  cancellation_rate_pp: 'Tasa cancelación (Δpp)',
  duration_avg_pct: 'Duración prom (Δ%)'
}

function getComparativeLabel (key) {
  return COMPARATIVE_LABELS[key] || key.replace(/_/g, ' ')
}

function formatComparativeValue (key, v) {
  if (v == null) return '—'
  if (typeof v !== 'number') return String(v)
  if (key.includes('_pp')) return `${v >= 0 ? '+' : ''}${v} pp`
  if (key.includes('_pct')) return `${v >= 0 ? '+' : ''}${v}%`
  return String(v)
}

export default function RealOperationalView ({ country = '', city = '' }) {
  const [subView, setSubView] = useState('snapshot')
  const [window, setWindow] = useState('today')
  const [snapshot, setSnapshot] = useState(null)
  const [dayView, setDayView] = useState(null)
  const [hourlyView, setHourlyView] = useState(null)
  const [cancellations, setCancellations] = useState(null)
  const [compTodayYesterday, setCompTodayYesterday] = useState(null)
  const [compSameWeekday, setCompSameWeekday] = useState(null)
  const [compHour, setCompHour] = useState(null)
  const [compWeek, setCompWeek] = useState(null)
  const [hourlyBaseline, setHourlyBaseline] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const params = { country: country || undefined, city: city || undefined }

  useEffect(() => {
    if (subView !== 'snapshot') return
    setLoading(true)
    setError(null)
    getRealOperationalSnapshot({ ...params, window })
      .then(setSnapshot)
      .catch((e) => { setError(e.message); setSnapshot(null) })
      .finally(() => setLoading(false))
  }, [subView, window, country, city])

  useEffect(() => {
    if (subView !== 'day') return
    setLoading(true)
    getRealOperationalDayView({ ...params, days_back: 14, group_by: 'day' })
      .then(setDayView)
      .catch((e) => { setError(e.message); setDayView(null) })
      .finally(() => setLoading(false))
  }, [subView, country, city])

  useEffect(() => {
    if (subView !== 'hourly') return
    setLoading(true)
    getRealOperationalHourlyView({ ...params, days_back: 7, group_by: 'hour' })
      .then(setHourlyView)
      .catch((e) => { setError(e.message); setHourlyView(null) })
      .finally(() => setLoading(false))
  }, [subView, country, city])
  useEffect(() => {
    if (subView !== 'hourly') return
    getRealOperationalCurrentHourVsHistorical({ ...params, weeks_back: 4 })
      .then((r) => { if (!r.error) setHourlyBaseline(r) })
      .catch(() => setHourlyBaseline(null))
  }, [subView, country, city])

  useEffect(() => {
    if (subView !== 'cancellations') return
    setLoading(true)
    getRealOperationalCancellations({ ...params, days_back: 14, by: 'reason_group', limit: 15 })
      .then(setCancellations)
      .catch((e) => { setError(e.message); setCancellations(null) })
      .finally(() => setLoading(false))
  }, [subView, country, city])

  useEffect(() => {
    if (subView !== 'comparatives') return
    setLoading(true)
    setError(null)
    Promise.all([
      getRealOperationalTodayVsYesterday(params),
      getRealOperationalTodayVsSameWeekday({ ...params, n_weeks: 4 }),
      getRealOperationalCurrentHourVsHistorical({ ...params, weeks_back: 4 }),
      getRealOperationalThisWeekVsComparable({ ...params, weeks_back: 4 })
    ])
      .then(([a, b, c, d]) => {
        setCompTodayYesterday(a.error ? null : a)
        setCompSameWeekday(b.error ? null : b)
        setCompHour(c.error ? null : c)
        setCompWeek(d.error ? null : d)
      })
      .catch((e) => { setError(e.message) })
      .finally(() => setLoading(false))
  }, [subView, country, city])

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex flex-wrap items-center gap-2 mb-4 border-b pb-2">
        {SUB_VIEWS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            onClick={() => setSubView(id)}
            className={`px-3 py-1.5 rounded text-sm font-medium ${subView === id ? 'bg-blue-600 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
          >
            {label}
          </button>
        ))}
        <DataStateBadge state="canonical" className="ml-auto" />
      </div>

      {error && <div className="mb-4 p-2 bg-red-100 text-red-800 rounded text-sm">{error}</div>}

      {subView === 'snapshot' && (
        <>
          <div className="flex gap-2 mb-4">
            {['today', 'yesterday', 'this_week'].map((w) => (
              <button
                key={w}
                type="button"
                onClick={() => setWindow(w)}
                className={`px-3 py-1 rounded text-sm ${window === w ? 'bg-blue-500 text-white' : 'bg-gray-100'}`}
              >
                {w === 'today' ? 'Hoy' : w === 'yesterday' ? 'Ayer' : 'Esta semana'}
              </button>
            ))}
          </div>
          {loading && <p className="text-gray-500">Cargando…</p>}
          {!loading && snapshot && !snapshot.error && (
            <>
              {snapshot.requested_trips === 0 && snapshot.completed_trips === 0 && (
                <p className="text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2 mb-3 text-sm">
                  Sin datos para este periodo. Compruebe que las MVs operativas (hourly/day) estén refrescadas y que la fuente tenga datos hasta la fecha.
                </p>
              )}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-3 bg-gray-50 rounded">
                <div className="text-xs text-gray-500 uppercase">Pedidos</div>
                <div className="text-xl font-semibold">{formatNum(snapshot.requested_trips)}</div>
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <div className="text-xs text-gray-500 uppercase">Completados</div>
                <div className="text-xl font-semibold">{formatNum(snapshot.completed_trips)}</div>
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <div className="text-xs text-gray-500 uppercase">Cancelados</div>
                <div className="text-xl font-semibold">{formatNum(snapshot.cancelled_trips)}</div>
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <div className="text-xs text-gray-500 uppercase">Tasa cancelación</div>
                <div className="text-xl font-semibold">{snapshot.cancellation_rate != null ? (snapshot.cancellation_rate * 100).toFixed(2) + '%' : '—'}</div>
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <div className="text-xs text-gray-500 uppercase">Revenue</div>
                {snapshot.gross_revenue_by_country?.length > 1 ? (
                  <div className="text-sm" title="No se suman monedas (COP/PEN). Ver por país.">
                    {snapshot.gross_revenue_by_country.map(({ country, gross_revenue }) => (
                      <div key={country}>{country ? country.toUpperCase() : '—'}: {formatNum(gross_revenue)}</div>
                    ))}
                  </div>
                ) : (
                  <div className="text-xl font-semibold">{formatNum(snapshot.gross_revenue)}</div>
                )}
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <div className="text-xs text-gray-500 uppercase">Margen</div>
                <div className="text-xl font-semibold">{formatNum(snapshot.margin_total)}</div>
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <div className="text-xs text-gray-500 uppercase">Duración prom (min)</div>
                <div className="text-xl font-semibold">{formatNum(snapshot.duration_avg_minutes)}</div>
              </div>
            </div>
            </>
          )}
        </>
      )}

      {subView === 'comparatives' && (
        <>
          <p className="text-xs text-gray-500 mb-2" title="Δ% = variación porcentual respecto al valor de referencia. Δpp = diferencia en puntos porcentuales (ej. tasa de cancelación).">
            Δ% = variación % respecto al baseline · Δpp = puntos porcentuales
          </p>
          {loading && <p className="text-gray-500">Cargando comparativos…</p>}
          {!loading && (
            <div className="space-y-6">
              {compTodayYesterday && !compTodayYesterday.error && (
                <section>
                  <h3 className="font-semibold text-gray-800 mb-2">Hoy vs Ayer</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                    {compTodayYesterday.comparative && Object.entries(compTodayYesterday.comparative).map(([k, v]) => (
                      <div key={k} className="p-2 bg-gray-50 rounded" title={k.includes('_pp') ? 'Puntos porcentuales de diferencia' : 'Variación porcentual'}><span className="text-gray-600">{getComparativeLabel(k)}:</span>{' '}<span className={pctClass(v)}>{formatComparativeValue(k, v)}</span></div>
                    ))}
                  </div>
                </section>
              )}
              {compSameWeekday && !compSameWeekday.error && compSameWeekday.comparative && (
                <section>
                  <h3 className="font-semibold text-gray-800 mb-2">Hoy vs mismo día de semana (últimos 4)</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                    {Object.entries(compSameWeekday.comparative).map(([k, v]) => (
                      <div key={k} className="p-2 bg-gray-50 rounded" title={k.includes('_pp') ? 'Puntos porcentuales' : 'Variación %'}><span className="text-gray-600">{getComparativeLabel(k)}:</span>{' '}<span className={pctClass(v)}>{formatComparativeValue(k, v)}</span></div>
                    ))}
                  </div>
                </section>
              )}
              {compHour && !compHour.error && compHour.comparative && (
                <section>
                  <h3 className="font-semibold text-gray-800 mb-2">Hora actual (UTC {compHour.current_hour}h) vs histórico</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                    {Object.entries(compHour.comparative).map(([k, v]) => (
                      <div key={k} className="p-2 bg-gray-50 rounded" title={k.includes('_pp') ? 'Puntos porcentuales' : 'Variación %'}><span className="text-gray-600">{getComparativeLabel(k)}:</span>{' '}<span className={pctClass(v)}>{formatComparativeValue(k, v)}</span></div>
                    ))}
                  </div>
                </section>
              )}
              {compWeek && !compWeek.error && compWeek.comparative && (
                <section>
                  <h3 className="font-semibold text-gray-800 mb-2">Esta semana vs semanas anteriores</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                    {Object.entries(compWeek.comparative).map(([k, v]) => (
                      <div key={k} className="p-2 bg-gray-50 rounded" title={k.includes('_pp') ? 'Puntos porcentuales' : 'Variación %'}><span className="text-gray-600">{getComparativeLabel(k)}:</span>{' '}<span className={pctClass(v)}>{formatComparativeValue(k, v)}</span></div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          )}
        </>
      )}

      {subView === 'day' && (
        <>
          {loading && <p className="text-gray-500">Cargando…</p>}
          {!loading && dayView && !dayView.error && dayView.rows?.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2">Fecha</th>
                    <th className="text-right py-2">Pedidos</th>
                    <th className="text-right py-2">Completados</th>
                    <th className="text-right py-2">Cancelados</th>
                    <th className="text-right py-2">Cancel %</th>
                    <th className="text-right py-2">Revenue</th>
                    <th className="text-right py-2">Duración (min)</th>
                  </tr>
                </thead>
                <tbody>
                  {dayView.rows.map((r, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      <td className="py-1">{r.period_key ?? r.trip_date}</td>
                      <td className="text-right">{formatNum(r.requested_trips)}</td>
                      <td className="text-right">{formatNum(r.completed_trips)}</td>
                      <td className="text-right">{formatNum(r.cancelled_trips)}</td>
                      <td className="text-right">{r.cancellation_rate != null ? (r.cancellation_rate * 100).toFixed(2) + '%' : '—'}</td>
                      <td className="text-right">{formatNum(r.gross_revenue)}</td>
                      <td className="text-right">{formatNum(r.duration_total_minutes)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {!loading && dayView && !dayView.error && (!dayView.rows || dayView.rows.length === 0) && <p className="text-gray-500">Sin datos para el rango seleccionado.</p>}
        </>
      )}

      {subView === 'hourly' && (
        <>
          {hourlyBaseline && !hourlyBaseline.error && hourlyBaseline.current && (
            <div className="mb-4 p-3 bg-slate-50 rounded border border-slate-200 text-sm">
              <h4 className="font-medium text-gray-800 mb-2">Hora actual (UTC {hourlyBaseline.current_hour}h) vs baseline (promedio mismas horas, últimas 4 semanas)</h4>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                <span className="text-gray-600">Pedidos:</span><span>{formatNum(hourlyBaseline.current?.requested_trips)} (baseline: {formatNum(hourlyBaseline.historical_same_hour?.requested_trips)})</span>
                <span className="text-gray-600">Completados:</span><span>{formatNum(hourlyBaseline.current?.completed_trips)} (baseline: {formatNum(hourlyBaseline.historical_same_hour?.completed_trips)})</span>
                <span className="text-gray-600">Cancelados:</span><span>{formatNum(hourlyBaseline.current?.cancelled_trips)} (baseline: {formatNum(hourlyBaseline.historical_same_hour?.cancelled_trips)})</span>
                <span className="text-gray-600">Tasa cancel.:</span><span>{hourlyBaseline.current?.cancellation_rate != null ? (hourlyBaseline.current.cancellation_rate * 100).toFixed(2) + '%' : '—'} (baseline: {hourlyBaseline.historical_same_hour?.cancellation_rate != null ? (hourlyBaseline.historical_same_hour.cancellation_rate * 100).toFixed(2) + '%' : '—'})</span>
                {hourlyBaseline.comparative && (
                  <>
                    <span className="text-gray-600">Δ% pedidos:</span><span className={pctClass(hourlyBaseline.comparative.requested_trips_pct)}>{formatComparativeValue('requested_trips_pct', hourlyBaseline.comparative.requested_trips_pct)}</span>
                    <span className="text-gray-600">Δpp cancel.:</span><span className={pctClass(hourlyBaseline.comparative.cancellation_rate_pp)}>{formatComparativeValue('cancellation_rate_pp', hourlyBaseline.comparative.cancellation_rate_pp)}</span>
                  </>
                )}
              </div>
            </div>
          )}
          {loading && <p className="text-gray-500">Cargando…</p>}
          {!loading && hourlyView && !hourlyView.error && hourlyView.rows?.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2">Hora</th>
                    <th className="text-right py-2">Pedidos</th>
                    <th className="text-right py-2">Completados</th>
                    <th className="text-right py-2">Cancelados</th>
                    <th className="text-right py-2">Cancel %</th>
                    <th className="text-right py-2">Revenue</th>
                  </tr>
                </thead>
                <tbody>
                  {hourlyView.rows.map((r, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      <td className="py-1">{r.trip_hour != null ? r.trip_hour + 'h' : r.period_key}</td>
                      <td className="text-right">{formatNum(r.requested_trips)}</td>
                      <td className="text-right">{formatNum(r.completed_trips)}</td>
                      <td className="text-right">{formatNum(r.cancelled_trips)}</td>
                      <td className="text-right">{r.cancellation_rate != null ? (r.cancellation_rate * 100).toFixed(2) + '%' : '—'}</td>
                      <td className="text-right">{formatNum(r.gross_revenue)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {!loading && hourlyView && !hourlyView.error && (!hourlyView.rows || hourlyView.rows.length === 0) && <p className="text-gray-500">Sin datos.</p>}
        </>
      )}

      {subView === 'cancellations' && (
        <>
          {loading && <p className="text-gray-500">Cargando…</p>}
          {!loading && cancellations && !cancellations.error && cancellations.rows?.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-2">Motivo / Grupo</th>
                    <th className="text-right py-2">Cancelados</th>
                    <th className="text-right py-2">Pedidos</th>
                    <th className="text-right py-2">Tasa</th>
                  </tr>
                </thead>
                <tbody>
                  {cancellations.rows.map((r, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      <td className="py-1">{r.reason_key ?? r.cancel_reason_group ?? '—'}</td>
                      <td className="text-right">{formatNum(r.cancelled_trips)}</td>
                      <td className="text-right">{formatNum(r.requested_trips)}</td>
                      <td className="text-right">{r.cancellation_rate != null ? (r.cancellation_rate * 100).toFixed(2) + '%' : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {!loading && cancellations && !cancellations.error && (!cancellations.rows || cancellations.rows.length === 0) && <p className="text-gray-500">Sin datos de cancelaciones.</p>}
        </>
      )}
    </div>
  )
}
