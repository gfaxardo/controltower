/**
 * alertingEngine.js — FASE 3.3 + FASE_VALIDATION_FIX
 *
 * Priorización, severidad y mapeo a acciones operativas (determinístico, explicable).
 * Sin llamadas a API. Sin ML.
 *
 * FASE_VALIDATION_FIX — blindaje de KPIs no aditivos:
 *   - trips_completed y revenue_yego_net: aditivos → alertas aditivas permitidas.
 *   - active_drivers: semi_additive_distinct → permitido en alertas SOLO si la
 *     comparación es vs plan del MISMO scope (mensual vs plan mensual).
 *     NO se usa como base de suma cross-grain.
 *   - avg_ticket, commission_pct, cancel_rate_pct: ratio → NO en alertas aditivas.
 *   - trips_per_driver: derived_ratio → RESTRICTED; no en ninguna alerta aditiva.
 *
 * El alerting engine opera sobre PROJECTION_KPIS (trips, revenue, active_drivers),
 * que ya excluye ratio/derived_ratio. El score de active_drivers se attenúa con
 * SCOPE_ONLY_ATTENUATOR para reflejar que su brecha es de scope, no de suma.
 */

import { computeProjectionDeltas, PROJECTION_KPIS } from './projectionMatrixUtils.js'
import { computeRootCause } from './rootCauseEngine.js'

const FEATURE_SOURCE = 'omniview_projection'
const HANDOFF_VERSION = '1.0'

/**
 * Pesos de KPI en el priority_score (0-100):
 *   trips_completed  : aditivo, principal volumen → peso alto.
 *   revenue_yego_net : aditivo, impacto económico → peso alto.
 *   active_drivers   : scope_only (semi_additive_distinct) → peso moderado.
 *                      La brecha vs plan se interpreta dentro del mismo scope mensual,
 *                      NO como suma de drivers semanales vs mensual.
 *
 * KPIs ratio (avg_ticket, commission_pct, cancel_rate_pct) y derived_ratio
 * (trips_per_driver) NO están en PROJECTION_KPIS y no participan en scoring.
 */
export const KPI_WEIGHT = {
  trips_completed: 40,
  revenue_yego_net: 38,
  active_drivers: 32,    // scope_only — ver SCOPE_ONLY_ATTENUATOR
}

/**
 * Atenuador para KPIs scope_only (active_drivers).
 * La brecha de un distinct-count no se debe escalar igual que un aditivo puro:
 * un gap de -20 drivers en un mes podría no tener la misma urgencia que
 * -20% de trips (depende del scope). Se aplica sobre el gap_component.
 */
const SCOPE_ONLY_ATTENUATOR = {
  active_drivers: 0.80,   // atenúa 20% el gap_component para evitar falsos CRITICAL
}

/**
 * KPIs que NO deben gatillar alertas de brecha aditiva.
 * Están explícitamente excluidos del PROJECTION_KPIS ya, pero esta lista
 * es el guardrail documental de por qué no deben añadirse.
 */
export const NON_ADDITIVE_KPIS_EXCLUDED_FROM_ALERTS = [
  'avg_ticket',       // non_additive_ratio   → formula_only
  'commission_pct',   // non_additive_ratio   → formula_only
  'cancel_rate_pct',  // non_additive_ratio   → formula_only
  'trips_per_driver', // derived_ratio        → restricted
  'trips_cancelled',  // additive pero componente; no es KPI de scoring principal
]

const SIGNAL_POINTS = {
  danger: 20,
  warning: 10,
  green: 0,
  no_data: 0,
}

/** Atenúa ruido en grano fino (documentado). */
export const GRAIN_FACTOR = {
  monthly: 1.0,
  weekly: 0.85,
  daily: 0.7,
}

/** Multiplicador por confianza de curva (documentado). */
const CONFIDENCE_MULT = {
  high: 1,
  medium: 0.95,
  low: 0.88,
  fallback: 0.85,
}

function _clamp (n, lo, hi) {
  return Math.min(hi, Math.max(lo, n))
}

function _safeNum (v) {
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

/**
 * Score 0–100 explicable.
 * Base: brecha relativa vs expected (cap 40 pts) escalada por peso de KPI + puntos por semáforo.
 * Ajuste: grano + confianza de curva + atenuador scope_only (para active_drivers).
 *
 * FASE_VALIDATION_FIX: para KPIs scope_only (active_drivers), el gap_component
 * se atenúa con SCOPE_ONLY_ATTENUATOR[kpiKey] para evitar falsos CRITICAL
 * causados por la naturaleza distinct-count del KPI.
 */
export function computePriorityScore (delta, kpiKey, grain, rootCauseResult = null) {
  // Guardrail: KPIs no aditivos excluidos no deberían llegar aquí,
  // pero si lo hacen, devolvemos score 0 para no generar alertas falsas.
  if (NON_ADDITIVE_KPIS_EXCLUDED_FROM_ALERTS.includes(kpiKey)) {
    return {
      priority_score: 0,
      score_breakdown: { excluded_reason: 'non_additive_kpi_excluded_from_alerts' },
      impact_basis: `KPI ${kpiKey} excluido de alertas aditivas (non_additive/derived_ratio).`,
    }
  }

  const expected = _safeNum(delta?.projected_expected)
  const gap = _safeNum(delta?.gap_to_expected)
  const signal = delta?.signal || 'no_data'
  const conf = delta?.curve_confidence || 'medium'

  const relGapPct =
    expected != null && expected !== 0 && gap != null
      ? Math.abs(gap / expected) * 100
      : 0

  const w = KPI_WEIGHT[kpiKey] ?? 35
  // FASE_VALIDATION_FIX: atenuar gap_component para scope_only KPIs
  const scopeAttenuator = SCOPE_ONLY_ATTENUATOR[kpiKey] ?? 1.0
  const gapComponent = _clamp(relGapPct * (w / 40) * scopeAttenuator, 0, 40)
  const signalComponent = SIGNAL_POINTS[signal] ?? 0

  const rawPreGrain = gapComponent + signalComponent
  const g = GRAIN_FACTOR[grain] ?? 1
  const confMult = CONFIDENCE_MULT[conf] ?? 0.9

  const priority_score = _clamp(rawPreGrain * g * confMult, 0, 100)

  const score_breakdown = {
    rel_gap_pct: Math.round(relGapPct * 100) / 100,
    gap_component: Math.round(gapComponent * 100) / 100,
    signal_component: signalComponent,
    kpi_weight: w,
    scope_attenuator: scopeAttenuator,
    grain_factor: g,
    confidence_multiplier: confMult,
    curve_confidence: conf,
    raw_pre_cap: Math.round(rawPreGrain * 100) / 100,
    main_driver_key: rootCauseResult?.main_driver?.key ?? null,
  }

  const scopeNote = scopeAttenuator < 1.0
    ? ` [scope_only ×${scopeAttenuator}]`
    : ''

  const impact_basis =
    `Brecha vs expected (${relGapPct.toFixed(1)}% del expected)${scopeNote} + semáforo (${signal}) ` +
    `× grano (${g}) × confianza curva (${confMult})`

  return {
    priority_score: Math.round(priority_score * 100) / 100,
    score_breakdown,
    impact_basis: impact_basis,
  }
}

/**
 * @returns {{ priority_band: string, severity: string }}
 */
export function classifyAlert (priorityScore, attainmentPct, signal, delta) {
  const att = _safeNum(attainmentPct)
  const gap = _safeNum(delta?.gap_to_expected)

  // Sobrecumplimiento → WATCH
  if (att != null && att >= 100) {
    return { priority_band: 'WATCH', severity: 'WATCH' }
  }
  if (gap != null && gap > 0 && att != null && att > 100) {
    return { priority_band: 'WATCH', severity: 'WATCH' }
  }

  const s = priorityScore ?? 0

  if (s >= 70 || (att != null && att < 75)) {
    return { priority_band: 'CRITICAL', severity: 'CRITICAL' }
  }
  if (s >= 50 || (att != null && att < 90)) {
    return { priority_band: 'HIGH', severity: 'HIGH' }
  }
  if (s >= 25 || (att != null && att < 100)) {
    return { priority_band: 'MEDIUM', severity: 'MEDIUM' }
  }
  if (gap != null && gap < 0) {
    return { priority_band: 'LOW', severity: 'LOW' }
  }
  return { priority_band: 'LOW', severity: 'LOW' }
}

const ACTION_TYPES = {
  SUPPLY_ACTIVATION: 'supply_activation',
  DISPATCH_OPS: 'dispatch_ops',
  DEMAND_MIX: 'demand_mix',
  PRICING_MIX: 'pricing_mix',
  DRIVER_RETENTION: 'driver_retention',
  MONITOR_WATCH: 'monitor_watch',
  GENERIC_UNDERPERF: 'generic_underperformance',
}

/**
 * Reglas auditables: main_driver × KPI → acción.
 */
export function mapToAction (mainDriverKey, kpiKey, severity, delta, rootCauseResult) {
  const md = mainDriverKey || 'unknown'
  const gap = _safeNum(delta?.gap_to_expected)
  const urgent =
    severity === 'CRITICAL' ? 'immediate'
      : severity === 'HIGH' ? 'same_day'
        : 'this_week'

  // Sobrecumplimiento / WATCH
  if (severity === 'WATCH') {
    return {
      suggested_action_type: ACTION_TYPES.MONITOR_WATCH,
      suggested_action_text:
        'Monitorear capacidad y calidad de servicio; validar sostenibilidad del ritmo vs plan.',
      target_team: 'ops',
      urgency: 'this_week',
      action_rationale:
        'Sobrecumplimiento vs expected: priorizar estabilidad operativa y evitar degradación.',
    }
  }

  // Drivers KPI: gap directo
  if (kpiKey === 'active_drivers') {
    if (md === 'gap' || md === 'unknown') {
      const u = gap != null && gap < -50 ? 'immediate' : urgent
      return {
        suggested_action_type: ACTION_TYPES.DRIVER_RETENTION,
        suggested_action_text:
          'Reactivación y retención de conductores: revisar churn, incentivos y onboarding.',
        target_team: 'supply',
        urgency: u,
        action_rationale:
          'KPI conductores activos por debajo del expected: foco en base instalada.',
      }
    }
  }

  if (kpiKey === 'trips_completed') {
    if (md === 'drivers') {
      return {
        suggested_action_type: ACTION_TYPES.SUPPLY_ACTIVATION,
        suggested_action_text:
          'Activación de conductores / reducir churn y mejorar disponibilidad en la tajada.',
        target_team: 'supply',
        urgency: severity === 'CRITICAL' ? 'immediate' : 'same_day',
        action_rationale:
          'Root cause: volumen de trips explicado principalmente por conductores vs plan.',
      }
    }
    if (md === 'productivity') {
      return {
        suggested_action_type: ACTION_TYPES.DISPATCH_OPS,
        suggested_action_text:
          'Revisar asignación, dispatch y utilización por conductor (viajes por driver).',
        target_team: 'ops',
        urgency: 'same_day',
        action_rationale:
          'Root cause: productividad (trips/driver) desviada respecto al expected.',
      }
    }
  }

  if (kpiKey === 'revenue_yego_net') {
    if (md === 'trips') {
      return {
        suggested_action_type: ACTION_TYPES.DEMAND_MIX,
        suggested_action_text:
          'Revisar demanda, asignación de volumen y mix de servicios que impactan revenue.',
        target_team: 'ops',
        urgency: 'same_day',
        action_rationale:
          'Root cause: volumen (trips) como mayor contribución al gap de revenue.',
      }
    }
    if (md === 'ticket' || md === 'residual') {
      return {
        suggested_action_type: ACTION_TYPES.PRICING_MIX,
        suggested_action_text:
          'Revisar pricing, promos, mix de producto y distribución por zona/tajada.',
        target_team: 'pricing',
        urgency: 'this_week',
        action_rationale:
          'Root cause: ticket promedio (o residual) como driver principal del gap de revenue.',
      }
    }
  }

  return {
    suggested_action_type: ACTION_TYPES.GENERIC_UNDERPERF,
    suggested_action_text:
      'Revisar plan vs real con ciudad/tajada: alinear supply, demanda y precio según brecha.',
    target_team: 'ops',
    urgency: urgent,
    action_rationale:
      'Combinación no cubierta por reglas específicas; priorizar diagnóstico local.',
  }
}

function _randomId () {
  return `al_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 9)}`
}

export function buildAlertPayload ({
  cityKey,
  lineKey,
  city,
  country,
  slice,
  period,
  grain,
  kpiKey,
  delta,
  rootCauseResult,
  navigation,
}) {
  const { priority_score, score_breakdown, impact_basis } = computePriorityScore(
    delta,
    kpiKey,
    grain,
    rootCauseResult
  )
  const { priority_band, severity } = classifyAlert(
    priority_score,
    delta?.attainment_pct,
    delta?.signal,
    delta
  )
  const action = mapToAction(
    rootCauseResult?.main_driver?.key,
    kpiKey,
    severity,
    delta,
    rootCauseResult
  )

  const trustNotes = []
  if (delta?.projection_confidence === 'low') {
    trustNotes.push('Proyección de baja confianza — validar curva antes de escalar decisión.')
  }
  if (delta?.projection_anomaly) {
    trustNotes.push('Anomalía de curva detectada — verificar distribución histórica.')
  }
  // FASE_VALIDATION_FIX: añadir nota de interpretación para KPIs scope_only
  if (kpiKey === 'active_drivers') {
    trustNotes.push(
      'Drivers únicos (scope_only): brecha vs plan del mismo scope. ' +
      'No comparar contra suma de semanas o días — son distintos scopes.'
    )
  }

  return {
    alert_id: _randomId(),
    feature_source: FEATURE_SOURCE,
    city_key: cityKey,
    line_key: lineKey,
    city,
    country,
    slice,
    kpi_key: kpiKey,
    period,
    grain,
    attainment_pct: delta?.attainment_pct ?? null,
    gap_total: delta?.gap_to_expected ?? null,
    main_driver: rootCauseResult?.main_driver
      ? {
        key: rootCauseResult.main_driver.key,
        label: rootCauseResult.main_driver.label,
        pct: rootCauseResult.main_driver.pct,
      }
      : null,
    root_cause_complete: !!rootCauseResult?.is_complete,
    priority_score,
    priority_band,
    severity,
    impact_basis,
    ...action,
    curve_confidence: delta?.curve_confidence ?? null,
    projection_confidence: delta?.projection_confidence ?? null,
    projection_anomaly: !!delta?.projection_anomaly,
    trust_notes: trustNotes,
    signal: delta?.signal ?? 'no_data',
    score_breakdown,
    navigation,
  }
}

export function buildActionHandoff (alertPayload) {
  if (!alertPayload) return null
  return {
    handoff_version: HANDOFF_VERSION,
    source: 'yego_control_tower_omniview',
    generated_at: new Date().toISOString(),
    intended_consumers: ['closer', 'ops', 'supply', 'campaigns_outbound'],
    alert: alertPayload,
  }
}

/**
 * Contexto local de alerta/acción para el drill (misma lógica que buildAlertPayload sin recorrer matriz).
 */
export function buildDrillAlertPayload ({ cityKey, lineKey, city, country, slice, period, grain, kpiKey, periodDeltas }) {
  const delta = periodDeltas?.[kpiKey]
  if (!delta?.isProjection) return null

  const rc = computeRootCause(kpiKey, periodDeltas)
  return buildAlertPayload({
    cityKey,
    lineKey,
    city,
    country,
    slice,
    period,
    grain,
    kpiKey,
    delta,
    rootCauseResult: rc,
    navigation: null,
  })
}

/**
 * Recorre la matriz de proyección (último período) y construye alertas priorizadas.
 */
export function computeAlertsForMatrix (projMatrix, focusedKpi, grain) {
  if (!projMatrix || !PROJECTION_KPIS.includes(focusedKpi)) {
    return { underperforming: [], watch: [] }
  }

  const { cities, allPeriods } = projMatrix
  const lastPk = allPeriods.length > 0 ? allPeriods[allPeriods.length - 1] : null
  if (!lastPk) return { underperforming: [], watch: [] }

  const alerts = []

  for (const [cityKey, cityData] of cities) {
    for (const [lineKey, lineData] of cityData.lines) {
      const deltasMap = computeProjectionDeltas(lineData.periods, allPeriods)
      const periodDeltas = deltasMap.get(lastPk)
      if (!periodDeltas) continue

      const d = periodDeltas[focusedKpi]
      if (!d || !d.isProjection || d.attainment_pct == null) continue

      const rc = computeRootCause(focusedKpi, periodDeltas)
      const nav = {
        cityKey,
        lineKey,
        period: lastPk,
        kpiKey: focusedKpi,
        lineData,
        periodDeltas,
        raw: lineData.periods.get(lastPk)?.raw,
      }

      const payload = buildAlertPayload({
        cityKey,
        lineKey,
        city: cityData.city,
        country: cityData.country,
        slice: lineData.business_slice_name,
        period: lastPk,
        grain,
        kpiKey: focusedKpi,
        delta: d,
        rootCauseResult: rc,
        navigation: nav,
      })

      alerts.push(payload)
    }
  }

  const watch = alerts
    .filter(a => a.priority_band === 'WATCH')
    .sort((a, b) => (b.attainment_pct || 0) - (a.attainment_pct || 0))
    .slice(0, 5)

  const underperforming = alerts
    .filter(a => a.priority_band !== 'WATCH')
    .sort((a, b) => b.priority_score - a.priority_score)
    .slice(0, 5)

  return { underperforming, watch }
}
