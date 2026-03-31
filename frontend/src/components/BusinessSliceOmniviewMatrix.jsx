/**
 * BusinessSliceOmniviewMatrix — vista principal BI premium (full-width, dual density).
 *
 * 4 bloques:
 *   1. Header de contexto y controles (filtros + grano + densidad)
 *   2. Strip ejecutivo de KPIs
 *   3. Matriz principal tipo Control Tower
 *   4. Panel lateral / Inspector de detalle
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  getBusinessSliceFilters,
  getBusinessSliceMonthly,
  getBusinessSliceWeekly,
  getBusinessSliceDaily,
} from '../services/api.js'
import {
  buildMatrix,
  aggregateExecutiveKpis,
  MATRIX_KPIS,
  fmtValue,
  signalColor,
  signalArrow,
  fmtDelta,
} from './omniview/omniviewMatrixUtils.js'
import BusinessSliceOmniviewMatrixTable from './BusinessSliceOmniviewMatrixTable.jsx'
import BusinessSliceOmniviewInspector from './BusinessSliceOmniviewInspector.jsx'

const GRAINS = [
  { id: 'monthly', label: 'Mensual' },
  { id: 'weekly', label: 'Semanal' },
  { id: 'daily', label: 'Diario' },
]

const btnCls = (active) =>
  `px-2.5 py-1 rounded-md text-xs font-semibold transition-colors ${
    active
      ? 'bg-slate-800 text-white shadow-sm'
      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
  }`

const densityCls = (active) =>
  `px-2 py-0.5 rounded text-[11px] font-medium transition-colors ${
    active
      ? 'bg-slate-700 text-white'
      : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
  }`

const selectCls = 'border border-gray-300 rounded-md text-xs px-2 py-1 bg-white focus:ring-1 focus:ring-blue-400 focus:border-blue-400 outline-none'

export default function BusinessSliceOmniviewMatrix () {
  const [grain, setGrain] = useState('monthly')
  const [compact, setCompact] = useState(false)
  const [filtersMeta, setFiltersMeta] = useState(null)
  const [country, setCountry] = useState('')
  const [city, setCity] = useState('')
  const [businessSlice, setBusinessSlice] = useState('')
  const [fleet, setFleet] = useState('')
  const [showSubfleets, setShowSubfleets] = useState(true)
  const [year, setYear] = useState(new Date().getFullYear())
  const [month, setMonth] = useState('')
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)
  const [selectedCell, setSelectedCell] = useState(null)
  const [selection, setSelection] = useState(null)

  const needsCountry = grain === 'weekly' || grain === 'daily'
  const blockedByCountry = needsCountry && !country

  useEffect(() => {
    getBusinessSliceFilters()
      .then(setFiltersMeta)
      .catch(() => {})
  }, [])

  const countries = filtersMeta?.countries || []
  const allCities = filtersMeta?.cities || []
  const citiesForCountry = useMemo(() => {
    if (!country) return allCities
    return allCities
  }, [allCities, country])
  const slices = filtersMeta?.business_slices || []
  const fleets = filtersMeta?.fleets || []

  const loadData = useCallback(async () => {
    if (blockedByCountry) { setRows([]); setErr(null); return }
    setLoading(true)
    setErr(null)
    try {
      const params = {}
      if (country) params.country = country
      if (city) params.city = city
      if (businessSlice) params.business_slice = businessSlice
      if (year != null && year !== '') params.year = Number(year)
      if (month) params.month = Number(month)
      if (grain === 'monthly') {
        if (fleet) params.fleet = fleet
      }

      let res
      if (grain === 'weekly') res = await getBusinessSliceWeekly(params)
      else if (grain === 'daily') res = await getBusinessSliceDaily(params)
      else res = await getBusinessSliceMonthly(params)

      let data = Array.isArray(res?.data) ? res.data : (Array.isArray(res) ? res : [])
      if (!showSubfleets) data = data.filter((r) => !r.is_subfleet)
      setRows(data)
    } catch (e) {
      setErr(e?.response?.data?.detail || e.message || 'Error cargando datos')
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [grain, country, city, businessSlice, fleet, showSubfleets, year, month, blockedByCountry])

  useEffect(() => { loadData() }, [loadData])

  const matrix = useMemo(() => buildMatrix(rows, grain), [rows, grain])
  const execKpis = useMemo(() => aggregateExecutiveKpis(rows), [rows])

  const handleCellClick = useCallback((cellInfo) => {
    setSelectedCell((prev) => (prev === cellInfo.id ? null : cellInfo.id))
    setSelection((prev) => (prev?.id === cellInfo.id ? null : cellInfo))
  }, [])

  const execCards = useMemo(() => {
    const cards = [
      { key: 'trips_completed', label: 'Trips completed' },
      { key: 'revenue_yego_net', label: 'Revenue YEGO net' },
      { key: 'commission_pct', label: 'Commission %' },
      { key: 'active_drivers', label: 'Active drivers' },
      { key: 'cancel_rate_pct', label: 'Cancel rate %' },
      { key: 'trips_per_driver', label: 'Trips / driver' },
    ]

    const p = matrix.allPeriods
    const currPk = p.length > 0 ? p[p.length - 1] : null
    const prevPk = p.length > 1 ? p[p.length - 2] : null
    const currTotals = currPk ? matrix.totals.get(currPk) : null
    const prevTotals = prevPk ? matrix.totals.get(prevPk) : null

    return cards.map((c) => {
      const val = execKpis[c.key]
      let delta = null
      let signal = 'neutral'
      if (currTotals && prevTotals) {
        const cv = currTotals[c.key]
        const pv = prevTotals[c.key]
        if (cv != null && pv != null && pv !== 0) {
          const diff = cv - pv
          delta = { delta_pct: diff / Math.abs(pv), signal: diff > 0 ? 'up' : diff < 0 ? 'down' : 'neutral' }
          signal = delta.signal
        }
      }
      return { ...c, val, delta, signal }
    })
  }, [execKpis, matrix])

  // ═══════════════════════════════════════════════════════════════════════════
  // RENDER — full-width breakout from parent container
  // ═══════════════════════════════════════════════════════════════════════════
  return (
    <div
      className="relative"
      style={{ width: '100vw', left: '50%', right: '50%', marginLeft: '-50vw', marginRight: '-50vw' }}
    >
      <div className="px-4 md:px-6 lg:px-8 space-y-3">
        {/* ── BLOQUE 1: Header de controles (compacto, horizontal) ────── */}
        <div className="rounded-lg border border-gray-200 bg-white shadow-sm px-4 py-2.5">
          <div className="flex flex-wrap items-end gap-x-3 gap-y-2">
            <div>
              <label className="block text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-0.5">Grano</label>
              <div className="flex gap-0.5">
                {GRAINS.map((g) => (
                  <button key={g.id} type="button" className={btnCls(grain === g.id)} onClick={() => setGrain(g.id)}>
                    {g.label}
                  </button>
                ))}
              </div>
            </div>

            <FilterSelect label="País" value={country} onChange={setCountry} options={countries} placeholder="Todos" required={needsCountry} />
            <FilterSelect label="Ciudad" value={city} onChange={setCity} options={citiesForCountry} placeholder="Todas" />
            <FilterSelect label="Tajada" value={businessSlice} onChange={setBusinessSlice} options={slices} placeholder="Todas" />
            {grain === 'monthly' && (
              <FilterSelect label="Flota" value={fleet} onChange={setFleet} options={fleets} placeholder="Todas" />
            )}

            <div>
              <label className="block text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-0.5">Año</label>
              <input
                type="number"
                className={selectCls + ' w-[68px]'}
                value={year}
                onChange={(e) => setYear(e.target.value === '' ? '' : Number(e.target.value))}
              />
            </div>

            {(grain === 'monthly' || grain === 'daily') && (
              <div>
                <label className="block text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-0.5">Mes</label>
                <select className={selectCls + ' w-[68px]'} value={month} onChange={(e) => setMonth(e.target.value)}>
                  <option value="">—</option>
                  {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>
            )}

            <label className="flex items-center gap-1 text-[11px] text-gray-500 cursor-pointer select-none pb-0.5">
              <input
                type="checkbox"
                checked={showSubfleets}
                onChange={(e) => setShowSubfleets(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 h-3 w-3"
              />
              Subflotas
            </label>

            {/* ── Density toggle ─────────────────────────────────── */}
            <div className="ml-auto flex items-end gap-1 pb-0.5">
              <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider mr-1">Densidad</span>
              <button type="button" className={densityCls(!compact)} onClick={() => setCompact(false)}>Cómodo</button>
              <button type="button" className={densityCls(compact)} onClick={() => setCompact(true)}>Compacto</button>
            </div>
          </div>

          {blockedByCountry && (
            <div className="mt-2 rounded border border-amber-300 bg-amber-50 px-3 py-1.5 text-[11px] text-amber-900 font-medium">
              Selecciona un <strong>país</strong> para habilitar análisis semanal o diario.
            </div>
          )}
        </div>

        {/* ── BLOQUE 2: Strip ejecutivo de KPIs ─────────────────────── */}
        {!blockedByCountry && rows.length > 0 && (
          <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
            {execCards.map((card) => (
              <div
                key={card.key}
                className={`rounded-lg border border-gray-200 bg-white shadow-sm ${compact ? 'px-3 py-1.5' : 'px-3 py-2.5'}`}
              >
                <p className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider leading-tight">{card.label}</p>
                <p className={`font-bold text-gray-900 leading-tight ${compact ? 'text-base' : 'text-lg'}`}>
                  {fmtValue(card.val, card.key)}
                </p>
                {card.delta && (
                  <p className="text-[11px] font-semibold leading-tight" style={{ color: signalColor(card.signal) }}>
                    {signalArrow(card.signal)} {fmtDelta(card.delta)}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {err && !blockedByCountry && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-xs text-red-800">{String(err)}</div>
        )}

        {loading && (
          <div className="flex items-center gap-2 text-xs text-gray-500 py-6 justify-center">
            <span className="inline-block w-3.5 h-3.5 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
            Cargando datos…
          </div>
        )}

        {/* ── BLOQUES 3 + 4: Matrix + Inspector ─────────────────────── */}
        {!loading && !blockedByCountry && (
          <div className="flex gap-3 items-start">
            <div className="flex-1 min-w-0">
              <BusinessSliceOmniviewMatrixTable
                matrix={matrix}
                grain={grain}
                compact={compact}
                onCellClick={handleCellClick}
                selectedCell={selectedCell}
              />
            </div>
            <BusinessSliceOmniviewInspector
              selection={selection}
              grain={grain}
              compact={compact}
              onClose={() => { setSelection(null); setSelectedCell(null) }}
            />
          </div>
        )}
      </div>
    </div>
  )
}

function FilterSelect ({ label, value, onChange, options, placeholder, required }) {
  return (
    <div>
      <label className="block text-[10px] font-semibold text-gray-400 uppercase tracking-wider mb-0.5">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      <select
        className={`border rounded-md text-xs px-2 py-1 bg-white focus:ring-1 focus:ring-blue-400 focus:border-blue-400 outline-none min-w-[100px] ${
          required && !value ? 'border-amber-400 bg-amber-50' : 'border-gray-300'
        }`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{placeholder}</option>
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    </div>
  )
}
