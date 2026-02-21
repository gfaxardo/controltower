/**
 * RealLOBView — Observabilidad (tabla detalle) y Modo Ejecutivo (KPIs, tendencia, LOB, ciudades).
 *
 * DIAGNÓSTICO TOGGLE (PR):
 * (a) El toggle SÍ actualiza estado (viewMode: 'observability' | 'executive').
 * (b) En Observabilidad se llaman: GET /ops/real-lob/monthly-v2 o weekly-v2.
 * (c) En Ejecutivo se llaman solo: GET /ops/real-strategy/country y GET /ops/real-strategy/lob (no monthly-v2).
 * (d) Las vistas estrategia existen en DB: ops.v_real_country_month, v_real_country_month_forecast,
 *     v_real_country_lob_month, v_real_country_city_month (migración 045). Si no existen, ejecutar alembic upgrade head.
 *
 * Corrección aplicada: el contenido de Observabilidad (meta, error, loading, tabla) se renderiza solo cuando
 * viewMode === 'observability'. En modo Ejecutivo solo se muestra el ExecutivePanel (filtros + KPIs + tendencia + tablas).
 */
import { useState, useEffect } from 'react'
import { getRealLobMonthly, getRealLobWeekly, getRealLobMonthlyV2, getRealLobWeeklyV2, getRealStrategyCountry, getRealStrategyLob, getRealLobFilters, getRealLobV2Data } from '../services/api'

const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
const LOB_GROUPS = ['auto taxi', 'delivery', 'tuk tuk', 'taxi moto', 'UNCLASSIFIED']
const SEGMENT_OPTIONS = [{ value: '', label: 'Todos' }, { value: 'B2B', label: 'B2B' }, { value: 'B2C', label: 'B2C' }]
const AGG_LEVEL_OPTIONS = [
  { value: 'DETALLE', label: 'Detalle (sin consolidar)' },
  { value: 'TOTAL_PAIS', label: 'Total país' },
  { value: 'TOTAL_CIUDAD', label: 'Total ciudad' },
  { value: 'TOTAL_PARK', label: 'Total park' },
  { value: 'PARK_X_MES', label: 'Park × mes' },
  { value: 'PARK_X_MES_X_LOB', label: 'Park × mes × LOB' },
  { value: 'PARK_X_SEMANA', label: 'Park × semana' },
  { value: 'PARK_X_SEMANA_X_LOB', label: 'Park × semana × LOB' },
]

function RealLOBView({ filters = {} }) {
  const [viewMode, setViewMode] = useState('observability') // 'observability' | 'executive'
  const [version, setVersion] = useState('v1')
  const [granularity, setGranularity] = useState('monthly')
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [meta, setMeta] = useState({ last_available_month: null, last_available_week: null })
  // Modo Ejecutivo: strategy data
  const [strategyCountry, setStrategyCountry] = useState(null)
  const [strategyLob, setStrategyLob] = useState(null)
  const [strategyLoading, setStrategyLoading] = useState(false)
  const [strategyError, setStrategyError] = useState(null)
  const [strategyYearReal, setStrategyYearReal] = useState('')

  // Filtros locales v2 (se mezclan con filters del padre)
  const [v2Country, setV2Country] = useState('')
  const [v2City, setV2City] = useState('')
  const [v2ParkId, setV2ParkId] = useState('')
  const [v2LobGroup, setV2LobGroup] = useState('')
  const [v2TipoServicio, setV2TipoServicio] = useState('')
  const [v2Segment, setV2Segment] = useState('')
  const [v2Year, setV2Year] = useState('') // '' = últimos 12 meses
  const [groupBy, setGroupBy] = useState('lob_group')
  const [aggLevel, setAggLevel] = useState('DETALLE')
  const [filterOptions, setFilterOptions] = useState({ countries: [], cities: [], parks: [], lob_groups: [], tipo_servicio: [], segments: ['Todos', 'B2B', 'B2C'], years: [] })
  const [totals, setTotals] = useState(null) // { trips, b2b_trips, b2b_ratio, rows }

  const effectiveFilters = version === 'v2'
    ? {
        country: v2Country || filters.country || undefined,
        city: v2City || filters.city || undefined,
        park_id: v2ParkId || filters.park_id || undefined,
        lob_group: v2LobGroup || filters.lob_group || undefined,
        real_tipo_servicio: v2TipoServicio || filters.real_tipo_servicio || undefined,
        segment_tag: v2Segment || filters.segment_tag || undefined,
        month: filters.month || undefined,
        week_start: filters.week_start || undefined,
        year_real: v2Year ? parseInt(v2Year, 10) : (filters.year_real != null && filters.year_real !== '' ? Number(filters.year_real) : undefined)
      }
    : {
        country: filters.country,
        city: filters.city,
        lob_name: filters.lob_name || filters.lob || filters.line_of_business,
        month: filters.month,
        week_start: filters.week_start,
        year_real: filters.year_real != null && filters.year_real !== '' ? Number(filters.year_real) : undefined
      }

  const executiveCountry = (viewMode === 'executive' ? (v2Country || filters.country) : null) || ''

  // Cargar opciones de filtros (dropdowns) una vez
  useEffect(() => {
    getRealLobFilters()
      .then((opts) => setFilterOptions(opts))
      .catch((e) => console.error('Error cargando filtros Real LOB:', e))
  }, [])

  useEffect(() => {
    if (viewMode === 'executive') {
      if (executiveCountry && executiveCountry.trim()) {
        loadStrategyData()
      } else {
        setStrategyCountry(null)
        setStrategyLob(null)
        setStrategyError(null)
        setStrategyLoading(false)
      }
      // En modo Ejecutivo NO se llaman endpoints monthly-v2/weekly-v2; solo /ops/real-strategy/*
      return
    }
    loadData()
  }, [viewMode, version, granularity, effectiveFilters.country, effectiveFilters.city, effectiveFilters.park_id, effectiveFilters.lob_group, effectiveFilters.real_tipo_servicio, effectiveFilters.segment_tag, effectiveFilters.lob_name, effectiveFilters.month, effectiveFilters.week_start, effectiveFilters.year_real, executiveCountry, strategyYearReal, aggLevel])

  const loadStrategyData = async () => {
    const country = executiveCountry
    if (!country || !country.trim()) {
      setStrategyCountry(null)
      setStrategyLob(null)
      return
    }
    setStrategyLoading(true)
    setStrategyError(null)
    try {
      const yearVal = strategyYearReal ? parseInt(strategyYearReal, 10) : (filters.year_real ?? undefined)
      const [countryRes, lobRes] = await Promise.all([
        getRealStrategyCountry({ country, year_real: yearVal, segment_tag: effectiveFilters.segment_tag || undefined }),
        getRealStrategyLob({ country, year_real: yearVal, segment_tag: effectiveFilters.segment_tag || undefined, lob_group: effectiveFilters.lob_group || undefined })
      ])
      setStrategyCountry(countryRes.error ? null : countryRes)
      setStrategyLob(lobRes.error ? null : lobRes)
      if (countryRes.error) setStrategyError(countryRes.error)
    } catch (e) {
      console.error('Error cargando Real Strategy:', e)
      setStrategyCountry(null)
      setStrategyLob(null)
      setStrategyError(e.message || 'Error al cargar modo Ejecutivo')
    } finally {
      setStrategyLoading(false)
    }
  }

  const loadData = async () => {
    setLoading(true)
    setError(null)
    setTotals(null)
    try {
      if (version === 'v2') {
        const res = await getRealLobV2Data({
          period_type: granularity === 'weekly' ? 'weekly' : 'monthly',
          agg_level: aggLevel,
          country: effectiveFilters.country || undefined,
          city: effectiveFilters.city || undefined,
          park_id: effectiveFilters.park_id || undefined,
          lob_group: effectiveFilters.lob_group || undefined,
          tipo_servicio: effectiveFilters.real_tipo_servicio || undefined,
          segment_tag: effectiveFilters.segment_tag || undefined,
          year: effectiveFilters.year_real || undefined
        })
        setData(res.rows || [])
        setTotals(res.totals || null)
        setMeta({
          last_available_month: res.meta?.last_month_real ?? null,
          last_available_week: res.meta?.last_week_real ?? null
        })
      } else {
        if (granularity === 'monthly') {
          const res = await getRealLobMonthly({
            country: effectiveFilters.country,
            city: effectiveFilters.city,
            lob_name: effectiveFilters.lob_name,
            month: effectiveFilters.month,
            year_real: effectiveFilters.year_real
          })
          setData(res.data || [])
          setMeta({ last_available_month: res.last_available_month ?? null, last_available_week: res.last_available_week ?? null })
        } else {
          const res = await getRealLobWeekly({
            country: effectiveFilters.country,
            city: effectiveFilters.city,
            lob_name: effectiveFilters.lob_name,
            week_start: effectiveFilters.week_start,
            year_real: effectiveFilters.year_real
          })
          setData(res.data || [])
          setMeta({ last_available_month: res.last_available_month ?? null, last_available_week: res.last_available_week ?? null })
        }
      }
    } catch (e) {
      console.error('Error cargando Real LOB:', e)
      setData([])
      const isTimeout = e.code === 'ECONNABORTED' || e.message?.includes('timeout')
      setError(isTimeout ? 'La solicitud tardó demasiado (timeout 15 s).' : (e.message || 'Error al cargar datos'))
    } finally {
      setLoading(false)
    }
  }

  const formatNumber = (n) => (n != null ? Math.round(n).toLocaleString('es-ES') : '-')
  const formatRevenue = (n, currency) => {
    if (n == null) return '-'
    const num = Math.max(0, Number(n))
    if (currency === 'PEN') return num.toLocaleString('es-PE', { style: 'currency', currency: 'PEN', maximumFractionDigits: 0 })
    if (currency === 'COP') return num.toLocaleString('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 })
    return num.toLocaleString('es-ES', { maximumFractionDigits: 0 })
  }
  const displayPeriod = (row) => {
    const dm = row.display_period || row.display_month || row.period_date
    const w = row.display_week || row.period_date
    if (granularity === 'monthly') {
      if (!dm) return '-'
      const m = String(dm)
      if (m.length >= 7) {
        const [y, mo] = m.split('-')
        const monthLabel = MESES[parseInt(mo, 10) - 1] || mo
        return `${monthLabel} ${y}`
      }
      return m
    }
    return w ? `Semana ${w}` : (dm ? String(dm) : '-')
  }

  const byLob = data.reduce((acc, r) => {
    const key = r.lob_name || r.lob || r.lob_group || 'UNCLASSIFIED'
    if (!acc[key]) acc[key] = { trips: 0, revenue: 0 }
    acc[key].trips += r.trips || 0
    acc[key].revenue += r.revenue || 0
    return acc
  }, {})
  const maxTripsLob = Math.max(...Object.values(byLob).map((a) => a.trips || 0), 1)

  const sortedData = version === 'v2' && data.length
    ? [...data].sort((a, b) => {
        const key = groupBy === 'lob_group' ? 'lob_group' : 'real_tipo_servicio_norm'
        const va = (a[key] || '').toLowerCase()
        const vb = (b[key] || '').toLowerCase()
        if (va !== vb) return va.localeCompare(vb)
        return (b.trips || 0) - (a.trips || 0)
      })
    : data

  const formatPct = (n) => (n != null ? `${Number(n).toFixed(2)}%` : '-')
  const formatGrowth = (n) => (n != null ? `${(Number(n) * 100).toFixed(2)}%` : '-')

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      <div className="flex flex-wrap justify-between items-center gap-4 mb-4">
        <h3 className="text-lg font-semibold">Real LOB — {viewMode === 'executive' ? 'Modo Ejecutivo' : 'Observabilidad (solo Real, sin Plan)'}</h3>
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-sm text-gray-500">Modo:</span>
          <button
            type="button"
            onClick={() => setViewMode('observability')}
            className={`px-3 py-1.5 rounded text-sm ${viewMode === 'observability' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            Observabilidad
          </button>
          <button
            type="button"
            onClick={() => setViewMode('executive')}
            className={`px-3 py-1.5 rounded text-sm ${viewMode === 'executive' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            Ejecutivo
          </button>
          {viewMode === 'observability' && (
            <>
              <span className="w-px h-6 bg-gray-300" />
              <span className="text-sm text-gray-500">Versión:</span>
              <button
                type="button"
                onClick={() => setVersion('v1')}
                className={`px-3 py-1.5 rounded text-sm ${version === 'v1' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
              >
                v1
              </button>
              <button
                type="button"
                onClick={() => setVersion('v2')}
                className={`px-3 py-1.5 rounded text-sm ${version === 'v2' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
              >
                v2
              </button>
              <span className="w-px h-6 bg-gray-300" />
              <button
                type="button"
                onClick={() => setGranularity('monthly')}
                className={`px-4 py-2 rounded ${granularity === 'monthly' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
              >
                Mensual
              </button>
              <button
                type="button"
                onClick={() => setGranularity('weekly')}
                className={`px-4 py-2 rounded ${granularity === 'weekly' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
              >
                Semanal
              </button>
            </>
          )}
        </div>
      </div>

      {viewMode === 'executive' && (
        <div className="mb-4 p-4 bg-slate-50 rounded-lg border border-slate-200">
          <h4 className="text-sm font-medium text-slate-700 mb-2">Filtros (modo Ejecutivo)</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <div>
              <label className="block text-xs text-slate-500 mb-0.5">País (requerido)</label>
              <select
                value={v2Country || ''}
                onChange={(e) => {
                  setV2Country(e.target.value)
                  setV2City('')
                  setV2ParkId('')
                }}
                className="border rounded px-2 py-1.5 text-sm w-full"
              >
                <option value="">Seleccione un país</option>
                {(filterOptions.countries || []).map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-0.5">Año</label>
              <select
                value={strategyYearReal}
                onChange={(e) => setStrategyYearReal(e.target.value)}
                className="border rounded px-2 py-1.5 text-sm w-full"
              >
                <option value="">Últimos 12 meses</option>
                {(filterOptions.years || []).map((y) => (
                  <option key={y} value={String(y)}>{y}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-0.5">Segmento</label>
              <select
                value={v2Segment || ''}
                onChange={(e) => setV2Segment(e.target.value)}
                className="border rounded px-2 py-1.5 text-sm w-full"
              >
                {SEGMENT_OPTIONS.map((o) => (
                  <option key={o.value || 'all'} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-0.5">LOB_GROUP</label>
              <select
                value={v2LobGroup || ''}
                onChange={(e) => setV2LobGroup(e.target.value)}
                className="border rounded px-2 py-1.5 text-sm w-full"
              >
                <option value="">Todos</option>
                {(filterOptions.lob_groups || LOB_GROUPS).map((g) => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      {viewMode === 'executive' && (
        <>
          {!executiveCountry ? (
            <p className="text-amber-700 bg-amber-50 p-4 rounded">Seleccione un país (ej. co, pe) para ver KPIs y forecast.</p>
          ) : strategyLoading ? (
            <div className="animate-pulse space-y-3">
              <div className="h-4 bg-gray-200 rounded w-1/3" />
              <div className="h-24 bg-gray-200 rounded" />
              <div className="h-48 bg-gray-200 rounded" />
            </div>
          ) : strategyError ? (
            <div className="p-4 bg-red-50 border border-red-200 rounded text-red-800 text-sm">{strategyError}</div>
          ) : strategyCountry && (
            <>
              {/* KPIs Estratégicos */}
              <section className="mb-6">
                <h4 className="text-sm font-semibold text-slate-700 mb-3">KPIs Estratégicos</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
                  <div className="bg-slate-50 p-3 rounded border border-slate-200">
                    <div className="text-xs text-slate-500">Total viajes (YTD)</div>
                    <div className="text-lg font-semibold">{formatNumber(strategyCountry.kpis?.total_trips_ytd)}</div>
                  </div>
                  <div className="bg-slate-50 p-3 rounded border border-slate-200">
                    <div className="text-xs text-slate-500">Crecimiento MoM</div>
                    <div className="text-lg font-semibold">{formatGrowth(strategyCountry.kpis?.growth_mom)}</div>
                  </div>
                  <div className="bg-slate-50 p-3 rounded border border-slate-200">
                    <div className="text-xs text-slate-500">% B2B</div>
                    <div className="text-lg font-semibold">{formatPct(strategyCountry.kpis?.b2b_ratio != null ? strategyCountry.kpis.b2b_ratio * 100 : null)}</div>
                  </div>
                  <div className="bg-slate-50 p-3 rounded border border-slate-200">
                    <div className="text-xs text-slate-500">Forecast próximo mes</div>
                    <div className="text-lg font-semibold">{strategyCountry.forecast?.available !== false ? formatNumber(strategyCountry.kpis?.forecast_next_month) : '-'}</div>
                  </div>
                  <div className="bg-slate-50 p-3 rounded border border-slate-200">
                    <div className="text-xs text-slate-500">Crec. forecast</div>
                    <div className="text-lg font-semibold">{formatGrowth(strategyCountry.kpis?.forecast_growth)}</div>
                  </div>
                  <div className="bg-slate-50 p-3 rounded border border-slate-200">
                    <div className="text-xs text-slate-500">Aceleración</div>
                    <div className="flex items-center gap-1">
                      <span className="text-lg font-semibold">
                        {strategyCountry.kpis?.acceleration_index != null ? (strategyCountry.kpis.acceleration_index * 100).toFixed(2) + '%' : '-'}
                      </span>
                      {strategyCountry.kpis?.acceleration_index != null && (
                        <span className={`inline-flex px-1.5 py-0.5 rounded text-xs font-medium ${strategyCountry.kpis.acceleration_index > 0 ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'}`}>
                          {strategyCountry.kpis.acceleration_index > 0 ? 'Positiva' : 'Negativa'}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="bg-slate-50 p-3 rounded border border-slate-200">
                    <div className="text-xs text-slate-500">Concentración (top 3)</div>
                    <div className="text-lg font-semibold">{strategyCountry.kpis?.concentration_index != null ? formatPct(strategyCountry.kpis.concentration_index * 100) : '-'}</div>
                  </div>
                </div>
                {strategyCountry.forecast?.disclaimer && (
                  <p className="text-xs text-slate-500 mt-2 italic">{strategyCountry.forecast.disclaimer}</p>
                )}
              </section>

              {/* Gráfico Tendencia: 12 meses real + forecast punteado */}
              <section className="mb-6">
                <h4 className="text-sm font-semibold text-slate-700 mb-3">Tendencia (12 meses real + forecast)</h4>
                {strategyCountry.trend?.length > 0 ? (
                  <div className="flex flex-wrap items-end gap-1" style={{ minHeight: 120 }}>
                    {(() => {
                      const trendList = [...(strategyCountry.trend || [])].reverse()
                      const maxTrips = Math.max(...trendList.map((x) => x.trips || 0), strategyCountry.forecast?.next_month || 0, 1)
                      return (
                        <>
                          {trendList.map((t, i) => (
                            <div key={i} className="flex flex-col items-center flex-1 min-w-[24px]">
                              <div
                                className="w-full bg-blue-500 rounded-t rounded-b-none"
                                style={{ height: Math.max(4, (t.trips || 0) / maxTrips * 80) + 'px' }}
                                title={`${t.display_month || t.month_start}: ${formatNumber(t.trips)}`}
                              />
                              <span className="text-[10px] text-slate-500 truncate w-full text-center">{t.display_month?.slice(-2) || ''}</span>
                            </div>
                          ))}
                          {strategyCountry.forecast?.next_month != null && strategyCountry.forecast?.available !== false && (
                            <div className="flex flex-col items-center flex-1 min-w-[24px] border-l border-dashed border-slate-300 pl-1">
                              <div
                                className="w-full bg-slate-400 rounded-t rounded-b-none border border-dashed border-slate-500"
                                style={{ height: Math.max(4, (strategyCountry.forecast.next_month || 0) / maxTrips * 80) + 'px' }}
                                title={`Forecast: ${formatNumber(strategyCountry.forecast.next_month)}`}
                              />
                              <span className="text-[10px] text-slate-500">F</span>
                            </div>
                          )}
                        </>
                      )
                    })()}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">Sin datos de tendencia. Necesita al menos 2 meses reales para forecast.</p>
                )}
              </section>

              {/* Distribución LOB */}
              <section className="mb-6">
                <h4 className="text-sm font-semibold text-slate-700 mb-3">Distribución LOB</h4>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">LOB</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Viajes</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">% participación</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">MoM</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Forecast</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Momentum</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {(strategyLob?.rankings || []).map((r, i) => (
                        <tr key={i}>
                          <td className="px-3 py-2 text-sm text-gray-900">{r.lob_group}</td>
                          <td className="px-3 py-2 text-sm text-right">{formatNumber(r.trips)}</td>
                          <td className="px-3 py-2 text-sm text-right">{formatPct(r.participation_pct)}</td>
                          <td className="px-3 py-2 text-sm text-right">{formatGrowth(r.growth_mom)}</td>
                          <td className="px-3 py-2 text-sm text-right">{formatNumber(r.forecast_next_month)}</td>
                          <td className="px-3 py-2 text-sm text-right">{r.momentum_score != null ? formatGrowth(r.momentum_score) : '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!(strategyLob?.rankings?.length) && <p className="text-sm text-slate-500 py-2">Sin datos LOB para este país.</p>}
                </div>
              </section>

              {/* Ranking Ciudades */}
              <section>
                <h4 className="text-sm font-semibold text-slate-700 mb-3">Ranking Ciudades</h4>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Ciudad</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Viajes</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">MoM</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">% País</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Índice Expansión</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {(strategyCountry.rankings || []).map((r, i) => (
                        <tr key={i}>
                          <td className="px-3 py-2 text-sm text-gray-900">{r.city}</td>
                          <td className="px-3 py-2 text-sm text-right">{formatNumber(r.trips)}</td>
                          <td className="px-3 py-2 text-sm text-right">{formatGrowth(r.growth_mom)}</td>
                          <td className="px-3 py-2 text-sm text-right">{r.pct_country != null ? formatPct(r.pct_country) : (strategyCountry.kpis?.trips_last_month ? formatPct((r.trips || 0) / strategyCountry.kpis.trips_last_month * 100) : '-')}</td>
                          <td className="px-3 py-2 text-sm text-right">{r.expansion_index != null ? (Number(r.expansion_index).toFixed(2) + 'x') : '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!(strategyCountry.rankings?.length) && <p className="text-sm text-slate-500 py-2">Sin datos de ciudades.</p>}
                </div>
              </section>
            </>
          )}
        </>
      )}

      {viewMode === 'observability' && version === 'v2' && (
        <div className="mb-4 p-4 bg-gray-50 rounded-lg">
          <h4 className="text-sm font-medium text-gray-700 mb-2">Filtros v2 (selectores)</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-2">
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">País</label>
              <select
                value={v2Country}
                onChange={(e) => { setV2Country(e.target.value); setV2City(''); setV2ParkId('') }}
                className="border rounded px-2 py-1.5 text-sm w-full"
              >
                <option value="">Todos</option>
                {(filterOptions.countries || []).map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Ciudad</label>
              <select
                value={v2City}
                onChange={(e) => { setV2City(e.target.value); setV2ParkId('') }}
                className="border rounded px-2 py-1.5 text-sm w-full"
              >
                <option value="">Todas</option>
                {(filterOptions.cities || [])
                  .filter((c) => !v2Country || (c.country || '').toLowerCase() === v2Country.toLowerCase())
                  .map((c) => (
                    <option key={`${c.country}-${c.city}`} value={c.city}>{c.city}</option>
                  ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Park</label>
              <select
                value={v2ParkId}
                onChange={(e) => setV2ParkId(e.target.value)}
                className="border rounded px-2 py-1.5 text-sm w-full"
              >
                <option value="">Todos</option>
                {(filterOptions.parks || [])
                  .filter((p) => (!v2Country || (p.country || '').toLowerCase() === v2Country.toLowerCase()) && (!v2City || (p.city || '').toLowerCase() === v2City.toLowerCase()))
                  .map((p) => (
                    <option key={p.park_id} value={p.park_id}>{p.park_name || p.park_id}</option>
                  ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">LOB_GROUP</label>
              <select value={v2LobGroup} onChange={(e) => setV2LobGroup(e.target.value)} className="border rounded px-2 py-1.5 text-sm w-full">
                <option value="">Todos</option>
                {(filterOptions.lob_groups || LOB_GROUPS).map((g) => (
                  <option key={g} value={g}>{g}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Tipo servicio</label>
              <select value={v2TipoServicio} onChange={(e) => setV2TipoServicio(e.target.value)} className="border rounded px-2 py-1.5 text-sm w-full">
                <option value="">Todos</option>
                {(filterOptions.tipo_servicio || []).map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Segmento</label>
              <select value={v2Segment} onChange={(e) => setV2Segment(e.target.value)} className="border rounded px-2 py-1.5 text-sm w-full">
                {SEGMENT_OPTIONS.map((o) => (
                  <option key={o.value || 'all'} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Año</label>
              <select value={v2Year} onChange={(e) => setV2Year(e.target.value)} className="border rounded px-2 py-1.5 text-sm w-full">
                <option value="">Últimos 12 meses</option>
                {(filterOptions.years || []).map((y) => (
                  <option key={y} value={String(y)}>{y}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Consolidar por</label>
              <select value={aggLevel} onChange={(e) => setAggLevel(e.target.value)} className="border rounded px-2 py-1.5 text-sm w-full">
                {AGG_LEVEL_OPTIONS.filter((o) => (granularity === 'weekly' ? o.value.includes('SEMANA') || o.value === 'DETALLE' || o.value.startsWith('TOTAL') : !o.value.includes('SEMANA'))).map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      {viewMode === 'observability' && (
        <>
          {version === 'v2' && totals && (
            <div className="mb-4 flex flex-wrap gap-4 p-3 bg-slate-50 rounded-lg border border-slate-200">
              <div className="font-medium text-slate-700">Totales (filtro aplicado):</div>
              <span><strong>Viajes:</strong> {formatNumber(totals.trips)}</span>
              <span><strong>% B2B:</strong> {totals.b2b_ratio != null ? (Number(totals.b2b_ratio) * 100).toFixed(2) + '%' : '-'}</span>
              <span><strong>Filas:</strong> {totals.rows ?? 0}</span>
              <span className="text-slate-500">Periodo: {meta.last_available_month ?? meta.last_available_week ?? '—'}</span>
            </div>
          )}
          {(meta.last_available_month || meta.last_available_week) && !(version === 'v2' && totals) && (
            <p className="text-sm text-gray-500 mb-2">
              Último mes real: {meta.last_available_month ?? '—'}. Última semana: {meta.last_available_week ?? '—'}
            </p>
          )}
          {error && (
            <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded text-amber-800 text-sm">
              {error}
            </div>
          )}
          {loading ? (
            <div className="animate-pulse space-y-3">
              <div className="h-4 bg-gray-200 rounded w-1/3" />
              <div className="h-12 bg-gray-200 rounded" />
              <div className="h-12 bg-gray-200 rounded" />
            </div>
          ) : (
            <>
              {version === 'v1' && Object.keys(byLob).length > 0 && (
            <div className="mb-6">
              <h4 className="text-sm font-medium text-gray-600 mb-2">Viajes por LOB (totales en vista)</h4>
              <div className="space-y-2">
                {Object.entries(byLob)
                  .sort((a, b) => (b[1].trips || 0) - (a[1].trips || 0))
                  .map(([lob, agg]) => (
                    <div key={lob} className="flex items-center gap-3">
                      <span className="w-32 text-sm text-gray-700 truncate" title={lob}>{lob}</span>
                      <div className="flex-1 bg-gray-100 rounded overflow-hidden" style={{ maxWidth: 400 }}>
                        <div
                          className="h-6 bg-blue-500 rounded"
                          style={{ width: `${Math.min(100, (agg.trips / maxTripsLob) * 100)}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium text-gray-900">{formatNumber(agg.trips)}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">País</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ciudad</th>
                  {version === 'v2' && <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Park</th>}
                  {version === 'v2' ? (
                    <>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">LOB_GROUP</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Tipo servicio</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Segmento</th>
                    </>
                  ) : (
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">LOB</th>
                  )}
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Periodo</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Estado</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Viajes</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Revenue</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {sortedData.length === 0 ? (
                  <tr>
                    <td colSpan={version === 'v2' ? 10 : 7} className="px-4 py-4 text-center text-gray-500">
                      {meta.last_available_month || meta.last_available_week
                        ? `Sin datos para los filtros. Último mes: ${meta.last_available_month ?? '—'}. Última semana: ${meta.last_available_week ?? '—'}.`
                        : version === 'v2' ? 'No hay datos. Ejecute scripts/refresh_real_lob_mvs_v2.py.' : 'No hay datos. Ejecute scripts/refresh_real_lob_mvs.py.'}
                    </td>
                  </tr>
                ) : (
                  sortedData.slice(0, 200).map((row, i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm text-gray-900">{row.country || '-'}</td>
                      <td className="px-4 py-3 text-sm text-gray-900">{row.city || '-'}</td>
                      {version === 'v2' && (
                        <td className="px-4 py-3 text-sm text-gray-900" title={row.park_id}>{row.park_name || row.park_id || '-'}</td>
                      )}
                      {version === 'v2' ? (
                        <>
                          <td className="px-4 py-3 text-sm text-gray-900">{row.lob_group || '-'}</td>
                          <td className="px-4 py-3 text-sm text-gray-900">{row.real_tipo_servicio_norm || '-'}</td>
                          <td className="px-4 py-3 text-sm text-gray-900">{row.segment_tag || '-'}</td>
                        </>
                      ) : (
                        <td className="px-4 py-3 text-sm text-gray-900">{row.lob_name || row.lob || '-'}</td>
                      )}
                      <td className="px-4 py-3 text-sm text-gray-900">{displayPeriod(row)}</td>
                      <td className="px-4 py-3 text-sm">
                        {row.is_open ? (
                          <span className="inline-flex items-center gap-1 text-amber-700" title="Periodo en curso">🟡 Abierto</span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-green-700" title="Periodo cerrado">🟢 Cerrado</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-right text-gray-900">{formatNumber(row.trips)}</td>
                      <td className="px-4 py-3 text-sm text-right text-gray-900">{formatRevenue(row.revenue, row.currency)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            {sortedData.length > 200 && (
              <p className="text-sm text-gray-500 mt-2">Mostrando 200 de {sortedData.length} registros</p>
            )}
          </div>
            </>
          )}
        </>
      )}
    </div>
  )
}

export default RealLOBView
