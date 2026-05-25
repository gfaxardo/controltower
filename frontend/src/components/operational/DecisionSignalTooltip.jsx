/**
 * DecisionSignalTooltip — Tooltip explicativo de severidad.
 * 
 * Muestra las razones que produjeron una severidad operacional.
 * Usado en hover/focus de badges de severidad.
 * 
 * Motor: Control Foundation
 */
import { useMemo } from 'react'
import { explainDecisionSeverity } from '../../utils/operationalDecisionSeverity'

/**
 * @param {object} props
 * @param {object} props.data - Datos con señales operacionales
 * @param {boolean} [props.showIfNormal] - Mostrar también para NORMAL (default: false)
 */
export default function DecisionSignalTooltip({ data, showIfNormal = false }) {
  const explanation = useMemo(() => explainDecisionSeverity(data), [data])

  if (!showIfNormal && explanation.severity === 'normal') return null

  return (
    <div className="rounded-md border border-ct-border bg-ct-card p-2.5 shadow-sm max-w-xs text-left">
      <div className="flex items-center gap-1.5 mb-1.5">
        <DecisionSeverityBadge severity={explanation.severity} compact />
        <span className="text-xs font-semibold text-ct-text">{explanation.label}</span>
      </div>
      <div className="flex flex-col gap-0.5">
        {explanation.reasons.map((r, i) => (
          <span key={i} className="text-[11px] text-ct-text2 leading-snug">
            {r}
          </span>
        ))}
      </div>
    </div>
  )
}

// Local import for the badge inside the tooltip
function DecisionSeverityBadge({ severity, compact }) {
  if (compact) {
    const dotColor = severity === 'blocked' ? '#dc2626' : severity === 'critical' ? '#ef4444' : severity === 'elevated' ? '#f59e0b' : severity === 'warning' ? '#fbbf24' : severity === 'normal' ? '#22c55e' : '#d6d3d0'
    return <span className="ct-severity-dot" style={{background: dotColor}} />
  }
  return null
}
