/**
 * DiagnosticDominantFactor — Factor dominante en una sola línea.
 * Muestra "Critical due to {factor}." con el detalle.
 * 
 * Motor: Diagnostic Engine (temprano)
 */
import { useMemo } from 'react'
import { buildDiagnosticExplanation } from '../../utils/diagnosticExplanationEngine'
import DiagnosticFactorBadge from './DiagnosticFactorBadge'

/**
 * @param {object} props
 * @param {object} props.signals - Operational signals
 * @param {string} [props.className]
 */
export default function DiagnosticDominantFactor({ signals, className = '' }) {
  const explanation = useMemo(() => buildDiagnosticExplanation(signals), [signals])

  const { severity, dominantFactor } = explanation
  if (!dominantFactor) return null

  // Solo mostrar para severities que requieren atención
  if (severity === 'normal') return null

  const severityPrefix = severity === 'blocked' ? 'Blocked due to'
    : severity === 'critical' ? 'Critical due to'
    : severity === 'elevated' ? 'Elevated due to'
    : severity === 'warning' ? 'Warning'
    : 'Unknown'

  return (
    <div className={`flex items-center gap-1.5 text-xs ${className}`}>
      <span className="font-semibold text-ct-text whitespace-nowrap">{severityPrefix}</span>
      <DiagnosticFactorBadge factor={dominantFactor.factor} detail={dominantFactor.detail} />
    </div>
  )
}
