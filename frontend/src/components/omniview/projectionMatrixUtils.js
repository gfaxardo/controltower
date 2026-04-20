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

// ─── Orden de países ─────────────────────────────────────────────────────────
// Perú siempre arriba, Colombia debajo, el resto al final.
const _COUNTRY_RANK = {
  peru: 0, perú: 0, 'pe': 0,
  colombia: 1, col: 1, 'co': 1,
}
export function countryRank (country) {
  return _COUNTRY_RANK[(country || '').toLowerCase()] ?? 99
}

// ─── Estados visuales de celda ───────────────────────────────────────────────
/**
 * Devuelve una etiqueta operativa para el estado de la celda.
 * hasPlan: projected_total > 0
 * hasReal: actual > 0 (o actual !== null con valor)
 * attainment_pct: % cumplimiento (puede ser null si sin real)
 */
export function getProjectionStatusLabel (attainment_pct, hasPlan, hasReal) {
  if (!hasPlan) return null
  if (!hasReal) return 'Sin ejecución'
  if (attainment_pct == null) return null
  if (attainment_pct >= 105) return 'Sobre plan'
  if (attainment_pct >= 95) return 'En línea'
  if (attainment_pct >= 80) return 'Bajo plan'
  return 'Bajo plan'
}

export function getProjectionStatusColors (statusLabel) {
  switch (statusLabel) {
    case 'Sobre plan':    return { text: 'text-emerald-700', bg: 'bg-emerald-50' }
    case 'En línea':     return { text: 'text-blue-600',    bg: 'bg-blue-50'    }
    case 'Bajo plan':    return { text: 'text-amber-700',   bg: 'bg-amber-50'   }
    case 'Sin ejecución': return { text: 'text-slate-500',  bg: 'bg-slate-50'   }
    default:             return { text: 'text-gray-400',    bg: ''              }
  }
}

// ─── Etiquetas KPI-específicas ────────────────────────────────────────────────
export const KPI_PROJ_LABELS = {
  trips_completed:  { proy: 'Proy viajes', real: 'Real viajes', short_proy: 'Proy', short_real: 'Real' },
  revenue_yego_net: { proy: 'Proy rev.',   real: 'Real rev.',   short_proy: 'Proy', short_real: 'Real' },
  active_drivers:   { proy: 'Proy cond.',  real: 'Real cond.',  short_proy: 'Proy', short_real: 'Real' },
  avg_ticket:       { proy: 'Proy ticket', real: 'Real ticket', short_proy: 'Proy', short_real: 'Real' },
  trips_per_driver: { proy: 'Proy TPD',    real: 'Real TPD',    short_proy: 'Proy', short_real: 'Real' },
  commission_pct:   { proy: 'Proy %',      real: 'Real %',      short_proy: 'Proy', short_real: 'Real' },
  cancel_rate_pct:  { proy: 'Proy canc.',  real: 'Real canc.',  short_proy: 'Proy', short_real: 'Real' },
}

export function projectionSignalColor (signal) {
  return SIGNAL_COLORS[signal] || SIGNAL_COLORS.no_data
}

export function fmtAttainment (pct) {
  if (pct == null) return '—'
  return `${pct >= 1000 ? '>999' : pct.toFixed(1)}%`
}

export function fmtGap (gap, kpiKey) {
  if (gap == null) return null
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
 * Returns { cities, allPeriods, totals, cityVolumeMap, lineVolumeMap }
 *
 * cityVolumeMap: Map<cityKey, number> → volumen proyectado trips para ordenar ciudades
 * lineVolumeMap: Map<`${cityKey}::${lineKey}`, number> → volumen proyectado trips para ordenar líneas
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

    // Clave canónica de fila: solo business_slice_name + subfleet.
    // NO incluir fleet_display_name porque varía entre filas con plan y sin plan
    // (plan→"", real-only→bsn) y causaría filas duplicadas para YMA/YMM.
    const sliceKey = `${raw.business_slice_name || '—'}::${raw.is_subfleet ? '1' : '0'}::${raw.subfleet_name || ''}`
    if (!cityBucket.lines.has(sliceKey)) {
      cityBucket.lines.set(sliceKey, {
        business_slice_name: raw.business_slice_name || '—',
        // fleet_display_name usa business_slice_name como fallback para display consistente
        fleet_display_name: raw.business_slice_name || raw.fleet_display_name || '—',
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
        actual:             raw[kpi] ?? null,
        projected_total:    raw[`${kpi}_projected_total`] ?? null,
        projected_expected: raw[`${kpi}_projected_expected`] ?? null,
        attainment_pct:     raw[`${kpi}_attainment_pct`] ?? null,   // canónico: NUNCA negativo
        gap_to_expected:    raw[`${kpi}_gap_to_expected`] ?? null,   // gap_abs
        gap_pct:            raw[`${kpi}_gap_pct`] ?? null,           // NUEVO canónico: puede ser negativo
        gap_to_full:        raw[`${kpi}_gap_to_full`] ?? null,
        completion_pct:     raw[`${kpi}_completion_pct`] ?? null,
        signal:             raw[`${kpi}_signal`] || 'no_data',
        curve_method:       raw[`${kpi}_curve_method`] ?? null,
        curve_confidence:   raw[`${kpi}_curve_confidence`] ?? null,
        fallback_level:     raw[`${kpi}_fallback_level`] ?? null,
        expected_ratio:     raw[`${kpi}_expected_ratio`] ?? null,
        comparison_basis:   raw[`${kpi}_comparison_basis`] ?? null,  // NUEVO canónico
        conservation_adjustment_applied: raw[`${kpi}_conservation_adjustment_applied`] ?? false,
        conservation_adjustment_value: raw[`${kpi}_conservation_adjustment_value`] ?? null
      }
    }

    lineBucket.periods.set(pk, {
      metrics,
      projection,
      raw,
      comparison_status: raw.comparison_status || null,
      projection_confidence: raw.projection_confidence ?? null,
      projection_anomaly: !!raw.projection_anomaly
    })

    if (!totalsBucket.has(pk)) {
      totalsBucket.set(pk, { _comparison_basis: null })
      for (const kpi of PROJECTION_KPIS) {
        totalsBucket.get(pk)[kpi] = { actual: 0, projected_total: 0, projected_expected: 0 }
      }
    }
    const tb = totalsBucket.get(pk)
    // comparison_basis es igual para todas las filas del mismo período → tomamos el primero
    if (!tb._comparison_basis && raw[`${PROJECTION_KPIS[0]}_comparison_basis`]) {
      tb._comparison_basis = raw[`${PROJECTION_KPIS[0]}_comparison_basis`]
    }
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

      // Canónico: avance_pct NUNCA negativo (actual < 0 → null)
      const avance = (projected_expected > 0 && actual >= 0)
        ? (actual / projected_expected) * 100
        : null
      const gap_abs = projected_expected != null ? actual - projected_expected : null
      const gap_pct = (projected_expected != null && projected_expected !== 0)
        ? ((actual - projected_expected) / projected_expected) * 100
        : null
      const signal = avance == null
        ? (actual < 0 ? 'danger' : 'no_data')
        : avance >= 100 ? 'green'
          : avance >= 90 ? 'warning'
            : 'danger'

      entry[kpi] = actual
      entry[`${kpi}_projected_total`]    = projected_total
      entry[`${kpi}_projected_expected`] = projected_expected
      entry[`${kpi}_attainment_pct`]     = avance != null ? Math.round(avance * 100) / 100 : null
      entry[`${kpi}_gap_to_expected`]    = gap_abs != null ? Math.round(gap_abs * 100) / 100 : null
      entry[`${kpi}_gap_pct`]            = gap_pct != null ? Math.round(gap_pct * 100) / 100 : null
      entry[`${kpi}_signal`]             = signal
      entry[`${kpi}_comparison_basis`]   = tb._comparison_basis || null
    }
    totals.set(pk, entry)
  }

  // ── Mapas de volumen para ordenar ciudades y líneas por volumen proyectado ──
  const cityVolumeMap = new Map()
  const lineVolumeMap = new Map()

  for (const [cityKey, cityBucket] of cities) {
    let cityVol = 0
    for (const [lineKey, lineBucket] of cityBucket.lines) {
      let lineVol = 0
      for (const [, cell] of lineBucket.periods) {
        lineVol += Number(cell.projection?.trips_completed?.projected_total) || 0
      }
      lineVolumeMap.set(`${cityKey}::${lineKey}`, lineVol)
      cityVol += lineVol
    }
    cityVolumeMap.set(cityKey, cityVol)
  }

  return { cities, allPeriods, totals, cityVolumeMap, lineVolumeMap }
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
          value:              proj.actual,
          projected_total:    proj.projected_total,
          projected_expected: proj.projected_expected,
          attainment_pct:     proj.attainment_pct,     // canónico: NUNCA negativo
          gap_to_expected:    proj.gap_to_expected,    // gap_abs
          gap_pct:            proj.gap_pct,            // NUEVO: puede ser negativo
          gap_to_full:        proj.gap_to_full,
          completion_pct:     proj.completion_pct,
          signal:             proj.signal,
          curve_method:       proj.curve_method,
          curve_confidence:   proj.curve_confidence,
          fallback_level:     proj.fallback_level,
          expected_ratio:     proj.expected_ratio,
          comparison_basis:   proj.comparison_basis,
          conservation_adjustment_applied: proj.conservation_adjustment_applied,
          conservation_adjustment_value: proj.conservation_adjustment_value,
          projection_confidence: cell.projection_confidence ?? null,
          projection_anomaly: cell.projection_anomaly ?? false,
          isProjection: true,
          comparison_status: cell.comparison_status,
        }
      } else {
        deltas[key] = {
          value: cell.metrics[key],
          signal: 'no_data',
          isProjection: false,
          comparison_status: cell.comparison_status,
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
          value:              t[key],
          projected_total:    t[`${key}_projected_total`],
          projected_expected: t[`${key}_projected_expected`],
          attainment_pct:     t[`${key}_attainment_pct`],
          gap_to_expected:    t[`${key}_gap_to_expected`],
          gap_pct:            t[`${key}_gap_pct`] ?? null,
          comparison_basis:   t[`${key}_comparison_basis`] ?? null,
          signal:             t[`${key}_signal`] || 'no_data',
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

// ─── Etiquetas legibles para comparison_basis (FASE 3.5) ─────────────────────
export const COMPARISON_BASIS_LABELS = {
  full_month:               'Plan mes completo (período cerrado)',
  expected_to_date_month:   'Expected al corte (mes en curso)',
  full_week:                'Plan semana completa (semana cerrada)',
  expected_to_date_week:    'Expected al corte (semana en curso)',
  full_day:                 'Plan diario',
  unknown:                  'Base no determinada',
}

export function describeBasis (basis) {
  if (!basis) return '—'
  return COMPARISON_BASIS_LABELS[basis] || basis
}

/**
 * Formatea gap_pct como string con signo y símbolo %.
 * gap_pct puede ser negativo (diferencia a favor o en contra de lo esperado).
 */
export function fmtGapPct (pct) {
  if (pct == null) return null
  return `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`
}

/**
 * Devuelve el sufijo visual que indica la base de comparación en la celda.
 * (E) = Expected al corte (mes/semana en curso)
 * (F) = Full period (período cerrado, plan completo)
 *  ''  = sin información de base
 */
export function basisSuffix (basis) {
  if (!basis) return ''
  if (basis === 'expected_to_date_month' || basis === 'expected_to_date_week') return '(E)'
  if (basis === 'full_month' || basis === 'full_week' || basis === 'full_day') return '(F)'
  return ''
}

export function buildProjectionCellTooltip (kpi, delta, cityName, lineName, periodLbl) {
  const parts = [`${cityName} · ${lineName}`, `Periodo: ${periodLbl}`, `KPI: ${kpi?.label || '—'}`]
  if (!delta) {
    parts.push('', 'Sin datos para este periodo / línea.')
    return parts.join('\n')
  }

  if (delta.isProjection) {
    const hasPlan         = (delta.projected_total ?? 0) > 0
    const hasReal         = delta.value != null && delta.value > 0
    const hasNegActual    = delta.value != null && delta.value < 0
    const suffix          = basisSuffix(delta.comparison_basis)

    // ── 1. Base de comparación (prominente, primera línea informativa) ──────
    parts.push('')
    const basisLabel = delta.comparison_basis ? describeBasis(delta.comparison_basis) : null
    if (basisLabel) {
      parts.push(`Base de comparación: ${basisLabel}`)
    }

    // ── 2. Valores: Actual · Expected · Plan completo ──────────────────────
    parts.push('')
    const realLbl = hasReal
      ? _fmtNum(delta.value)
      : hasNegActual ? _fmtNum(delta.value)
        : '0 (sin ejecución)'
    parts.push(`Actual:          ${realLbl}`)

    if (delta.projected_expected != null) {
      parts.push(`Expected${suffix || ' al corte'}: ${_fmtNum(delta.projected_expected)}`)
    }
    if (hasPlan) {
      parts.push(`Plan (mes):      ${_fmtNum(delta.projected_total)}`)
    }

    // ── 3. Métricas: Avance · Gap abs · Gap % ─────────────────────────────
    parts.push('')
    const attStr = hasNegActual
      ? `N/A (valor negativo)`
      : hasReal
        ? (delta.attainment_pct != null ? `${delta.attainment_pct.toFixed(1)}%${suffix ? ' ' + suffix : ''}` : '—')
        : hasPlan ? `0.0%${suffix ? ' ' + suffix : ''} (sin ejecución)` : '—'
    parts.push(`Avance ${suffix}:       ${attStr}`)

    if (delta.gap_to_expected != null) {
      const gapFmt = `${delta.gap_to_expected >= 0 ? '+' : ''}${_fmtNum(delta.gap_to_expected)}`
      parts.push(`Gap absoluto:    ${gapFmt}`)
    }
    if (delta.gap_pct != null) {
      const gpStr = `${delta.gap_pct >= 0 ? '+' : ''}${delta.gap_pct.toFixed(1)}%`
      parts.push(`Gap %:           ${gpStr}`)
    }

    // ── 4. full_plan_ratio: "Equivale a X% del plan mensual" ──────────────
    if (hasPlan && delta.completion_pct != null) {
      parts.push(`Equivale al:     ${delta.completion_pct.toFixed(1)}% del plan mensual`)
    } else if (hasPlan && hasReal && delta.projected_total > 0) {
      const ratio = (delta.value / delta.projected_total) * 100
      parts.push(`Equivale al:     ${ratio.toFixed(1)}% del plan mensual`)
    }

    // ── 5. Estado semántico ───────────────────────────────────────────────
    const statusLabel = getProjectionStatusLabel(
      hasReal && !hasNegActual ? delta.attainment_pct : (hasPlan ? 0 : null),
      hasPlan,
      hasReal,
    )
    if (statusLabel) parts.push(`Estado:          ${statusLabel}`)

    // ── 6. Detalles técnicos (curva) ──────────────────────────────────────
    if (delta.curve_method || delta.curve_confidence || delta.expected_ratio != null) {
      parts.push('')
      if (delta.curve_method)       parts.push(`Curva: ${describeCurveSource(delta.curve_method)}`)
      if (delta.curve_confidence)   parts.push(`Confianza: ${delta.curve_confidence}`)
      if (delta.expected_ratio != null) parts.push(`Ratio al corte: ${(delta.expected_ratio * 100).toFixed(1)}%`)
      if (delta.fallback_level != null) parts.push(`Nivel fallback: ${delta.fallback_level}`)
    }
  } else {
    if (delta.value != null) parts.push(`Valor real: ${_fmtNum(delta.value)}`)
    parts.push('Sin proyección definida para este KPI en el modo Vs Proyección.')
  }

  return parts.join('\n')
}

function _fmtNum (v) {
  if (v == null) return '—'
  const n = Number(v)
  if (!isFinite(n)) return '—'
  if (Math.abs(n) >= 1000000) return `${(n / 1000000).toFixed(2)}M`
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1)}K`
  return n.toFixed(n % 1 === 0 ? 0 : 2)
}
