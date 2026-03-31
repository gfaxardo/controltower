/**
 * Business Slice Omniview — comparativo current/previous (REAL), jerarquía operativa.
 * No sustituye BusinessSliceView; consume GET /ops/business-slice/omniview.
 */
import { useCallback, useEffect, useState, useMemo } from 'react'
import {
  getBusinessSliceFilters,
  getBusinessSliceOmniview
} from '../services/api.js'
import BusinessSliceOmniviewKpis from './BusinessSliceOmniviewKpis.jsx'
import BusinessSliceOmniviewTable from './BusinessSliceOmniviewTable.jsx'
import BusinessSliceOmniviewSidebar from './BusinessSliceOmniviewSidebar.jsx'

function formatApiError (e) {
  const d = e?.response?.data?.detail
  if (Array.isArray(d)) {
    return d.map((x) => x.msg || JSON.stringify(x)).join('; ')
  }
  if (d != null) return String(d)
  return e?.message || 'Error al cargar Omniview'
}

function todayMonthValue () {
  const t = new Date()
  const y = t.getFullYear()
  const m = String(t.getMonth() + 1).padStart(2, '0')
  return `${y}-${m}`
}

function todayDateValue () {
  const t = new Date()
  const y = t.getFullYear()
  const m = String(t.getMonth() + 1).padStart(2, '0')
  const d = String(t.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function yesterdayDateValue () {
  const t = new Date()
  t.setDate(t.getDate() - 1)
  const y = t.getFullYear()
  const m = String(t.getMonth() + 1).padStart(2, '0')
  const d = String(t.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

const RULE_LABELS = {
  MoM: 'Mes vs mes anterior (MoM)',
  WoW: 'Semana ISO vs semana anterior (WoW)',
  DoW_minus_7: 'Día vs mismo día de la semana anterior (−7 días)'
}

export default function BusinessSliceOmniview () {
  const [filtersMeta, setFiltersMeta] = useState(null)
  const [granularity, setGranularity] = useState('monthly')
  const [periodMonth, setPeriodMonth] = useState(todayMonthValue)
  const [periodWeekDate, setPeriodWeekDate] = useState(todayDateValue)
  const [periodDay, setPeriodDay] = useState(yesterdayDateValue)
  const [country, setCountry] = useState('')
  const [city, setCity] = useState('')
  const [businessSlice, setBusinessSlice] = useState('')
  const [includeSubfleets, setIncludeSubfleets] = useState(false)
  const [expandedView, setExpandedView] = useState(false)
  const [expandedPaths, setExpandedPaths] = useState({})
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)
  const [sidebarRow, setSidebarRow] = useState(null)

  const periodParam = useMemo(() => {
    if (granularity === 'monthly') {
      const [y, m] = periodMonth.split('-')
      return `${y}-${m}-01`
    }
    if (granularity === 'weekly') return periodWeekDate
    return periodDay
  }, [granularity, periodMonth, periodWeekDate, periodDay])

  const needsCountry = granularity === 'weekly' || granularity === 'daily'
  const countryOk = Boolean(country && String(country).trim())

  const loadFilters = useCallback(async () => {
    try {
      const f = await getBusinessSliceFilters()
      setFiltersMeta(f)
    } catch {
      setFiltersMeta(null)
    }
  }, [])

  const loadOmniview = useCallback(async () => {
    if (needsCountry && !countryOk) {
      setData(null)
      setErr(null)
      return
    }
    setLoading(true)
    setErr(null)
    try {
      const params = {
        granularity,
        period: periodParam,
        include_subfleets: includeSubfleets,
        limit_rows: 2000
      }
      if (countryOk) params.country = String(country).trim()
      if (city?.trim()) params.city = city.trim()
      if (businessSlice?.trim()) params.business_slice = businessSlice.trim()

      const res = await getBusinessSliceOmniview(params)
      setData(res)
    } catch (e) {
      setErr(formatApiError(e))
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [
    granularity,
    periodParam,
    countryOk,
    country,
    city,
    businessSlice,
    includeSubfleets,
    needsCountry
  ])

  useEffect(() => {
    loadFilters().catch(() => {})
  }, [loadFilters])

  useEffect(() => {
    loadOmniview()
  }, [loadOmniview])

  const togglePath = useCallback((path) => {
    setExpandedPaths((prev) => ({ ...prev, [path]: !prev[path] }))
  }, [])

  const countries = filtersMeta?.countries || []
  const cities = filtersMeta?.cities || []
  const slices = filtersMeta?.business_slices || []

  const meta = data?.meta || {}
  const unitsMeta = meta.units || {}
  const comparisonRule = data?.comparison_rule
  const ruleLabel = RULE_LABELS[comparisonRule] || comparisonRule || '—'

  const blockedByCountry = needsCountry && !countryOk

  return (
    <div className="space-y-4">
      {/* —— Controles —— */}
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm space-y-3">
        <div className="flex flex-wrap gap-3 items-end">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Granularidad</label>
            <select
              value={granularity}
              onChange={(e) => setGranularity(e.target.value)}
              className="border border-slate-300 rounded-md px-2 py-1.5 text-sm"
            >
              <option value="monthly">Mensual</option>
              <option value="weekly">Semanal</option>
              <option value="daily">Diario</option>
            </select>
          </div>
          {granularity === 'monthly' && (
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Mes</label>
              <input
                type="month"
                value={periodMonth}
                onChange={(e) => setPeriodMonth(e.target.value)}
                className="border border-slate-300 rounded-md px-2 py-1.5 text-sm"
              />
            </div>
          )}
          {granularity === 'weekly' && (
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Semana (cualquier día)</label>
              <input
                type="date"
                value={periodWeekDate}
                onChange={(e) => setPeriodWeekDate(e.target.value)}
                className="border border-slate-300 rounded-md px-2 py-1.5 text-sm"
              />
            </div>
          )}
          {granularity === 'daily' && (
            <div>
              <label className="block text-xs font-medium text-slate-500 mb-1">Día</label>
              <input
                type="date"
                value={periodDay}
                onChange={(e) => setPeriodDay(e.target.value)}
                className="border border-slate-300 rounded-md px-2 py-1.5 text-sm"
              />
            </div>
          )}
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">País</label>
            <select
              value={country}
              onChange={(e) => {
                setCountry(e.target.value)
                setCity('')
              }}
              className="border border-slate-300 rounded-md px-2 py-1.5 text-sm min-w-[140px]"
            >
              <option value="">{needsCountry ? '— requerido —' : 'Todos'}</option>
              {countries.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Ciudad</label>
            <select
              value={city}
              onChange={(e) => setCity(e.target.value)}
              className="border border-slate-300 rounded-md px-2 py-1.5 text-sm min-w-[140px]"
            >
              <option value="">Todas</option>
              {cities.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Tajada</label>
            <select
              value={businessSlice}
              onChange={(e) => setBusinessSlice(e.target.value)}
              className="border border-slate-300 rounded-md px-2 py-1.5 text-sm min-w-[160px]"
            >
              <option value="">Todas</option>
              {slices.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer pt-5">
            <input
              type="checkbox"
              checked={includeSubfleets}
              onChange={(e) => setIncludeSubfleets(e.target.checked)}
            />
            Incluir subflotas
          </label>
          <div className="flex items-center gap-2 pt-5">
            <span className="text-xs text-slate-500">Vista</span>
            <button
              type="button"
              onClick={() => setExpandedView(false)}
              className={`px-2 py-1 rounded text-xs font-medium ${!expandedView ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-600'}`}
            >
              Core
            </button>
            <button
              type="button"
              onClick={() => setExpandedView(true)}
              className={`px-2 py-1 rounded text-xs font-medium ${expandedView ? 'bg-slate-800 text-white' : 'bg-slate-100 text-slate-600'}`}
            >
              Expandida
            </button>
          </div>
          <button
            type="button"
            onClick={() => loadOmniview()}
            disabled={loading || blockedByCountry}
            className="ml-auto px-3 py-1.5 rounded-md bg-amber-600 text-white text-sm font-medium hover:bg-amber-700 disabled:opacity-50"
          >
            Actualizar
          </button>
        </div>
      </div>

      {/* —— Bloqueo país —— */}
      {blockedByCountry && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-8 text-center">
          <p className="text-amber-900 font-medium text-lg">Selecciona un país para habilitar el análisis operativo</p>
          <p className="text-sm text-amber-800 mt-2 max-w-lg mx-auto">
            Las vistas semanal y diaria están acotadas por rendimiento: el backend exige país.
            No se enviará la consulta hasta elegir uno.
          </p>
        </div>
      )}

      {/* —— Contexto / alertas —— */}
      {!blockedByCountry && (
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-sm space-y-2">
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-slate-700">
            <span>
              <span className="font-semibold text-slate-600">Comparativa:</span>{' '}
              {ruleLabel}
            </span>
            <span>
              <span className="font-semibold text-slate-600">Actual:</span>{' '}
              {data?.current_period_start ?? periodParam}
              {data?.current_period_end_exclusive && (
                <> → {data.current_period_end_exclusive}</>
              )}
            </span>
            <span>
              <span className="font-semibold text-slate-600">Anterior:</span>{' '}
              {data?.previous_period_start ?? '—'}
            </span>
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            {data?.is_current_partial && (
              <span className="inline-flex items-center rounded-full bg-amber-100 text-amber-900 px-2 py-0.5 text-xs font-medium">
                Periodo actual parcial
              </span>
            )}
            {data?.is_previous_partial && (
              <span className="inline-flex items-center rounded-full bg-amber-100 text-amber-900 px-2 py-0.5 text-xs font-medium">
                Periodo anterior parcial
              </span>
            )}
            {data?.mixed_currency_warning && (
              <span className="inline-flex items-center rounded-full bg-amber-200 text-amber-950 px-2 py-0.5 text-xs font-medium">
                Posible mezcla de monedas (mensual sin país)
              </span>
            )}
            <span className="inline-flex items-center rounded-full bg-slate-200 text-slate-800 px-2 py-0.5 text-xs">
              Cobertura por tajada: no disponible en API — ver{' '}
              <code className="mx-1 text-xs">/business-slice/coverage</code> ciudad×mes
            </span>
          </div>
          {data?.warnings?.length > 0 && (
            <ul className="list-disc pl-5 text-amber-900 text-sm">
              {data.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          )}
          <div className="text-xs text-slate-500 pt-1 border-t border-slate-200">
            <span className="font-medium text-slate-600">Fuentes:</span> detalle{' '}
            <code className="text-xs">{meta.detail_source || '—'}</code>
            {' · '}totales/subtotales{' '}
            <code className="text-xs">{meta.totals_source || '—'}</code>
          </div>
        </div>
      )}

      {/* —— Error / loading —— */}
      {err && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-red-800 text-sm">
          {err}
        </div>
      )}
      {loading && !blockedByCountry && (
        <div className="text-slate-500 text-sm py-4">Cargando Omniview…</div>
      )}

      {/* —— KPIs —— */}
      {!blockedByCountry && !loading && data?.totals && (
        <BusinessSliceOmniviewKpis totals={data.totals} unitsMeta={unitsMeta} />
      )}

      {/* —— Tabla —— */}
      {!blockedByCountry && !loading && data && (
        <BusinessSliceOmniviewTable
          rows={data.rows || []}
          subtotals={data.subtotals || []}
          expanded={expandedPaths}
          toggle={togglePath}
          unitsMeta={unitsMeta}
          expandedView={expandedView}
          onLeafClick={(row) => setSidebarRow(row)}
        />
      )}

      {!blockedByCountry && !loading && data && (!data.rows || data.rows.length === 0) && (
        <p className="text-slate-500 text-sm">Sin filas en la respuesta (prueba otros filtros o periodo).</p>
      )}

      <BusinessSliceOmniviewSidebar
        open={Boolean(sidebarRow)}
        onClose={() => setSidebarRow(null)}
        row={sidebarRow}
        detailMeta={meta}
        warnings={data?.warnings}
      />
    </div>
  )
}
