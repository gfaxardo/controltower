/**
 * OmniviewMomentumPriorityStrip — Tira compacta de prioridades de momentum.
 * 
 * Muestra las entidades (ciudades/líneas) con mayor deterioro
 * detectado por el Priority Engine determinístico.
 * 
 * Compacto: 1 línea. Alta autoridad visual.
 * Ubicación: debajo del Command Header, arriba del toolbar/matrix.
 * 
 * Motor: Control Foundation + Diagnostic Engine Temprano
 */
import { useMemo, memo } from 'react'
import { extractMomentumPriorityFromMatrix, MOMENTUM_RISK } from '../../../utils/operationalMomentumPriority'
import { getDecisionSeverity } from '../../../utils/operationalDecisionSeverity'

const RISK_COLORS = {
  [MOMENTUM_RISK.CRITICAL_DECLINE]:  { bg: '#fee2e2', text: '#dc2626', border: '#fecaca' },
  [MOMENTUM_RISK.ACCELERATING_DOWN]: { bg: '#fee2e2', text: '#ef4444', border: '#fecaca' },
  [MOMENTUM_RISK.CONSECUTIVE_DOWN]:  { bg: '#fef3c7', text: '#d97706', border: '#fde68a' },
  [MOMENTUM_RISK.SINGLE_DECLINE]:    { bg: '#fffbeb', text: '#92400e', border: '#fde68a' },
  [MOMENTUM_RISK.STABLE]:            { bg: '#f0fdf4', text: '#065f46', border: '#bbf7d0' },
  [MOMENTUM_RISK.RECOVERING]:        { bg: '#d1fae5', text: '#059669', border: '#a7f3d0' },
  [MOMENTUM_RISK.IMPROVING]:         { bg: '#d1fae5', text: '#059669', border: '#a7f3d0' },
}

/**
 * @param {object} props
 * @param {Map|null}  [props.cities=null] — baseMatrix.cities Map
 * @param {Array}  [props.allPeriods=[]] — baseMatrix.allPeriods (sorted period keys)
 * @param {string} [props.grain='daily'] — current grain
 * @param {number} [props.maxItems=5] — max priority items to show
 * @param {boolean} [props.showImprovements=false] — also show improvements
 * @param {string} [props.className]
 */
export default memo(function OmniviewMomentumPriorityStrip({
  cities = null,
  allPeriods = [],
  grain = 'daily',
  maxItems = 5,
  showImprovements = false,
  className = '',
}) {
  const priorities = useMemo(() => {
    return extractMomentumPriorityFromMatrix(cities, allPeriods, grain, maxItems)
  }, [cities, allPeriods, grain, maxItems])

  if (priorities.length === 0) {
    return null // No deteriorations detected — clean slate
  }

  const declines = priorities.filter(p =>
    p.risk !== MOMENTUM_RISK.STABLE && p.risk !== MOMENTUM_RISK.IMPROVING
  )
  const improvements = showImprovements
    ? priorities.filter(p => p.risk === MOMENTUM_RISK.IMPROVING).slice(0, 2)
    : []

  return (
    <div className={`flex flex-wrap items-center gap-x-3 gap-y-0.5 px-3 py-1 text-xs ${className}`}
      style={{
        background: declines.length > 2 ? '#fef2f2' : '#fafaf8',
        borderBottom: '1px solid #e7e5e2',
        minHeight: 24,
      }}
      role="status"
      aria-label="Momentum priority strip">
      <span className="font-semibold text-ct-text whitespace-nowrap">Momentum</span>

      {declines.map((item, i) => {
        const colors = RISK_COLORS[item.risk] || RISK_COLORS[MOMENTUM_RISK.STABLE]
        return (
          <span key={item.id}
            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[11px] font-semibold whitespace-nowrap"
            style={{
              background: colors.bg,
              color: colors.text,
              borderColor: colors.border,
            }}>
            <span className="opacity-70">{item.risk === MOMENTUM_RISK.CRITICAL_DECLINE ? '!!' : item.risk === MOMENTUM_RISK.ACCELERATING_DOWN ? '!!' : item.risk === MOMENTUM_RISK.CONSECUTIVE_DOWN ? '!' : '↓'}</span>
            <span>{item.label}</span>
          </span>
        )
      })}

      {declines.length === 0 && (
        <span className="text-ct-text3">No deteriorations</span>
      )}

      {improvements.length > 0 && (
        <>
          <span className="text-ct-text3">|</span>
          {improvements.map((item, i) => (
            <span key={item.id}
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[11px] font-medium text-emerald-700 bg-emerald-50 border-emerald-200 whitespace-nowrap">
              <span>↑</span>
              <span>{item.label}</span>
            </span>
          ))}
        </>
      )}
    </div>
  )
})
