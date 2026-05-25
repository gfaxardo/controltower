/**
 * DecisionAttentionHeader — Header compacto con resumen de atención.
 * 
 * Muestra título + conteo por severidad en una sola línea.
 * Ideal para headers de panel de alertas, secciones de prioridad.
 * 
 * Motor: Control Foundation
 */
import { useMemo } from 'react'
import { getAttentionSummary, getAttentionRatio } from '../../utils/operationalAttentionRouting'
import DecisionPriorityStrip from './DecisionPriorityStrip'

/**
 * @param {object} props
 * @param {string} props.title - Título de la sección
 * @param {Array}  props.items - Items a resumir
 * @param {Function} [props.signalExtractor] - (item) => signals
 * @param {ReactNode} [props.actions] - Acciones a la derecha (botones, filtros)
 * @param {string} [props.className]
 */
export default function DecisionAttentionHeader({
  title,
  items = [],
  signalExtractor,
  actions,
  className = '',
}) {
  const attentionRatio = useMemo(() => getAttentionRatio(items, signalExtractor), [items, signalExtractor])

  return (
    <div className={`flex flex-wrap items-center justify-between gap-2 ${className}`}>
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-sm font-semibold text-ct-text truncate">{title}</span>
        {items.length > 0 && (
          <DecisionPriorityStrip items={items} signalExtractor={signalExtractor} />
        )}
        {attentionRatio > 0 && (
          <span className={`text-xs font-semibold ${attentionRatio > 50 ? 'text-ct-bad' : attentionRatio > 25 ? 'text-ct-warn' : 'text-ct-text2'}`}>
            {attentionRatio}% attention
          </span>
        )}
      </div>
      {actions && (
        <div className="flex items-center gap-1.5">{actions}</div>
      )}
    </div>
  )
}
