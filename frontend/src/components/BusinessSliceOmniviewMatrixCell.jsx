import { memo } from 'react'
import { fmtValue, fmtDelta, signalColorForKpi, signalArrow, buildCellTooltip, trustPeriodCellOverlayClass, trustSegmentsDetailForTooltip } from './omniview/omniviewMatrixUtils.js'
import {
  fmtAttainment,
  projectionSignalColor,
  SIGNAL_DOT,
  buildProjectionCellTooltip,
  PROJECTION_KPIS,
} from './omniview/projectionMatrixUtils.js'

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
  mode = 'evolution',
}) {
  if (mode === 'projection') {
    return (
      <ProjectionCellRender
        kpiKey={kpiKey} kpi={kpi} delta={delta} onClick={onClick}
        isSelected={isSelected} compact={compact} periodIdx={periodIdx}
        cityName={cityName} lineName={lineName} periodLbl={periodLbl}
        matrixCellId={matrixCellId}
      />
    )
  }

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

function ProjectionCellRender ({ kpiKey, kpi, delta, onClick, isSelected, compact, periodIdx, cityName, lineName, periodLbl, matrixCellId }) {
  const py = compact ? 'py-px' : 'py-0.5'
  const valSize = compact ? 'text-[11px]' : 'text-xs'
  const deltaSize = compact ? 'text-[9px]' : 'text-[10px]'
  const zebra = periodIdx % 2 === 1
  const isProjectable = PROJECTION_KPIS.includes(kpiKey)

  if (!delta) {
    return (
      <td
        data-matrix-cell-id={matrixCellId || undefined}
        className={`px-1 ${py} text-center ${valSize} text-gray-300 border-r border-gray-100/60 cursor-default select-none ${isSelected ? 'bg-blue-50' : zebra ? 'bg-slate-50/50' : ''}`}
        title={buildProjectionCellTooltip(kpi, null, cityName, lineName, periodLbl)}
      >
        —
      </td>
    )
  }

  const val = fmtValue(delta.value, kpiKey)
  const signal = delta.signal || 'no_data'
  const tooltip = buildProjectionCellTooltip(kpi, delta, cityName, lineName, periodLbl)

  if (!isProjectable || !delta.isProjection) {
    return (
      <td
        data-matrix-cell-id={matrixCellId || undefined}
        className={`px-1 ${py} text-center whitespace-nowrap cursor-pointer select-none border-r border-gray-100/60 transition-colors
          ${isSelected ? 'bg-blue-50 ring-1 ring-inset ring-blue-300' : zebra ? 'bg-slate-50/50 hover:bg-blue-50/40' : 'hover:bg-blue-50/40'}`}
        onClick={onClick}
        title={tooltip}
      >
        <div className={`${valSize} font-semibold text-gray-800 leading-none`}>{val}</div>
        <div className={`${deltaSize} leading-none font-medium mt-px text-gray-400`}>—</div>
      </td>
    )
  }

  const attainmentText = fmtAttainment(delta.attainment_pct)
  const dotClass = SIGNAL_DOT[signal] || SIGNAL_DOT.no_data
  const attainmentColor = projectionSignalColor(signal)

  const signalBg = signal === 'danger' ? 'bg-red-50/60'
    : signal === 'warning' ? 'bg-amber-50/40'
    : signal === 'green' ? 'bg-emerald-50/30'
    : ''

  const conf = delta.curve_confidence
  const lowConfidence = conf === 'low' || conf === 'fallback'
  const medConfidence = conf === 'medium'
  const confBorder = lowConfidence ? 'ring-1 ring-inset ring-dashed ring-red-300/70'
    : medConfidence ? 'ring-1 ring-inset ring-dashed ring-amber-300/60'
    : ''

  const criticalAlert = signal === 'danger' && delta.attainment_pct != null && delta.attainment_pct < 75

  return (
    <td
      data-matrix-cell-id={matrixCellId || undefined}
      className={`px-1 ${py} text-center whitespace-nowrap cursor-pointer select-none border-r border-gray-100/60 transition-colors relative
        ${isSelected ? 'bg-blue-50 ring-1 ring-inset ring-blue-300'
          : `${signalBg} ${zebra && !signalBg ? 'bg-slate-50/50' : ''} hover:bg-blue-50/40`}
        ${!isSelected ? confBorder : ''}`}
      onClick={onClick}
      title={tooltip}
    >
      {criticalAlert && (
        <span
          className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-red-600 ring-1 ring-white shadow-sm"
          title="Alerta crítica (cumplimiento bajo 75%)"
          aria-hidden
        />
      )}
      <div className={`${valSize} font-semibold text-gray-800 leading-none`}>{val}</div>
      <div className={`${deltaSize} leading-none font-medium mt-px flex items-center justify-center gap-0.5`}>
        <span className={`inline-block w-1.5 h-1.5 rounded-full ${dotClass} flex-shrink-0`} />
        <span style={{ color: attainmentColor }}>{attainmentText}</span>
        {lowConfidence && <span className="text-[7px] text-red-400 font-bold ml-px" title="Baja confianza en curva">?</span>}
      </div>
    </td>
  )
}
