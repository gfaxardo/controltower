/**
 * Explainability semantics: behavior direction, persistence labels, colors.
 * Used by Behavioral Alerts and Action Engine for consistent UX.
 */

/** Derive human-readable "Estado conductual" from row (driver or cohort aggregate). */
export function getBehaviorDirection (row) {
  if (!row) return '—'
  const deltaPct = row.delta_pct != null ? Number(row.delta_pct) : null
  const declining = (row.weeks_declining_consecutively ?? 0) | 0
  const rising = (row.weeks_rising_consecutively ?? 0) | 0
  const alertType = row.alert_type || ''

  if (alertType === 'Sudden Stop') return 'Empeorando'
  if (alertType === 'High Volatility') return 'Volátil'
  if (alertType === 'Strong Recovery' || (deltaPct != null && deltaPct > 0.2 && rising >= 1)) return 'En recuperación'
  if (deltaPct != null && deltaPct > 0.05 && (rising >= 2 || alertType === 'Strong Recovery')) return 'Mejorando'
  if (deltaPct != null && deltaPct < -0.05 && (declining >= 2 || ['Critical Drop', 'Moderate Drop'].includes(alertType))) return 'Empeorando'
  if (deltaPct != null && deltaPct > 0.05) return 'Mejorando'
  if (deltaPct != null && deltaPct < -0.05) return 'Empeorando'
  return 'Estable'
}

/** Persistence label: "X semanas en deterioro" / "X semanas recuperándose". */
export function getPersistenceLabel (row) {
  if (!row) return '—'
  const declining = (row.weeks_declining_consecutively ?? 0) | 0
  const rising = (row.weeks_rising_consecutively ?? 0) | 0
  if (declining >= 1) return `${declining} sem. en deterioro`
  if (rising >= 1) return `${rising} sem. recuperándose`
  return '—'
}

/** CSS classes for behavior direction (badges/chips). */
export const BEHAVIOR_DIRECTION_COLORS = {
  Empeorando: 'bg-red-100 text-red-800 border-red-200',
  Mejorando: 'bg-green-100 text-green-800 border-green-200',
  'En recuperación': 'bg-green-100 text-green-800 border-green-200',
  Estable: 'bg-gray-100 text-gray-700 border-gray-200',
  Volátil: 'bg-purple-100 text-purple-800 border-purple-200',
  '—': 'bg-gray-50 text-gray-500 border-gray-200'
}

/** Delta % color by sign (for table cells). */
export function getDeltaPctColor (deltaPct) {
  if (deltaPct == null) return ''
  const n = Number(deltaPct)
  if (n < -0.05) return 'text-red-600 font-medium'
  if (n > 0.05) return 'text-green-600 font-medium'
  return 'text-gray-600'
}

/** Risk band semantic colors. */
export const RISK_BAND_COLORS = {
  'high risk': 'bg-red-100 text-red-800 border-red-200',
  'medium risk': 'bg-amber-100 text-amber-800 border-amber-200',
  monitor: 'bg-blue-50 text-blue-800 border-blue-200',
  stable: 'bg-gray-100 text-gray-700 border-gray-200'
}

/** Alert type semantic colors (aligned with severity). Precedence: Sudden Stop, Critical Drop, Moderate Drop, Silent Erosion, High Volatility, Strong Recovery, Stable Performer. */
export const ALERT_COLORS = {
  'Sudden Stop': 'bg-red-100 text-red-800 border-red-200',
  'Critical Drop': 'bg-red-100 text-red-800 border-red-200',
  'Moderate Drop': 'bg-amber-100 text-amber-800 border-amber-200',
  'Strong Recovery': 'bg-green-100 text-green-800 border-green-200',
  'Silent Erosion': 'bg-yellow-100 text-yellow-800 border-yellow-200',
  'High Volatility': 'bg-purple-100 text-purple-800 border-purple-200',
  'Stable Performer': 'bg-gray-100 text-gray-700 border-gray-200'
}

/** Severity semantic colors. */
export const SEVERITY_COLORS = {
  critical: 'bg-red-100 text-red-800 border-red-200',
  moderate: 'bg-amber-100 text-amber-800 border-amber-200',
  positive: 'bg-green-100 text-green-800 border-green-200',
  neutral: 'bg-gray-100 text-gray-700 border-gray-200'
}

/** Time/decision context label for a row (e.g. "Última semana vs baseline 6 sem."). */
export function getDecisionContextLabel (baselineWeeks = 6) {
  return `Última semana vs baseline ${baselineWeeks} sem.`
}

/** Action rationale short text by cohort_type (for cards and drilldown). */
export const COHORT_RATIONALE = {
  high_value_deteriorating: 'Proteger supply premium antes de mayor caída.',
  silent_erosion: 'Detectar deterioro oculto antes de que colapse el segmento.',
  recoverable_mid_performers: 'Acelerar conversión a mayor productividad.',
  near_upgrade_opportunity: 'Fijar subida de segmento.',
  near_drop_risk: 'Evitar caída al segmento inferior.',
  volatile_drivers: 'Revisar patrón antes de contactar.',
  high_value_recovery_candidates: 'Reactivar de alto ROI.'
}
