import { memo } from 'react'
import { fmtValue, fmtDelta, signalColorForKpi, signalArrow, buildCellTooltip, trustPeriodCellOverlayClass, trustSegmentsDetailForTooltip } from './omniview/omniviewMatrixUtils.js'

export default memo(function BusinessSliceOmniviewMatrixCell ({
  kpiKey,
  kpi,
  delta,
  onClick,
  isSelected,
  compact,
  periodIdx,
  cityName,
  lineName,
  periodLbl,
  insightSeverity,
  insightMode,
  periodState,
  grain,
  periodTrustVisual = null,
  trustLine = null,
  matrixTrust = null,
  periodKey = null,
  matrixCellId = null,
}) {
  const py = compact ? 'py-px' : 'py-0.5'
  const valSize = compact ? 'text-[11px]' : 'text-xs'
  const deltaSize = compact ? 'text-[9px]' : 'text-[10px]'
  const zebra = periodIdx % 2 === 1
  const trustOverlay = trustPeriodCellOverlayClass(periodTrustVisual)
  const tipTrust = periodTrustVisual ? trustLine : null
  const segDetail = periodTrustVisual && matrixTrust && periodKey != null
    ? trustSegmentsDetailForTooltip(matrixTrust, grain, cityName, lineName, periodKey, kpiKey)
    : null

  const hasInsight = !!insightSeverity
  const insightBorder = insightSeverity === 'critical'
    ? 'ring-2 ring-inset ring-red-400 bg-red-50/50'
    : insightSeverity === 'warning'
      ? 'ring-1 ring-inset ring-amber-400 bg-amber-50/40'
      : ''

  const dimmed = insightMode && !hasInsight
  const isPC = delta?.isPartialComparison

  if (!delta) {
    const emptyTooltip = [buildCellTooltip(kpi, null, cityName, lineName, periodLbl, periodState, grain, tipTrust), segDetail].filter(Boolean).join('\n\n')
    return (
      <td
        data-matrix-cell-id={matrixCellId || undefined}
        className={`px-1 ${py} text-center ${valSize} text-gray-300 border-r border-gray-100/60 cursor-default select-none ${trustOverlay} ${isSelected ? 'bg-blue-50' : zebra ? 'bg-slate-50/50' : ''} ${dimmed ? 'opacity-30' : ''}`}
        title={emptyTooltip || undefined}
      >
        —
      </td>
    )
  }

  const val = fmtValue(delta.value, kpiKey)
  const deltaTxt = fmtDelta(delta)
  const color = signalColorForKpi(delta.signal, kpiKey)
  const arrow = signalArrow(delta.signal)
  const tooltip = [buildCellTooltip(kpi, delta, cityName, lineName, periodLbl, periodState, grain, tipTrust), segDetail].filter(Boolean).join('\n\n')

  return (
    <td
      data-matrix-cell-id={matrixCellId || undefined}
      className={`px-1 ${py} text-center whitespace-nowrap cursor-pointer select-none border-r border-gray-100/60 transition-colors ${trustOverlay}
        ${isSelected ? 'bg-blue-50 ring-1 ring-inset ring-blue-300'
          : hasInsight ? insightBorder
          : zebra ? 'bg-slate-50/50 hover:bg-blue-50/40'
          : 'hover:bg-blue-50/40'}
        ${dimmed ? 'opacity-30' : ''}`}
      onClick={onClick}
      title={tooltip}
    >
      <div className={`${valSize} font-semibold text-gray-800 leading-none`}>{val}</div>
      {deltaTxt && (
        <div className={`${deltaSize} leading-none font-medium mt-px`} style={{ color, opacity: isPC ? 0.55 : 1 }}>
          {arrow}{deltaTxt}{isPC ? '~' : ''}
        </div>
      )}
    </td>
  )
})
