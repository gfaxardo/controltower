/**
 * RealLOBDrillView — Vista drill-down jerárquica (Fase 2C+).
 * Timeline mensual/semanal por país (CO, PE); doble click despliega por LOB o por Park.
 * Sin inputs de país/ciudad/park; segmento Todos|B2B|B2C.
 */
import { useState, useEffect, useCallback, Fragment } from 'react'
import {
  getRealDrillSummary,
  getRealDrillByLob,
  getRealDrillByPark
} from '../services/api'

const MARGIN_TOOLTIP = 'Margen mostrado en positivo (ABS) para lectura de negocio.'

const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
const SEGMENT_OPTIONS = [
  { value: 'Todos', label: 'Todos' },
  { value: 'B2B', label: 'B2B' },
  { value: 'B2C', label: 'B2C' }
]

function formatPeriod (periodStart, periodType) {
  if (!periodStart) return ''
  const s = String(periodStart)
  if (periodType === 'weekly') {
    return s.length >= 10 ? `Semana ${s}` : s
  }
  const [y, m] = s.slice(0, 7).split('-')
  const monthName = MESES[parseInt(m, 10) - 1] || m
  return `${monthName} ${y}`
}

function formatNumber (n) {
  if (n == null || n === '') return '—'
  const num = Number(n)
  if (Number.isNaN(num)) return '—'
  if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M'
  if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K'
  return num.toLocaleString()
}

function formatMargin (n, trips) {
  if (trips === 0 || n == null || Number.isNaN(Number(n))) return '—'
  return Number(n).toFixed(2)
}

function formatDistanceKm (n, trips) {
  if (trips === 0 || n == null || Number.isNaN(Number(n))) return '—'
  return Number(n).toFixed(2)
}

export default function RealLOBDrillView () {
  const [periodType, setPeriodType] = useState('monthly')
  const [drillBy, setDrillBy] = useState('lob') // 'lob' | 'park'
  const [segment, setSegment] = useState('Todos')
  const [countries, setCountries] = useState([]) // [{ country, coverage, kpis, rows }]
  const [meta, setMeta] = useState({ last_period_monthly: null, last_period_weekly: null })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(new Set()) // keys "country|period_start"
  const [subrows, setSubrows] = useState({}) // key -> { loading, data, error }

  const limitPeriods = periodType === 'monthly' ? 24 : 26

  const loadSummary = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const summaryRes = await getRealDrillSummary({
        period_type: periodType,
        segment: segment === 'Todos' ? undefined : segment,
        limit_periods: limitPeriods
      })
      setCountries(summaryRes.countries || [])
      setMeta(summaryRes.meta || {})
    } catch (e) {
      setError(e.message || 'Error al cargar timeline')
      setCountries([])
    } finally {
      setLoading(false)
    }
  }, [periodType, segment, limitPeriods])

  useEffect(() => {
    loadSummary()
  }, [loadSummary])

  const normalizePeriodStart = (periodStart) => {
    const s = String(periodStart).trim()
    if (periodType === 'monthly' && s.length === 7) return `${s}-01`
    return s
  }

  const toggleExpand = useCallback(async (country, periodStart) => {
    const rawKey = `${country}|${periodStart}`
    const key = `${country}|${normalizePeriodStart(periodStart)}`
    if (expanded.has(key) || expanded.has(rawKey)) {
      setExpanded((prev) => {
        const next = new Set(prev)
        next.delete(key)
        next.delete(rawKey)
        return next
      })
      return
    }
    setExpanded((prev) => new Set(prev).add(key))
    if (subrows[key]?.data || subrows[rawKey]?.data) return
    setSubrows((prev) => ({ ...prev, [key]: { loading: true, data: null, error: null } }))
    try {
      const params = {
        period_type: periodType,
        country,
        period_start: normalizePeriodStart(periodStart),
        segment: segment === 'Todos' ? undefined : segment
      }
      const fetcher = drillBy === 'lob' ? getRealDrillByLob : getRealDrillByPark
      const res = await fetcher(params)
      setSubrows((prev) => ({
        ...prev,
        [key]: { loading: false, data: res.data || [], error: null }
      }))
    } catch (e) {
      setSubrows((prev) => ({
        ...prev,
        [key]: { loading: false, data: null, error: e.message || 'Error al cargar desglose' }
      }))
    }
  }, [expanded, subrows, periodType, drillBy, segment])

  const now = new Date()
  const currentMonthStart = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
  const currentWeekStart = (() => {
    const d = new Date(now)
    const day = d.getDay()
    const diff = d.getDate() - day + (day === 0 ? -6 : 1)
    d.setDate(diff)
    return d.toISOString().slice(0, 10)
  })()

  const isPeriodOpen = (periodStart) => {
    const s = String(periodStart).slice(0, 10)
    if (periodType === 'monthly') return s.slice(0, 7) === currentMonthStart.slice(0, 7)
    return s === currentWeekStart
  }

  // countries ya viene ordenado PE, CO desde la API

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      <div className="flex flex-wrap justify-between items-center gap-4 mb-4">
        <h3 className="text-lg font-semibold">Real LOB — Drill por país</h3>
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-sm text-gray-500">Periodo:</span>
          <button
            type="button"
            onClick={() => setPeriodType('monthly')}
            className={`px-3 py-1.5 rounded text-sm ${periodType === 'monthly' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            Mensual
          </button>
          <button
            type="button"
            onClick={() => setPeriodType('weekly')}
            className={`px-3 py-1.5 rounded text-sm ${periodType === 'weekly' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            Semanal
          </button>
          <span className="w-px h-6 bg-gray-300" />
          <span className="text-sm text-gray-500">Desglose:</span>
          <button
            type="button"
            onClick={() => setDrillBy('lob')}
            className={`px-3 py-1.5 rounded text-sm ${drillBy === 'lob' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            LOB
          </button>
          <button
            type="button"
            onClick={() => setDrillBy('park')}
            className={`px-3 py-1.5 rounded text-sm ${drillBy === 'park' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            Park
          </button>
          <span className="w-px h-6 bg-gray-300" />
          <span className="text-sm text-gray-500">Segmento:</span>
          <select
            value={segment}
            onChange={(e) => setSegment(e.target.value)}
            className="border rounded px-2 py-1.5 text-sm"
          >
            {SEGMENT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      {meta.hint && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded text-amber-800 text-sm mb-4">
          {meta.hint}
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded text-red-800 text-sm mb-4">{error}</div>
      )}

      {loading ? (
        <div className="animate-pulse space-y-3">
          <div className="h-4 bg-gray-200 rounded w-1/3" />
          <div className="h-32 bg-gray-200 rounded" />
        </div>
      ) : (
        <div className="space-y-6">
          {countries.map(({ country: countryCode, coverage: countryCoverage, kpis, rows }) => {
            const country = (countryCode || '').toUpperCase()
            return (
              <section key={country}>
                {/* Cobertura para este país */}
                {countryCoverage && (countryCoverage.last_trip_date || countryCoverage.last_month_with_data || countryCoverage.last_week_with_data) && (
                  <div className="mb-2 p-3 bg-slate-100 rounded border border-slate-200 text-sm">
                    <span className="font-medium text-slate-600">{country}:</span>{' '}
                    último día con data <span className="font-mono">{countryCoverage.last_trip_date || '—'}</span>
                    {periodType === 'monthly' && (<> · último mes <span className="font-mono">{countryCoverage.last_month_with_data || '—'}</span></>)}
                    {periodType === 'weekly' && (<> · última semana <span className="font-mono">{countryCoverage.last_week_with_data || '—'}</span></>)}
                  </div>
                )}
                {/* KPI bar por país */}
                {kpis && (
                  <div className="grid grid-cols-2 md:grid-cols-5 lg:grid-cols-6 gap-3 mb-3 p-4 bg-slate-50 rounded-lg border border-slate-200">
                    <div>
                      <div className="text-xs text-slate-500">Total viajes</div>
                      <div className="text-lg font-semibold">{formatNumber(kpis.total_trips)}</div>
                    </div>
                    <div title={MARGIN_TOOLTIP}>
                      <div className="text-xs text-slate-500">Margen total</div>
                      <div className="text-lg font-semibold">{kpis.total_trips ? formatMargin(kpis.margin_total_pos, kpis.total_trips) : '—'}</div>
                    </div>
                    <div title={MARGIN_TOOLTIP}>
                      <div className="text-xs text-slate-500">Margen/trip</div>
                      <div className="text-lg font-semibold">{formatMargin(kpis.margin_unit_pos, kpis.total_trips)}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500">Km prom</div>
                      <div className="text-lg font-semibold">{formatDistanceKm(kpis.km_prom, kpis.total_trips)}</div>
                    </div>
                    {segment === 'Todos' && (kpis.b2b_trips != null || kpis.b2b_pct != null) && (
                      <div>
                        <div className="text-xs text-slate-500">Viajes B2B / %B2B</div>
                        <div className="text-lg font-semibold">
                          {formatNumber(kpis.b2b_trips)}
                          {kpis.b2b_pct != null && ` (${Number(kpis.b2b_pct * 100).toFixed(2)}%)`}
                        </div>
                      </div>
                    )}
                    <div>
                      <div className="text-xs text-slate-500">Último periodo</div>
                      <div className="text-sm font-medium">{kpis.last_period || '—'}</div>
                    </div>
                  </div>
                )}
                {rows.length === 0 ? (
                  <div className="p-4 border border-gray-200 rounded-lg bg-gray-50 text-sm text-gray-500">
                    Sin datos para este país en el rango seleccionado.
                  </div>
                ) : (
                <div className="overflow-x-auto border border-gray-200 rounded-lg">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase w-8" />
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Periodo</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Viajes</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase" title={MARGIN_TOOLTIP}>Margen total</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase" title={MARGIN_TOOLTIP}>Margen/trip</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Km prom</th>
                        <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase">Segmento / B2B</th>
                        <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase">Estado</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {rows.map((row) => {
                        const key = `${(row.country || countryCode || '').trim()}|${normalizePeriodStart(row.period_start)}`
                        const isExp = expanded.has(key)
                        const sr = subrows[key] || subrows[`${(row.country || countryCode || '').trim()}|${row.period_start}`]
                        const open = isPeriodOpen(row.period_start)
                        const b2bRatio =
                          segment === 'Todos' && row.trips > 0 && row.b2b_trips != null
                            ? (100 * row.b2b_trips / row.trips).toFixed(1)
                            : null
                        const marginTotalPos = row.margin_total_pos != null ? row.margin_total_pos : (row.margin_total != null ? Math.abs(row.margin_total) : null)
                        const marginUnit = row.trips > 0 && (row.margin_unit_pos != null || row.margin_unit_avg != null) ? formatMargin(row.margin_unit_pos ?? row.margin_unit_avg, row.trips) : '—'
                        const distanceKm = row.trips > 0 && (row.km_prom != null || row.distance_km_avg != null || row.distance_total_km != null)
                          ? formatDistanceKm(row.km_prom ?? row.distance_km_avg ?? (row.distance_total_km / row.trips), row.trips)
                          : '—'
                        return (
                          <Fragment key={key}>
                            <tr
                              onDoubleClick={() => toggleExpand((row.country || countryCode || '').trim(), row.period_start)}
                              className="cursor-pointer hover:bg-slate-50 select-none"
                            >
                              <td className="px-3 py-2 text-sm text-gray-500">
                                {sr?.loading ? (
                                  <span className="animate-pulse">…</span>
                                ) : (
                                  <span className="inline-block w-5 text-center">{isExp ? '▼' : '▶'}</span>
                                )}
                              </td>
                              <td className="px-3 py-2 text-sm font-medium text-gray-900">
                                {formatPeriod(row.period_start, periodType)}
                              </td>
                              <td className="px-3 py-2 text-sm text-right">{formatNumber(row.trips)}</td>
                              <td className="px-3 py-2 text-sm text-right">{row.trips ? formatMargin(marginTotalPos, row.trips) : '—'}</td>
                              <td className="px-3 py-2 text-sm text-right">{marginUnit}</td>
                              <td className="px-3 py-2 text-sm text-right">{distanceKm}</td>
                              <td className="px-3 py-2 text-sm text-center">
                                {segment !== 'Todos' ? (
                                  <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-800">
                                    {segment}
                                  </span>
                                ) : b2bRatio != null ? (
                                  <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                                    B2B {b2bRatio}%
                                  </span>
                                ) : (
                                  '—'
                                )}
                              </td>
                              <td className="px-3 py-2 text-sm text-center">
                                {(() => {
                                  const estado = row.estado || (open ? 'ABIERTO' : 'CERRADO')
                                  const expectedDate = row.expected_last_date ? String(row.expected_last_date).slice(0, 10) : null
                                  const faltaDataTitle = expectedDate
                                    ? `Falta data hasta cierre de ayer (${expectedDate})`
                                    : 'Falta data hasta cierre de ayer'
                                  const config = {
                                    CERRADO: { className: 'bg-green-100 text-green-800', label: 'Cerrado' },
                                    ABIERTO: { className: 'bg-blue-100 text-blue-800', label: 'Abierto' },
                                    FALTA_DATA: { className: 'bg-red-100 text-red-800', label: 'Falta data', title: faltaDataTitle },
                                    VACIO: { className: 'bg-gray-200 text-gray-600', label: 'Vacío' }
                                  }
                                  const { className, label, title } = config[estado] || config.ABIERTO
                                  return (
                                    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${className}`} title={title || undefined}>
                                      {label}
                                    </span>
                                  )
                                })()}
                              </td>
                            </tr>
                            {isExp && sr && (
                              <tr key={`${key}-sub`} className="bg-slate-50">
                                <td colSpan={8} className="px-4 py-3">
                                  {sr.loading && <p className="text-sm text-gray-500">Cargando…</p>}
                                  {sr.error && <p className="text-sm text-red-600">{sr.error}</p>}
                                  {sr.data && sr.data.length > 0 && (
                                    <table className="min-w-full text-sm">
                                      <thead>
                                        <tr className="text-left text-gray-500">
                                          {drillBy === 'lob' && <th className="pr-4 py-1">LOB</th>}
                                          {drillBy === 'park' && (
                                            <>
                                              <th className="pr-4 py-1">Ciudad</th>
                                              <th className="pr-4 py-1">Park</th>
                                              <th className="pr-4 py-1">Bucket</th>
                                            </>
                                          )}
                                          <th className="text-right py-1">Viajes</th>
                                          <th className="text-right py-1" title={MARGIN_TOOLTIP}>Margen total</th>
                                          <th className="text-right py-1" title={MARGIN_TOOLTIP}>Margen/trip</th>
                                          <th className="text-right py-1">Km prom</th>
                                          {segment === 'Todos' && <th className="text-right py-1">B2B</th>}
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {sr.data.map((r, i) => {
                                          const subTrips = r.trips ?? 0
                                          const subMarginTotal = r.margin_total_pos ?? (r.margin_total != null ? Math.abs(r.margin_total) : null)
                                          const subMargin = subTrips > 0 && (r.margin_unit_pos != null || r.margin_unit_avg != null || r.margin_total != null)
                                            ? formatMargin(r.margin_unit_pos ?? r.margin_unit_avg ?? (subMarginTotal != null ? subMarginTotal / subTrips : null), subTrips)
                                            : '—'
                                          const subKm = subTrips > 0 && (r.km_prom != null || r.distance_km_avg != null || r.distance_total_km != null)
                                            ? formatDistanceKm(r.km_prom ?? r.distance_km_avg ?? (r.distance_total_km / subTrips), subTrips)
                                            : '—'
                                          return (
                                            <tr key={i}>
                                              {drillBy === 'lob' && (
                                                <td className="pr-4 py-1 text-gray-900">{r.lob_group ?? '—'}</td>
                                              )}
                                              {drillBy === 'park' && (
                                                <>
                                                  <td className="pr-4 py-1 text-gray-700">{r.city ?? '—'}</td>
                                                  <td className="pr-4 py-1 text-gray-900">{r.park_name_resolved ?? r.park_name ?? r.park_id ?? '—'}</td>
                                                  <td className="pr-4 py-1">
                                                    {r.park_bucket && r.park_bucket !== 'OK' ? (
                                                      <span className="inline-flex px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800" title="Park sin ID o no catalogado">
                                                        {r.park_bucket}
                                                      </span>
                                                    ) : (
                                                      '—'
                                                    )}
                                                  </td>
                                                </>
                                              )}
                                              <td className="text-right py-1">{formatNumber(r.trips)}</td>
                                              <td className="text-right py-1">{subTrips ? formatMargin(subMarginTotal, subTrips) : '—'}</td>
                                              <td className="text-right py-1">{subMargin}</td>
                                              <td className="text-right py-1">{subKm}</td>
                                              {segment === 'Todos' && (
                                                <td className="text-right py-1">{formatNumber(r.b2b_trips)}</td>
                                              )}
                                            </tr>
                                          )
                                        })}
                                      </tbody>
                                    </table>
                                  )}
                                  {sr.data && sr.data.length === 0 && (
                                    <p className="text-sm text-gray-500">Sin datos para este periodo.</p>
                                  )}
                                </td>
                              </tr>
                            )}
                          </Fragment>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
                )}
              </section>
            )
          })}
        </div>
      )}

      <p className="mt-4 text-xs text-gray-500">
        Doble click en una fila para desplegar desglose por {drillBy === 'lob' ? 'LOB' : 'Park'}.
        Orden: más reciente → más antiguo; subfilas por viajes descendente.
      </p>
    </div>
  )
}
