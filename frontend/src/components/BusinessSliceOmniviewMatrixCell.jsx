import { fmtValue, fmtDelta, signalColor, signalArrow } from './omniview/omniviewMatrixUtils.js'

export default function BusinessSliceOmniviewMatrixCell ({
  kpiKey,
  delta,
  onClick,
  isSelected,
  compact,
}) {
  const py = compact ? 'py-px' : 'py-0.5'
  const valSize = compact ? 'text-[11px]' : 'text-xs'
  const deltaSize = compact ? 'text-[9px]' : 'text-[10px]'

  if (!delta) {
    return (
      <td
        className={`px-1 ${py} text-center ${valSize} text-gray-300 border-r border-gray-100/60 cursor-default select-none ${isSelected ? 'bg-blue-50' : ''}`}
      >
        —
      </td>
    )
  }

  const val = fmtValue(delta.value, kpiKey)
  const deltaTxt = fmtDelta(delta)
  const color = signalColor(delta.signal)
  const arrow = signalArrow(delta.signal)

  return (
    <td
      className={`px-1 ${py} text-center whitespace-nowrap cursor-pointer select-none border-r border-gray-100/60 transition-colors
        ${isSelected ? 'bg-blue-50 ring-1 ring-inset ring-blue-300' : 'hover:bg-slate-50'}`}
      onClick={onClick}
      title={deltaTxt ? `${val} (${arrow} ${deltaTxt})` : val}
    >
      <div className={`${valSize} font-semibold text-gray-800 leading-none`}>{val}</div>
      {deltaTxt && (
        <div className={`${deltaSize} leading-none font-medium mt-px`} style={{ color }}>
          {arrow}{deltaTxt}
        </div>
      )}
    </td>
  )
}
