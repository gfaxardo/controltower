/**
 * Real LOB Daily — Vista diaria con comparativos D-1, mismo día semana pasada, promedio 4 mismos días.
 */
import { useState, useEffect } from 'react'
import {
  getRealLobDailySummary,
  getRealLobDailyComparative,
  getRealLobDailyTable,
  getPeriodSemantics
} from '../services/api'
import { getComparativeClass, COMPARATIVE_LABELS } from '../constants/gridSemantics'

const BASELINE_OPTIONS = [
  { value: 'D-1', label: 'D-1 (vs día anterior)' },
  { value: 'same_weekday_previous_week', label: 'Mismo día semana pasada (WoW)' },
  { value: 'same_weekday_avg_4w', label: 'Promedio últimos 4 mismos días' }
]

function formatNum (n) {
  if (n == null || n === '') return '—'
  const num = Number(n)
  if (Number.isNaN(num)) return '—'
  if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M'
  if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K'
  return num.toLocaleString()
}

export default function RealLOBDailyView () {
  const [day, setDay] = useState('') // '' = último día cerrado
  const [lastClosedDay, setLastClosedDay] = useState(null)
  const [baseline, setBaseline] = useState('D-1')
  const [summary, setSummary] = useState(null)
  const [comparative, setComparative] = useState(null)
  const [table, setTable] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const effectiveDay = day || (summary?.trip_day) || ''

  useEffect(() => {
    getPeriodSemantics()
      .then((d) => setLastClosedDay(d.last_closed_day || null))
      .catch(() => setLastClosedDay(null))
  }, [])

  useEffect(() => {
    setLoading(true)
    setError(null)
    const params = {}
    if (day) params.day = day
    Promise.all([
      getRealLobDailySummary(params),
      getRealLobDailyComparative({ ...params, baseline }),
      getRealLobDailyTable({ ...params, group_by: 'lob', baseline })
    ])
      .then(([sum, comp, tbl]) => {
        setSummary(sum)
        setComparative(comp)
        setTable(tbl)
      })
      .catch((e) => {
        setError(e?.message || 'Error al cargar vista diaria')
        setSummary(null)
        setComparative(null)
        setTable(null)
      })
      .finally(() => setLoading(false))
  }, [day, baseline])

  const baselineLabel = BASELINE_OPTIONS.find((o) => o.value === baseline)?.label || baseline

  return (
    <div className="space-y-4">
      <div className="p-3 bg-amber-50 border border-amber-200 rounded text-sm">
        <strong>Selector de día y baseline</strong> — El día por defecto es el último día cerrado (ayer). El comparativo usa el baseline elegido.
      </div>
      <div className="flex flex-wrap gap-4 items-center">
        <label className="text-sm font-medium text-gray-700">
          Día:
          <input
            type="date"
            value={day || effectiveDay}
            onChange={(e) => setDay(e.target.value || '')}
            className="ml-2 border border-gray-300 rounded px-2 py-1.5"
          />
        </label>
        <span className="text-xs text-gray-500">
          {!day && lastClosedDay ? `(por defecto: último día cerrado ${lastClosedDay})` : ''}
        </span>
        <label className="text-sm font-medium text-gray-700">
          Comparar con (baseline):
          <select
            value={baseline}
            onChange={(e) => setBaseline(e.target.value)}
            className="ml-2 border border-gray-300 rounded px-2 py-1.5"
          >
            {BASELINE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
        <span className="text-xs text-gray-600 font-mono">→ {baselineLabel}</span>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
          {error}
        </div>
      )}

      {loading && (
        <div className="p-4 text-gray-500">Cargando vista diaria…</div>
      )}

      {!loading && !summary && !error && (
        <div className="p-4 text-gray-500">No hay datos para mostrar. Compruebe que el backend esté en marcha y que real_rollup_day_fact tenga datos.</div>
      )}

      {!loading && summary && (
        <>
          <div className="p-3 bg-slate-100 border border-slate-300 rounded text-sm font-medium">
            Día consultado: <span className="font-mono">{summary.trip_day}</span> · Baseline: <span className="font-mono">{comparative?.baseline_label || baselineLabel}</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {summary.by_country?.map(({ country: c, trips, margin_total, margin_trip, km_prom, b2b_pct }) => (
              <div key={c} className="p-4 border rounded-lg bg-white border-gray-200">
                <div className="font-medium text-gray-800 uppercase mb-2">{c}</div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <span>Viajes:</span><span>{formatNum(trips)}</span>
                  <span>Margen total:</span><span>{margin_total != null ? Number(margin_total).toFixed(2) : '—'}</span>
                  <span>Margen/trip:</span><span>{margin_trip != null ? Number(margin_trip).toFixed(2) : '—'}</span>
                  <span>Km prom:</span><span>{km_prom != null ? Number(km_prom).toFixed(2) : '—'}</span>
                  <span>B2B %:</span><span>{b2b_pct != null ? Number(b2b_pct).toFixed(1) + '%' : '—'}</span>
                </div>
              </div>
            ))}
          </div>

          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="text-sm font-semibold text-blue-900 mb-2">Comparativo diario (vs baseline seleccionado)</div>
            {comparative?.error && <p className="text-sm text-amber-700">{comparative.error}</p>}
            {comparative && !comparative.error && (!comparative.by_country || comparative.by_country.length === 0) && (
              <p className="text-sm text-gray-600">Sin datos para este día o baseline.</p>
            )}
            {comparative && !comparative.error && comparative.by_country?.length > 0 && (
              <div className="flex flex-wrap gap-4">
                {comparative.by_country.map(({ country: c, metrics }) => (
                  <div key={c} className="flex flex-wrap gap-3 items-baseline">
                    <span className="font-medium uppercase">{c}</span>
                    {metrics?.map((m) => (
                      <span key={m.metric} className="text-sm" title={`Actual: ${m.value_current ?? '—'} | Baseline: ${m.value_baseline ?? '—'}`}>
                        {m.metric}: {m.delta_pct != null ? `${m.delta_pct > 0 ? '↑' : m.delta_pct < 0 ? '↓' : '→'} ${Number(m.delta_pct).toFixed(1)}%` : '—'}
                      </span>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="font-medium text-gray-700 mt-2">
            Tabla por LOB (día {summary.trip_day})
            {table?.baseline_label && <span className="ml-2 text-blue-700 font-normal">· Baseline: {table.baseline_label}</span>}
          </div>
          {table?.error && <p className="text-sm text-amber-700">{table.error}</p>}
          {table && table.rows?.length > 0 ? (
            <div className="overflow-x-auto border rounded-lg">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">País</th>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">LOB / Park</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Viajes</th>
                    {table.baseline && <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase w-20">{COMPARATIVE_LABELS.dailyDeltaPctLabel(baseline)}</th>}
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Margen total</th>
                    {table.baseline && <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase w-20">{COMPARATIVE_LABELS.dailyDeltaPctLabel(baseline)}</th>}
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Margen/trip</th>
                    {table.baseline && <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase w-20">{COMPARATIVE_LABELS.dailyDeltaPctLabel(baseline)}</th>}
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Km prom</th>
                    {table.baseline && <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase w-20">{COMPARATIVE_LABELS.dailyDeltaPctLabel(baseline)}</th>}
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">B2B %</th>
                    {table.baseline && <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase w-16">{COMPARATIVE_LABELS.dailyPpLabel()}</th>}
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {table.rows.map((row, i) => (
                    <tr key={i}>
                      <td className="px-3 py-2 text-sm">{row.country}</td>
                      <td className="px-3 py-2 text-sm font-medium">{row.dimension_key ?? row.park_name_resolved ?? '—'}</td>
                      <td className="px-3 py-2 text-sm text-right">{formatNum(row.trips)}</td>
                      {table.baseline && (
                        <td className={`px-3 py-2 text-sm text-right ${getComparativeClass(row.trips_trend).bg}`}>
                          {row.trips_delta_pct != null ? (
                            <span className={getComparativeClass(row.trips_trend).text}>
                              {getComparativeClass(row.trips_trend).arrow} {Number(row.trips_delta_pct).toFixed(1)}%
                            </span>
                          ) : '—'}
                        </td>
                      )}
                      <td className="px-3 py-2 text-sm text-right">{row.margin_total != null ? Number(row.margin_total).toFixed(2) : '—'}</td>
                      {table.baseline && (
                        <td className={`px-3 py-2 text-sm text-right ${getComparativeClass(row.margin_total_trend).bg}`}>
                          {row.margin_total_delta_pct != null ? (
                            <span className={getComparativeClass(row.margin_total_trend).text}>
                              {getComparativeClass(row.margin_total_trend).arrow} {Number(row.margin_total_delta_pct).toFixed(1)}%
                            </span>
                          ) : '—'}
                        </td>
                      )}
                      <td className="px-3 py-2 text-sm text-right">{row.margin_trip != null ? Number(row.margin_trip).toFixed(2) : '—'}</td>
                      {table.baseline && (
                        <td className={`px-3 py-2 text-sm text-right ${getComparativeClass(row.margin_trip_trend).bg}`}>
                          {row.margin_trip_delta_pct != null ? (
                            <span className={getComparativeClass(row.margin_trip_trend).text}>
                              {getComparativeClass(row.margin_trip_trend).arrow} {Number(row.margin_trip_delta_pct).toFixed(1)}%
                            </span>
                          ) : '—'}
                        </td>
                      )}
                      <td className="px-3 py-2 text-sm text-right">{row.km_prom != null ? Number(row.km_prom).toFixed(2) : '—'}</td>
                      {table.baseline && (
                        <td className={`px-3 py-2 text-sm text-right ${getComparativeClass(row.km_prom_trend).bg}`}>
                          {row.km_prom_delta_pct != null ? (
                            <span className={getComparativeClass(row.km_prom_trend).text}>
                              {getComparativeClass(row.km_prom_trend).arrow} {Number(row.km_prom_delta_pct).toFixed(1)}%
                            </span>
                          ) : '—'}
                        </td>
                      )}
                      <td className="px-3 py-2 text-sm text-right">{row.b2b_pct != null ? Number(row.b2b_pct).toFixed(1) + '%' : '—'}</td>
                      {table.baseline && (
                        <td className={`px-3 py-2 text-sm text-right ${getComparativeClass(row.b2b_pct_trend).bg}`}>
                          {row.b2b_pct_delta_pp != null ? (
                            <span className={getComparativeClass(row.b2b_pct_trend).text}>
                              {getComparativeClass(row.b2b_pct_trend).arrow} {Number(row.b2b_pct_delta_pp).toFixed(1)} pp
                            </span>
                          ) : '—'}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-gray-500">Sin filas para este día.</p>
          )}
        </>
      )}
    </div>
  )
}
