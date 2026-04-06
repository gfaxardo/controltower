/**
 * omniviewMatrixUtils.js
 *
 * Transformación lista → matriz pivot (ciudad → línea → periodos → métricas).
 * PRINCIPIO: solo reorganiza; NO recalcula métricas ni deltas.
 * Backend es source of truth.
 */

export const MATRIX_KPIS = [
  { key: 'commission_pct',    label: '%',          short: '%',       unit: 'ratio',   showAsPct: true  },
  { key: 'trips_completed',   label: 'Viajes',     short: 'Viajes',  unit: 'number',  showAsPct: false },
  { key: 'avg_ticket',        label: 'Ticket',     short: 'Ticket',  unit: 'currency',showAsPct: false },
  { key: 'active_drivers',    label: 'Conductores',short: 'Cond.',   unit: 'number',  showAsPct: false },
  { key: 'revenue_yego_net',  label: 'Revenue',    short: 'Rev.',    unit: 'currency',showAsPct: false },
  { key: 'cancel_rate_pct',   label: 'Cancel %',   short: 'Canc.',   unit: 'ratio',   showAsPct: true  },
  { key: 'trips_per_driver',  label: 'TPD',        short: 'TPD',     unit: 'number',  showAsPct: false },
]

export const KPI_KEYS = MATRIX_KPIS.map(k => k.key)

// ─── Period helpers ─────────────────────────────────────────────────────────
export function periodKey (row, grain) {
  if (grain === 'monthly') return row?.month ?? null
  if (grain === 'weekly') return row?.week_start ?? null
  return row?.trip_date ?? null
}

const MONTH_SHORT = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
const DAYS_ES = ['DOMINGO', 'LUNES', 'MARTES', 'MIÉRCOLES', 'JUEVES', 'VIERNES', 'SÁBADO']
const DAYS_ES_SHORT = ['DOM', 'LUN', 'MAR', 'MIÉ', 'JUE', 'VIE', 'SÁB']

export function periodLabel (key, grain) {
  if (!key) return '—'
  if (grain === 'monthly') {
    const d = new Date(key + 'T00:00:00')
    if (isNaN(d)) return String(key).slice(0, 7)
    return `${MONTH_SHORT[d.getMonth()]} ${d.getFullYear()}`
  }
  if (grain === 'weekly') {
    const d = new Date(key + 'T00:00:00')
    if (isNaN(d)) return String(key).slice(0, 10)
    return `S${getISOWeek(d)}-${getISOWeekYear(d)}`
  }
  const dd = new Date(key + 'T00:00:00')
  if (isNaN(dd)) return String(key).slice(0, 10)
  return `${DAYS_ES[dd.getDay()]} S${getISOWeek(dd)}-${getISOWeekYear(dd)}`
}

export function periodLabelShort (key, grain) {
  if (!key) return '—'
  if (grain === 'monthly') {
    const d = new Date(key + 'T00:00:00')
    if (isNaN(d)) return String(key).slice(5, 7)
    return MONTH_SHORT[d.getMonth()]
  }
  if (grain === 'weekly') {
    const d = new Date(key + 'T00:00:00')
    if (isNaN(d)) return key
    return `S${getISOWeek(d)}-${getISOWeekYear(d)}`
  }
  const dd = new Date(key + 'T00:00:00')
  if (isNaN(dd)) return String(key).slice(5, 10)
  return `${DAYS_ES_SHORT[dd.getDay()]} S${getISOWeek(dd)}`
}

function getISOWeek (d) {
  const copy = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  copy.setUTCDate(copy.getUTCDate() + 4 - (copy.getUTCDay() || 7))
  const yearStart = new Date(Date.UTC(copy.getUTCFullYear(), 0, 1))
  return Math.ceil(((copy - yearStart) / 86400000 + 1) / 7)
}

function getISOWeekYear (d) {
  const copy = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  copy.setUTCDate(copy.getUTCDate() + 4 - (copy.getUTCDay() || 7))
  return copy.getUTCFullYear()
}

// ─── Period State ─────────────────────────────────────────────────────────
export const PERIOD_STATES = {
  CLOSED: 'CLOSED',
  PARTIAL: 'PARTIAL',
  CURRENT_DAY: 'CURRENT_DAY',
  STALE: 'STALE',
  FUTURE: 'FUTURE',
}

const STATE_LABELS = {
  CLOSED: 'Cerrado',
  PARTIAL: 'Parcial',
  CURRENT_DAY: 'Hoy',
  STALE: 'Stale',
  FUTURE: 'Futuro',
}

export function periodStateLabel (state) {
  return STATE_LABELS[state] || ''
}

export function computePeriodStates (allPeriods, grain, maxDataDate = null) {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const todayStr = today.toISOString().slice(0, 10)
  const maxData = maxDataDate ? new Date(maxDataDate + 'T00:00:00') : null
  const states = new Map()

  for (const pk of allPeriods) {
    const d = new Date(pk + 'T00:00:00')
    if (isNaN(d)) { states.set(pk, PERIOD_STATES.CLOSED); continue }

    let state = PERIOD_STATES.CLOSED

    if (grain === 'monthly') {
      const monthStart = new Date(d.getFullYear(), d.getMonth(), 1)
      const nextMonth = new Date(d.getFullYear(), d.getMonth() + 1, 1)
      if (today >= monthStart && today < nextMonth) {
        state = PERIOD_STATES.PARTIAL
      } else if (today < monthStart) {
        state = PERIOD_STATES.FUTURE
      } else if (maxData) {
        const lastDay = new Date(nextMonth - 1)
        if (maxData < lastDay) state = PERIOD_STATES.STALE
      }
    } else if (grain === 'weekly') {
      const weekStart = new Date(d)
      const weekEnd = new Date(weekStart)
      weekEnd.setDate(weekEnd.getDate() + 7)
      if (today >= weekStart && today < weekEnd) {
        state = PERIOD_STATES.PARTIAL
      } else if (today < weekStart) {
        state = PERIOD_STATES.FUTURE
      } else if (maxData) {
        const lastDay = new Date(weekEnd - 86400000)
        if (maxData < lastDay) state = PERIOD_STATES.STALE
      }
    } else {
      if (pk === todayStr) {
        state = PERIOD_STATES.CURRENT_DAY
      } else if (d > today) {
        state = PERIOD_STATES.FUTURE
      } else if (maxData && d > maxData) {
        state = PERIOD_STATES.STALE
      }
    }

    states.set(pk, state)
  }
  return states
}

export function periodElapsedDays (pk, grain) {
  const d = new Date(pk + 'T00:00:00')
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  if (grain === 'monthly') return Math.max(1, Math.floor((today - d) / 86400000) + 1)
  if (grain === 'weekly') return Math.min(7, Math.max(1, Math.floor((today - d) / 86400000) + 1))
  return 1
}

export function periodTotalDays (pk, grain) {
  if (grain === 'weekly') return 7
  if (grain === 'daily') return 1
  const d = new Date(pk + 'T00:00:00')
  return new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate()
}

// ─── Derived metrics ────────────────────────────────────────────────────────
function enrichRow (row) {
  const trips = Number(row.trips_completed) || 0
  const cancelled = Number(row.trips_cancelled) || 0
  const drivers = Number(row.active_drivers) || 0
  const total = trips + cancelled
  if (row.cancel_rate_pct == null && total > 0) row.cancel_rate_pct = cancelled / total
  if (row.trips_per_driver == null && drivers > 0) row.trips_per_driver = trips / drivers
  return row
}

// ─── Build matrix pivot ─────────────────────────────────────────────────────
export function buildMatrix (rows, grain) {
  const cities = new Map()
  const periodSet = new Set()
  const totalsBucket = new Map()
  const comparisonTotalsBucket = new Map()
  const comparisonMeta = new Map()

  for (const raw of rows) {
    const r = enrichRow({ ...raw })
    const pk = periodKey(r, grain)
    if (!pk) continue
    periodSet.add(pk)

    const cityKey = `${r.country || '—'}::${r.city || '—'}`
    if (!cities.has(cityKey)) {
      cities.set(cityKey, { country: r.country || '—', city: r.city || '—', lines: new Map() })
    }
    const cityBucket = cities.get(cityKey)

    const sliceKey = `${r.business_slice_name || '—'}::${r.fleet_display_name || '—'}::${r.is_subfleet ? '1' : '0'}::${r.subfleet_name || ''}`
    if (!cityBucket.lines.has(sliceKey)) {
      cityBucket.lines.set(sliceKey, {
        business_slice_name: r.business_slice_name || '—',
        fleet_display_name: r.fleet_display_name || '—',
        is_subfleet: !!r.is_subfleet,
        subfleet_name: r.subfleet_name || '',
        periods: new Map(),
      })
    }
    const lineBucket = cityBucket.lines.get(sliceKey)

    const metrics = {}
    for (const { key } of MATRIX_KPIS) { metrics[key] = r[key] ?? null }
    lineBucket.periods.set(pk, { metrics, raw: r })

    if (!totalsBucket.has(pk)) {
      totalsBucket.set(pk, { _trips: 0, _cancelled: 0, _revenue: 0, _drivers: 0, _ticketSum: 0, _ticketN: 0, _commSum: 0, _commN: 0 })
    }
    const tb = totalsBucket.get(pk)
    tb._trips += Number(r.trips_completed) || 0
    tb._cancelled += Number(r.trips_cancelled) || 0
    tb._revenue += Number(r.revenue_yego_net) || 0
    tb._drivers += Number(r.active_drivers) || 0
    if (r.avg_ticket != null) { tb._ticketSum += Number(r.avg_ticket); tb._ticketN += 1 }
    if (r.commission_pct != null) { tb._commSum += Number(r.commission_pct); tb._commN += 1 }

    const cmp = r.comparison_context
    const baseline = cmp?.baseline_metrics
    if (cmp && !comparisonMeta.has(pk)) {
      comparisonMeta.set(pk, {
        comparison_mode: cmp.comparison_mode ?? null,
        is_partial_equivalent: !!cmp.is_partial_equivalent,
        is_operationally_aligned: !!cmp.is_operationally_aligned,
        is_preliminary: !!cmp.is_preliminary,
        period_state: cmp.period_state ?? null,
        current_range_start: cmp.current_range_start ?? null,
        current_cutoff_date: cmp.current_cutoff_date ?? null,
        previous_equivalent_range_start: cmp.previous_equivalent_range_start ?? null,
        previous_equivalent_cutoff_date: cmp.previous_equivalent_cutoff_date ?? null,
        baseline_period_key: cmp.baseline_period_key ?? null,
      })
    }
    if (baseline) {
      if (!comparisonTotalsBucket.has(pk)) {
        comparisonTotalsBucket.set(pk, { _trips: 0, _cancelled: 0, _revenue: 0, _drivers: 0, _ticketSum: 0, _ticketN: 0, _commSum: 0, _commN: 0 })
      }
      const cb = comparisonTotalsBucket.get(pk)
      cb._trips += Number(baseline.trips_completed) || 0
      cb._cancelled += Number(baseline.trips_cancelled) || 0
      cb._revenue += Number(baseline.revenue_yego_net) || 0
      cb._drivers += Number(baseline.active_drivers) || 0
      if (baseline.avg_ticket != null) { cb._ticketSum += Number(baseline.avg_ticket); cb._ticketN += 1 }
      if (baseline.commission_pct != null) { cb._commSum += Number(baseline.commission_pct); cb._commN += 1 }
    }
  }

  const allPeriods = [...periodSet].sort()

  const totals = new Map()
  const comparisonTotals = new Map()
  const buildTotalsFromBucket = (bucket) => {
    const total = bucket._trips + bucket._cancelled
    return {
      trips_completed: bucket._trips,
      revenue_yego_net: bucket._revenue,
      active_drivers: bucket._drivers,
      commission_pct: bucket._commN > 0 ? bucket._commSum / bucket._commN : null,
      avg_ticket: bucket._ticketN > 0 ? bucket._ticketSum / bucket._ticketN : null,
      cancel_rate_pct: total > 0 ? bucket._cancelled / total : null,
      trips_per_driver: bucket._drivers > 0 ? bucket._trips / bucket._drivers : null,
    }
  }
  for (const [pk, tb] of totalsBucket) {
    totals.set(pk, buildTotalsFromBucket(tb))
  }
  for (const [pk, tb] of comparisonTotalsBucket) {
    comparisonTotals.set(pk, buildTotalsFromBucket(tb))
  }

  return { cities, allPeriods, totals, comparisonTotals, comparisonMeta }
}

function _comparisonMetaForDelta (cmp, isPartialComparison, hasEquivalentBaseline = null) {
  const equivalent = hasEquivalentBaseline ?? !!(cmp?.baseline_metrics && (cmp?.is_partial_equivalent || cmp?.is_operationally_aligned))
  return {
    comparison_mode: cmp?.comparison_mode ?? null,
    is_partial_equivalent: !!cmp?.is_partial_equivalent,
    is_operationally_aligned: !!cmp?.is_operationally_aligned,
    is_preliminary: !!cmp?.is_preliminary,
    is_equivalent_comparison: equivalent,
    isPartialComparison,
    current_range_start: cmp?.current_range_start ?? null,
    current_cutoff_date: cmp?.current_cutoff_date ?? null,
    previous_equivalent_range_start: cmp?.previous_equivalent_range_start ?? null,
    previous_equivalent_cutoff_date: cmp?.previous_equivalent_cutoff_date ?? null,
    baseline_period_key: cmp?.baseline_period_key ?? null,
  }
}

// ─── Deltas ─────────────────────────────────────────────────────────────────
function _isPartialState (s) {
  return s === PERIOD_STATES.PARTIAL || s === PERIOD_STATES.CURRENT_DAY
}

export function computeDeltas (linePeriods, allPeriods, periodStates) {
  const result = new Map()
  for (let i = 0; i < allPeriods.length; i++) {
    const pk = allPeriods[i]
    const prevPk = i > 0 ? allPeriods[i - 1] : null
    const curr = linePeriods.get(pk)
    const prev = prevPk ? linePeriods.get(prevPk) : null
    if (!curr) { result.set(pk, null); continue }

    const curState = periodStates?.get(pk)
    const prevState = prevPk ? periodStates?.get(prevPk) : null
    const cmp = curr.raw?.comparison_context || null
    const hasEquivalentBaseline = !!(cmp?.baseline_metrics && (cmp?.is_partial_equivalent || cmp?.is_operationally_aligned))
    const isPartialComparison = !!(periodStates && _isPartialState(curState) && prevState === PERIOD_STATES.CLOSED && !hasEquivalentBaseline)
    const meta = _comparisonMetaForDelta(cmp, isPartialComparison, hasEquivalentBaseline)

    const deltas = {}
    for (const { key, showAsPct } of MATRIX_KPIS) {
      const cv = curr.metrics[key]
      const pv = hasEquivalentBaseline ? cmp?.baseline_metrics?.[key] : prev?.metrics?.[key]
      if (cv == null || pv == null || pv === 0) {
        deltas[key] = { value: cv, delta_pct: null, delta_abs: null, signal: 'neutral', previous: pv, ...meta }
      } else {
        const diff = Number(cv) - Number(pv)
        const pct = Number(pv) !== 0 ? diff / Math.abs(Number(pv)) : null
        deltas[key] = {
          value: cv,
          previous: pv,
          delta_pct: pct,
          delta_abs: showAsPct ? diff : null,
          delta_abs_pp: showAsPct ? diff * 100 : null,
          signal: diff > 0 ? 'up' : diff < 0 ? 'down' : 'neutral',
          ...meta,
        }
      }
    }
    result.set(pk, deltas)
  }
  return result
}

// ─── Totals deltas (for frozen row) ─────────────────────────────────────────
export function computeTotalsDeltas (totals, allPeriods, periodStates, comparisonTotals, comparisonMeta) {
  const result = new Map()
  for (let i = 0; i < allPeriods.length; i++) {
    const pk = allPeriods[i]
    const prevPk = i > 0 ? allPeriods[i - 1] : null
    const curr = totals.get(pk)
    const prev = prevPk ? totals.get(prevPk) : null
    if (!curr) { result.set(pk, null); continue }

    const curState = periodStates?.get(pk)
    const prevState = prevPk ? periodStates?.get(prevPk) : null
    const cmp = comparisonMeta?.get(pk) || null
    const hasEquivalentBaseline = !!(comparisonTotals?.get(pk) && (cmp?.is_partial_equivalent || cmp?.is_operationally_aligned))
    const isPartialComparison = !!(periodStates && _isPartialState(curState) && prevState === PERIOD_STATES.CLOSED && !hasEquivalentBaseline)
    const meta = _comparisonMetaForDelta(cmp, isPartialComparison, hasEquivalentBaseline)

    const deltas = {}
    for (const { key, showAsPct } of MATRIX_KPIS) {
      const cv = curr[key]
      const pv = hasEquivalentBaseline ? comparisonTotals?.get(pk)?.[key] : prev?.[key]
      if (cv == null || pv == null || pv === 0) {
        deltas[key] = { value: cv, delta_pct: null, delta_abs: null, signal: 'neutral', previous: pv, ...meta }
      } else {
        const diff = Number(cv) - Number(pv)
        const pct = Number(pv) !== 0 ? diff / Math.abs(Number(pv)) : null
        deltas[key] = {
          value: cv, previous: pv, delta_pct: pct,
          delta_abs: showAsPct ? diff : null,
          delta_abs_pp: showAsPct ? diff * 100 : null,
          signal: diff > 0 ? 'up' : diff < 0 ? 'down' : 'neutral',
          ...meta,
        }
      }
    }
    result.set(pk, deltas)
  }
  return result
}

// ─── Executive KPIs ─────────────────────────────────────────────────────────
export function aggregateExecutiveKpis (rows) {
  let trips = 0, cancelled = 0, revenue = 0, drivers = 0
  let ticketSum = 0, ticketN = 0, commSum = 0, commN = 0
  for (const r of rows) {
    trips += Number(r.trips_completed) || 0
    cancelled += Number(r.trips_cancelled) || 0
    revenue += Number(r.revenue_yego_net) || 0
    drivers += Number(r.active_drivers) || 0
    if (r.avg_ticket != null) { ticketSum += Number(r.avg_ticket); ticketN += 1 }
    if (r.commission_pct != null) { commSum += Number(r.commission_pct); commN += 1 }
  }
  const total = trips + cancelled
  return {
    trips_completed: trips, revenue_yego_net: revenue,
    commission_pct: commN > 0 ? commSum / commN : null,
    active_drivers: drivers,
    cancel_rate_pct: total > 0 ? cancelled / total : null,
    trips_per_driver: drivers > 0 ? trips / drivers : null,
  }
}

// ─── Sort helpers ───────────────────────────────────────────────────────────
export const SORT_OPTIONS = [
  { id: 'alpha', label: 'A → Z' },
  { id: 'impact_desc', label: 'Impacto ↓' },
  { id: 'revenue_desc', label: 'Revenue ↓' },
  { id: 'trips_desc', label: 'Viajes ↓' },
]

export function sortLineEntries (entries, sortKey, opts = {}) {
  const { lineImpactMap, cityKey } = opts || {}
  if (sortKey === 'impact_desc' && lineImpactMap && cityKey != null) {
    return [...entries].sort((a, b) => {
      const ia = lineImpactMap.get(`${cityKey}::${a[0]}`) ?? 0
      const ib = lineImpactMap.get(`${cityKey}::${b[0]}`) ?? 0
      if (ib !== ia) return ib - ia
      return a[1].business_slice_name.localeCompare(b[1].business_slice_name)
    })
  }
  if (sortKey === 'revenue_desc') {
    return [...entries].sort((a, b) => {
      const ra = sumMetric(a[1].periods, 'revenue_yego_net')
      const rb = sumMetric(b[1].periods, 'revenue_yego_net')
      return rb - ra
    })
  }
  if (sortKey === 'trips_desc') {
    return [...entries].sort((a, b) => {
      const ta = sumMetric(a[1].periods, 'trips_completed')
      const tb = sumMetric(b[1].periods, 'trips_completed')
      return tb - ta
    })
  }
  return [...entries].sort((a, b) => a[1].business_slice_name.localeCompare(b[1].business_slice_name))
}

function sumMetric (periods, key) {
  let s = 0
  for (const [, p] of periods) { s += Number(p.metrics[key]) || 0 }
  return s
}

// ─── Format helpers ─────────────────────────────────────────────────────────
export function fmtValue (v, kpiKey) {
  if (v == null) return '—'
  const n = Number(v)
  if (!isFinite(n)) return '—'
  const kpi = MATRIX_KPIS.find(k => k.key === kpiKey)
  if (kpi?.showAsPct) return `${(n * 100).toFixed(1)}%`
  if (kpi?.unit === 'currency') {
    const abs = Math.abs(n)
    const sign = n < 0 ? '-' : ''
    return abs >= 1e6
      ? `${sign}${(abs / 1e6).toFixed(1)}M`
      : abs >= 1e3
        ? `${sign}${(abs / 1e3).toFixed(1)}K`
        : n.toLocaleString(undefined, { maximumFractionDigits: 1 })
  }
  return n.toLocaleString(undefined, { maximumFractionDigits: 1 })
}

export function fmtRaw (v) {
  if (v == null) return '—'
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })
}

export function fmtDelta (delta) {
  if (!delta || delta.delta_pct == null) return null
  const pct = (delta.delta_pct * 100).toFixed(1)
  const sign = delta.delta_pct > 0 ? '+' : ''
  return `${sign}${pct}%`
}

export function signalColor (signal) {
  if (signal === 'up') return '#22c55e'
  if (signal === 'down') return '#ef4444'
  return '#9ca3af'
}

const INVERTED_SIGNAL_KPIS = new Set(['cancel_rate_pct', 'trips_cancelled'])

export function signalColorForKpi (signal, kpiKey) {
  if (INVERTED_SIGNAL_KPIS.has(kpiKey)) {
    if (signal === 'up') return '#ef4444'
    if (signal === 'down') return '#22c55e'
    return '#9ca3af'
  }
  return signalColor(signal)
}

export function signalArrow (signal) {
  if (signal === 'up') return '▲'
  if (signal === 'down') return '▼'
  return '—'
}

export function describeComparison (delta, grain) {
  if (!delta) return null
  if (delta.is_equivalent_comparison) {
    if (delta.comparison_mode === 'weekly_partial_equivalent') {
      return `Parcial equivalente · ${delta.current_range_start} → ${delta.current_cutoff_date} vs ${delta.previous_equivalent_range_start} → ${delta.previous_equivalent_cutoff_date}`
    }
    if (delta.comparison_mode === 'monthly_partial_equivalent') {
      return `Parcial equivalente · ${delta.current_range_start} → ${delta.current_cutoff_date} vs ${delta.previous_equivalent_range_start} → ${delta.previous_equivalent_cutoff_date}`
    }
    if (delta.comparison_mode === 'daily_same_weekday') {
      return delta.is_preliminary
        ? `Mismo día semana anterior · día actual en curso`
        : `Mismo día semana anterior · ${delta.previous_equivalent_range_start}`
    }
  }
  if (delta.isPartialComparison) {
    return 'Comparativo parcial vs periodo previo completo'
  }
  if (grain === 'daily') return 'Comparativo diario vs periodo operativo equivalente'
  return 'Comparativo vs periodo anterior'
}

// ─── Tooltip builder ────────────────────────────────────────────────────────
export function buildCellTooltip (kpi, delta, cityName, lineName, periodLbl, periodState, grain) {
  const parts = [`${kpi.label} — ${lineName}`, `${cityName} · ${periodLbl}`]
  if (periodState) {
    const sl = periodStateLabel(periodState)
    if (sl) parts.push(`Estado: ${sl}`)
  }
  if (delta) {
    parts.push(`Actual: ${fmtRaw(delta.value)}`)
    if (delta.previous != null) parts.push(`Anterior: ${fmtRaw(delta.previous)}`)
    const dt = fmtDelta(delta)
    if (dt) parts.push(`Δ: ${signalArrow(delta.signal)} ${dt}`)
    if (delta.delta_abs_pp != null) parts.push(`Δ pp: ${delta.delta_abs_pp.toFixed(2)}`)
    const desc = describeComparison(delta, grain)
    if (desc) parts.push(desc)
  }
  return parts.join('\n')
}

// ─── CSV export ─────────────────────────────────────────────────────────────
export function exportMatrixCsv (matrix, grain) {
  const { cities, allPeriods, totals } = matrix
  const rows = []

  const h1 = ['Ciudad', 'Línea']
  for (const pk of allPeriods) {
    h1.push(periodLabel(pk, grain))
    for (let i = 1; i < MATRIX_KPIS.length; i++) h1.push('')
  }
  rows.push(h1)

  const h2 = ['', '']
  for (const _pk of allPeriods) {
    for (const kpi of MATRIX_KPIS) h2.push(kpi.label)
  }
  rows.push(h2)

  for (const [, cityData] of [...cities.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
    for (const [, lineData] of [...cityData.lines.entries()].sort((a, b) => a[1].business_slice_name.localeCompare(b[1].business_slice_name))) {
      const row = [cityData.city, lineData.business_slice_name]
      for (const pk of allPeriods) {
        const pd = lineData.periods.get(pk)
        for (const kpi of MATRIX_KPIS) { row.push(pd?.metrics?.[kpi.key] ?? '') }
      }
      rows.push(row)
    }
  }

  const totRow = ['TOTAL', '']
  for (const pk of allPeriods) {
    const t = totals.get(pk) || {}
    for (const kpi of MATRIX_KPIS) { totRow.push(t[kpi.key] ?? '') }
  }
  rows.push(totRow)

  return rows.map(r =>
    r.map(v => {
      const s = String(v === null || v === undefined ? '' : v)
      return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${s.replace(/"/g, '""')}"` : s
    }).join(',')
  ).join('\n')
}

export function downloadCsv (csv, filename) {
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// ─── localStorage persistence ───────────────────────────────────────────────
const LS_KEY = 'yego_omniview_matrix'

export function loadPersistedState () {
  try {
    const s = localStorage.getItem(LS_KEY)
    return s ? JSON.parse(s) : null
  } catch { return null }
}

export function persistState (state) {
  try { localStorage.setItem(LS_KEY, JSON.stringify(state)) } catch {}
}
