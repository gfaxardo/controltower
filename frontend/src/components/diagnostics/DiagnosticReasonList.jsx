/**
 * DiagnosticReasonList — Lista compacta de razones diagnósticas.
 * Para usar dentro de tooltips o paneles expandibles.
 * 
 * Motor: Diagnostic Engine (temprano)
 */
import { useMemo } from 'react'
import { extractDiagnosticFactors } from '../../utils/diagnosticExplanationEngine'
import DiagnosticFactorBadge from './DiagnosticFactorBadge'

/**
 * @param {object} props
 * @param {object} props.signals - Operational signals
 * @param {number} [props.maxItems] - Max factors to show (default: 4)
 * @param {string} [props.className]
 */
export default function DiagnosticReasonList({
  signals,
  maxItems = 4,
  className = '',
}) {
  const factors = useMemo(() => {
    const all = extractDiagnosticFactors(signals)
    return maxItems ? all.slice(0, maxItems) : all
  }, [signals, maxItems])

  if (factors.length === 0) return null

  return (
    <div className={`flex flex-col gap-0.5 ${className}`}>
      {factors.map((f, i) => (
        <DiagnosticFactorBadge key={i} factor={f.factor} detail={f.detail} />
      ))}
    </div>
  )
}
