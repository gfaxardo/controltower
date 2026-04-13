/**
 * Reportes Omniview — Apache ECharts (zoom, toolbox, leyenda), ancho total, suite alineada a la matriz.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import ReactEChartsCore from 'echarts-for-react/esm/core'
import { echarts } from './omniview/echartsRegister.js'
import {
  getBusinessSliceFilters,
  getBusinessSliceMonthly,
  getBusinessSliceWeekly,
  getBusinessSliceDaily,
  getBusinessSliceCoverageSummary,
} from '../services/api.js'
import {
  MATRIX_KPIS,
  buildMatrix,
  fmtValue,
  periodKey,
  periodLabelShort,
} from './omniview/omniviewMatrixUtils.js'
import {
  formatDeltaVsPrevious,
  formatPeriodWindowLabel,
  getLastPrevForKpi,
} from './omniview/omniviewReportKpiHelpers.js'
import OmniviewDataHelp from './omniview/OmniviewDataHelp.jsx'
import {
  FilterSelect,
  YearSelect,
  MonthSelect,
  normalizeOmniviewYear,
} from './omniview/OmniviewFilterPrimitives.jsx'
import {
  buildActualVsComparisonLineOption,
  buildCityTripsBarOption,
  buildCompositionBarOption,
  buildHeatmapOption,
  buildMainLineOption,
  buildSparklineOption,
  buildUnmappedTripsLineOption,
} from './omniview/omniviewReportsChartOptions.js'
import { ECHARTS_COLORS } from './omniview/echartsTheme.js'

const GRAINS = [
  { id: 'monthly', label: 'Mensual' },
  { id: 'weekly', label: 'Semanal' },
  { id: 'daily', label: 'Diario' },
]

const CHART_PALETTE = ECHARTS_COLORS

/** Igual que en la vista matriz: meta.period_totals como objeto → Map por clave de período. */
function toMetricMap (raw) {
  const out = new Map()
  if (!raw || typeof raw !== 'object') return out
  for (const [periodKey, metrics] of Object.entries(raw)) {
    if (!periodKey || !metrics || typeof metrics !== 'object') continue
    out.set(periodKey, metrics)
  }
  return out
}

const COVERAGE_FETCH_DELAY_MS = 400

function cityTripsLastPeriod (matrix, grain) {
  const periods = matrix?.allPeriods
  if (!periods?.length) return { labels: [], values: [] }
  const lastPk = periods[periods.length - 1]
  const acc = []
  for (const [, cd] of matrix.cities) {
    let trips = 0
    for (const [, line] of cd.lines) {
      const cell = line.periods.get(lastPk)
      const m = cell?.metrics
      if (m) trips += Number(m.trips_completed) || 0
    }
    const label =
      cd.city && String(cd.city).trim() && cd.city !== '—'
        ? String(cd.city)
        : [cd.country, cd.city].filter(Boolean).join(' · ') || '—'
    acc.push({ label, trips })
  }
  acc.sort((a, b) => b.trips - a.trips)
  return {
    labels: acc.map((x) => x.label),
    values: acc.map((x) => x.trips),
  }
}

function seriesKey (row) {
  return `${row.business_slice_name || '—'}::${row.fleet_display_name || '—'}::${row.is_subfleet ? '1' : '0'}::${row.subfleet_name || ''}`
}

function seriesLabel (row) {
  const a = row.business_slice_name || '—'
  const b = row.fleet_display_name && row.fleet_display_name !== '—' ? row.fleet_display_name : ''
  const c = row.is_subfleet && row.subfleet_name ? ` · ${row.subfleet_name}` : ''
  return `${a}${b ? ` · ${b}` : ''}${c}`.toUpperCase()
}

function filterRows (rows, { country, city, businessSlice, fleet, showSubfleets }) {
  return rows.filter((r) => {
    if (!showSubfleets && r.is_subfleet) return false
    if (country && String(r.country || '').toLowerCase() !== String(country).toLowerCase()) return false
    if (city && String(r.city || '').toLowerCase() !== String(city).toLowerCase()) return false
    if (businessSlice && String(r.business_slice_name || '') !== businessSlice) return false
    if (fleet && String(r.fleet_display_name || '') !== fleet) return false
    return true
  })
}

function defaultSelectedKeys (rows, grain, limit = 6) {
  const totals = new Map()
  for (const r of rows) {
    const sk = seriesKey(r)
    const t = (totals.get(sk) || 0) + (Number(r.trips_completed) || 0)
    totals.set(sk, t)
  }
  return [...totals.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([k]) => k)
}

function topLineKeysByTrips (rows, limit = 14) {
  const totals = new Map()
  for (const r of rows) {
    const sk = seriesKey(r)
    totals.set(sk, (totals.get(sk) || 0) + (Number(r.trips_completed) || 0))
  }
  return [...totals.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([k]) => k)
}

function buildHeatmapMatrix (filteredRows, grain, kpiKey, lineKeys, periods) {
  const matrix = lineKeys.map(() => periods.map(() => null))
  for (const r of filteredRows) {
    const sk = seriesKey(r)
    const pk = periodKey(r, grain)
    const li = lineKeys.indexOf(sk)
    const pi = periods.indexOf(pk)
    if (li >= 0 && pi >= 0) {
      const v = r[kpiKey]
      matrix[li][pi] = v != null && v !== '' ? Number(v) : null
    }
  }
  return matrix
}

function buildChartModel (rows, grain, kpiKey, selectedKeys) {
  const bySeries = new Map()
  const periodSet = new Set()
  for (const r of rows) {
    const sk = seriesKey(r)
    if (!selectedKeys.includes(sk)) continue
    const pk = periodKey(r, grain)
    if (!pk) continue
    periodSet.add(pk)
    if (!bySeries.has(sk)) {
      bySeries.set(sk, { label: seriesLabel(r), values: new Map() })
    }
    const v = r[kpiKey]
    bySeries.get(sk).values.set(pk, v != null && v !== '' ? Number(v) : null)
  }
  const periods = [...periodSet].sort()
  const seriesList = selectedKeys.filter((k) => bySeries.has(k)).map((k, i) => ({
    key: k,
    dataKey: `v${i}`,
    label: bySeries.get(k).label,
    color: CHART_PALETTE[i % CHART_PALETTE.length],
  }))
  const chartData = periods.map((pk) => {
    const row = { period: pk, xlabel: periodLabelShort(pk, grain) }
    seriesList.forEach((s, idx) => {
      const val = bySeries.get(s.key)?.values.get(pk)
      row[`v${idx}`] = val != null && !Number.isNaN(val) ? val : null
    })
    return row
  })
  return { chartData, seriesList, periods }
}

function compositionLastPeriod (rows, grain, limit = 12) {
  const pks = [...new Set(rows.map((r) => periodKey(r, grain)).filter(Boolean))].sort()
  const last = pks[pks.length - 1]
  if (!last) return { labels: [], values: [] }
  const m = new Map()
  for (const r of rows) {
    if (periodKey(r, grain) !== last) continue
    const sk = seriesKey(r)
    m.set(sk, (m.get(sk) || 0) + (Number(r.trips_completed) || 0))
  }
  const pairs = [...m.entries()].sort((a, b) => b[1] - a[1]).slice(0, limit)
  return {
    labels: pairs.map(([sk]) => {
      const row = rows.find((x) => seriesKey(x) === sk)
      return seriesLabel(row || {})
    }),
    values: pairs.map(([, v]) => v),
  }
}

const echartsOpts = { renderer: 'canvas' }

export default function BusinessSliceOmniviewReports () {
  const [filtersMeta, setFiltersMeta] = useState(null)
  const [grain, setGrain] = useState('monthly')
  const [country, setCountry] = useState('')
  const [city, setCity] = useState('')
  const [businessSlice, setBusinessSlice] = useState('')
  const [fleet, setFleet] = useState('')
  const [showSubfleets, setShowSubfleets] = useState(true)
  const [year, setYear] = useState(() => normalizeOmniviewYear(new Date().getFullYear()))
  const [month, setMonth] = useState('')

  const [rows, setRows] = useState([])
  const [matrixMeta, setMatrixMeta] = useState(null)
  const [coverageSummary, setCoverageSummary] = useState(null)
  const [sliceMaxTripDate, setSliceMaxTripDate] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)
  const [kpiKey, setKpiKey] = useState('trips_completed')
  const [heatmapKpi, setHeatmapKpi] = useState('trips_completed')
  const [selectedKeys, setSelectedKeys] = useState([])

  const needsCountry = grain === 'weekly' || grain === 'daily'
  const blocked = needsCountry && !country

  const countries = filtersMeta?.countries || []
  const allCities = filtersMeta?.cities || []
  const slices = filtersMeta?.business_slices || []
  const fleets = filtersMeta?.fleets || []

  const loadAbortRef = useRef(null)

  const cityCountryRef = useRef(new Map())
  useEffect(() => {
    const m = cityCountryRef.current
    m.clear()
    for (const r of rows) {
      if (r.country && r.city) m.set(String(r.city).toLowerCase(), String(r.country).toLowerCase())
    }
  }, [rows])

  const citiesForCountry = useMemo(() => {
    if (!country) return allCities
    const lc = country.toLowerCase()
    return allCities.filter((c) => {
      const x = cityCountryRef.current.get(String(c).toLowerCase())
      return !x || x === lc
    })
  }, [allCities, country, rows])

  useEffect(() => {
    const ctrl = new AbortController()
    getBusinessSliceFilters({ signal: ctrl.signal })
      .then(setFiltersMeta)
      .catch(() => {})
    return () => ctrl.abort()
  }, [])

  useEffect(() => {
    if (country && city) {
      const m = cityCountryRef.current.get(city.toLowerCase())
      if (m && m !== country.toLowerCase()) setCity('')
    }
  }, [country]) // eslint-disable-line react-hooks/exhaustive-deps

  const load = useCallback(async () => {
    loadAbortRef.current?.abort()
    const ac = new AbortController()
    loadAbortRef.current = ac
    const signal = ac.signal

    if (blocked) {
      setRows([])
      setSelectedKeys([])
      setMatrixMeta(null)
      setCoverageSummary(null)
      setSliceMaxTripDate(null)
      return
    }
    setLoading(true)
    setErr(null)
    const params = {}
    if (country) params.country = country
    if (city) params.city = city
    if (businessSlice) params.business_slice = businessSlice
    if (year != null && year !== '') params.year = Number(year)
    if (month) params.month = Number(month)
    if (grain === 'monthly' && fleet) params.fleet = fleet
    const coverageParams = {}
    if (country) coverageParams.country = country
    if (city) coverageParams.city = city
    if (year != null && year !== '') coverageParams.year = Number(year)
    if (month) coverageParams.month = Number(month)
    try {
      let res
      if (grain === 'weekly') res = await getBusinessSliceWeekly(params, { signal })
      else if (grain === 'daily') res = await getBusinessSliceDaily(params, { signal })
      else res = await getBusinessSliceMonthly(params, { signal })
      let data = Array.isArray(res?.data) ? res.data : []
      setMatrixMeta(res?.meta ?? null)
      setSliceMaxTripDate(res?.meta?.slice_max_trip_date ?? null)
      if (!showSubfleets) data = data.filter((r) => !r.is_subfleet)
      setRows(data)
      const filtered = filterRows(data, { country, city, businessSlice, fleet, showSubfleets })
      setSelectedKeys(defaultSelectedKeys(filtered, grain))

      await new Promise((resolve) => setTimeout(resolve, COVERAGE_FETCH_DELAY_MS))
      if (signal.aborted) return
      try {
        const cov = await getBusinessSliceCoverageSummary(coverageParams, { signal })
        if (!signal.aborted) setCoverageSummary(cov)
      } catch (ce) {
        if (ce?.code === 'ERR_CANCELED' || ce?.name === 'CanceledError' || ce?.name === 'AbortError') return
        setCoverageSummary(null)
      }
    } catch (e) {
      if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError' || e?.name === 'AbortError') return
      const detail = e?.response?.data?.detail
      setErr(typeof detail === 'string' ? detail : detail?.message || e.message || 'Error cargando datos')
      setRows([])
      setSelectedKeys([])
      setMatrixMeta(null)
      setCoverageSummary(null)
      setSliceMaxTripDate(null)
    } finally {
      if (!signal.aborted) setLoading(false)
    }
  }, [grain, country, city, businessSlice, fleet, year, month, showSubfleets, blocked])

  useEffect(() => {
    load()
  }, [load])

  const filteredRows = useMemo(
    () => filterRows(rows, { country, city, businessSlice, fleet, showSubfleets }),
    [rows, country, city, businessSlice, fleet, showSubfleets]
  )

  const baseMatrix = useMemo(
    () => (filteredRows.length ? buildMatrix(filteredRows, grain) : null),
    [filteredRows, grain]
  )

  const backendTotals = useMemo(() => toMetricMap(matrixMeta?.period_totals), [matrixMeta])
  const backendComparisonTotals = useMemo(
    () => toMetricMap(matrixMeta?.comparison_period_totals),
    [matrixMeta]
  )

  const matrix = useMemo(() => {
    if (!baseMatrix) return null
    return {
      ...baseMatrix,
      totals: backendTotals.size > 0 ? backendTotals : baseMatrix.totals,
      comparisonTotals:
        backendComparisonTotals.size > 0 ? backendComparisonTotals : baseMatrix.comparisonTotals,
    }
  }, [baseMatrix, backendTotals, backendComparisonTotals])

  const backendUnmappedTotals = useMemo(
    () => toMetricMap(matrixMeta?.unmapped_period_totals),
    [matrixMeta]
  )

  const { chartData, seriesList } = useMemo(() => {
    if (!selectedKeys.length || !kpiKey) return { chartData: [], seriesList: [] }
    return buildChartModel(filteredRows, grain, kpiKey, selectedKeys)
  }, [filteredRows, grain, kpiKey, selectedKeys])

  const grainLabel = GRAINS.find((g) => g.id === grain)?.label || grain

  const mainLineOption = useMemo(() => {
    if (!chartData.length || !seriesList.length || !matrix?.allPeriods?.length) return null
    const kpiDef = MATRIX_KPIS.find((k) => k.key === kpiKey)
    const titleText = (kpiDef?.label || kpiKey).toUpperCase()
    const subtext = `${formatPeriodWindowLabel(matrix.allPeriods, grain)} · ${grainLabel}`
    return buildMainLineOption({ chartData, seriesList, kpiKey, titleText, subtext })
  }, [chartData, seriesList, kpiKey, matrix, grain, grainLabel])

  const sparkSection = useMemo(() => {
    if (!matrix?.allPeriods?.length) return []
    const periods = matrix.allPeriods
    const rangeLabel = formatPeriodWindowLabel(periods, grain)
    return MATRIX_KPIS.map((kpi, i) => {
      const values = periods.map((pk) => {
        const t = matrix.totals.get(pk)
        const v = t?.[kpi.key]
        return v != null && v !== '' ? Number(v) : null
      })
      const snap = getLastPrevForKpi(matrix, kpi.key)
      const deltaText =
        snap && formatDeltaVsPrevious(kpi.key, snap.lastVal, snap.prevVal)
      return {
        kpi,
        snap,
        deltaText,
        rangeLabel,
        option: buildSparklineOption({
          periods,
          values,
          kpi,
          color: CHART_PALETTE[i % CHART_PALETTE.length],
          grain,
        }),
      }
    })
  }, [matrix, grain])

  const actualVsComparisonOption = useMemo(() => {
    if (!matrix?.allPeriods?.length) return null
    const periods = matrix.allPeriods
    const actualValues = periods.map((pk) => {
      const t = matrix.totals.get(pk)
      const v = t?.[kpiKey]
      return v != null && v !== '' ? Number(v) : null
    })
    const comparisonValues = periods.map((pk) => {
      const t = matrix.comparisonTotals?.get(pk)
      const v = t?.[kpiKey]
      return v != null && v !== '' ? Number(v) : null
    })
    const kpiDef = MATRIX_KPIS.find((k) => k.key === kpiKey)
    const subtext = `${formatPeriodWindowLabel(periods, grain)} · ${grainLabel}`
    return buildActualVsComparisonLineOption({
      periods,
      actualValues,
      comparisonValues,
      kpiKey,
      kpiLabel: `${kpiDef?.label || kpiKey} — total vs comparación`,
      subtext,
      grain,
    })
  }, [matrix, kpiKey, grain, grainLabel])

  const unmappedLineOption = useMemo(() => {
    if (!matrix?.allPeriods?.length) return null
    const periods = matrix.allPeriods
    const values = periods.map((pk) => {
      const t = backendUnmappedTotals.get(pk)
      const v = t?.trips_completed
      return v != null && v !== '' ? Number(v) : null
    })
    return buildUnmappedTripsLineOption({
      periods,
      values,
      grain,
      subtext: formatPeriodWindowLabel(periods, grain),
    })
  }, [matrix, backendUnmappedTotals, grain])

  const cityBarOption = useMemo(() => {
    if (!matrix?.cities || matrix.cities.size <= 1) return null
    const { labels, values } = cityTripsLastPeriod(matrix, grain)
    if (labels.length <= 1) return null
    const lastPk = matrix.allPeriods[matrix.allPeriods.length - 1]
    const sub = `${formatPeriodWindowLabel(matrix.allPeriods, grain)} · último período: ${periodLabelShort(lastPk, grain)}`
    return buildCityTripsBarOption({ labels, values, subtext: sub })
  }, [matrix, grain])

  const heatmapPayload = useMemo(() => {
    if (!filteredRows.length || !matrix?.allPeriods?.length) return null
    const periods = matrix.allPeriods
    const lineKeys = topLineKeysByTrips(filteredRows, 14)
    if (!lineKeys.length || !periods.length) return null
    const hm = buildHeatmapMatrix(filteredRows, grain, heatmapKpi, lineKeys, periods)
    const lineLabels = lineKeys.map((sk) => {
      const row = filteredRows.find((r) => seriesKey(r) === sk)
      return seriesLabel(row || {})
    })
    return {
      periods,
      lineKeys,
      matrix: hm,
      lineLabels,
      option: buildHeatmapOption({
        periods,
        lineKeys,
        matrix: hm,
        lineLabels,
        kpiKey: heatmapKpi,
        grain,
      }),
    }
  }, [filteredRows, grain, heatmapKpi, matrix])

  const compositionOption = useMemo(() => {
    if (!filteredRows.length) return null
    const { labels, values } = compositionLastPeriod(filteredRows, grain, 12)
    if (!labels.length) return null
    return buildCompositionBarOption({ labels, values })
  }, [filteredRows, grain])

  const allSeriesKeys = useMemo(() => {
    const s = new Set()
    for (const r of filteredRows) s.add(seriesKey(r))
    return [...s].sort()
  }, [filteredRows])

  const toggleSeries = (sk) => {
    setSelectedKeys((prev) => {
      if (prev.includes(sk)) return prev.filter((x) => x !== sk)
      if (prev.length >= 8) return prev
      return [...prev, sk]
    })
  }

  const btnCls = (active) =>
    `px-3 py-1.5 rounded-md text-xs font-semibold uppercase tracking-wide transition-all ${
      active ? 'bg-slate-900 text-white shadow-sm' : 'bg-white text-gray-600 border border-gray-200 hover:border-gray-300 hover:bg-gray-50'
    }`

  return (
    <div
      className="relative space-y-4"
      style={{ width: '100vw', left: '50%', right: '50%', marginLeft: '-50vw', marginRight: '-50vw' }}
    >
      <div className="px-4 md:px-6 lg:px-8 space-y-4">
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm divide-y divide-gray-100">
          <div className="px-4 py-3 flex flex-wrap items-end gap-x-4 gap-y-3">
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Grano</span>
              <div className="flex gap-1">
                {GRAINS.map((g) => (
                  <button key={g.id} type="button" className={btnCls(grain === g.id)} onClick={() => setGrain(g.id)}>
                    {g.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="hidden sm:block self-stretch w-px bg-gray-100 mx-1" />
            <FilterSelect
              label="País"
              value={country}
              onChange={setCountry}
              options={countries}
              placeholder="Todos los países"
              required={needsCountry}
            />
            <FilterSelect label="Ciudad" value={city} onChange={setCity} options={citiesForCountry} placeholder="Todas las ciudades" />
            <FilterSelect label="Tajada" value={businessSlice} onChange={setBusinessSlice} options={slices} placeholder="Todas las tajadas" />
            {grain === 'monthly' && (
              <FilterSelect label="Flota" value={fleet} onChange={setFleet} options={fleets} placeholder="Todas las flotas" />
            )}
            <div className="hidden sm:block self-stretch w-px bg-gray-100 mx-1" />
            <YearSelect value={year} onChange={setYear} />
            {(grain === 'monthly' || grain === 'daily') && <MonthSelect value={month} onChange={setMonth} />}
            <label className="flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer select-none self-end pb-1.5 uppercase tracking-wide">
              <input
                type="checkbox"
                checked={showSubfleets}
                onChange={(e) => setShowSubfleets(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 h-3.5 w-3.5"
              />
              Subflotas
            </label>
            <button
              type="button"
              onClick={() => load()}
              className="self-end px-3 py-1.5 rounded-md text-xs font-semibold uppercase tracking-wide bg-blue-600 text-white hover:bg-blue-700"
            >
              Actualizar
            </button>
          </div>
          <div className="px-4 py-2 border-t border-gray-100 bg-slate-50/40">
            <OmniviewDataHelp />
          </div>
        </div>

        <div className="rounded-xl border border-slate-200/90 bg-slate-50/90 px-4 py-3 text-sm text-slate-700 shadow-sm">
          <span className="font-semibold text-slate-900">Resumen operativo</span>
          <span className="mx-2 text-slate-300">·</span>
          <span className="text-slate-600">
            Grano: <strong className="font-medium text-slate-800">{grainLabel}</strong>
            {' · '}
            País: <strong className="font-medium text-slate-800">{country || 'Todos'}</strong>
            {' · '}
            Ciudad: <strong className="font-medium text-slate-800">{city || 'Todas'}</strong>
            {' · '}
            Año: <strong className="font-medium text-slate-800">{year ?? '—'}</strong>
            {(grain === 'monthly' || grain === 'daily') && (
              <>
                {' · '}
                Mes: <strong className="font-medium text-slate-800">{month || 'Todos'}</strong>
              </>
            )}
            {' · '}
            Tajada: <strong className="font-medium text-slate-800">{businessSlice || 'Todas'}</strong>
            {grain === 'monthly' && (
              <>
                {' · '}
                Flota: <strong className="font-medium text-slate-800">{fleet || 'Todas'}</strong>
              </>
            )}
            {' · '}
            Subflotas: <strong className="font-medium text-slate-800">{showSubfleets ? 'Sí' : 'No'}</strong>
            {sliceMaxTripDate && (
              <>
                {' · '}
                Corte datos: <strong className="font-medium text-slate-800">{sliceMaxTripDate}</strong>
              </>
            )}
          </span>
        </div>

        {blocked && (
          <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
            Seleccione un país para cargar datos en vista semanal o diaria.
          </p>
        )}

        {err && (
          <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{err}</p>
        )}

        {!loading && !blocked && coverageSummary && (
          <div className="rounded-xl border border-emerald-200/80 bg-emerald-50/50 px-4 py-3 flex flex-wrap gap-x-6 gap-y-2 text-sm text-emerald-950">
            <span>
              <span className="text-emerald-700/80 font-medium">Cobertura</span>{' '}
              <strong className="tabular-nums text-lg">{coverageSummary.coverage_pct ?? '—'}%</strong>
            </span>
            <span>
              <span className="text-emerald-700/80 font-medium">Viajes mapeados</span>{' '}
              <strong className="tabular-nums">{coverageSummary.mapped_trips?.toLocaleString?.() ?? coverageSummary.mapped_trips ?? '—'}</strong>
            </span>
            <span>
              <span className="text-emerald-700/80 font-medium">No mapeados</span>{' '}
              <strong className="tabular-nums">{coverageSummary.unmapped_trips?.toLocaleString?.() ?? coverageSummary.unmapped_trips ?? '—'}</strong>
            </span>
            <span>
              <span className="text-emerald-700/80 font-medium">Total viajes</span>{' '}
              <strong className="tabular-nums">{coverageSummary.total_trips?.toLocaleString?.() ?? coverageSummary.total_trips ?? '—'}</strong>
            </span>
          </div>
        )}

        {loading && (
          <div className="flex items-center gap-2 text-sm text-slate-500 py-8 justify-center">
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" aria-hidden />
            Cargando datos…
          </div>
        )}

        {!loading && !blocked && matrix && sparkSection.length > 0 && (
          <section className="rounded-2xl border border-slate-200/90 bg-gradient-to-b from-slate-50/90 to-white p-5 sm:p-6 shadow-sm ring-1 ring-slate-900/5">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-500 mb-4">
              Totales agregados por KPI (misma lógica que fila TOTAL en la matriz)
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {sparkSection.map(({ kpi, option, snap, deltaText, rangeLabel }) => (
                <div
                  key={kpi.key}
                  className="rounded-xl border border-slate-200/80 bg-white p-3 shadow-sm ring-1 ring-slate-900/5 flex flex-col"
                >
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1 truncate" title={kpi.label}>
                    {kpi.label}
                  </p>
                  <p className="text-2xl font-bold text-slate-900 tabular-nums leading-tight">
                    {snap ? fmtValue(snap.lastVal, kpi.key) : '—'}
                  </p>
                  {deltaText && (
                    <p className="text-xs text-slate-600 mt-1 leading-snug" title={deltaText}>
                      {deltaText}
                    </p>
                  )}
                  <p className="text-[10px] text-slate-400 mt-1.5">{rangeLabel}</p>
                  <div className="h-[72px] w-full mt-2 flex-1 min-h-[72px]">
                    <ReactEChartsCore echarts={echarts} option={option} opts={echartsOpts} style={{ height: '100%', width: '100%' }} notMerge lazyUpdate />
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        <div className="rounded-xl border border-slate-200/90 bg-white p-4 sm:p-5 space-y-6 shadow-sm ring-1 ring-slate-900/5">
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex flex-col gap-1">
              <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">KPI — tendencia comparativa</span>
              <select
                className="uppercase border border-gray-200 rounded-md text-sm px-2.5 py-1.5 bg-white focus:ring-2 focus:ring-blue-400 outline-none tracking-wide min-w-[180px]"
                value={kpiKey}
                onChange={(e) => setKpiKey(e.target.value)}
              >
                {MATRIX_KPIS.map((k) => (
                  <option key={k.key} value={k.key}>
                    {k.label.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>
            <p className="text-xs text-slate-500 max-w-3xl leading-relaxed">
              Zoom con la rueda o el slider inferior; exporte PNG o restaure vista desde la caja de herramientas. La leyenda permite
              activar o desactivar series con un clic.
            </p>
          </div>

          {!loading && !blocked && mainLineOption && (
            <div className="h-[460px] w-full rounded-2xl border border-slate-200/80 bg-white p-2 ring-1 ring-slate-900/5">
              <ReactEChartsCore
                echarts={echarts}
                option={mainLineOption}
                opts={echartsOpts}
                style={{ height: '100%', width: '100%' }}
                notMerge
                lazyUpdate
              />
            </div>
          )}

          {!loading && !blocked && actualVsComparisonOption && (
            <div className="h-[340px] w-full rounded-2xl border border-slate-200/80 bg-white p-2 ring-1 ring-slate-900/5">
              <ReactEChartsCore
                echarts={echarts}
                option={actualVsComparisonOption}
                opts={echartsOpts}
                style={{ height: '100%', width: '100%' }}
                notMerge
                lazyUpdate
              />
            </div>
          )}

          {!loading && !blocked && unmappedLineOption && (
            <div className="h-[280px] w-full rounded-2xl border border-amber-100 bg-amber-50/20 p-2 ring-1 ring-amber-200/40">
              <ReactEChartsCore
                echarts={echarts}
                option={unmappedLineOption}
                opts={echartsOpts}
                style={{ height: '100%', width: '100%' }}
                notMerge
                lazyUpdate
              />
            </div>
          )}

          {!loading && !blocked && chartData.length === 0 && rows.length > 0 && (
            <p className="text-sm text-gray-500">No hay puntos para el KPI y series seleccionadas.</p>
          )}

          {!loading && !blocked && rows.length === 0 && !err && (
            <p className="text-sm text-gray-500">Sin datos para los filtros actuales.</p>
          )}

          {allSeriesKeys.length > 0 && (
            <div className="border-t border-slate-200/80 pt-4">
              <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest block mb-3">
                Series en el gráfico principal (máx. 8)
              </span>
              <div className="flex flex-wrap gap-2 max-h-52 overflow-y-auto pr-1">
                {allSeriesKeys.map((sk) => {
                  const lbl = seriesLabel(filteredRows.find((r) => seriesKey(r) === sk) || {})
                  const on = selectedKeys.includes(sk)
                  return (
                    <label
                      key={sk}
                      className={`inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide px-3 py-2 rounded-xl border cursor-pointer transition-all ${
                        on
                          ? 'border-indigo-400 bg-indigo-50/90 text-indigo-950 shadow-sm ring-1 ring-indigo-200/60'
                          : 'border-slate-200 bg-slate-50/50 text-slate-500 hover:border-slate-300 hover:bg-white'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={on}
                        onChange={() => toggleSeries(sk)}
                        className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 h-3.5 w-3.5"
                      />
                      <span className="max-w-[220px] truncate" title={lbl}>
                        {lbl}
                      </span>
                    </label>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {!loading && !blocked && cityBarOption && (
          <section className="rounded-2xl border border-slate-200/90 bg-white p-5 sm:p-6 shadow-sm ring-1 ring-slate-900/5 space-y-3">
            <div className="h-[420px] min-h-[240px] w-full">
              <ReactEChartsCore
                echarts={echarts}
                option={cityBarOption}
                opts={echartsOpts}
                style={{ height: '100%', width: '100%' }}
                notMerge
                lazyUpdate
              />
            </div>
          </section>
        )}

        {!loading && !blocked && heatmapPayload?.option && (
          <section className="rounded-2xl border border-slate-200/90 bg-white p-5 sm:p-6 shadow-sm ring-1 ring-slate-900/5 space-y-3">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-500">Heatmap — período × línea (top 14 por viajes)</h2>
              <div className="flex flex-col gap-1">
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">KPI color</span>
                <select
                  className="uppercase border border-slate-200 rounded-md text-xs px-2 py-1.5 bg-white"
                  value={heatmapKpi}
                  onChange={(e) => setHeatmapKpi(e.target.value)}
                >
                  {MATRIX_KPIS.map((k) => (
                    <option key={k.key} value={k.key}>
                      {k.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="h-[min(520px,70vh)] min-h-[420px] w-full">
              <ReactEChartsCore
                echarts={echarts}
                option={heatmapPayload.option}
                opts={echartsOpts}
                style={{ height: '100%', width: '100%' }}
                notMerge
                lazyUpdate
              />
            </div>
          </section>
        )}

        {!loading && !blocked && compositionOption && (
          <section className="rounded-2xl border border-slate-200/90 bg-white p-5 sm:p-6 shadow-sm ring-1 ring-slate-900/5 space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-slate-500">
              Composición por tajada — último período (viajes completados)
            </h2>
            <div className="h-[min(480px,calc(14*36px))] min-h-[200px] w-full">
              <ReactEChartsCore
                echarts={echarts}
                option={compositionOption}
                opts={echartsOpts}
                style={{ height: '100%', width: '100%' }}
                notMerge
                lazyUpdate
              />
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
