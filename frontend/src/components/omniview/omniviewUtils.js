/**
 * Utilidades solo presentación — no reimplementar reglas de negocio del backend.
 */

export const SIGNAL_COLORS = {
  positive: '#22c55e',
  negative: '#ef4444',
  neutral: '#9ca3af',
  no_data: '#cbd5e1'
}

/** Flecha según signal + direction (solo visual). */
export function signalArrow (signal, direction) {
  if (signal === 'no_data' || signal === 'neutral') return '—'
  if (direction === 'lower_better') {
    if (signal === 'positive') return '▼'
    if (signal === 'negative') return '▲'
  } else if (direction === 'higher_better') {
    if (signal === 'positive') return '▲'
    if (signal === 'negative') return '▼'
  }
  return '—'
}

export function signalColor (signal) {
  if (signal === 'positive') return SIGNAL_COLORS.positive
  if (signal === 'negative') return SIGNAL_COLORS.negative
  if (signal === 'neutral') return SIGNAL_COLORS.neutral
  return SIGNAL_COLORS.no_data
}

/**
 * Formato display; commission_pct en ratio 0–1 según meta.units.
 */
export function formatMetricValue (key, value, unitsMeta) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  const u = unitsMeta?.[key]
  if (key === 'commission_pct' && u?.storage === 'ratio') {
    return `${(Number(value) * 100).toFixed(2)}%`
  }
  if (key === 'cancel_rate_pct') {
    return `${Number(value).toFixed(2)}%`
  }
  if (key === 'revenue_yego_net' || key === 'avg_ticket') {
    return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })
  }
  if (key === 'trips_per_driver') {
    return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })
  }
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 0 })
}

export function formatDeltaLine (key, deltaObj, unitsMeta) {
  if (!deltaObj) return null
  const pct = deltaObj.delta_pct
  const abs = deltaObj.delta_abs
  const pp = deltaObj.delta_abs_pp
  if (pct == null && abs == null && pp == null) return null
  if (key === 'commission_pct' && pp != null) {
    const sign = pp > 0 ? '+' : ''
    return `${sign}${pp.toFixed(2)} pp`
  }
  if (key === 'cancel_rate_pct' && pp != null) {
    const sign = pp > 0 ? '+' : ''
    return `${sign}${pp.toFixed(2)} pp`
  }
  if (pct != null) {
    const sign = pct > 0 ? '+' : ''
    return `${sign}${pct.toFixed(1)}%`
  }
  if (abs != null) {
    const sign = abs > 0 ? '+' : ''
    return `${sign}${formatMetricValue(key, abs, unitsMeta)}`
  }
  return null
}

const norm = (s) => (s == null ? '' : String(s).trim().toLowerCase())

/**
 * Árbol país → ciudad → tajada → hojas (flota/subflota).
 * Hojas ordenadas por revenue actual descendente.
 */
export function buildOmniviewTree (rows) {
  if (!rows?.length) return []
  const byCountry = new Map()

  for (const row of rows) {
    const d = row.dims || {}
    const country = d.country ?? '(sin país)'
    const city = d.city ?? '(sin ciudad)'
    const slice = d.business_slice_name ?? '(sin tajada)'
    const fleet = d.fleet_display_name ?? '—'
    const sub = d.is_subfleet && d.subfleet_name ? String(d.subfleet_name) : ''
    const leafLabel = sub ? `${fleet} · ${sub}` : fleet

    if (!byCountry.has(country)) {
      byCountry.set(country, { type: 'country', key: country, cities: new Map() })
    }
    const nc = byCountry.get(country)
    if (!nc.cities.has(city)) {
      nc.cities.set(city, { type: 'city', key: city, slices: new Map() })
    }
    const ncity = nc.cities.get(city)
    if (!ncity.slices.has(slice)) {
      ncity.slices.set(slice, { type: 'slice', key: slice, leaves: [] })
    }
    ncity.slices.get(slice).leaves.push({
      type: 'leaf',
      label: leafLabel,
      row
    })
  }

  const sortLeaves = (a, b) => {
    const ra = a.row?.current?.revenue_yego_net
    const rb = b.row?.current?.revenue_yego_net
    const na = ra != null ? Number(ra) : -Infinity
    const nb = rb != null ? Number(rb) : -Infinity
    return nb - na
  }

  const tree = []
  const countryKeys = [...byCountry.keys()].sort((a, b) => String(a).localeCompare(String(b)))
  for (const ck of countryKeys) {
    const nc = byCountry.get(ck)
    const cityNodes = []
    const cityKeys = [...nc.cities.keys()].sort((a, b) => String(a).localeCompare(String(b)))
    for (const cityK of cityKeys) {
      const ncity = nc.cities.get(cityK)
      const sliceNodes = []
      const sliceKeys = [...ncity.slices.keys()].sort((a, b) => String(a).localeCompare(String(b)))
      for (const sk of sliceKeys) {
        const nsl = ncity.slices.get(sk)
        nsl.leaves.sort(sortLeaves)
        sliceNodes.push({ type: 'slice', key: sk, leaves: nsl.leaves })
      }
      cityNodes.push({ type: 'city', key: cityK, slices: sliceNodes })
    }
    tree.push({ type: 'country', key: ck, cities: cityNodes })
  }
  return tree
}

export function findSubtotalForCountry (subtotals, country) {
  if (!subtotals?.length) return null
  return subtotals.find((s) => norm(s.country) === norm(country)) || null
}

/** Suma aditiva segura para filas padre (trips, revenue, cancelled). */
export function sumAdditiveFromLeaves (leaves, field) {
  let s = 0
  for (const { row } of leaves) {
    const v = row?.current?.[field]
    if (v != null && !Number.isNaN(Number(v))) s += Number(v)
  }
  return s
}
