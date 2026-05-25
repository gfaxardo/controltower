/**
 * OPERATIONAL DECISION SEVERITY — Contract Canónico
 * 
 * Centraliza todas las severities operacionales.
 * Ningún componente debe hardcodear thresholds ni definir severities propias.
 * 
 * Motor: Control Foundation + Diagnostic Engine Temprano
 * NO es Decision Engine. NO es Suggestion Engine.
 */

/* ── CONSTANTS ── */

/** Severities canónicas. Único vocabulario permitido. */
export const DECISION_SEVERITY = Object.freeze({
  BLOCKED:  'blocked',
  CRITICAL: 'critical',
  ELEVATED: 'elevated',
  WARNING:  'warning',
  NORMAL:   'normal',
  UNKNOWN:  'unknown',
})

/** Orden de prioridad (menor = más urgente) */
export const DECISION_PRIORITY_ORDER = Object.freeze({
  [DECISION_SEVERITY.BLOCKED]:  0,
  [DECISION_SEVERITY.CRITICAL]: 1,
  [DECISION_SEVERITY.ELEVATED]: 2,
  [DECISION_SEVERITY.WARNING]:  3,
  [DECISION_SEVERITY.NORMAL]:   4,
  [DECISION_SEVERITY.UNKNOWN]:  5,
})

/** Thresholds centralizados para determinar severidad */
export const DECISION_THRESHOLDS = Object.freeze({
  /** gap_pct: desviación porcentual sobre plan */
  gap_critical: 30,    // >30% gap → critical
  gap_elevated: 15,    // >15% gap → elevated
  gap_warning:  5,     // >5%  gap → warning

  /** confidence_score: confianza en los datos (0-100) */
  confidence_blocked: 10,   // <10  → blocked
  confidence_critical: 25,  // <25  → critical
  confidence_warning:  50,  // <50  → warning

  /** attainment_pct: porcentaje de alcance */
  attainment_blocked:  30,  // <30% attainment → blocked
  attainment_critical: 50,  // <50% attainment → critical
  attainment_elevated: 75,  // <75% attainment → elevated
  attainment_warning:  95,  // <95% attainment → warning
})

/* ── TONE MAPPING ── */

const SEVERITY_TONE = Object.freeze({
  [DECISION_SEVERITY.BLOCKED]:  { bg: '#fee2e2', text: '#991b1b', border: '#fecaca', dot: '#dc2626' },
  [DECISION_SEVERITY.CRITICAL]: { bg: '#fee2e2', text: '#991b1b', border: '#fecaca', dot: '#ef4444' },
  [DECISION_SEVERITY.ELEVATED]: { bg: '#fef3c7', text: '#92400e', border: '#fde68a', dot: '#f59e0b' },
  [DECISION_SEVERITY.WARNING]:  { bg: '#fffbeb', text: '#92400e', border: '#fde68a', dot: '#fbbf24' },
  [DECISION_SEVERITY.NORMAL]:   { bg: '#f0fdf4', text: '#065f46', border: '#bbf7d0', dot: '#22c55e' },
  [DECISION_SEVERITY.UNKNOWN]:  { bg: '#f5f3f0', text: '#78716c', border: '#e7e5e2', dot: '#d6d3d0' },
})

const SEVERITY_LABEL = Object.freeze({
  [DECISION_SEVERITY.BLOCKED]:  'Blocked',
  [DECISION_SEVERITY.CRITICAL]: 'Critical',
  [DECISION_SEVERITY.ELEVATED]: 'Elevated',
  [DECISION_SEVERITY.WARNING]:  'Warning',
  [DECISION_SEVERITY.NORMAL]:   'Normal',
  [DECISION_SEVERITY.UNKNOWN]:  'Unknown',
})

/* ── PURE FUNCTIONS ── */

/**
 * Normaliza un input de señal operacional a severidad canónica.
 * Acepta señales existentes de múltiples fuentes.
 */
export function normalizeDecisionSignal(input = {}) {
  const {
    trust_status,
    decision_mode,
    comparison_status,
    freshness_status,
    // numéricos
    gap_pct,
    gap_trips_pct,
    gap_revenue_pct,
    confidence_score,
    attainment_pct,
    // alert-specific
    unit_alert,
    severity,
    priority_band,
    max_severity,
    // booleanas
    meets_oro,
    data_complete,
    has_any_targets,
    // strings
    reachability,
    signal,
  } = input

  // ── BLOCKED ──
  if (trust_status === 'blocked') return DECISION_SEVERITY.BLOCKED
  if (decision_mode === 'BLOCKED') return DECISION_SEVERITY.BLOCKED
  if (comparison_status === 'missing_plan') return DECISION_SEVERITY.BLOCKED
  if (freshness_status === 'critical') return DECISION_SEVERITY.BLOCKED
  if (confidence_score != null && confidence_score < DECISION_THRESHOLDS.confidence_blocked) return DECISION_SEVERITY.BLOCKED
  if (attainment_pct != null && attainment_pct < DECISION_THRESHOLDS.attainment_blocked) return DECISION_SEVERITY.BLOCKED

  // ── CRITICAL ──
  const gapVal = gap_pct ?? gap_trips_pct ?? gap_revenue_pct
  if (gapVal != null && Math.abs(gapVal) > DECISION_THRESHOLDS.gap_critical) return DECISION_SEVERITY.CRITICAL
  if (unit_alert === true) return DECISION_SEVERITY.CRITICAL
  if (severity === 'P0' || severity === 'P1' || severity === 'critical') return DECISION_SEVERITY.CRITICAL
  if (max_severity === 'STRONG_DEGRADATION') return DECISION_SEVERITY.CRITICAL
  if (priority_band === 'CRITICAL') return DECISION_SEVERITY.CRITICAL
  if (confidence_score != null && confidence_score < DECISION_THRESHOLDS.confidence_critical) return DECISION_SEVERITY.CRITICAL
  if (attainment_pct != null && attainment_pct < DECISION_THRESHOLDS.attainment_critical) return DECISION_SEVERITY.CRITICAL

  // ── ELEVATED ──
  if (gapVal != null && Math.abs(gapVal) > DECISION_THRESHOLDS.gap_elevated) return DECISION_SEVERITY.ELEVATED
  if (severity === 'P2' || severity === 'high') return DECISION_SEVERITY.ELEVATED
  if (max_severity === 'MODERATE_DEGRADATION') return DECISION_SEVERITY.ELEVATED
  if (priority_band === 'HIGH') return DECISION_SEVERITY.ELEVATED
  if (freshness_status === 'stale') return DECISION_SEVERITY.ELEVATED
  if (attainment_pct != null && attainment_pct < DECISION_THRESHOLDS.attainment_elevated) return DECISION_SEVERITY.ELEVATED

  // ── WARNING ──
  if (gapVal != null && Math.abs(gapVal) > DECISION_THRESHOLDS.gap_warning) return DECISION_SEVERITY.WARNING
  if (severity === 'P3' || severity === 'low') return DECISION_SEVERITY.WARNING
  if (max_severity === 'EARLY_WARNING') return DECISION_SEVERITY.WARNING
  if (priority_band === 'MEDIUM' || priority_band === 'LOW') return DECISION_SEVERITY.WARNING
  if (confidence_score != null && confidence_score < DECISION_THRESHOLDS.confidence_warning) return DECISION_SEVERITY.WARNING
  if (comparison_status === 'plan_without_real') return DECISION_SEVERITY.WARNING
  if (meets_oro === false) return DECISION_SEVERITY.WARNING
  if (data_complete === false) return DECISION_SEVERITY.WARNING
  if (has_any_targets === false) return DECISION_SEVERITY.WARNING
  if (attainment_pct != null && attainment_pct < DECISION_THRESHOLDS.attainment_warning) return DECISION_SEVERITY.WARNING

  // ── NORMAL ──
  if (signal === 'green' || reachability === 'ON_TRACK' || meets_oro === true) return DECISION_SEVERITY.NORMAL
  if (comparison_status === 'matched') return DECISION_SEVERITY.NORMAL
  if (trust_status === 'ok') return DECISION_SEVERITY.NORMAL

  // ── UNKNOWN ──
  if (reachability === 'DATA_MISSING') return DECISION_SEVERITY.UNKNOWN
  if (confidence_score == null && gapVal == null && attainment_pct == null) return DECISION_SEVERITY.UNKNOWN

  return DECISION_SEVERITY.UNKNOWN
}

/**
 * Retorna la severidad canónica de una entidad.
 * Si ya tiene severity canónica, la retorna directamente.
 * Si tiene señales crudas, las normaliza.
 * Si no tiene señales, retorna UNKNOWN.
 */
export function getDecisionSeverity(entity = {}) {
  // Si ya es una severity canónica
  if (entity.__decisionSeverity) return entity.__decisionSeverity
  if (entity.severity && Object.values(DECISION_SEVERITY).includes(entity.severity)) {
    return entity.severity
  }

  // Normalizar desde señales crudas
  const severity = normalizeDecisionSignal(entity.__signals || entity)
  return severity
}

/** Tono visual (colores) para una severidad */
export function getDecisionTone(severity) {
  return SEVERITY_TONE[severity] || SEVERITY_TONE[DECISION_SEVERITY.UNKNOWN]
}

/** Label corto para una severidad */
export function getDecisionLabel(severity) {
  return SEVERITY_LABEL[severity] || severity
}

/** Rank numérico de prioridad (menor = más urgente) */
export function getDecisionRank(severity) {
  return DECISION_PRIORITY_ORDER[severity] ?? DECISION_PRIORITY_ORDER[DECISION_SEVERITY.UNKNOWN]
}

/**
 * Ordena items por prioridad operacional.
 * Modifica el orden pero NO modifica los items.
 * Retorna nuevo array.
 */
export function sortByDecisionPriority(items, signalExtractor = (item) => item) {
  return [...items].sort((a, b) => {
    const sa = getDecisionRank(getDecisionSeverity(signalExtractor(a)))
    const sb = getDecisionRank(getDecisionSeverity(signalExtractor(b)))
    return sa - sb
  })
}

/**
 * Explica qué señales produjeron una severidad.
 * Retorna array de strings legibles.
 */
export function explainDecisionSeverity(input = {}) {
  const severity = getDecisionSeverity(input)
  const reasons = []

  const signals = input.__signals || input

  if (signals.trust_status && signals.trust_status !== 'ok') {
    reasons.push(`Trust: ${signals.trust_status}`)
  }
  if (signals.decision_mode && signals.decision_mode !== 'SAFE') {
    reasons.push(`Decision mode: ${signals.decision_mode}`)
  }
  if (signals.comparison_status && signals.comparison_status !== 'matched') {
    reasons.push(`Comparison: ${signals.comparison_status}`)
  }
  if (signals.freshness_status && signals.freshness_status !== 'fresh') {
    reasons.push(`Freshness: ${signals.freshness_status}`)
  }
  if (signals.gap_pct != null) {
    reasons.push(`Gap: ${signals.gap_pct.toFixed(1)}%`)
  }
  if (signals.gap_trips_pct != null) {
    reasons.push(`Trips gap: ${signals.gap_trips_pct.toFixed(1)}%`)
  }
  if (signals.gap_revenue_pct != null) {
    reasons.push(`Revenue gap: ${signals.gap_revenue_pct.toFixed(1)}%`)
  }
  if (signals.confidence_score != null) {
    reasons.push(`Confidence: ${signals.confidence_score}`)
  }
  if (signals.attainment_pct != null) {
    reasons.push(`Attainment: ${signals.attainment_pct.toFixed(0)}%`)
  }
  if (signals.unit_alert === true) {
    reasons.push(`Unit alert triggered`)
  }
  if (signals.meets_oro === false) {
    reasons.push(`Below Oro threshold`)
  }
  if (signals.data_complete === false) {
    reasons.push(`Data incomplete`)
  }

  return {
    severity,
    label: getDecisionLabel(severity),
    reasons: reasons.length > 0 ? reasons : ['Insufficient signal data'],
  }
}

/* ── EXPORTS ── */

export { SEVERITY_TONE, SEVERITY_LABEL }
export default {
  DECISION_SEVERITY,
  DECISION_PRIORITY_ORDER,
  DECISION_THRESHOLDS,
  normalizeDecisionSignal,
  getDecisionSeverity,
  getDecisionTone,
  getDecisionLabel,
  getDecisionRank,
  sortByDecisionPriority,
  explainDecisionSeverity,
}
