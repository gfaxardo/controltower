/**
 * Vista aditiva: Plan vs Real (Control Loop / proyección agregada).
 * No usa Omniview Matrix ni sus componentes.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  getControlLoopPlanVersions,
  getControlLoopPlanVsReal,
  uploadControlLoopProjection,
} from '../services/api.js'

function signalColor (pct, delta) {
  if (pct == null && delta == null) return 'bg-slate-100 text-slate-500'
  const p = pct != null ? pct : 0
  if (p >= 0) return 'bg-emerald-100 text-emerald-800'
  if (p > -10) return 'bg-amber-100 text-amber-900'
  return 'bg-rose-100 text-rose-900'
}

function signalGapPct (gapPct) {
  if (gapPct == null) return 'bg-slate-100 text-slate-500'
  const g = Number(gapPct)
  if (g <= 0) return 'bg-emerald-100 text-emerald-800'
  if (g <= 10) return 'bg-amber-100 text-amber-900'
  return 'bg-rose-100 text-rose-900'
}

function fmt (v) {
  return v != null ? Number(v).toLocaleString() : '—'
}

function fmtPct (v) {
  return v != null ? `${Number(v).toFixed(1)}%` : '—'
}

export default function ControlLoopPlanVsRealView () {
  const [planVersions, setPlanVersions] = useState([])
  const [planVersion, setPlanVersion] = useState('')
  const [country, setCountry] = useState('')
  const [city, setCity] = useState('')
  const [linea, setLinea] = useState('')
  const [periodFrom, setPeriodFrom] = useState('2025-01')
  const [periodTo, setPeriodTo] = useState('2026-12')
  const [kpi, setKpi] = useState('trips')
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [versionsLoading, setVersionsLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [uploadMsg, setUploadMsg] = useState(null)
  const [uploadErr, setUploadErr] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [queried, setQueried] = useState(false)
  const fileInputRef = useRef(null)

  const loadVersions = async () => {
    setVersionsLoading(true)
    try {
      const res = await getControlLoopPlanVersions()
      const v = res.plan_versions || []
      setPlanVersions(v)
      if (v.length && !planVersion) setPlanVersion(v[0])
    } catch {
      setPlanVersions([])
    } finally {
      setVersionsLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      await loadVersions()
      if (cancelled) return
    })()
    return () => { cancelled = true }
  }, [])

  const fetchData = async () => {
    if (!planVersion) {
      setErr('Seleccione una plan_version antes de aplicar filtros.')
      return
    }
    setLoading(true)
    setErr(null)
    setQueried(true)
    try {
      const res = await getControlLoopPlanVsReal({
        plan_version: planVersion,
        country: country || undefined,
        city: city || undefined,
        linea_negocio: linea || undefined,
        period_from: periodFrom || undefined,
        period_to: periodTo || undefined,
      })
      setRows(res.data || [])
    } catch (e) {
      setErr(e.response?.data?.detail || e.message)
      setRows([])
    } finally {
      setLoading(false)
    }
  }

  const onFileSelect = (e) => {
    const file = e.target.files?.[0]
    setSelectedFile(file || null)
    setUploadMsg(null)
    setUploadErr(false)
  }

  const onUpload = async () => {
    if (!selectedFile) return
    setUploading(true)
    setUploadMsg(null)
    setUploadErr(false)
    try {
      const res = await uploadControlLoopProjection(selectedFile, null)
      setUploadMsg(
        `Carga exitosa: ${res.rows_valid_inserted} filas válidas, ${res.rows_invalid} rechazadas. Versión: ${res.plan_version}`
      )
      setUploadErr(false)
      setPlanVersion(res.plan_version)
      setSelectedFile(null)
      if (fileInputRef.current) fileInputRef.current.value = ''
      await loadVersions()
    } catch (ex) {
      setUploadMsg(ex.response?.data?.detail || ex.message)
      setUploadErr(true)
    } finally {
      setUploading(false)
    }
  }

  const displayRows = useMemo(() => {
    return rows.map((r) => {
      let planV, realV, delta, pct, gap, gapPct
      if (kpi === 'trips') {
        planV = r.projected_trips; realV = r.real_trips; delta = r.delta_trips
        pct = r.delta_trips_pct; gap = r.gap_trips; gapPct = r.gap_trips_pct
      } else if (kpi === 'revenue') {
        planV = r.projected_revenue; realV = r.real_revenue; delta = r.delta_revenue
        pct = r.delta_revenue_pct; gap = r.gap_revenue; gapPct = r.gap_revenue_pct
      } else {
        planV = r.projected_active_drivers; realV = r.real_active_drivers; delta = r.delta_active_drivers
        pct = r.delta_active_drivers_pct; gap = r.gap_active_drivers; gapPct = r.gap_active_drivers_pct
      }
      return { ...r, _planV: planV, _realV: realV, _delta: delta, _pct: pct, _gap: gap, _gapPct: gapPct }
    })
  }, [rows, kpi])

  const currencyNote = useMemo(() => {
    const countries = new Set(rows.map((r) => (r.country || '').toLowerCase()))
    if (countries.size > 1) return 'Varios países: no sumar revenue entre filas (monedas distintas).'
    return null
  }, [rows])

  const emptyMessage = useMemo(() => {
    if (loading) return null
    if (!queried) {
      if (!planVersions.length && !versionsLoading) {
        return 'No hay versiones de plan cargadas. Suba una plantilla de proyección primero.'
      }
      return 'Seleccione una versión de plan y pulse "Aplicar filtros" para ver la comparación.'
    }
    if (!rows.length) {
      const parts = []
      if (planVersion) parts.push(`plan_version="${planVersion}"`)
      if (country) parts.push(`país="${country}"`)
      if (city) parts.push(`ciudad="${city}"`)
      if (linea) parts.push(`línea="${linea}"`)
      parts.push(`periodo: ${periodFrom || '—'} a ${periodTo || '—'}`)
      return `Sin datos para: ${parts.join(', ')}. Posibles causas: el plan no tiene filas para estos filtros, o no hay datos de real (fact table) para este rango.`
    }
    return null
  }, [queried, rows, loading, planVersion, country, city, linea, periodFrom, periodTo, planVersions, versionsLoading])

  return (
    <div className="space-y-4" aria-label="Control Loop Plan vs Real">
      <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm">
        <h2 className="text-lg font-semibold text-gray-800 mb-1">Control Loop — Plan vs Real</h2>
        <p className="text-sm text-gray-600 mb-4">
          Comparación de proyección (plan cargado) contra real materializado{' '}
          (<span className="font-mono text-xs">real_business_slice_month_fact</span>).
          Sin modificar la pantalla Omniview Matrix.
        </p>

        {/* ─── Filtros ─── */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
          <label className="block text-sm">
            <span className="text-gray-600">Plan version</span>
            <select
              value={planVersion}
              onChange={(e) => setPlanVersion(e.target.value)}
              className="mt-1 w-full border rounded-md px-2 py-1.5 text-sm"
              disabled={versionsLoading}
            >
              {versionsLoading && <option value="">Cargando…</option>}
              {!versionsLoading && !planVersions.length && <option value="">Sin versiones — suba una plantilla</option>}
              {!versionsLoading && planVersions.length > 0 && <option value="">Seleccionar…</option>}
              {planVersions.map((v) => (
                <option key={v} value={v}>{v}</option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">País</span>
            <select
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              className="mt-1 w-full border rounded-md px-2 py-1.5 text-sm"
            >
              <option value="">Todos</option>
              <option value="pe">Perú (pe)</option>
              <option value="co">Colombia (co)</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Ciudad</span>
            <input
              value={city}
              onChange={(e) => setCity(e.target.value)}
              className="mt-1 w-full border rounded-md px-2 py-1.5 text-sm"
              placeholder="lima, medellin…"
            />
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Línea (canónica / Excel)</span>
            <input
              value={linea}
              onChange={(e) => setLinea(e.target.value)}
              className="mt-1 w-full border rounded-md px-2 py-1.5 text-sm"
              placeholder="auto_taxi, pro…"
            />
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Desde (YYYY-MM)</span>
            <input
              type="month"
              value={periodFrom}
              onChange={(e) => setPeriodFrom(e.target.value)}
              className="mt-1 w-full border rounded-md px-2 py-1.5 text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="text-gray-600">Hasta (YYYY-MM)</span>
            <input
              type="month"
              value={periodTo}
              onChange={(e) => setPeriodTo(e.target.value)}
              className="mt-1 w-full border rounded-md px-2 py-1.5 text-sm"
            />
          </label>
        </div>

        {/* ─── KPI + Aplicar ─── */}
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <span className="text-sm text-gray-600">KPI</span>
          {['trips', 'revenue', 'drivers'].map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setKpi(k)}
              className={`px-3 py-1 rounded-full text-sm font-medium ${
                kpi === k ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700'
              }`}
            >
              {k === 'trips' ? 'Trips' : k === 'revenue' ? 'Revenue' : 'Drivers'}
            </button>
          ))}
          <button
            type="button"
            onClick={fetchData}
            disabled={loading || !planVersion}
            className="ml-auto px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium disabled:opacity-50"
          >
            {loading ? 'Cargando…' : 'Aplicar filtros'}
          </button>
        </div>

        {/* ─── Upload ─── */}
        <details className="border-t border-gray-100 pt-4 group">
          <summary className="text-sm font-medium text-gray-700 cursor-pointer select-none">
            Subir plantilla de proyección (.xlsx / .csv)
          </summary>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={onFileSelect}
              disabled={uploading}
              className="text-sm"
            />
            <button
              type="button"
              onClick={onUpload}
              disabled={uploading || !selectedFile}
              className="px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium disabled:opacity-50"
            >
              {uploading ? 'Procesando…' : 'Subir y procesar'}
            </button>
          </div>
          {uploadMsg && (
            <p className={`text-sm mt-2 ${uploadErr ? 'text-red-700' : 'text-green-700'}`}>{uploadMsg}</p>
          )}
          <p className="text-xs text-gray-500 mt-2">
            Excel con hojas TRIPS, REVENUE, DRIVERS (columnas: country, city, linea_negocio + meses YYYY-MM).
            Al procesar se creará una nueva plan_version y aparecerá en el selector.
          </p>
        </details>
      </div>

      {currencyNote && (
        <div className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
          {currencyNote}
        </div>
      )}

      {err && (
        <div className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-md px-3 py-2">{String(err)}</div>
      )}

      {/* ─── Tabla ─── */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-x-auto shadow-sm">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-left">
            <tr>
              <th className="px-3 py-2 font-medium text-gray-700">Mes</th>
              <th className="px-3 py-2 font-medium text-gray-700">País</th>
              <th className="px-3 py-2 font-medium text-gray-700">Ciudad</th>
              <th className="px-3 py-2 font-medium text-gray-700">Canónico</th>
              <th className="px-3 py-2 font-medium text-gray-700">Tajada (Matrix)</th>
              <th className="px-3 py-2 font-medium text-gray-700">Plan</th>
              <th className="px-3 py-2 font-medium text-gray-700">Real</th>
              <th className="px-3 py-2 font-medium text-gray-700">Δ (R−P)</th>
              <th className="px-3 py-2 font-medium text-gray-700">Δ %</th>
              <th className="px-3 py-2 font-medium text-gray-700">Gap (P−R)</th>
              <th className="px-3 py-2 font-medium text-gray-700">Gap %</th>
              <th className="px-3 py-2 font-medium text-gray-700">Estado</th>
              <th className="px-3 py-2 font-medium text-gray-700">Δ sem.</th>
              <th className="px-3 py-2 font-medium text-gray-700">Gap sem.</th>
            </tr>
          </thead>
          <tbody>
            {displayRows.map((r, i) => (
              <tr key={`${r.period}-${r.country}-${r.city}-${r.linea_negocio}-${i}`} className="border-t border-gray-100">
                <td className="px-3 py-2 whitespace-nowrap">{r.period}</td>
                <td className="px-3 py-2">{r.country}</td>
                <td className="px-3 py-2">{r.city}</td>
                <td className="px-3 py-2 font-mono text-xs">{r.linea_negocio}</td>
                <td className="px-3 py-2 text-xs max-w-[140px] truncate" title={r.business_slice_name || ''}>
                  {r.business_slice_name || '—'}
                </td>
                <td className="px-3 py-2">{fmt(r._planV)}</td>
                <td className="px-3 py-2">{fmt(r._realV)}</td>
                <td className="px-3 py-2">{fmt(r._delta)}</td>
                <td className="px-3 py-2">{fmtPct(r._pct)}</td>
                <td className="px-3 py-2">{fmt(r._gap)}</td>
                <td className="px-3 py-2">{fmtPct(r._gapPct)}</td>
                <td className="px-3 py-2 text-xs">{r.comparison_status}</td>
                <td className="px-3 py-2">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs ${signalColor(r._pct, r._delta)}`}>
                    {r._pct != null ? `${Number(r._pct).toFixed(0)}%` : 'n/a'}
                  </span>
                </td>
                <td className="px-3 py-2">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs ${signalGapPct(r._gapPct)}`}>
                    {r._gapPct != null ? `${Number(r._gapPct).toFixed(0)}%` : 'n/a'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {emptyMessage && !loading && (
          <p className="p-4 text-sm text-gray-500">{emptyMessage}</p>
        )}
        {loading && (
          <p className="p-4 text-sm text-blue-600 animate-pulse">Consultando Plan vs Real…</p>
        )}
      </div>
    </div>
  )
}
