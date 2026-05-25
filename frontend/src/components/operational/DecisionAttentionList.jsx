/**
 * DecisionAttentionList — Lista ordenada por prioridad de atención.
 * 
 * Renderiza children ordenados por severidad operacional.
 * Items más urgentes primero (blocked → critical → elevated → warning → normal → unknown).
 * 
 * NO modifica los items originales.
 * Solo: routing visual.
 * 
 * Motor: Control Foundation
 */
import { useMemo } from 'react'
import { stablePrioritySort } from '../../utils/operationalAttentionRouting'
import { getDecisionSeverity } from '../../utils/operationalDecisionSeverity'

/**
 * @param {object} props
 * @param {Array}  props.items - Items a renderizar
 * @param {Function} props.renderItem - (item, index) => ReactNode
 * @param {Function} [props.signalExtractor] - (item) => signals object. Default: item => item
 * @param {boolean} [props.showAll] - Mostrar todos (default: true). Si false, solo blocked+critical+elevated
 * @param {number}  [props.maxItems] - Máximo de items a mostrar
 * @param {boolean} [props.groupBySeverity] - Insertar headers de severidad entre grupos
 * @param {Function} [props.renderGroupHeader] - (severity, count) => ReactNode para headers de grupo
 */
export default function DecisionAttentionList({
  items = [],
  renderItem,
  signalExtractor,
  showAll = true,
  maxItems,
  groupBySeverity = false,
  renderGroupHeader,
}) {
  const sorted = useMemo(() => {
    let list = stablePrioritySort(items, signalExtractor)
    if (!showAll) {
      const extractor = signalExtractor || ((item) => item)
      list = list.filter(item => {
        const s = getDecisionSeverity(extractor(item))
        return s === 'blocked' || s === 'critical' || s === 'elevated'
      })
    }
    if (maxItems && maxItems > 0) {
      list = list.slice(0, maxItems)
    }
    return list
  }, [items, signalExtractor, showAll, maxItems])

  if (sorted.length === 0) {
    return (
      <div className="ct-empty-fill py-6">
        <span className="text-ct-text3 text-xs">No items requiring attention</span>
      </div>
    )
  }

  if (!groupBySeverity) {
    return sorted.map((item, idx) => renderItem(item, idx))
  }

  // Agrupado por severidad
  const groups = []
  let currentSeverity = null
  let currentGroup = []

  for (const item of sorted) {
    const extractor = signalExtractor || ((i) => i)
    const s = require('../../utils/operationalDecisionSeverity').getDecisionSeverity(extractor(item))
    if (s !== currentSeverity) {
      if (currentGroup.length > 0) {
        groups.push({ severity: currentSeverity, items: currentGroup })
      }
      currentSeverity = s
      currentGroup = [item]
    } else {
      currentGroup.push(item)
    }
  }
  if (currentGroup.length > 0) {
    groups.push({ severity: currentSeverity, items: currentGroup })
  }

  return groups.map((group, gi) => (
    <div key={gi}>
      {renderGroupHeader && renderGroupHeader(group.severity, group.items.length)}
      {group.items.map((item, idx) => renderItem(item, idx))}
    </div>
  ))
}
