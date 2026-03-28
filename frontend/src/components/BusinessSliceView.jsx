/**
 * Business Slice — vista ejecutiva REAL (tajadas / flota / subflota).
 * Métricas desde ops.real_business_slice_month_fact (vista compat mv_real_business_slice_monthly); auditoría unmatched/conflicts.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  getBusinessSliceFilters,
  getBusinessSliceMonthly,
  getBusinessSliceCoverage,
  getBusinessSliceUnmatched,
  getBusinessSliceConflicts
} from '../services/api.js'

const METRICS = [
  { key: 'trips_completed', label: 'Viajes completados' },
  { key: 'trips_cancelled', label: 'Cancelaciones' },
  { key: 'active_drivers', label: 'Conductores activos' },
  { key: 'avg_ticket', label: 'Ticket medio' },
  { key: 'commission_pct', label: 'Comisión % (take rate)' },
  { key: 'trips_per_driver', label: 'Viajes / conductor' },
  { key: 'revenue_yego_net', label: 'Revenue YEGO (comisión canónica)' },
  { key: 'precio_km', label: 'Precio / km' },
  { key: 'tiempo_km', label: 'Min / km' },
  { key: 'completados_por_hora', label: 'Completados / hora' },
  { key: 'cancelados_por_hora', label: 'Cancelados / hora' }
]

function fmt (v, metricKey) {
  if (v == null || Number.isNaN(v)) return '—'
  if (metricKey === 'commission_pct' || metricKey.includes('pct')) {
    return `${(Number(v) * 100).toFixed(2)}%`
  }
  if (metricKey === 'revenue_yego_net' || metricKey === 'avg_ticket' || metricKey === 'precio_km') {
    return Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })
  }
  if (metricKey === 'tiempo_km' || metricKey === 'trips_per_driver' || metricKey.includes('por_hora')) {
    return Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })
  }
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })
}

export default function BusinessSliceView () {
  const [filtersMeta, setFiltersMeta] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [rows, setRows] = useState([])
  const [country, setCountry] = useState('')
  const [city, setCity] = useState('')
  const [businessSlice, setBusinessSlice] = useState('')
  const [fleet, setFleet] = useState('')
  const [subfleet, setSubfleet] = useState('')
  const [year, setYear] = useState(new Date().getFullYear())
  const [month, setMonth] = useState('')
  const [metricKey, setMetricKey] = useState('trips_completed')
  const [showSubfleets, setShowSubfleets] = useState(true)
  const [auditTab, setAuditTab] = useState('coverage')
  const [coverage, setCoverage] = useState(null)
  const [unmatched, setUnmatched] = useState([])
  const [conflicts, setConflicts] = useState([])

  const loadFilters = useCallback(async () => {
    const f = await getBusinessSliceFilters()
    setFiltersMeta(f)
  }, [])

  const loadMonthly = useCallback(async () => {
    setLoading(true)
    setErr(null)
    try {
      const params = {}
      if (country) params.country = country
      if (city) params.city = city
      if (businessSlice) params.business_slice = businessSlice
      if (fleet) params.fleet = fleet
      if (subfleet) params.subfleet = subfleet
      if (year) params.year = year
      if (month) params.month = Number(month)
      const res = await getBusinessSliceMonthly(params)
      let data = res.data || []
      if (!showSubfleets) {
        data = data.filter((r) => !r.is_subfleet)
      }
      setRows(data)
    } catch (e) {
      setErr(e?.response?.data?.detail || e.message || 'Error')
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [country, city, businessSlice, fleet, subfleet, year, month, showSubfleets])

  const loadAudit = useCallback(async () => {
    try {
      if (auditTab === 'coverage') {
        const c = await getBusinessSliceCoverage({ year: year || undefined })
        setCoverage(c)
      } else if (auditTab === 'unmatched') {
        const u = await getBusinessSliceUnmatched({
          country: country || undefined,
          city: city || undefined,
          limit: 50
        })
        setUnmatched(u.data || [])
      } else if (auditTab === 'conflicts') {
        const cf = await getBusinessSliceConflicts({
          country: country || undefined,
          city: city || undefined,
          limit: 50
        })
        setConflicts(cf.data || [])
      }
    } catch {
      /* silencioso en panel secundario */
    }
  }, [auditTab, country, city, year])

  useEffect(() => {
    loadFilters().catch((e) => setErr(e.message))
  }, [loadFilters])

  useEffect(() => {
    loadMonthly()
  }, [loadMonthly])

  useEffect(() => {
    loadAudit()
  }, [loadAudit])

  const cityOptions = useMemo(() => {
    const all = filtersMeta?.cities || []
    if (!country) return all
    const fromRows = [...new Set(
      rows.filter((r) => r.country === country).map((r) => r.city).filter(Boolean)
    )].sort()
    return fromRows.length ? fromRows : all
  }, [filtersMeta, country, rows])

  const kpiTotal = useMemo(() => {
    if (!rows.length) return null
    let sum = 0
    let n = 0
    for (const r of rows) {
      const v = r[metricKey]
      if (v != null && !Number.isNaN(Number(v))) {
        sum += Number(v)
        n += 1
      }
    }
    if (metricKey === 'avg_ticket' || metricKey === 'commission_pct' || metricKey === 'trips_per_driver' || metricKey === 'precio_km' || metricKey === 'tiempo_km' || metricKey.includes('por_hora')) {
      return n ? sum / n : null
    }
    return sum
  }, [rows, metricKey])

  const grouped = useMemo(() => {
    const m = new Map()
    for (const r of rows) {
      const ck = `${r.country || '—'}::${r.city || '—'}`
      if (!m.has(ck)) m.set(ck, [])
      m.get(ck).push(r)
    }
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  }, [rows])

  const countries = filtersMeta?.countries || []

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <p className="text-sm text-slate-600 mb-3">
          Capa <strong>Business Slice</strong>: mismos viajes REAL que el resto del Control Tower, clasificados por reglas de negocio (park, tipo de servicio, works_terms). No mezcla Plan.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <label className="block text-xs font-medium text-slate-500">País
            <select
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              value={country}
              onChange={(e) => { setCountry(e.target.value); setCity('') }}
            >
              <option value="">Todos</option>
              {countries.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </label>
          <label className="block text-xs font-medium text-slate-500">Ciudad
            <select
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              value={city}
              onChange={(e) => setCity(e.target.value)}
            >
              <option value="">Todas</option>
              {cityOptions.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </label>
          <label className="block text-xs font-medium text-slate-500">Año
            <input
              type="number"
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
            />
          </label>
          <label className="block text-xs font-medium text-slate-500">Mes
            <select
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
            >
              <option value="">Todos</option>
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </label>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-3">
          <label className="block text-xs font-medium text-slate-500">Tajada
            <select
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              value={businessSlice}
              onChange={(e) => setBusinessSlice(e.target.value)}
            >
              <option value="">Todas</option>
              {(filtersMeta?.business_slices || []).map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="block text-xs font-medium text-slate-500">Flota (display)
            <select
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              value={fleet}
              onChange={(e) => setFleet(e.target.value)}
            >
              <option value="">Todas</option>
              {(filtersMeta?.fleets || []).map((f) => (
                <option key={f} value={f}>{f}</option>
              ))}
            </select>
          </label>
          <label className="block text-xs font-medium text-slate-500">Subflota
            <select
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              value={subfleet}
              onChange={(e) => setSubfleet(e.target.value)}
            >
              <option value="">Todas</option>
              {(filtersMeta?.subfleets || []).filter(Boolean).map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
          <label className="block text-xs font-medium text-slate-500">Métrica en matriz
            <select
              className="mt-1 w-full rounded border border-slate-300 px-2 py-1.5 text-sm"
              value={metricKey}
              onChange={(e) => setMetricKey(e.target.value)}
            >
              {METRICS.map((m) => (
                <option key={m.key} value={m.key}>{m.label}</option>
              ))}
            </select>
          </label>
        </div>
        <label className="inline-flex items-center gap-2 mt-3 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={showSubfleets}
            onChange={(e) => setShowSubfleets(e.target.checked)}
          />
          Ver filas de subflota
        </label>
      </div>

      {err && (
        <div className="rounded-md bg-red-50 text-red-800 text-sm px-3 py-2">{String(err)}</div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="rounded-lg bg-slate-900 text-white p-4">
          <div className="text-xs uppercase tracking-wide text-slate-400">Selección</div>
          <div className="text-2xl font-semibold mt-1">
            {fmt(kpiTotal, metricKey)}
          </div>
          <div className="text-sm text-slate-300 mt-1">
            {METRICS.find((m) => m.key === metricKey)?.label}
          </div>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-4 md:col-span-2">
          <div className="text-xs font-medium text-slate-500 mb-1">Lectura ejecutiva</div>
          <p className="text-sm text-slate-600">
            Agrupación por país y ciudad (orden tipo hoja de ruta). La celda muestra la métrica elegida por mes en cada fila.
            {!country && metricKey === 'revenue_yego_net' && (
              <span className="block mt-2 text-amber-700">
                Atención: mezclar países puede sumar monedas distintas; filtre por país para revenue.
              </span>
            )}
          </p>
        </div>
      </div>

      <div className="rounded-lg border border-slate-200 bg-white overflow-hidden shadow-sm">
        <div className="px-4 py-2 border-b border-slate-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-800">Matriz mensual</h3>
          {loading && <span className="text-xs text-slate-500">Cargando…</span>}
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-left text-xs text-slate-600">
                <th className="px-3 py-2">País / Ciudad</th>
                <th className="px-3 py-2">Tajada</th>
                <th className="px-3 py-2">Flota</th>
                <th className="px-3 py-2">Subflota</th>
                <th className="px-3 py-2">Mes</th>
                <th className="px-3 py-2 text-right">Valor</th>
              </tr>
            </thead>
            <tbody>
              {grouped.map(([ck, list]) => {
                const [co, ci] = ck.split('::')
                return (
                  <FragmentBlock key={ck} country={co} city={ci} list={list} metricKey={metricKey} />
                )
              })}
              {!rows.length && !loading && (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-slate-500">
                    Sin filas. ¿Importó reglas y refrescó la MV?{' '}
                    <code className="text-xs bg-slate-100 px-1 rounded">python -m scripts.import_business_slice_mapping_from_xlsx --replace</code>
                    {' '}y{' '}
                    <code className="text-xs bg-slate-100 px-1 rounded">python -m scripts.refresh_business_slice_mvs</code>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="rounded-lg border border-amber-200 bg-amber-50/40 p-4">
        <h3 className="text-sm font-semibold text-amber-900 mb-2">Auditoría (sin ocultar problemas)</h3>
        <div className="flex flex-wrap gap-2 mb-3">
          {['coverage', 'unmatched', 'conflicts'].map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setAuditTab(t)}
              className={`px-3 py-1 rounded text-sm ${
                auditTab === t ? 'bg-amber-600 text-white' : 'bg-white border border-amber-300 text-amber-900'
              }`}
            >
              {t === 'coverage' && 'Cobertura'}
              {t === 'unmatched' && 'Unmatched'}
              {t === 'conflicts' && 'Conflictos'}
            </button>
          ))}
        </div>
        {auditTab === 'coverage' && coverage && (
          <div className="text-sm text-slate-700 space-y-2">
            <div>
              <span className="font-medium">Resolución (viajes con fecha):</span>{' '}
              {JSON.stringify(coverage.resolution_counts || {})}
            </div>
            <div className="max-h-48 overflow-auto border border-amber-100 rounded bg-white">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-slate-500">
                    <th className="p-2">Mes</th>
                    <th className="p-2">Ciudad</th>
                    <th className="p-2">Cobertura %</th>
                  </tr>
                </thead>
                <tbody>
                  {(coverage.by_city_month || []).slice(0, 40).map((r, i) => (
                    <tr key={i} className="border-t border-slate-100">
                      <td className="p-2">{r.month}</td>
                      <td className="p-2">{r.city}</td>
                      <td className="p-2">{r.coverage_pct}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
        {auditTab === 'unmatched' && (
          <div className="text-xs max-h-56 overflow-auto bg-white rounded border border-amber-100 p-2">
            <pre className="whitespace-pre-wrap">{JSON.stringify(unmatched.slice(0, 12), null, 2)}</pre>
          </div>
        )}
        {auditTab === 'conflicts' && (
          <div className="text-xs max-h-56 overflow-auto bg-white rounded border border-amber-100 p-2">
            <pre className="whitespace-pre-wrap">{JSON.stringify(conflicts.slice(0, 8), null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  )
}

function FragmentBlock ({ country, city, list, metricKey }) {
  return (
    <>
      <tr className="bg-slate-100/80">
        <td colSpan={6} className="px-3 py-1.5 text-xs font-semibold text-slate-700">
          {country} — {city}
        </td>
      </tr>
      {list
        .sort((a, b) => (a.business_slice_name || '').localeCompare(b.business_slice_name || ''))
        .map((r, idx) => (
          <tr key={`${r.month}-${r.business_slice_name}-${r.fleet_display_name}-${idx}`} className="border-t border-slate-100 hover:bg-slate-50/80">
            <td className="px-3 py-1.5 text-slate-500"> </td>
            <td className="px-3 py-1.5">{r.business_slice_name}</td>
            <td className="px-3 py-1.5">{r.fleet_display_name}</td>
            <td className="px-3 py-1.5">{r.subfleet_name || (r.is_subfleet ? '—' : '')}</td>
            <td className="px-3 py-1.5 text-slate-600">{r.month}</td>
            <td className="px-3 py-1.5 text-right font-medium tabular-nums">
              {fmt(r[metricKey], metricKey)}
            </td>
          </tr>
        ))}
    </>
  )
}
