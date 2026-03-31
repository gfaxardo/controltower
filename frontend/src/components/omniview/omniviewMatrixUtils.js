/**
 * omniviewMatrixUtils.js
 *
 * Transformación de la respuesta plana del API (lista de filas) a una estructura
 * jerárquica pivot (ciudad → línea de negocio → periodos → métricas) lista para
 * renderizar la Omniview Matrix.
 *
 * PRINCIPIO: solo reorganiza; NO recalcula métricas ni deltas.
 * Backend es source of truth para señales, flags y comparativos.
 */

// ─── KPIs obligatorios por celda de periodo ─────────────────────────────────
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

// ─── Extracción de la clave temporal según grano ────────────────────────────
export function periodKey (row, grain) {
  if (grain === 'monthly') return row?.month ?? null
  if (grain === 'weekly') return row?.week_start ?? null
  return row?.trip_date ?? null
}

// ─── Label legible para un periodo ──────────────────────────────────────────
const MONTH_SHORT = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

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
    return `S${getISOWeek(d)} ${d.getFullYear()}`
  }
  return String(key).slice(0, 10)
}

function getISOWeek (d) {
  const copy = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  copy.setUTCDate(copy.getUTCDate() + 4 - (copy.getUTCDay() || 7))
  const yearStart = new Date(Date.UTC(copy.getUTCFullYear(), 0, 1))
  return Math.ceil(((copy - yearStart) / 86400000 + 1) / 7)
}

// ─── Métricas derivadas que backend no devuelve directamente ────────────────
function enrichRow (row) {
  const trips = Number(row.trips_completed) || 0
  const cancelled = Number(row.trips_cancelled) || 0
  const drivers = Number(row.active_drivers) || 0
  const total = trips + cancelled

  if (row.cancel_rate_pct == null && total > 0) {
    row.cancel_rate_pct = cancelled / total
  }
  if (row.trips_per_driver == null && drivers > 0) {
    row.trips_per_driver = trips / drivers
  }
  return row
}

// ─── Pivot principal: lista → matriz jerárquica ─────────────────────────────
//
// Retorna:
// {
//   cities: Map<cityKey, {
//     country, city,
//     lines: Map<sliceKey, {
//       business_slice_name, fleet_display_name, is_subfleet, subfleet_name,
//       periods: Map<periodKey, { metrics: {…}, raw: originalRow }>
//     }>
//   }>,
//   allPeriods: string[]          (sorted)
//   totals: Map<periodKey, {…}>  (agregado ejecutivo)
// }

export function buildMatrix (rows, grain) {
  const cities = new Map()
  const periodSet = new Set()
  const totalsBucket = new Map()

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
    for (const { key } of MATRIX_KPIS) {
      metrics[key] = r[key] ?? null
    }

    lineBucket.periods.set(pk, { metrics, raw: r })

    // Acumular totales ejecutivos
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
  }

  const allPeriods = [...periodSet].sort()

  const totals = new Map()
  for (const [pk, tb] of totalsBucket) {
    const total = tb._trips + tb._cancelled
    totals.set(pk, {
      trips_completed: tb._trips,
      revenue_yego_net: tb._revenue,
      active_drivers: tb._drivers,
      commission_pct: tb._commN > 0 ? tb._commSum / tb._commN : null,
      avg_ticket: tb._ticketN > 0 ? tb._ticketSum / tb._ticketN : null,
      cancel_rate_pct: total > 0 ? tb._cancelled / total : null,
      trips_per_driver: tb._drivers > 0 ? tb._trips / tb._drivers : null,
    })
  }

  return { cities, allPeriods, totals }
}

// ─── Delta / comparativo embebido ───────────────────────────────────────────
// Calcula delta entre periodo actual y periodo anterior en la misma serie.
// Como backend no devuelve MoM/WoW/DoD para business-slice, lo hacemos aquí
// con la información de periodos contiguos disponibles en el mismo response.

export function computeDeltas (linePeriods, allPeriods) {
  const result = new Map()
  for (let i = 0; i < allPeriods.length; i++) {
    const pk = allPeriods[i]
    const prevPk = i > 0 ? allPeriods[i - 1] : null
    const curr = linePeriods.get(pk)
    const prev = prevPk ? linePeriods.get(prevPk) : null

    if (!curr) { result.set(pk, null); continue }

    const deltas = {}
    for (const { key, showAsPct } of MATRIX_KPIS) {
      const cv = curr.metrics[key]
      const pv = prev?.metrics?.[key]
      if (cv == null || pv == null || pv === 0) {
        deltas[key] = { value: cv, delta_pct: null, delta_abs: null, signal: 'neutral' }
      } else {
        const diff = Number(cv) - Number(pv)
        const pct = Number(pv) !== 0 ? diff / Math.abs(Number(pv)) : null
        deltas[key] = {
          value: cv,
          delta_pct: pct,
          delta_abs: showAsPct ? diff : null,
          delta_abs_pp: showAsPct ? diff * 100 : null,
          signal: diff > 0 ? 'up' : diff < 0 ? 'down' : 'neutral',
        }
      }
    }
    result.set(pk, deltas)
  }
  return result
}

// ─── Totales ejecutivos (strip KPI) ─────────────────────────────────────────
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
    trips_completed: trips,
    revenue_yego_net: revenue,
    commission_pct: commN > 0 ? commSum / commN : null,
    active_drivers: drivers,
    cancel_rate_pct: total > 0 ? cancelled / total : null,
    trips_per_driver: drivers > 0 ? trips / drivers : null,
  }
}

// ─── Formato de valores ─────────────────────────────────────────────────────
export function fmtValue (v, kpiKey) {
  if (v == null || (typeof v === 'number' && isNaN(v))) return '—'
  const n = Number(v)
  const kpi = MATRIX_KPIS.find(k => k.key === kpiKey)
  if (kpi?.showAsPct) return `${(n * 100).toFixed(1)}%`
  if (kpi?.unit === 'currency') return n >= 1e6
    ? `${(n / 1e6).toFixed(1)}M`
    : n >= 1e3
      ? `${(n / 1e3).toFixed(1)}K`
      : n.toLocaleString(undefined, { maximumFractionDigits: 1 })
  return n.toLocaleString(undefined, { maximumFractionDigits: 1 })
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

export function signalArrow (signal) {
  if (signal === 'up') return '▲'
  if (signal === 'down') return '▼'
  return '—'
}
