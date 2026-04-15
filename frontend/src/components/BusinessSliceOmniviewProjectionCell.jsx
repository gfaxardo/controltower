/**
 * @deprecated FASE 3.1B — Este componente ya no se usa en producción.
 * La lógica de celda de proyección fue absorbida por BusinessSliceOmniviewMatrixCell
 * (prop mode="projection"). Se conserva por seguridad y referencia.
 */
import { memo } from 'react'
import { fmtValue } from './omniview/omniviewMatrixUtils.js'
import {
  fmtAttainment,
  projectionSignalColor,
  SIGNAL_DOT,
  buildProjectionCellTooltip,
  PROJECTION_KPIS,
} from './omniview/projectionMatrixUtils.js'

export default memo(function BusinessSliceOmniviewProjectionCell ({
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
  matrixCellId = null,
}) {
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

  return (
    <td
      data-matrix-cell-id={matrixCellId || undefined}
      className={`px-1 ${py} text-center whitespace-nowrap cursor-pointer select-none border-r border-gray-100/60 transition-colors
        ${isSelected ? 'bg-blue-50 ring-1 ring-inset ring-blue-300'
          : `${signalBg} ${zebra && !signalBg ? 'bg-slate-50/50' : ''} hover:bg-blue-50/40`}`}
      onClick={onClick}
      title={tooltip}
    >
      <div className={`${valSize} font-semibold text-gray-800 leading-none`}>{val}</div>
      <div className={`${deltaSize} leading-none font-medium mt-px flex items-center justify-center gap-0.5`}>
        <span className={`inline-block w-1.5 h-1.5 rounded-full ${dotClass} flex-shrink-0`} />
        <span style={{ color: attainmentColor }}>{attainmentText}</span>
      </div>
    </td>
  )
})
