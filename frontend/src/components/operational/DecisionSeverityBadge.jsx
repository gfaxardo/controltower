/**
 * DecisionSeverityBadge — Badge compacto de severidad operacional.
 * 
 * Muestra la severidad canónica en un chip visual ligero.
 * NO domina viewport. NO repite información.
 * 
 * Motor: Control Foundation
 */
import { useMemo } from 'react'
import { getDecisionSeverity, getDecisionTone, getDecisionLabel } from '../../utils/operationalDecisionSeverity'

/**
 * @param {object} props
 * @param {object} props.entity - Entidad con señales operacionales
 * @param {object} [props.signals] - Señales explícitas (alternativa a entity)
 * @param {string} [props.severity] - Severidad canónica directa (atajo)
 * @param {boolean} [props.showLabel] - Mostrar texto (default: true)
 * @param {boolean} [props.compact] - Modo solo-dot (default: false)
 * @param {string} [props.className]
 */
export default function DecisionSeverityBadge({
  entity,
  signals,
  severity: explicitSeverity,
  showLabel = true,
  compact = false,
  className = '',
}) {
  const severity = useMemo(() => {
    if (explicitSeverity) return explicitSeverity
    if (signals) return getDecisionSeverity(signals)
    if (entity) return getDecisionSeverity(entity)
    return 'unknown'
  }, [explicitSeverity, signals, entity])

  const tone = useMemo(() => getDecisionTone(severity), [severity])

  if (compact) {
    return (
      <span
        className={`ct-severity-dot ct-severity-dot--${severity === 'blocked' || severity === 'critical' ? 'bad' : severity === 'elevated' || severity === 'warning' ? 'warn' : severity === 'normal' ? 'ok' : 'warn'} ${className}`}
        title={getDecisionLabel(severity)}
        role="status"
        aria-label={getDecisionLabel(severity)}
      />
    )
  }

  return (
    <span
      className={`ct-badge ${severity === 'blocked' || severity === 'critical' ? 'ct-badge--bad' : severity === 'elevated' || severity === 'warning' ? 'ct-badge--warn' : severity === 'normal' ? 'ct-badge--ok' : 'ct-badge--neutral'} ${className}`}
      role="status"
      aria-label={getDecisionLabel(severity)}
    >
      {showLabel ? getDecisionLabel(severity) : null}
    </span>
  )
}
