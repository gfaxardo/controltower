import { MATRIX_KPIS, periodLabel } from './omniview/omniviewMatrixUtils.js'

export const COL1_W = 90
export const COL2_W = 130
export const HEADER_H_COMFORTABLE = 52
export const HEADER_H_COMPACT = 40

export default function BusinessSliceOmniviewMatrixHeader ({ allPeriods, grain, compact }) {
  const py1 = compact ? 'py-1' : 'py-1.5'
  const py2 = compact ? 'py-0.5' : 'py-1'
  const fontSize1 = compact ? 'text-[10px]' : 'text-xs'
  const fontSize2 = compact ? 'text-[9px]' : 'text-[10px]'

  return (
    <thead className="sticky top-0 z-20">
      <tr className="bg-slate-800 text-white">
        <th
          className={`sticky left-0 z-30 bg-slate-800 px-2 ${py1} text-left ${fontSize1} font-bold uppercase tracking-wider border-r border-slate-700`}
          rowSpan={2}
          style={{ width: COL1_W, minWidth: COL1_W }}
        >
          Ciudad
        </th>
        <th
          className={`sticky z-30 bg-slate-800 px-2 ${py1} text-left ${fontSize1} font-bold uppercase tracking-wider border-r border-slate-600`}
          rowSpan={2}
          style={{ left: COL1_W, width: COL2_W, minWidth: COL2_W }}
        >
          Línea
        </th>
        {allPeriods.map((pk, idx) => (
          <th
            key={pk}
            colSpan={MATRIX_KPIS.length}
            className={`px-0 ${py1} text-center ${fontSize1} font-bold uppercase tracking-wide border-l-2 border-slate-500 ${idx % 2 === 1 ? 'bg-slate-750' : ''}`}
            style={idx % 2 === 1 ? { backgroundColor: 'rgb(40,50,70)' } : undefined}
          >
            {periodLabel(pk, grain)}
          </th>
        ))}
      </tr>

      <tr className="bg-slate-700 text-slate-300">
        {allPeriods.map((pk, pIdx) =>
          MATRIX_KPIS.map((kpi, j) => (
            <th
              key={`${pk}-${kpi.key}`}
              className={`px-0.5 ${py2} text-center ${fontSize2} font-semibold uppercase tracking-wide whitespace-nowrap
                ${j === 0 ? 'border-l-2 border-slate-500' : 'border-l border-slate-600/50'}`}
              style={pIdx % 2 === 1 ? { backgroundColor: 'rgb(48,58,78)' } : undefined}
              title={kpi.label}
            >
              {kpi.short}
            </th>
          ))
        )}
      </tr>
    </thead>
  )
}
