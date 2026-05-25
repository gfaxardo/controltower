/**
 * OPERATIONAL ATTENTION ROUTING
 * 
 * Routing visual de atención operacional.
 * Ordena items por severidad para guiar atención del operador.
 * 
 * NO modifica datos originales.
 * NO introduce lógica de decisión.
 * Solo: routing visual.
 * 
 * Motor: Control Foundation + Diagnostic Engine Temprano
 */

import {
  DECISION_SEVERITY,
  DECISION_PRIORITY_ORDER,
  getDecisionSeverity,
  getDecisionRank,
} from './operationalDecisionSeverity'

/**
 * Separa items en buckets operacionales.
 * Útil para mostrar blocked/critical primero, luego el resto.
 */
export function partitionBySeverity(items, signalExtractor) {
  const blocked   = []
  const critical  = []
  const elevated  = []
  const warning   = []
  const normal    = []
  const unknown   = []

  for (const item of items) {
    const severity = getDecisionSeverity(signalExtractor ? signalExtractor(item) : item)
    switch (severity) {
      case DECISION_SEVERITY.BLOCKED:  blocked.push(item); break
      case DECISION_SEVERITY.CRITICAL: critical.push(item); break
      case DECISION_SEVERITY.ELEVATED: elevated.push(item); break
      case DECISION_SEVERITY.WARNING:  warning.push(item); break
      case DECISION_SEVERITY.NORMAL:   normal.push(item); break
      default:                          unknown.push(item); break
    }
  }

  return { blocked, critical, elevated, warning, normal, unknown }
}

/**
 * Ordena items manteniendo estabilidad visual.
 * Blocked/critical primero, unknown al final.
 * Items del mismo bucket mantienen orden original.
 */
export function stablePrioritySort(items, signalExtractor) {
  const buckets = partitionBySeverity(items, signalExtractor)
  return [
    ...buckets.blocked,
    ...buckets.critical,
    ...buckets.elevated,
    ...buckets.warning,
    ...buckets.normal,
    ...buckets.unknown,
  ]
}

/**
 * Computa un resumen de atención para un conjunto de items.
 * Útil para mostrar "X blocked, Y critical" en headers.
 */
export function getAttentionSummary(items, signalExtractor) {
  const summary = { blocked: 0, critical: 0, elevated: 0, warning: 0, normal: 0, unknown: 0, total: items.length }
  for (const item of items) {
    const severity = getDecisionSeverity(signalExtractor ? signalExtractor(item) : item)
    summary[severity] = (summary[severity] || 0) + 1
  }
  return summary
}

/**
 * Retorna el porcentaje de items que requieren atención inmediata.
 */
export function getAttentionRatio(items, signalExtractor) {
  if (items.length === 0) return 0
  const summary = getAttentionSummary(items, signalExtractor)
  const needingAttention = summary.blocked + summary.critical + summary.elevated
  return Math.round((needingAttention / items.length) * 100)
}

export default {
  partitionBySeverity,
  stablePrioritySort,
  getAttentionSummary,
  getAttentionRatio,
}
