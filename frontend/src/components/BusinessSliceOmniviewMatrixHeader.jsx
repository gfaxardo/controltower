import { Fragment } from 'react'
import { periodLabel, periodSecondaryLabel, periodStateLabel, PERIOD_STATES, resolvePeriodTrustVisual, trustIssueSummaryForTooltip } from './omniview/omniviewMatrixUtils.js'
import { projectionPeriodLabel, projectionPeriodSecondaryLabel } from './omniview/projectionMatrixUtils.js'

export const COL1_W = 90
export const COL2_W = 130
export const HEADER_H_COMFORTABLE = 52
export const HEADER_H_COMPACT = 40

const STATE_BADGE_STYLES = {
  [PERIOD_STATES.OPEN]: 'bg-emerald-600/90 text-white',
  [PERIOD_STATES.PARTIAL]: 'bg-blue-500/80 text-white',
  [PERIOD_STATES.CURRENT_DAY]: 'bg-blue-500/80 text-white',
  [PERIOD_STATES.STALE]: 'bg-amber-500/80 text-white',
  [PERIOD_STATES.FUTURE]: 'bg-slate-500/60 text-slate-200',
}

export default function BusinessSliceOmniviewMatrixHeader ({ allPeriods, grain, compact, periodStates, matrixTrust = null, focusedKpi, periodMeta = null, isProjection = false }) {
  const py1 = compact ? 'py-1' : 'py-1.5'
  const py2 = compact ? 'py-0.5' : 'py-1'
  const fontSize1 = compact ? 'text-[10px]' : 'text-xs'
  const fontSize2 = compact ? 'text-[9px]' : 'text-[10px]'
  const trustTip = trustIssueSummaryForTooltip(matrixTrust)
  const renderPeriodLabel = (pk) => (isProjection ? projectionPeriodLabel(pk, grain, periodMeta) : periodLabel(pk, grain))
  const renderPeriodSecondary = (pk) => (isProjection ? projectionPeriodSecondaryLabel(pk, grain, periodMeta) : periodSecondaryLabel(pk, grain))

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
        {allPeriods.map((pk, idx) => {
          const state = periodStates?.get(pk)
          const badge = state && state !== PERIOD_STATES.CLOSED
          const badgeCls = STATE_BADGE_STYLES[state] || ''
          const periodTrust = resolvePeriodTrustVisual(pk, grain, matrixTrust)
          const trustTop =
            periodTrust === 'blocked' ? 'border-t-[3px] border-t-red-500' : periodTrust === 'warning' ? 'border-t-[3px] border-t-amber-500' : ''
          return (
            <th
              key={pk}
              colSpan={1}
              className={`px-0 ${py1} text-center ${fontSize1} font-bold uppercase tracking-wide border-l-2 border-slate-500 ${idx % 2 === 1 ? 'bg-slate-750' : ''} ${trustTop}`}
              style={idx % 2 === 1 ? { backgroundColor: 'rgb(40,50,70)' } : undefined}
              title={periodTrust && trustTip ? trustTip : undefined}
            >
              <div className="flex flex-col items-center leading-tight">
                <span>{renderPeriodLabel(pk)}</span>
                {renderPeriodSecondary(pk) && (
                  <span className="mt-0.5 text-[10px] font-medium normal-case tracking-normal text-slate-200">
                    {renderPeriodSecondary(pk)}
                  </span>
                )}
              </div>
              {badge && (
                <span className={`ml-1.5 px-1 py-px rounded text-[8px] font-bold normal-case ${badgeCls}`}>
                  {periodStateLabel(state)}
                </span>
              )}
            </th>
          )
        })}
      </tr>

      <tr className="bg-slate-700 text-slate-300">
        {allPeriods.map((pk, pIdx) => {
          const periodTrust = resolvePeriodTrustVisual(pk, grain, matrixTrust)
          const trustTop =
            periodTrust === 'blocked' ? 'border-t-[2px] border-t-red-500/90' : periodTrust === 'warning' ? 'border-t-[2px] border-t-amber-500/90' : ''
          return (
            <Fragment key={`hdr-${pk}`}>
              <th
                key={`${pk}-${focusedKpi.key}`}
                className={`px-0.5 ${py2} text-center ${fontSize2} font-semibold uppercase tracking-wide whitespace-nowrap border-l-2 border-slate-500 ${trustTop}`}
                style={pIdx % 2 === 1 ? { backgroundColor: 'rgb(48,58,78)' } : undefined}
                title={periodTrust && trustTip ? `${focusedKpi.label} · ${trustTip}` : focusedKpi.label}
              >
                {focusedKpi.short}
              </th>
            </Fragment>
          )
        })}
      </tr>
    </thead>
  )
}
