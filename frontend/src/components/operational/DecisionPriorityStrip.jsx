/**
 * DecisionPriorityStrip — Tira horizontal de resumen de prioridad.
 * 
 * Muestra conteo de items por severidad en una tira compacta.
 * Ideal para headers de sección o toolbars.
 * 
 * Motor: Control Foundation
 */
import { useMemo } from 'react'
import { getAttentionSummary } from '../../utils/operationalAttentionRouting'

/**
 * @param {object} props
 * @param {Array}  props.items - Items a resumir
 * @param {Function} [props.signalExtractor] - Extrae señales de cada item
 * @param {boolean} [props.showNormal] - Mostrar conteo normal (default: false)
 * @param {boolean} [props.showUnknown] - Mostrar conteo unknown (default: false)
 * @param {string} [props.className]
 */
export default function DecisionPriorityStrip({
  items = [],
  signalExtractor,
  showNormal = false,
  showUnknown = false,
  className = '',
}) {
  const summary = useMemo(() => getAttentionSummary(items, signalExtractor), [items, signalExtractor])

  if (items.length === 0) return null

  const segments = []
  if (summary.blocked > 0) {
    segments.push(
      <span key="b" className="inline-flex items-center gap-1 px-1.5 py-px rounded text-xs font-bold bg-red-100 text-red-800 border border-red-200">
        {summary.blocked} blocked
      </span>
    )
  }
  if (summary.critical > 0) {
    segments.push(
      <span key="c" className="inline-flex items-center gap-1 px-1.5 py-px rounded text-xs font-bold bg-red-50 text-red-700 border border-red-100">
        {summary.critical} critical
      </span>
    )
  }
  if (summary.elevated > 0) {
    segments.push(
      <span key="e" className="inline-flex items-center gap-1 px-1.5 py-px rounded text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
        {summary.elevated} elevated
      </span>
    )
  }
  if (summary.warning > 0) {
    segments.push(
      <span key="w" className="inline-flex items-center gap-1 px-1.5 py-px rounded text-xs font-medium bg-amber-50/50 text-amber-600 border border-amber-100">
        {summary.warning} warning
      </span>
    )
  }
  if (showNormal && summary.normal > 0) {
    segments.push(
      <span key="n" className="inline-flex items-center gap-1 px-1.5 py-px rounded text-xs text-emerald-600">
        {summary.normal} normal
      </span>
    )
  }
  if (showUnknown && summary.unknown > 0) {
    segments.push(
      <span key="u" className="inline-flex items-center gap-1 px-1.5 py-px rounded text-xs text-ct-text3">
        {summary.unknown} unknown
      </span>
    )
  }

  if (segments.length === 0) return null

  return (
    <div className={`flex flex-wrap items-center gap-1 ${className}`} role="status" aria-label="Resumen de atención operacional">
      {segments}
    </div>
  )
}
