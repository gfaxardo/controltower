/**
 * Decision layer colors — semantic signals for operational UI.
 * Use for KPIs, severity badges, priority scores, and risk bands.
 */
export const decisionColors = {
  good: '#22c55e',
  warning: '#f59e0b',
  critical: '#ef4444',
  neutral: '#64748b',
  info: '#3b82f6'
}

/** Tailwind classes for badges/chips using decision semantics */
export const decisionColorClasses = {
  good: 'bg-green-100 text-green-800 border-green-200',
  warning: 'bg-amber-100 text-amber-800 border-amber-200',
  critical: 'bg-red-100 text-red-800 border-red-200',
  neutral: 'bg-gray-100 text-gray-700 border-gray-200',
  info: 'bg-blue-100 text-blue-800 border-blue-200'
}

/** Severity → decision color key */
export const severityToDecision = {
  critical: 'critical',
  moderate: 'warning',
  positive: 'good',
  neutral: 'neutral',
  info: 'info'
}

/**
 * KPI color for conversion rate (e.g. %)
 * > 35% good, 20–35% warning, < 20% critical
 */
export function conversionRateDecision (pct) {
  if (pct == null || Number.isNaN(Number(pct))) return 'neutral'
  const n = Number(pct)
  if (n > 35) return 'good'
  if (n >= 20) return 'warning'
  return 'critical'
}

/**
 * KPI color for reactivation rate (e.g. %)
 * > 10% good, 5–10% warning, < 5% critical
 */
export function reactivationRateDecision (pct) {
  if (pct == null || Number.isNaN(Number(pct))) return 'neutral'
  const n = Number(pct)
  if (n > 10) return 'good'
  if (n >= 5) return 'warning'
  return 'critical'
}

/**
 * KPI color for driver downgrades (% of cohort)
 * > 15% critical, 5–15% warning, < 5% good
 */
export function downgradeRateDecision (pct) {
  if (pct == null || Number.isNaN(Number(pct))) return 'neutral'
  const n = Number(pct)
  if (n > 15) return 'critical'
  if (n >= 5) return 'warning'
  return 'good'
}

/**
 * Priority score 0–100 → decision
 * 80–100 critical (red), 50–79 warning (amber), 0–49 good (green)
 */
export function priorityScoreDecision (score) {
  if (score == null || Number.isNaN(Number(score))) return 'neutral'
  const n = Number(score)
  if (n >= 80) return 'critical'
  if (n >= 50) return 'warning'
  return 'good'
}

/**
 * Delta % for trend arrow and color
 * negative → critical, positive → good, near zero → neutral
 */
export function deltaPctDecision (deltaPct) {
  if (deltaPct == null || Number.isNaN(Number(deltaPct))) return 'neutral'
  const n = Number(deltaPct)
  if (n < -0.05) return 'critical'
  if (n > 0.05) return 'good'
  return 'neutral'
}
