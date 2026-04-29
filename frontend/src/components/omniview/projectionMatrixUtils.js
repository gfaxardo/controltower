/**
 * projectionMatrixUtils.js
 *
 * Utilidades para el modo Proyección de Omniview Matrix.
 * Reutiliza MATRIX_KPIS y periodKey del módulo base; adapta
 * buildMatrix y computeDeltas para mostrar attainment vs plan
 * en lugar de variación temporal (MoM/WoW/DoD).
 */

import { MATRIX_KPIS, periodKey as basePeriodKey, periodLabel as basePeriodLabel } from './omniviewMatrixUtils.js'

export const PROJECTION_KPIS = ['trips_completed', 'revenue_yego_net', 'active_drivers']

/* ────────────────────────────────────────────────────────────────────────────
 * FASE_KPI_CONSISTENCY: contrato KPI cross-grain en el cliente.
 *
 * Fuente de verdad oficial: backend `meta.kpi_contract` en la respuesta de
 * `/ops/business-slice/omniview-projection`. Este fallback estático garantiza
 * que la UI puede renderizar badges y notas incluso si el backend aún no envía
 * el contrato (por ejemplo, en versiones antiguas o si la llamada falló).
 * ────────────────────────────────────────────────────────────────────────── */
export const KPI_AGGREGATION_TYPE = {
  ADDITIVE: 'additive',
  SEMI_ADDITIVE: 'semi_additive_distinct',
  RATIO: 'non_additive_ratio',
  DERIVED_RATIO: 'derived_ratio',
}

export const KPI_COMPARISON_RULE = {
  EXACT_SUM: 'exact_sum',
  SAME_FORMULA: 'same_formula_different_scope',
  NOT_COMPARABLE: 'not_directly_comparable',
}

/**
 * FASE_VALIDATION_FIX: cada entrada del fallback ahora incluye los campos
 * de decision readiness alineados con el contrato backend.
 *
 * decision_status:
 *   - 'decision_ready'  : aditivo, comparable, permite drift alerts y scoring.
 *   - 'scope_only'      : semi_additive; comparar solo vs plan del mismo scope.
 *   - 'formula_only'    : ratio; comparable por fórmula recomputada, no por suma.
 *   - 'restricted'      : no usar en decisiones cross-grain ni en alertas aditivas.
 */
export const KPI_CONTRACT_FALLBACK = {
  trips_completed: {
    aggregation_type: KPI_AGGREGATION_TYPE.ADDITIVE,
    comparable_across_grains: true,
    comparison_rule: KPI_COMPARISON_RULE.EXACT_SUM,
    recommended_ui_note: 'Aditivo: la suma de días del mes equivale al mensual.',
    allowed_for_cross_grain_decision: true,
    allowed_for_drift_alerts: true,
    allowed_for_priority_scoring: true,
    decision_status: 'decision_ready',
    decision_note: 'Usar daily_in_month como base. La suma ISO semanal puede incluir días de otro mes.',
  },
  trips_cancelled: {
    aggregation_type: KPI_AGGREGATION_TYPE.ADDITIVE,
    comparable_across_grains: true,
    comparison_rule: KPI_COMPARISON_RULE.EXACT_SUM,
    recommended_ui_note: 'Aditivo: la suma de días del mes equivale al mensual.',
    allowed_for_cross_grain_decision: true,
    allowed_for_drift_alerts: true,
    allowed_for_priority_scoring: false,
    decision_status: 'decision_ready',
    decision_note: 'Componente de cancel_rate. No es KPI principal de scoring.',
  },
  revenue_yego_net: {
    aggregation_type: KPI_AGGREGATION_TYPE.ADDITIVE,
    comparable_across_grains: true,
    comparison_rule: KPI_COMPARISON_RULE.EXACT_SUM,
    recommended_ui_note: 'Aditivo: la suma de días del mes equivale al mensual.',
    allowed_for_cross_grain_decision: true,
    allowed_for_drift_alerts: true,
    allowed_for_priority_scoring: true,
    decision_status: 'decision_ready',
    decision_note: 'KPI de revenue aditivo; comparar vs plan mensual o acumulado diario.',
  },
  active_drivers: {
    aggregation_type: KPI_AGGREGATION_TYPE.SEMI_ADDITIVE,
    comparable_across_grains: false,
    comparison_rule: KPI_COMPARISON_RULE.NOT_COMPARABLE,
    recommended_ui_note: 'Drivers únicos del periodo. No sumar entre granos. Leer por scope.',
    allowed_for_cross_grain_decision: false,
    allowed_for_drift_alerts: true,
    allowed_for_priority_scoring: true,
    decision_status: 'scope_only',
    decision_note: 'Brecha válida SOLO vs plan del mismo scope (mensual vs plan mensual). No comparar suma semanal contra mensual.',
  },
  avg_ticket: {
    aggregation_type: KPI_AGGREGATION_TYPE.RATIO,
    comparable_across_grains: true,
    comparison_rule: KPI_COMPARISON_RULE.SAME_FORMULA,
    recommended_ui_note: 'Ratio: misma fórmula aplicada a distinto periodo. Comparar por scope, no por suma.',
    allowed_for_cross_grain_decision: true,
    allowed_for_drift_alerts: false,
    allowed_for_priority_scoring: false,
    decision_status: 'formula_only',
    decision_note: 'Comparable si se recomputa ticket_sum/ticket_count para cada scope. No alertas aditivas entre granos.',
  },
  commission_pct: {
    aggregation_type: KPI_AGGREGATION_TYPE.RATIO,
    comparable_across_grains: true,
    comparison_rule: KPI_COMPARISON_RULE.SAME_FORMULA,
    recommended_ui_note: 'Ratio: misma fórmula aplicada a distinto periodo. Comparar por scope, no por suma.',
    allowed_for_cross_grain_decision: true,
    allowed_for_drift_alerts: false,
    allowed_for_priority_scoring: false,
    decision_status: 'formula_only',
    decision_note: 'Recomputa rev/fare para cada scope. No alertas aditivas entre granos.',
  },
  cancel_rate_pct: {
    aggregation_type: KPI_AGGREGATION_TYPE.RATIO,
    comparable_across_grains: true,
    comparison_rule: KPI_COMPARISON_RULE.SAME_FORMULA,
    recommended_ui_note: 'Ratio: misma fórmula aplicada a distinto periodo. Comparar por scope, no por suma.',
    allowed_for_cross_grain_decision: true,
    allowed_for_drift_alerts: false,
    allowed_for_priority_scoring: false,
    decision_status: 'formula_only',
    decision_note: 'Usar solo para comparar la tasa del periodo contra plan del mismo scope.',
  },
  trips_per_driver: {
    aggregation_type: KPI_AGGREGATION_TYPE.DERIVED_RATIO,
    comparable_across_grains: false,
    comparison_rule: KPI_COMPARISON_RULE.NOT_COMPARABLE,
    recommended_ui_note: 'Derivado de drivers únicos. No comparable por suma entre granos. Leer por scope.',
    allowed_for_cross_grain_decision: false,
    allowed_for_drift_alerts: false,
    allowed_for_priority_scoring: false,
    decision_status: 'restricted',
    decision_note: 'No usar en decisiones cross-grain ni en alertas de brecha aditiva.',
  },
}

export function getKpiContract (kpiKey, contractFromMeta) {
  if (contractFromMeta && contractFromMeta[kpiKey]) return contractFromMeta[kpiKey]
  return KPI_CONTRACT_FALLBACK[kpiKey] || null
}

export function isKpiComparableAcrossGrains (kpiKey, contractFromMeta) {
  const c = getKpiContract(kpiKey, contractFromMeta)
  return c ? !!c.comparable_across_grains : true
}

export function getKpiComparabilityBadge (kpiKey, contractFromMeta) {
  const c = getKpiContract(kpiKey, contractFromMeta)
  if (!c) return null
  switch (c.aggregation_type) {
    case KPI_AGGREGATION_TYPE.ADDITIVE:
      return { label: 'Aditivo', tone: 'emerald', short: 'Σ' }
    case KPI_AGGREGATION_TYPE.SEMI_ADDITIVE:
      return { label: 'Distinct', tone: 'slate', short: '≠Σ' }
    case KPI_AGGREGATION_TYPE.RATIO:
      return { label: 'Ratio', tone: 'sky', short: '%' }
    case KPI_AGGREGATION_TYPE.DERIVED_RATIO:
      return { label: 'Derivado', tone: 'amber', short: 'd/' }
    default:
      return null
  }
}

export function getKpiComparabilityNote (kpiKey, contractFromMeta) {
  const c = getKpiContract(kpiKey, contractFromMeta)
  return c ? (c.recommended_ui_note || c.diagnostic_note || '') : ''
}

/**
 * FASE_VALIDATION_FIX: devuelve el estado de decision readiness del KPI.
 * 'decision_ready' | 'scope_only' | 'formula_only' | 'restricted'
 */
export function getKpiDecisionStatus (kpiKey, contractFromMeta) {
  const c = getKpiContract(kpiKey, contractFromMeta)
  return c?.decision_status || 'restricted'
}

/**
 * FASE_VALIDATION_FIX: devuelve la nota de uso correcto para el KPI.
 */
export function getKpiDecisionNote (kpiKey, contractFromMeta) {
  const c = getKpiContract(kpiKey, contractFromMeta)
  return c?.decision_note || ''
}

/**
 * FASE_VALIDATION_FIX: devuelve badge visual con color semántico para decision status.
 */
export function getKpiDecisionBadge (kpiKey, contractFromMeta) {
  const status = getKpiDecisionStatus(kpiKey, contractFromMeta)
  switch (status) {
    case 'decision_ready':
      return { label: 'Decision Ready', tone: 'emerald', short: '✓' }
    case 'scope_only':
      return { label: 'Scope Only', tone: 'amber', short: 'S' }
    case 'formula_only':
      return { label: 'Formula Only', tone: 'sky', short: 'F' }
    case 'restricted':
      return { label: 'Restricted', tone: 'red', short: '⊘' }
    default:
      return null
  }
}

/**
 * True si el KPI puede usarse en alertas de brecha aditiva (gap_abs, gap_pct).
 */
export function isKpiAllowedForDriftAlerts (kpiKey, contractFromMeta) {
  const c = getKpiContract(kpiKey, contractFromMeta)
  return c ? !!c.allowed_for_drift_alerts : false
}

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
  const periodMeta = new Map()

  for (const raw of rows) {
    const pk = basePeriodKey(raw, grain)
    if (!pk) continue
    periodSet.add(pk)
    if (!periodMeta.has(pk)) {
      periodMeta.set(pk, {
        month: raw.month || null,
        week_start: raw.week_start ?? null,
        week_end: raw.week_end ?? null,
        iso_year: raw.iso_year ?? null,
        iso_week: raw.iso_week ?? null,
        week_label: raw.week_label ?? null,
        week_range_label: raw.week_range_label ?? null,
        week_full_label: raw.week_full_label ?? null,
        day_label: raw.day_label ?? null,
      })
    }

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
      totalsBucket.set(pk, {
        _comparison_basis: null,
        _trips: 0,
        _cancelled: 0,
        _revenue: 0,
        _drivers: 0,
        _ticketSum: 0,
        _ticketN: 0,
        _commSum: 0,
        _commN: 0,
      })
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
    tb._trips += Number(raw.trips_completed) || 0
    tb._cancelled += Number(raw.trips_cancelled) || 0
    tb._revenue += Number(raw.revenue_yego_net) || 0
    tb._drivers += Number(raw.active_drivers) || 0
    if (raw.avg_ticket != null) {
      tb._ticketSum += Number(raw.avg_ticket) || 0
      tb._ticketN += 1
    }
    if (raw.commission_pct != null) {
      tb._commSum += Number(raw.commission_pct) || 0
      tb._commN += 1
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
    entry.trips_completed = tb._trips
    entry.trips_cancelled = tb._cancelled
    entry.revenue_yego_net = tb._revenue
    entry.active_drivers = tb._drivers
    entry.avg_ticket = tb._ticketN > 0 ? tb._ticketSum / tb._ticketN : null
    entry.trips_per_driver = tb._drivers > 0 ? tb._trips / tb._drivers : null
    entry.cancel_rate_pct = (tb._trips + tb._cancelled) > 0
      ? (tb._cancelled / (tb._trips + tb._cancelled)) * 100
      : null
    entry.commission_pct = tb._commN > 0 ? tb._commSum / tb._commN : null
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

  return { cities, allPeriods, totals, cityVolumeMap, lineVolumeMap, periodMeta }
}

export function projectionPeriodLabel (key, grain, periodMeta = null) {
  const meta = periodMeta?.get?.(key)
  if (grain === 'daily' && meta?.day_label) return String(meta.day_label)
  if (grain !== 'weekly') return basePeriodLabel(key, grain)
  return meta?.week_label || basePeriodLabel(key, grain)
}

export function projectionPeriodSecondaryLabel (key, grain, periodMeta = null) {
  if (grain !== 'weekly') return null
  const meta = periodMeta?.get?.(key)
  if (meta?.week_label && String(meta.week_label).includes(' · ')) return null
  return meta?.week_range_label || null
}

export function projectionPeriodTooltipLabel (key, grain, periodMeta = null) {
  const meta = periodMeta?.get?.(key)
  if (grain === 'daily' && meta?.day_label) return String(meta.day_label)
  if (grain !== 'weekly') return basePeriodLabel(key, grain)
  return meta?.week_full_label || meta?.week_label || basePeriodLabel(key, grain)
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

export function buildProjectionCellTooltip (kpi, delta, cityName, lineName, periodLbl, kpiContract) {
  const parts = [`${cityName} · ${lineName}`, `Periodo: ${periodLbl}`, `KPI: ${kpi?.label || '—'}`]

  // FASE_KPI_CONSISTENCY: contrato cross-grain (badge + nota canónica)
  const badge = kpi?.key ? getKpiComparabilityBadge(kpi.key, kpiContract) : null
  const compNote = kpi?.key ? getKpiComparabilityNote(kpi.key, kpiContract) : ''
  if (badge) parts.push(`Tipo: ${badge.label}`)
  if (compNote) parts.push(compNote)

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
