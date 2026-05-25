/**
 * DiagnosticExplanationCard — Panel compacto de explicación diagnóstica.
 * 
 * Muestra la explicación estructurada:
 * 1. Dominant factor (siempre visible)
 * 2. Secondary factors (si existen)
 * 3. Signal summary (colapsado por default)
 * 
 * Motor: Diagnostic Engine (temprano)
 */
import { useMemo } from 'react'
import { buildDiagnosticExplanation, summarizeDiagnosticSignals } from '../../utils/diagnosticExplanationEngine'
import DiagnosticFactorBadge from './DiagnosticFactorBadge'
import DecisionSeverityBadge from '../operational/DecisionSeverityBadge'

/**
 * @param {object} props
 * @param {object} props.signals - Operational signals
 * @param {boolean} [props.showIfNormal] - Mostrar incluso si es NORMAL (default: false)
 * @param {string} [props.className]
 */
export default function DiagnosticExplanationCard({
  signals,
  showIfNormal = false,
  className = '',
}) {
  const explanation = useMemo(() => buildDiagnosticExplanation(signals), [signals])

  const { severity, dominantFactor, secondaryFactors } = explanation
  if (!dominantFactor) return null
  if (!showIfNormal && severity === 'normal') return null

  const signalSummary = summarizeDiagnosticSignals(signals)

  return (
    <div className={`rounded-md border border-ct-border bg-ct-card p-2.5 ${className}`} role="status">
      {/* Dominant factor row */}
      <div className="flex items-center gap-2">
        <DecisionSeverityBadge severity={severity} compact />
        <span className="text-xs font-semibold text-ct-text">
          {severity === 'blocked' ? 'Blocked' : severity === 'critical' ? 'Critical' : severity === 'elevated' ? 'Elevated' : severity === 'warning' ? 'Warning' : 'Unknown'}
        </span>
        <DiagnosticFactorBadge factor={dominantFactor.factor} detail={dominantFactor.detail} />
      </div>

      {/* Secondary factors */}
      {secondaryFactors.length > 0 && (
        <div className="mt-1.5 ml-4 pl-2 border-l-2 border-ct-border/50">
          <div className="flex flex-wrap gap-1">
            {secondaryFactors.map((f, i) => (
              <DiagnosticFactorBadge key={i} factor={f.factor} showDetail={false} />
            ))}
          </div>
        </div>
      )}

      {/* Signal summary */}
      <div className="mt-1.5 pt-1.5 border-t border-ct-border/50 text-[11px] text-ct-text3">
        {signalSummary}
      </div>
    </div>
  )
}
