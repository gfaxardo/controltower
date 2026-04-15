/**
 * projectionMatrixUtils.js
 *
 * Utilidades para el modo Proyección de Omniview Matrix.
 * Reutiliza MATRIX_KPIS y periodKey del módulo base; adapta
 * buildMatrix y computeDeltas para mostrar attainment vs plan
 * en lugar de variación temporal (MoM/WoW/DoD).
 */

import { MATRIX_KPIS, periodKey as basePeriodKey } from './omniviewMatrixUtils.js'

export const PROJECTION_KPIS = ['trips_completed', 'revenue_yego_net', 'active_drivers']

export const SIGNAL_COLORS = {
  green: '#16a34a',
  warning: '#d97706',
  danger: '#dc2626',
  no_data: '#9ca3af',
}

export const SIGNAL_BG = {
  green: 'bg-emerald-50',
  warning: 'bg-amber-50',
  danger: 'bg-red-50',
  no_data: '',
}

export const SIGNAL_DOT = {
  green: 'bg-emerald-500',
  warning: 'bg-amber-500',
  danger: 'bg-red-500',
  no_data: 'bg-gray-300',
}

export function projectionSignalColor (signal) {
  return SIGNAL_COLORS[signal] || SIGNAL_COLORS.no_data
}

export function fmtAttainment (pct) {
  if (pct == null) return '—'
  return `${pct >= 1000 ? '>999' : pct.toFixed(1)}%`
}

export function fmtGap (gap, kpiKey) {
  if (gap == null) return '—'
  const kpi = MATRIX_KPIS.find(k => k.key === kpiKey)
  if (kpi?.unit === 'currency') {
    const abs = Math.abs(gap)
    const formatted = abs >= 1000000
      ? `${(abs / 1000000).toFixed(1)}M`
      : abs >= 1000
        ? `${(abs / 1000).toFixed(1)}K`
        : abs.toFixed(0)
    return `${gap >= 0 ? '+' : '-'}${formatted}`
  }
  if (kpi?.unit === 'ratio' || kpi?.showAsPct) {
    return `${gap >= 0 ? '+' : ''}${(gap * 100).toFixed(1)}pp`
  }
  const abs = Math.abs(gap)
  const formatted = abs >= 1000
    ? `${(abs / 1000).toFixed(1)}K`
    : abs.toFixed(0)
  return `${gap >= 0 ? '+' : '-'}${formatted}`
}

/**
 * Build a projection matrix from backend response rows.
 * Same shape as buildMatrix from omniviewMatrixUtils: { cities, allPeriods, totals }
 */
export function buildProjectionMatrix (rows, grain) {
  const cities = new Map()
  const periodSet = new Set()
  const totalsBucket = new Map()

  for (const raw of rows) {
    const pk = basePeriodKey(raw, grain)
    if (!pk) continue
    periodSet.add(pk)

    const cityKey = `${raw.country || '—'}::${raw.city || '—'}`
    if (!cities.has(cityKey)) {
      cities.set(cityKey, {
        country: raw.country || '—',
        city: raw.city || '—',
        lines: new Map(),
      })
    }
    const cityBucket = cities.get(cityKey)

    const sliceKey = `${raw.business_slice_name || '—'}::${raw.fleet_display_name || '—'}::${raw.is_subfleet ? '1' : '0'}::${raw.subfleet_name || ''}`
    if (!cityBucket.lines.has(sliceKey)) {
      cityBucket.lines.set(sliceKey, {
        business_slice_name: raw.business_slice_name || '—',
        fleet_display_name: raw.fleet_display_name || '—',
        is_subfleet: !!raw.is_subfleet,
        subfleet_name: raw.subfleet_name || '',
        periods: new Map(),
      })
    }
    const lineBucket = cityBucket.lines.get(sliceKey)

    const metrics = {}
    for (const { key } of MATRIX_KPIS) {
      metrics[key] = raw[key] ?? null
    }

    const projection = {}
    for (const kpi of PROJECTION_KPIS) {
      projection[kpi] = {
        actual: raw[kpi] ?? null,
        projected_total: raw[`${kpi}_projected_total`] ?? null,
        projected_expected: raw[`${kpi}_projected_expected`] ?? null,
        attainment_pct: raw[`${kpi}_attainment_pct`] ?? null,
        gap_to_expected: raw[`${kpi}_gap_to_expected`] ?? null,
        gap_to_full: raw[`${kpi}_gap_to_full`] ?? null,
        completion_pct: raw[`${kpi}_completion_pct`] ?? null,
        signal: raw[`${kpi}_signal`] || 'no_data',
        curve_method: raw[`${kpi}_curve_method`] ?? null,
        curve_confidence: raw[`${kpi}_curve_confidence`] ?? null,
        fallback_level: raw[`${kpi}_fallback_level`] ?? null,
        expected_ratio: raw[`${kpi}_expected_ratio`] ?? null,
      }
    }

    lineBucket.periods.set(pk, { metrics, projection, raw })

    if (!totalsBucket.has(pk)) {
      totalsBucket.set(pk, {})
      for (const kpi of PROJECTION_KPIS) {
        totalsBucket.get(pk)[kpi] = { actual: 0, projected_total: 0, projected_expected: 0 }
      }
    }
    const tb = totalsBucket.get(pk)
    for (const kpi of PROJECTION_KPIS) {
      tb[kpi].actual += Number(raw[kpi]) || 0
      tb[kpi].projected_total += Number(raw[`${kpi}_projected_total`]) || 0
      tb[kpi].projected_expected += Number(raw[`${kpi}_projected_expected`]) || 0
    }
  }

  const allPeriods = [...periodSet].sort()

  const totals = new Map()
  for (const [pk, tb] of totalsBucket) {
    const entry = {}
    for (const kpi of PROJECTION_KPIS) {
      const { actual, projected_total, projected_expected } = tb[kpi]
      const attainment = projected_expected > 0 ? (actual / projected_expected) * 100 : null
      const signal = attainment == null ? 'no_data'
        : attainment >= 100 ? 'green'
        : attainment >= 90 ? 'warning'
        : 'danger'

      entry[kpi] = actual
      entry[`${kpi}_projected_total`] = projected_total
      entry[`${kpi}_projected_expected`] = projected_expected
      entry[`${kpi}_attainment_pct`] = attainment != null ? Math.round(attainment * 100) / 100 : null
      entry[`${kpi}_gap_to_expected`] = projected_expected > 0 ? actual - projected_expected : null
      entry[`${kpi}_signal`] = signal
    }
    totals.set(pk, entry)
  }

  return { cities, allPeriods, totals }
}

/**
 * Compute projection deltas for a single line across periods.
 * Unlike computeDeltas (which compares period-over-period),
 * this returns projection metrics per period.
 */
export function computeProjectionDeltas (linePeriods, allPeriods) {
  const result = new Map()

  for (const pk of allPeriods) {
    const cell = linePeriods.get(pk)
    if (!cell) {
      result.set(pk, null)
      continue
    }

    const deltas = {}
    for (const { key } of MATRIX_KPIS) {
      const proj = cell.projection?.[key]
      const isProjectable = PROJECTION_KPIS.includes(key)

      if (isProjectable && proj) {
        deltas[key] = {
          value: proj.actual,
          projected_total: proj.projected_total,
          projected_expected: proj.projected_expected,
          attainment_pct: proj.attainment_pct,
          gap_to_expected: proj.gap_to_expected,
          gap_to_full: proj.gap_to_full,
          completion_pct: proj.completion_pct,
          signal: proj.signal,
          curve_method: proj.curve_method,
          curve_confidence: proj.curve_confidence,
          fallback_level: proj.fallback_level,
          expected_ratio: proj.expected_ratio,
          isProjection: true,
        }
      } else {
        deltas[key] = {
          value: cell.metrics[key],
          signal: 'no_data',
          isProjection: false,
        }
      }
    }
    result.set(pk, deltas)
  }
  return result
}

/**
 * Compute totals deltas for the frozen totals row.
 */
export function computeProjectionTotalsDeltas (totals, allPeriods) {
  const result = new Map()
  for (const pk of allPeriods) {
    const t = totals.get(pk)
    if (!t) { result.set(pk, null); continue }

    const deltas = {}
    for (const { key } of MATRIX_KPIS) {
      const isProjectable = PROJECTION_KPIS.includes(key)
      if (isProjectable) {
        deltas[key] = {
          value: t[key],
          projected_total: t[`${key}_projected_total`],
          projected_expected: t[`${key}_projected_expected`],
          attainment_pct: t[`${key}_attainment_pct`],
          gap_to_expected: t[`${key}_gap_to_expected`],
          signal: t[`${key}_signal`] || 'no_data',
          isProjection: true,
        }
      } else {
        deltas[key] = { value: t[key] ?? null, signal: 'no_data', isProjection: false }
      }
    }
    result.set(pk, deltas)
  }
  return result
}

const CURVE_SOURCE_LABELS = {
  city_slice_3m: 'Ciudad + Tajada (3 meses)',
  city_all_3m: 'Ciudad total (3 meses)',
  country_slice_3m: 'País + Tajada (3 meses)',
  country_all_3m: 'País total (3 meses)',
  linear_fallback: 'Lineal (fallback)',
}

export function describeCurveSource (method) {
  if (!method) return '—'
  return CURVE_SOURCE_LABELS[method] || method
}

export function buildProjectionCellTooltip (kpi, delta, cityName, lineName, periodLbl) {
  const parts = [`${cityName} · ${lineName}`, `Periodo: ${periodLbl}`, `KPI: ${kpi?.label || '—'}`]
  if (!delta) return parts.join('\n')

  if (delta.isProjection) {
    parts.push('')
    if (delta.value != null) parts.push(`Real al corte: ${_fmtNum(delta.value)}`)
    if (delta.projected_expected != null) parts.push(`Expected al corte: ${_fmtNum(delta.projected_expected)}`)
    if (delta.projected_total != null) parts.push(`Plan total periodo: ${_fmtNum(delta.projected_total)}`)
    if (delta.attainment_pct != null) parts.push(`Cumplimiento: ${delta.attainment_pct.toFixed(1)}%`)
    if (delta.gap_to_expected != null) parts.push(`Gap vs expected: ${delta.gap_to_expected >= 0 ? '+' : ''}${_fmtNum(delta.gap_to_expected)}`)
    parts.push('')
    if (delta.curve_method) parts.push(`Base: ${describeCurveSource(delta.curve_method)}`)
    if (delta.curve_confidence) parts.push(`Confianza: ${delta.curve_confidence}`)
    if (delta.fallback_level != null) parts.push(`Nivel fallback: ${delta.fallback_level}`)
    if (delta.expected_ratio != null) parts.push(`Ratio esperado: ${(delta.expected_ratio * 100).toFixed(1)}%`)
  } else {
    if (delta.value != null) parts.push(`Valor: ${_fmtNum(delta.value)}`)
    parts.push('(Sin proyección para este KPI)')
  }

  return parts.join('\n')
}

function _fmtNum (v) {
  if (v == null) return '—'
  const n = Number(v)
  if (Math.abs(n) >= 1000000) return `${(n / 1000000).toFixed(2)}M`
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1)}K`
  return n.toFixed(n % 1 === 0 ? 0 : 2)
}
