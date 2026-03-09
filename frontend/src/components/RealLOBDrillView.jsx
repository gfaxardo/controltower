/**
 * RealLOBDrillView — Vista drill-down jerárquica (Fase 2C+).
 * Timeline mensual/semanal por país (CO, PE); doble click despliega por LOB o por Park.
 * FASE 2D: clave dimensional con buildDrillKey, reset al cambiar dim, AbortController + guard.
 */
import { useState, useEffect, useCallback, useRef, Fragment } from 'react'
import {
  getRealLobDrillPro,
  getRealLobDrillProChildren,
  getRealDrillSummary,
  getRealDrillByLob,
  getRealDrillByPark,
  getRealLobDrillParks,
  getRealLobComparativesWeekly,
  getRealLobComparativesMonthly,
  getPeriodSemantics
} from '../services/api'
import RealLOBDailyView from './RealLOBDailyView'
import { buildDimKey, buildDrillKey } from '../utils/dimKey'

const USE_DRILL_PRO = true

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
  const [subView, setSubView] = useState('drill') // 'drill' | 'daily'
  const [periodType, setPeriodType] = useState('monthly')
  const [drillBy, setDrillBy] = useState('lob') // 'lob' | 'park' | 'service_type'
  const [segment, setSegment] = useState('Todos')
  const [parkId, setParkId] = useState('') // '' = todos; si hay valor, timeline y desglose tipo_servicio filtrados por park
  const [parks, setParks] = useState([]) // lista para filtro Park (fuente: drill); siempre poblada, independiente del desglose
  const [countries, setCountries] = useState([]) // [{ country, coverage, kpis, rows }]
  const [meta, setMeta] = useState({ last_period_monthly: null, last_period_weekly: null })
  const [periodSemantics, setPeriodSemantics] = useState(null) // GET /ops/period-semantics (no depende del drill)
  const [lobCoverage, setLobCoverage] = useState(null) // { min_trip_date_loaded, max_trip_date_loaded, recent_days_config }
  const [comparative, setComparative] = useState(null) // WoW o MoM payload
  const [comparativeLoading, setComparativeLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(new Set())
  const [subrows, setSubrows] = useState({}) // key -> { loading, data, error }

  const abortControllerRef = useRef(null)
  const summaryAbortRef = useRef(null)
  const activeDimKeyRef = useRef('')

  const limitPeriods = periodType === 'monthly' ? 24 : 26

  const getDimObj = useCallback(() => ({
    drillBy,
    periodType,
    segment,
    parkId
  }), [drillBy, periodType, segment, parkId])

  // Parks para filtro de contexto: misma fuente que el drill (real_drill_dim_fact). No depende del tipo de desglose.
  useEffect(() => {
    getRealLobDrillParks()
      .then((res) => setParks(res.parks || []))
      .catch(() => setParks([]))
  }, [])

  // Semántica temporal: carga independiente del drill para mostrar siempre "última cerrada / actual abierta"
  useEffect(() => {
    getPeriodSemantics()
      .then((data) => setPeriodSemantics(data))
      .catch(() => setPeriodSemantics(null))
  }, [])

  const resetDrillState = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()
    setExpanded(new Set())
    setSubrows({})
  }, [])

  const loadSummary = useCallback(async () => {
    if (summaryAbortRef.current) summaryAbortRef.current.abort()
    const ac = new AbortController()
    summaryAbortRef.current = ac
    setLoading(true)
    setError(null)
    const t0 = Date.now()
    try {
      if (USE_DRILL_PRO) {
        const res = await getRealLobDrillPro({
          period: periodType === 'monthly' ? 'month' : 'week',
          desglose: drillBy === 'lob' ? 'LOB' : drillBy === 'park' ? 'PARK' : 'SERVICE_TYPE',
          segmento: segment === 'Todos' ? 'all' : segment.toLowerCase(),
          park_id: parkId && parkId.trim() ? parkId.trim() : undefined,
          signal: ac.signal
        })
        setCountries(res.countries || [])
        setMeta(res.meta || {})
        setLobCoverage(res.lob_coverage || null)
      } else {
        const summaryRes = await getRealDrillSummary({
          period_type: periodType,
          segment: segment === 'Todos' ? undefined : segment,
          limit_periods: limitPeriods
        })
        setCountries(summaryRes.countries || [])
        setMeta(summaryRes.meta || {})
        setLobCoverage(null)
      }
    } catch (e) {
      if (e?.name === 'CanceledError' || e?.name === 'AbortError' || ac.signal.aborted) return
      let msg = 'Error al cargar timeline'
      if (e?.response?.data?.detail) {
        msg = Array.isArray(e.response.data.detail)
          ? e.response.data.detail.map(d => d.msg || JSON.stringify(d)).join(' ')
          : String(e.response.data.detail)
      } else if (e?.code === 'ECONNABORTED') {
        msg = 'La solicitud tardó demasiado (timeout). El drill puede tardar hasta 5 min; si persiste, revisa el backend (p. ej. espacio en disco: docs/MIGRACION_064_DISKFULL_TROUBLESHOOTING.md).'
      } else if (e?.code === 'ECONNREFUSED' || e?.message?.includes('ECONNREFUSED')) {
        msg = 'No se pudo conectar al backend. Comprueba que uvicorn esté en marcha (puerto 8000).'
      } else if (e?.message) {
        msg = e.message
      }
      setError(msg)
      setCountries([])
    } finally {
      setLoading(false)
    }
  }, [periodType, segment, limitPeriods, drillBy, parkId])

  useEffect(() => {
    loadSummary()
  }, [loadSummary])

  // Cargar comparativo WoW o MoM cuando está en drill y cambia el tipo de periodo
  useEffect(() => {
    if (subView !== 'drill') return
    setComparativeLoading(true)
    const fetchComparative = periodType === 'weekly' ? getRealLobComparativesWeekly : getRealLobComparativesMonthly
    fetchComparative()
      .then((data) => { setComparative(data); setComparativeLoading(false) })
      .catch(() => { setComparative(null); setComparativeLoading(false) })
  }, [subView, periodType])

  const normalizePeriodStart = (periodStart) => {
    const s = String(periodStart).trim()
    if (periodType === 'monthly' && s.length === 7) return `${s}-01`
    return s
  }

  const subrowKey = useCallback((country, periodStart) => {
    const norm = normalizePeriodStart(periodStart)
    const dimObj = { ...getDimObj(), country: (country || '').trim() }
    return buildDrillKey(dimObj, norm)
  }, [getDimObj])

  const handleDrillByChange = useCallback((newDrillBy) => {
    if (newDrillBy === drillBy) return
    resetDrillState()
    setDrillBy(newDrillBy)
  }, [drillBy, resetDrillState])

  const handlePeriodTypeChange = useCallback((newPeriodType) => {
    if (newPeriodType === periodType) return
    resetDrillState()
    setPeriodType(newPeriodType)
  }, [periodType, resetDrillState])

  const toggleExpand = useCallback(async (country, periodStart) => {
    const key = subrowKey((country || '').trim(), periodStart)
    if (expanded.has(key)) {
      setExpanded((prev) => {
        const next = new Set(prev)
        next.delete(key)
        return next
      })
      return
    }
    setExpanded((prev) => new Set(prev).add(key))
    if (subrows[key]?.data) return
    if (!abortControllerRef.current) {
      abortControllerRef.current = new AbortController()
    }
    const signal = abortControllerRef.current.signal
    const dimKeyAtRequest = buildDimKey(getDimObj())
    activeDimKeyRef.current = dimKeyAtRequest
    setSubrows((prev) => ({ ...prev, [key]: { loading: true, data: null, error: null } }))
    try {
      if (USE_DRILL_PRO) {
        const res = await getRealLobDrillProChildren({
          country: (country || '').trim(),
          period: periodType === 'monthly' ? 'month' : 'week',
          period_start: normalizePeriodStart(periodStart),
          desglose: drillBy === 'lob' ? 'LOB' : drillBy === 'park' ? 'PARK' : 'SERVICE_TYPE',
          segmento: segment === 'Todos' ? 'all' : segment.toLowerCase(),
          park_id: parkId && parkId.trim() ? parkId.trim() : undefined,
          signal
        })
        if (activeDimKeyRef.current === buildDimKey(getDimObj())) {
          setSubrows((prev) => ({
            ...prev,
            [key]: { loading: false, data: res.data || [], error: null }
          }))
        }
      } else {
        const params = {
          period_type: periodType,
          country: (country || '').trim(),
          period_start: normalizePeriodStart(periodStart),
          segment: segment === 'Todos' ? undefined : segment
        }
        const fetcher = drillBy === 'lob' ? getRealDrillByLob : getRealDrillByPark
        const res = await fetcher(params)
        if (activeDimKeyRef.current === buildDimKey(getDimObj())) {
          setSubrows((prev) => ({
            ...prev,
            [key]: { loading: false, data: res.data || [], error: null }
          }))
        }
      }
    } catch (e) {
      if (e?.name === 'AbortError' || e?.code === 'ERR_CANCELED') return
      if (activeDimKeyRef.current === buildDimKey(getDimObj())) {
        let errMsg = e.message || 'Error al cargar desglose'
        if (e?.code === 'ECONNABORTED' || errMsg.toLowerCase().includes('timeout')) {
          errMsg = 'La consulta tardó demasiado. Prueba sin filtrar por park o otro periodo.'
        } else if (e?.response?.status === 500 && parkId) {
          errMsg = 'Error en el servidor al filtrar por park. Prueba sin park o más tarde.'
        }
        setSubrows((prev) => ({
          ...prev,
          [key]: { loading: false, data: null, error: errMsg }
        }))
      }
    }
  }, [expanded, subrows, periodType, drillBy, segment, parkId, subrowKey, getDimObj])

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

  // ─── Vista diaria: subtab visible al entrar a Real LOB ─────────────────
  if (subView === 'daily') {
    return (
      <div className="bg-white p-6 rounded-lg shadow-md">
        <div className="flex flex-wrap items-center gap-2 mb-4 border-b border-gray-200 pb-4">
          <h3 className="text-lg font-semibold text-gray-800">Real LOB</h3>
          <span className="w-px h-6 bg-gray-300" />
          <button
            type="button"
            onClick={() => setSubView('drill')}
            className={`px-3 py-1.5 rounded text-sm font-medium ${subView !== 'daily' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
          >
            Drill (semanal/mensual)
          </button>
          <button
            type="button"
            onClick={() => setSubView('daily')}
            className={`px-3 py-1.5 rounded text-sm font-medium ${subView === 'daily' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
          >
            Vista diaria
          </button>
        </div>
        <RealLOBDailyView />
      </div>
    )
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      {/* Fila 1: Título + subtabs Drill | Vista diaria (siempre visibles) */}
      <div className="flex flex-wrap items-center gap-2 mb-4 border-b border-gray-200 pb-4">
        <h3 className="text-lg font-semibold text-gray-800">Real LOB</h3>
        <span className="w-px h-6 bg-gray-300" />
        <button
          type="button"
          onClick={() => setSubView('drill')}
          className={`px-3 py-1.5 rounded text-sm font-medium ${subView === 'drill' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
        >
          Drill (semanal/mensual)
        </button>
        <button
          type="button"
          onClick={() => setSubView('daily')}
          className={`px-3 py-1.5 rounded text-sm font-medium ${subView === 'daily' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
        >
          Vista diaria
        </button>
      </div>
      <div className="flex flex-wrap justify-between items-center gap-4 mb-4">
        <span className="text-sm text-gray-600">Drill por país — Periodo:</span>
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-sm text-gray-500">Periodo:</span>
          <button
            type="button"
            onClick={() => handlePeriodTypeChange('monthly')}
            className={`px-3 py-1.5 rounded text-sm ${periodType === 'monthly' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            Mensual
          </button>
          <button
            type="button"
            onClick={() => handlePeriodTypeChange('weekly')}
            className={`px-3 py-1.5 rounded text-sm ${periodType === 'weekly' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            Semanal
          </button>
          <span className="w-px h-6 bg-gray-300" />
          <span className="text-sm text-gray-500">Desglose:</span>
          <button
            type="button"
            onClick={() => handleDrillByChange('lob')}
            className={`px-3 py-1.5 rounded text-sm ${drillBy === 'lob' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            LOB
          </button>
          <button
            type="button"
            onClick={() => handleDrillByChange('park')}
            className={`px-3 py-1.5 rounded text-sm ${drillBy === 'park' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            Park
          </button>
          <button
            type="button"
            onClick={() => handleDrillByChange('service_type')}
            className={`px-3 py-1.5 rounded text-sm ${drillBy === 'service_type' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            Tipo de servicio
          </button>
          <span className="w-px h-6 bg-gray-300" />
          <span className="text-sm text-gray-500">Park:</span>
          <select
            value={parkId}
            onChange={(e) => {
              const v = e.target.value
              resetDrillState()
              setParkId(v)
            }}
            className="border rounded px-2 py-1.5 text-sm min-w-[200px]"
            title="Filtro de contexto por park; el desglose por tipo de servicio respeta este filtro"
          >
            <option value="">Todos</option>
            {parks.map((p) => {
              const id = p.park_id ?? p.id ?? ''
              const name = p.park_name || p.park_id || p.id || '—'
              const city = p.city && String(p.city).trim() && String(p.city).toLowerCase() !== 'sin_city' ? p.city : null
              const label = city ? `${name} — ${city}` : name
              return (
                <option key={id} value={id}>
                  {label}
                </option>
              )
            })}
          </select>
          <span className="w-px h-6 bg-gray-300" />
          <span className="text-sm text-gray-500">Segmento:</span>
          <select
            value={segment}
            onChange={(e) => {
              const v = e.target.value
              resetDrillState()
              setSegment(v)
            }}
            className="border rounded px-2 py-1.5 text-sm"
          >
            {SEGMENT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Semántica temporal: siempre visible (fuente: GET /ops/period-semantics, no depende del drill) */}
      <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg text-slate-800 text-sm mb-4">
        <div className="font-semibold text-emerald-900 mb-2">Períodos (semántica cerrada / abierta)</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {periodSemantics ? (
            <>
              <div><strong>Última semana cerrada:</strong> <span className="font-mono">{periodSemantics.last_closed_week_label || '—'}</span></div>
              <div><strong>Semana actual (parcial):</strong> <span className="font-mono">{periodSemantics.current_open_week_label || '—'}</span></div>
              <div><strong>Último mes cerrado:</strong> <span className="font-mono">{periodSemantics.last_closed_month_label || '—'}</span></div>
              <div><strong>Mes actual (parcial):</strong> <span className="font-mono">{periodSemantics.current_open_month_label || '—'}</span></div>
            </>
          ) : (
            <span className="text-gray-500">Cargando semántica temporal…</span>
          )}
        </div>
      </div>
      {meta.hint && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded text-amber-800 text-sm mb-4">
          {meta.hint}
        </div>
      )}

      {lobCoverage && (lobCoverage.min_trip_date_loaded || lobCoverage.max_trip_date_loaded) && (
        <div className="p-3 bg-slate-50 border border-slate-200 rounded text-slate-700 text-sm mb-4">
          <span className="font-medium">Cobertura actual:</span>{' '}
          {lobCoverage.min_trip_date_loaded && lobCoverage.max_trip_date_loaded
            ? `${lobCoverage.min_trip_date_loaded} — ${lobCoverage.max_trip_date_loaded}`
            : lobCoverage.max_trip_date_loaded
              ? `Último día con data: ${lobCoverage.max_trip_date_loaded}`
              : `Desde: ${lobCoverage.min_trip_date_loaded}`}
          {lobCoverage.recent_days_config != null && (
            <span className="ml-2 text-slate-500">(ventana: {lobCoverage.recent_days_config} días)</span>
          )}
        </div>
      )}

      {/* Comparativo WoW / MoM: siempre visible (cargando, error, sin datos o datos) */}
      <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <div className="text-sm font-semibold text-blue-900 mb-2">
          {periodType === 'weekly' ? 'Comparativo WoW (última semana cerrada vs anterior)' : 'Comparativo MoM (último mes cerrado vs anterior)'}
        </div>
        {comparativeLoading && !comparative && (
          <p className="text-sm text-blue-700">Cargando comparativo…</p>
        )}
        {comparative?.error && (
          <p className="text-sm text-amber-700">Error: {comparative.error}</p>
        )}
        {!comparativeLoading && comparative && !comparative.error && (!comparative.by_country || comparative.by_country.length === 0) && (
          <p className="text-sm text-gray-600">Sin datos para períodos cerrados (compruebe que real_rollup_day_fact tenga datos).</p>
        )}
        {comparative && !comparative.error && comparative.by_country?.length > 0 && (
          <div className="flex flex-wrap gap-4">
            {comparative.by_country.map(({ country: c, metrics }) => (
              <div key={c} className="flex flex-wrap gap-3 items-baseline">
                <span className="font-medium text-gray-800 uppercase">{c}</span>
                {metrics && metrics.slice(0, 5).map((m) => (
                  <span key={m.metric} className="text-sm text-gray-700" title={`Actual: ${m.value_current ?? '—'} | Anterior: ${m.value_previous ?? '—'} | Δ: ${m.delta_abs ?? '—'}`}>
                    {m.metric}: {m.delta_pct != null ? `${m.delta_pct > 0 ? '↑' : m.delta_pct < 0 ? '↓' : '→'} ${Number(m.delta_pct).toFixed(1)}%` : '—'}
                  </span>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded text-red-800 text-sm mb-4 flex flex-wrap items-center justify-between gap-2">
          <span>{error}</span>
          <button
            type="button"
            onClick={() => { setError(null); loadSummary(); }}
            className="px-3 py-1.5 bg-red-600 text-white text-sm rounded hover:bg-red-700"
          >
            Reintentar
          </button>
        </div>
      )}

      {loading ? (
        <div className="p-6 space-y-3">
          <div className="animate-pulse space-y-3">
            <div className="h-4 bg-gray-200 rounded w-1/3" />
            <div className="h-32 bg-gray-200 rounded" />
          </div>
          <p className="text-sm text-gray-500">
            Cargando drill… Puede tardar hasta 5 minutos. Si tarda más, revisa la consola del backend.
          </p>
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
                {/* KPI bar por país: totales de los periodos listados (no del drill expandido) */}
                {kpis && (
                  <div className="grid grid-cols-2 md:grid-cols-5 lg:grid-cols-6 gap-3 mb-3 p-4 bg-slate-50 rounded-lg border border-slate-200">
                    <div className="col-span-full md:col-span-6 text-xs text-slate-500 mb-1" title="Estas métricas corresponden a la suma de todos los periodos de la tabla inferior">
                      Totales (periodos listados)
                    </div>
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
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase w-20">{periodType === 'weekly' ? 'WoW Δ%' : 'MoM Δ%'}</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase" title={MARGIN_TOOLTIP}>Margen total</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase w-20">{periodType === 'weekly' ? 'WoW Δ%' : 'MoM Δ%'}</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase" title={MARGIN_TOOLTIP}>Margen/trip</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase w-20">{periodType === 'weekly' ? 'WoW Δ%' : 'MoM Δ%'}</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Km prom</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase w-20">{periodType === 'weekly' ? 'WoW Δ%' : 'MoM Δ%'}</th>
                        <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase">Segmento / B2B</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase w-16">{periodType === 'weekly' ? 'WoW pp' : 'MoM pp'}</th>
                        <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase">Estado</th>
                      </tr>
                    </thead>
                    {/* Subrow headers: Dimensión | Viajes | Margen total | Margen/trip | Km prom | B2B */}
                    <tbody className="bg-white divide-y divide-gray-200">
                      {rows.map((row) => {
                        const rowId = `${(row.country || countryCode || '').trim()}|${normalizePeriodStart(row.period_start)}`
                        const key = subrowKey((row.country || countryCode || '').trim(), row.period_start)
                        const isExp = expanded.has(key)
                        const sr = subrows[key]
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
                          <Fragment key={rowId}>
                            <tr
                              onClick={() => toggleExpand((row.country || countryCode || '').trim(), row.period_start)}
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
                                {row.is_partial_comparison && (
                                  <span className="ml-1 inline-flex px-1.5 py-0.5 rounded text-xs bg-amber-100 text-amber-800" title="Comparativo parcial (periodo abierto)">Parcial</span>
                                )}
                              </td>
                              <td className="px-3 py-2 text-sm text-right">{formatNumber(row.trips)}</td>
                              <td className={`px-3 py-2 text-sm text-right ${row.viajes_trend === 'up' ? 'bg-green-50' : row.viajes_trend === 'down' ? 'bg-red-50' : 'bg-gray-50'}`}>
                                {row.viajes_delta_pct != null ? (
                                  <span className={row.viajes_trend === 'up' ? 'text-green-700 font-medium' : row.viajes_trend === 'down' ? 'text-red-700 font-medium' : 'text-gray-600'}>
                                    {row.viajes_trend === 'up' ? '↑' : row.viajes_trend === 'down' ? '↓' : '→'} {Number(row.viajes_delta_pct).toFixed(1)}%
                                  </span>
                                ) : '—'}
                              </td>
                              <td className="px-3 py-2 text-sm text-right">{row.trips ? formatMargin(marginTotalPos, row.trips) : '—'}</td>
                              <td className={`px-3 py-2 text-sm text-right ${row.margen_total_trend === 'up' ? 'bg-green-50' : row.margen_total_trend === 'down' ? 'bg-red-50' : 'bg-gray-50'}`}>
                                {row.margen_total_delta_pct != null ? (
                                  <span className={row.margen_total_trend === 'up' ? 'text-green-700 font-medium' : row.margen_total_trend === 'down' ? 'text-red-700 font-medium' : 'text-gray-600'}>
                                    {row.margen_total_trend === 'up' ? '↑' : row.margen_total_trend === 'down' ? '↓' : '→'} {Number(row.margen_total_delta_pct).toFixed(1)}%
                                  </span>
                                ) : '—'}
                              </td>
                              <td className="px-3 py-2 text-sm text-right">{marginUnit}</td>
                              <td className={`px-3 py-2 text-sm text-right ${row.margen_trip_trend === 'up' ? 'bg-green-50' : row.margen_trip_trend === 'down' ? 'bg-red-50' : 'bg-gray-50'}`}>
                                {row.margen_trip_delta_pct != null ? (
                                  <span className={row.margen_trip_trend === 'up' ? 'text-green-700 font-medium' : row.margen_trip_trend === 'down' ? 'text-red-700 font-medium' : 'text-gray-600'}>
                                    {row.margen_trip_trend === 'up' ? '↑' : row.margen_trip_trend === 'down' ? '↓' : '→'} {Number(row.margen_trip_delta_pct).toFixed(1)}%
                                  </span>
                                ) : '—'}
                              </td>
                              <td className="px-3 py-2 text-sm text-right">{distanceKm}</td>
                              <td className={`px-3 py-2 text-sm text-right ${row.km_prom_trend === 'up' ? 'bg-green-50' : row.km_prom_trend === 'down' ? 'bg-red-50' : 'bg-gray-50'}`}>
                                {row.km_prom_delta_pct != null ? (
                                  <span className={row.km_prom_trend === 'up' ? 'text-green-700 font-medium' : row.km_prom_trend === 'down' ? 'text-red-700 font-medium' : 'text-gray-600'}>
                                    {row.km_prom_trend === 'up' ? '↑' : row.km_prom_trend === 'down' ? '↓' : '→'} {Number(row.km_prom_delta_pct).toFixed(1)}%
                                  </span>
                                ) : '—'}
                              </td>
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
                              <td className={`px-3 py-2 text-sm text-right ${row.pct_b2b_trend === 'up' ? 'bg-green-50' : row.pct_b2b_trend === 'down' ? 'bg-red-50' : 'bg-gray-50'}`}>
                                {row.pct_b2b_delta_pp != null ? (
                                  <span className={row.pct_b2b_trend === 'up' ? 'text-green-700 font-medium' : row.pct_b2b_trend === 'down' ? 'text-red-700 font-medium' : 'text-gray-600'}>
                                    {row.pct_b2b_trend === 'up' ? '↑' : row.pct_b2b_trend === 'down' ? '↓' : '→'} {Number(row.pct_b2b_delta_pp).toFixed(1)} pp
                                  </span>
                                ) : '—'}
                              </td>
                              <td className="px-3 py-2 text-sm text-center">
                                {(() => {
                                  const estado = row.estado || (open ? 'ABIERTO' : 'CERRADO')
                                  const expectedDate = row.expected_last_date ? String(row.expected_last_date).slice(0, 10) : null
                                  const faltaDataTitle = expectedDate
                                    ? `Falta data hasta cierre de ayer (${expectedDate})`
                                    : 'Falta data hasta cierre de ayer'
                                  const config = {
                                    CERRADO: { className: 'bg-green-100 text-green-800', label: 'Cerrado', title: 'Periodo cerrado' },
                                    ABIERTO: { className: 'bg-blue-100 text-blue-800', label: 'Abierto', title: 'Mes/semana en curso (datos parciales)' },
                                    FALTA_DATA: { className: 'bg-red-100 text-red-800', label: 'Falta data', title: faltaDataTitle },
                                    VACIO: { className: 'bg-gray-200 text-gray-600', label: 'Vacío', title: 'Sin datos' }
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
                              <tr key={`${rowId}-sub`} className="bg-slate-50">
                                <td colSpan={14} className="px-4 py-3">
                                  {sr.loading && <p className="text-sm text-gray-500">Cargando…</p>}
                                  {sr.error && <p className="text-sm text-red-600">{sr.error}</p>}
                                  {sr.data && sr.data.length > 0 && (() => {
                                    const drillLabel = drillBy === 'lob' ? 'LOB' : drillBy === 'park' ? 'Park' : 'Tipo de servicio'
                                    const periodLabel = formatPeriod(row.period_start, periodType)
                                    const filteredData = sr.data.filter(
                                      (r) => (r.dimension_key || '').toUpperCase() !== 'LOW_VOLUME' && (r.lob_group || '').toUpperCase() !== 'LOW_VOLUME'
                                    )
                                    return filteredData.length > 0 ? (
                                    <div className="border-l-2 border-slate-300 pl-3">
                                      <p className="text-xs text-slate-500 mb-2">
                                        Desglose de <strong>{periodLabel}</strong> por {drillLabel}
                                      </p>
                                    <table className="min-w-full text-sm">
                                      <thead>
                                        <tr className="text-left text-gray-500">
                                          {drillBy === 'lob' && <th className="pr-4 py-1">LOB</th>}
                                          {drillBy === 'park' && <th className="pr-4 py-1">Park</th>}
                                          {drillBy === 'service_type' && <th className="pr-4 py-1">Tipo de servicio</th>}
                                          <th className="text-right py-1">Viajes</th>
                                          <th className="text-right py-1" title={MARGIN_TOOLTIP}>Margen total</th>
                                          <th className="text-right py-1" title={MARGIN_TOOLTIP}>Margen/trip</th>
                                          <th className="text-right py-1">Km prom</th>
                                          {segment === 'Todos' && <th className="text-right py-1">B2B</th>}
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {filteredData.map((r, i) => {
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
                                          {drillBy === 'service_type' && (
                                                <td className="pr-4 py-1 text-gray-900">{r.service_type ?? r.dimension_key ?? '—'}</td>
                                          )}
                                              {drillBy === 'park' && (
                                                <td className="pr-4 py-1 text-gray-900">{r.dimension_key ?? r.park_name_resolved ?? r.park_name ?? '—'}</td>
                                              )}
                                              <td className="text-right py-1">{formatNumber(r.trips)}</td>
                                              <td className="text-right py-1">{subTrips ? formatMargin(subMarginTotal, subTrips) : '—'}</td>
                                              <td className="text-right py-1">{subMargin}</td>
                                              <td className="text-right py-1">{subKm}</td>
                                              {segment === 'Todos' && (
                                                <td className="text-right py-1">
                                                  {formatNumber(r.b2b_trips)}
                                                  {r.pct_b2b != null ? ` (${(Number(r.pct_b2b) * 100).toFixed(1)}%)` : ''}
                                                </td>
                                              )}
                                            </tr>
                                          )
                                        })}
                                      </tbody>
                                    </table>
                                    </div>
                                    ) : (
                                      <p className="text-sm text-gray-500">Sin datos para este periodo.</p>
                                    )
                                  })()}
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
        Clic en una fila para desplegar desglose por {drillBy === 'lob' ? 'LOB' : drillBy === 'park' ? 'Park' : 'Tipo de servicio'}.
        Orden: más reciente → más antiguo; subfilas por viajes descendente.
      </p>
    </div>
  )
}
