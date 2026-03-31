import { MATRIX_KPIS, periodLabel } from './omniview/omniviewMatrixUtils.js'

const COL1_W = 90
const COL2_W = 130

export { COL1_W, COL2_W }

export default function BusinessSliceOmniviewMatrixHeader ({ allPeriods, grain, compact }) {
  const py1 = compact ? 'py-1' : 'py-1.5'
  const py2 = compact ? 'py-0.5' : 'py-1'
  const fontSize1 = compact ? 'text-[10px]' : 'text-xs'
  const fontSize2 = compact ? 'text-[9px]' : 'text-[10px]'

  return (
    <thead className="sticky top-0 z-20">
      {/* ── ROW 1: Period super-columns ──────────────────────────── */}
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
        {allPeriods.map((pk) => (
          <th
            key={pk}
            colSpan={MATRIX_KPIS.length}
            className={`px-0 ${py1} text-center ${fontSize1} font-bold uppercase tracking-wide border-l-2 border-slate-500`}
          >
            {periodLabel(pk, grain)}
          </th>
        ))}
      </tr>

      {/* ── ROW 2: KPI sub-columns per period ────────────────────── */}
      <tr className="bg-slate-700 text-slate-300">
        {allPeriods.map((pk) =>
          MATRIX_KPIS.map((kpi, j) => (
            <th
              key={`${pk}-${kpi.key}`}
              className={`px-0.5 ${py2} text-center ${fontSize2} font-semibold uppercase tracking-wide whitespace-nowrap
                ${j === 0 ? 'border-l-2 border-slate-500' : 'border-l border-slate-600/50'}`}
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
