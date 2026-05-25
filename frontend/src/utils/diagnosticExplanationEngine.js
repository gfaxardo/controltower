/**
 * DIAGNOSTIC EXPLANATION ENGINE
 * 
 * Capa explicativa determinística.
 * Explica POR QUÉ una señal es critical/blocked/elevated/unknown.
 * 
 * NO recomienda acciones.
 * NO sugiere remediación.
 * NO inventa causalidad.
 * 
 * Motor: Diagnostic Engine (temprano)
 */

import {
  DECISION_SEVERITY,
  DECISION_THRESHOLDS,
  getDecisionSeverity,
} from './operationalDecisionSeverity'

/* ── OFFICIAL DIAGNOSTIC FACTORS ── */

export const DIAGNOSTIC_FACTOR = Object.freeze({
  FRESHNESS_DEGRADED:      'freshness_degraded',
  TRUST_DEGRADED:          'trust_degraded',
  MISSING_COMPARABLE:      'missing_comparable',
  MISSING_PLAN:            'missing_plan',
  PROJECTION_MISSING:      'projection_missing',
  SEVERE_GAP:              'severe_gap',
  SUSTAINED_NEGATIVE:      'sustained_negative',
  INSUFFICIENT_SIGNAL:     'insufficient_signal',
  STALE_DATA:              'stale_data',
  CONFIDENCE_DEGRADED:     'confidence_degraded',
  WEEKLY_DETERIORATION:    'weekly_deterioration',
  MONTHLY_DETERIORATION:   'monthly_deterioration',
  BLOCKED_COMPARISON:      'blocked_comparison',
  MISSING_SERVING:         'missing_serving',
  UNIT_ALERT_TRIGGERED:    'unit_alert_triggered',
  CONFIG_INCOMPLETE:       'config_incomplete',
  DATA_INCOMPLETE:         'data_incomplete',
  ATTAINMENT_GAP:          'attainment_gap',
})

/**
 * Priority order: lower = more important (dominant factor).
 * First match becomes dominant factor.
 */
const FACTOR_PRIORITY = [
  DIAGNOSTIC_FACTOR.FRESHNESS_DEGRADED,
  DIAGNOSTIC_FACTOR.MISSING_SERVING,
  DIAGNOSTIC_FACTOR.TRUST_DEGRADED,
  DIAGNOSTIC_FACTOR.BLOCKED_COMPARISON,
  DIAGNOSTIC_FACTOR.MISSING_COMPARABLE,
  DIAGNOSTIC_FACTOR.MISSING_PLAN,
  DIAGNOSTIC_FACTOR.PROJECTION_MISSING,
  DIAGNOSTIC_FACTOR.SEVERE_GAP,
  DIAGNOSTIC_FACTOR.UNIT_ALERT_TRIGGERED,
  DIAGNOSTIC_FACTOR.SUSTAINED_NEGATIVE,
  DIAGNOSTIC_FACTOR.WEEKLY_DETERIORATION,
  DIAGNOSTIC_FACTOR.MONTHLY_DETERIORATION,
  DIAGNOSTIC_FACTOR.CONFIDENCE_DEGRADED,
  DIAGNOSTIC_FACTOR.STALE_DATA,
  DIAGNOSTIC_FACTOR.CONFIG_INCOMPLETE,
  DIAGNOSTIC_FACTOR.DATA_INCOMPLETE,
  DIAGNOSTIC_FACTOR.ATTAINMENT_GAP,
  DIAGNOSTIC_FACTOR.INSUFFICIENT_SIGNAL,
]

/* ── FACTOR LABELS ── */

const FACTOR_LABEL = {
  [DIAGNOSTIC_FACTOR.FRESHNESS_DEGRADED]:   'Freshness degraded',
  [DIAGNOSTIC_FACTOR.TRUST_DEGRADED]:       'Trust degraded',
  [DIAGNOSTIC_FACTOR.MISSING_COMPARABLE]:   'Missing comparable data',
  [DIAGNOSTIC_FACTOR.MISSING_PLAN]:         'Missing plan data',
  [DIAGNOSTIC_FACTOR.PROJECTION_MISSING]:   'Projection unavailable',
  [DIAGNOSTIC_FACTOR.SEVERE_GAP]:           'Severe plan deviation',
  [DIAGNOSTIC_FACTOR.SUSTAINED_NEGATIVE]:   'Sustained negative trend',
  [DIAGNOSTIC_FACTOR.INSUFFICIENT_SIGNAL]:  'Insufficient signal',
  [DIAGNOSTIC_FACTOR.STALE_DATA]:           'Stale data',
  [DIAGNOSTIC_FACTOR.CONFIDENCE_DEGRADED]:  'Confidence degraded',
  [DIAGNOSTIC_FACTOR.WEEKLY_DETERIORATION]: 'Weekly deterioration',
  [DIAGNOSTIC_FACTOR.MONTHLY_DETERIORATION]: 'Monthly deterioration',
  [DIAGNOSTIC_FACTOR.BLOCKED_COMPARISON]:   'Comparison blocked',
  [DIAGNOSTIC_FACTOR.MISSING_SERVING]:      'Missing serving data',
  [DIAGNOSTIC_FACTOR.UNIT_ALERT_TRIGGERED]: 'Unit alert active',
  [DIAGNOSTIC_FACTOR.CONFIG_INCOMPLETE]:    'Configuration incomplete',
  [DIAGNOSTIC_FACTOR.DATA_INCOMPLETE]:      'Data incomplete',
  [DIAGNOSTIC_FACTOR.ATTAINMENT_GAP]:       'Attainment below target',
}

/* ── PURE FUNCTIONS ── */

/**
 * Detecta todos los factores diagnósticos activos en los datos.
 * Retorna array de { factor, detail }.
 */
export function extractDiagnosticFactors(signals = {}) {
  const factors = []

  // ── Blocking factors first ──
  if (signals.freshness_status === 'critical' || signals.freshness_status === 'atrasada') {
    factors.push({ factor: DIAGNOSTIC_FACTOR.FRESHNESS_DEGRADED, detail: `Status: ${signals.freshness_status || 'degraded'}. Lag: ${signals.lag_days != null ? signals.lag_days + 'd' : 'unknown'}` })
  }
  if (signals.freshness_status === 'parcial_esperada' || signals.freshness_status === 'stale') {
    factors.push({ factor: DIAGNOSTIC_FACTOR.STALE_DATA, detail: `Status: ${signals.freshness_status}. Lag: ${signals.lag_days != null ? signals.lag_days + 'd' : 'unknown'}` })
  }

  if (signals.trust_status === 'blocked') {
    factors.push({ factor: DIAGNOSTIC_FACTOR.TRUST_DEGRADED, detail: 'Trust layer blocked. Data cannot be validated.' })
  }
  if (signals.trust_status === 'warning') {
    factors.push({ factor: DIAGNOSTIC_FACTOR.TRUST_DEGRADED, detail: 'Trust uncertain. Validation conditions partially met.' })
  }

  if (signals.comparison_status === 'missing_plan') {
    factors.push({ factor: DIAGNOSTIC_FACTOR.MISSING_PLAN, detail: 'No plan data available for comparison period.' })
  }
  if (signals.comparison_status === 'plan_without_real') {
    factors.push({ factor: DIAGNOSTIC_FACTOR.MISSING_COMPARABLE, detail: 'Plan exists but no real data for comparison.' })
  }
  if (signals.comparison_status === 'blocked') {
    factors.push({ factor: DIAGNOSTIC_FACTOR.BLOCKED_COMPARISON, detail: 'Comparison cannot be performed.' })
  }

  if (signals.missing_serving_fact === true || signals.fact_status === 'empty') {
    factors.push({ factor: DIAGNOSTIC_FACTOR.MISSING_SERVING, detail: 'Serving fact layer is empty or unavailable.' })
  }

  // ── Gap factors ──
  const gapVal = signals.gap_pct ?? signals.gap_trips_pct ?? signals.gap_revenue_pct
  const absGap = Math.abs(gapVal ?? 0)
  if (absGap > DECISION_THRESHOLDS.gap_critical) {
    factors.push({ factor: DIAGNOSTIC_FACTOR.SEVERE_GAP, detail: `Deviation: ${absGap.toFixed(1)}% vs plan. Threshold for critical: >${DECISION_THRESHOLDS.gap_critical}%` })
  } else if (absGap > DECISION_THRESHOLDS.gap_elevated) {
    factors.push({ factor: DIAGNOSTIC_FACTOR.SEVERE_GAP, detail: `Deviation: ${absGap.toFixed(1)}% vs plan.` })
  }

  if (signals.gap_trips_pct != null && Math.abs(signals.gap_trips_pct) > 0) {
    const label = signals.gap_trips_pct > 0 ? 'above' : 'below'
    factors.push({ factor: DIAGNOSTIC_FACTOR.ATTAINMENT_GAP, detail: `Trips ${label} plan by ${Math.abs(signals.gap_trips_pct).toFixed(1)}%` })
  }
  if (signals.gap_revenue_pct != null && Math.abs(signals.gap_revenue_pct) > 0) {
    const label = signals.gap_revenue_pct > 0 ? 'above' : 'below'
    factors.push({ factor: DIAGNOSTIC_FACTOR.ATTAINMENT_GAP, detail: `Revenue ${label} plan by ${Math.abs(signals.gap_revenue_pct).toFixed(1)}%` })
  }

  // ── Alert factors ──
  if (signals.unit_alert === true) {
    factors.push({ factor: DIAGNOSTIC_FACTOR.UNIT_ALERT_TRIGGERED, detail: 'Unit economics alert activated. Per-trip revenue deviation detected.' })
  }

  // ── Confidence factors ──
  if (signals.confidence_score != null && signals.confidence_score < DECISION_THRESHOLDS.confidence_blocked) {
    factors.push({ factor: DIAGNOSTIC_FACTOR.CONFIDENCE_DEGRADED, detail: `Confidence score: ${signals.confidence_score}. Data trust critically low.` })
  } else if (signals.confidence_score != null && signals.confidence_score < DECISION_THRESHOLDS.confidence_critical) {
    factors.push({ factor: DIAGNOSTIC_FACTOR.CONFIDENCE_DEGRADED, detail: `Confidence score: ${signals.confidence_score}.` })
  }

  // ── Trend factors ──
  if (signals.weeks_declining_consecutively && signals.weeks_declining_consecutively >= 3) {
    factors.push({ factor: DIAGNOSTIC_FACTOR.SUSTAINED_NEGATIVE, detail: `${signals.weeks_declining_consecutively} consecutive weeks declining.` })
  }
  if (signals.weeks_declining_consecutively && signals.weeks_declining_consecutively >= 1) {
    factors.push({ factor: DIAGNOSTIC_FACTOR.WEEKLY_DETERIORATION, detail: `${signals.weeks_declining_consecutively} week(s) declining.` })
  }

  // ── Config & data completeness ──
  if (signals.has_any_targets === false) {
    factors.push({ factor: DIAGNOSTIC_FACTOR.CONFIG_INCOMPLETE, detail: 'No operational targets configured.' })
  }
  if (signals.data_complete === false) {
    const pending = signals.manual_kpis_pending || 0
    factors.push({ factor: DIAGNOSTIC_FACTOR.DATA_INCOMPLETE, detail: pending > 0 ? `${pending} KPI(s) pending manual entry.` : 'Incomplete data for scoring.' })
  }
  if (signals.attainment_pct != null && signals.attainment_pct < 50) {
    factors.push({ factor: DIAGNOSTIC_FACTOR.ATTAINMENT_GAP, detail: `Attainment: ${signals.attainment_pct.toFixed(0)}% of target.` })
  }

  // ── Insufficient signal ──
  if (signals.reachability === 'DATA_MISSING') {
    factors.push({ factor: DIAGNOSTIC_FACTOR.INSUFFICIENT_SIGNAL, detail: 'No reachability data available.' })
  }

  // Always at least one factor for unknown
  if (factors.length === 0) {
    factors.push({ factor: DIAGNOSTIC_FACTOR.INSUFFICIENT_SIGNAL, detail: 'No diagnostic signals detected.' })
  }

  return factors
}

/**
 * Extrae el factor dominante (mayor prioridad).
 */
export function extractDominantDiagnosticFactor(signals = {}) {
  const factors = extractDiagnosticFactors(signals)
  if (factors.length === 0) return { factor: DIAGNOSTIC_FACTOR.INSUFFICIENT_SIGNAL, detail: 'No data' }

  for (const priorityFactor of FACTOR_PRIORITY) {
    const match = factors.find(f => f.factor === priorityFactor)
    if (match) return match
  }

  return factors[0]
}

/**
 * Construye una explicación diagnóstica completa para un estado operacional.
 * Retorna objeto estructurado con dominant factor, secondary factors, y severity.
 */
export function buildDiagnosticExplanation(signals = {}) {
  const severity = signals.__severity || getDecisionSeverity(signals)
  const allFactors = extractDiagnosticFactors(signals)
  const dominant = extractDominantDiagnosticFactor(signals)

  const secondary = allFactors
    .filter(f => f.factor !== dominant.factor)
    .slice(0, 2) // max 2 secondary factors

  return {
    severity,
    dominantFactor: dominant,
    secondaryFactors: secondary,
    allFactors,
    summary: `${FACTOR_LABEL[dominant.factor] || dominant.factor}: ${dominant.detail}`,
  }
}

/**
 * Explica estado BLOCKED.
 */
export function explainBlockedState(signals = {}) {
  const diag = buildDiagnosticExplanation({ ...signals, __severity: DECISION_SEVERITY.BLOCKED })
  return {
    ...diag,
    prefix: 'Blocked due to',
    explanation: `Blocked due to ${FACTOR_LABEL[diag.dominantFactor.factor]?.toLowerCase() || diag.dominantFactor.factor}. ${diag.dominantFactor.detail}`,
  }
}

/**
 * Explica estado CRITICAL.
 */
export function explainCriticalState(signals = {}) {
  const diag = buildDiagnosticExplanation({ ...signals, __severity: DECISION_SEVERITY.CRITICAL })
  return {
    ...diag,
    prefix: 'Critical due to',
    explanation: `Critical due to ${FACTOR_LABEL[diag.dominantFactor.factor]?.toLowerCase() || diag.dominantFactor.factor}. ${diag.dominantFactor.detail}`,
  }
}

/**
 * Explica estado ELEVATED.
 */
export function explainElevatedState(signals = {}) {
  const diag = buildDiagnosticExplanation({ ...signals, __severity: DECISION_SEVERITY.ELEVATED })
  return {
    ...diag,
    prefix: 'Elevated due to',
    explanation: `Elevated due to ${FACTOR_LABEL[diag.dominantFactor.factor]?.toLowerCase() || diag.dominantFactor.factor}. ${diag.dominantFactor.detail}`,
  }
}

/**
 * Explica estado UNKNOWN.
 */
export function explainUnknownState(signals = {}) {
  const diag = buildDiagnosticExplanation({ ...signals, __severity: DECISION_SEVERITY.UNKNOWN })
  return {
    ...diag,
    prefix: 'Unknown because',
    explanation: `Unknown: ${diag.dominantFactor.detail}`,
  }
}

/**
 * Resume señales diagnósticas en formato legible.
 */
export function summarizeDiagnosticSignals(signals = {}) {
  const parts = []
  if (signals.gap_pct != null) parts.push(`gap: ${signals.gap_pct.toFixed(1)}%`)
  if (signals.gap_trips_pct != null) parts.push(`trips: ${signals.gap_trips_pct.toFixed(1)}%`)
  if (signals.gap_revenue_pct != null) parts.push(`revenue: ${signals.gap_revenue_pct.toFixed(1)}%`)
  if (signals.confidence_score != null) parts.push(`conf: ${signals.confidence_score}`)
  if (signals.trust_status) parts.push(`trust: ${signals.trust_status}`)
  if (signals.freshness_status) parts.push(`freshness: ${signals.freshness_status}`)
  return parts.join(' · ') || 'No signals'
}

/* ── EXPORTS ── */

export { FACTOR_PRIORITY, FACTOR_LABEL }
export default {
  DIAGNOSTIC_FACTOR,
  extractDiagnosticFactors,
  extractDominantDiagnosticFactor,
  buildDiagnosticExplanation,
  explainBlockedState,
  explainCriticalState,
  explainElevatedState,
  explainUnknownState,
  summarizeDiagnosticSignals,
}
