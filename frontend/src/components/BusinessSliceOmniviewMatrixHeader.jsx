import { Fragment } from 'react'
import { periodLabel, periodSecondaryLabel, periodStateLabel, PERIOD_STATES, resolvePeriodTrustVisual, trustIssueSummaryForTooltip, periodHeaderPrimary, periodHeaderSecondary, isCurrentPeriod, getCurrentPeriodBadge } from './omniview/omniviewMatrixUtils.js'
import { projectionPeriodLabel, projectionPeriodSecondaryLabel } from './omniview/projectionMatrixUtils.js'

export const COL1_W = 100
export const COL2_W = 140
export const HEADER_H_COMFORTABLE = 64
export const HEADER_H_COMPACT = 40

const STATE_BADGE_STYLES = {
  [PERIOD_STATES.OPEN]: 'bg-emerald-600/90 text-white',
  [PERIOD_STATES.PARTIAL]: 'bg-blue-500/80 text-white',
  [PERIOD_STATES.CURRENT_DAY]: 'bg-blue-500/80 text-white',
  [PERIOD_STATES.STALE]: 'bg-amber-500/80 text-white',
  [PERIOD_STATES.FUTURE]: 'bg-slate-500/60 text-slate-200',
}

const CURRENT_PERIOD_BG = 'bg-blue-950/90'
const CURRENT_PERIOD_GLOW = 'ring-1 ring-inset ring-blue-400/60 shadow-[inset_0_0_16px_rgba(59,130,246,0.25)]'

export default function BusinessSliceOmniviewMatrixHeader ({ allPeriods, grain, compact, periodStates, matrixTrust = null, focusedKpi, periodMeta = null, periodDayLabels = null, isProjection = false, currentPeriodKey = null }) {
  const py1 = compact ? 'py-1' : 'py-2'
  const py2 = compact ? 'py-0.5' : 'py-1.5'
  const fontSize1 = compact ? 'text-[10px]' : 'text-[13px]'
  const fontSize2 = compact ? 'text-[9px]' : 'text-[11px]'
  const trustTip = trustIssueSummaryForTooltip(matrixTrust)
  const renderPeriodLabel = (pk) => (isProjection ? projectionPeriodLabel(pk, grain, periodMeta) : periodHeaderPrimary(pk, grain, periodDayLabels))
  const renderPeriodSecondary = (pk) => (isProjection ? projectionPeriodSecondaryLabel(pk, grain, periodMeta) : periodHeaderSecondary(pk, grain))

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
          const isCurrent = currentPeriodKey ? (pk === currentPeriodKey) : isCurrentPeriod(pk, grain)
          const currentBadge = isCurrent ? getCurrentPeriodBadge(pk, grain) : null
          const currentPeriodFontSize1 = isCurrent
            ? compact ? 'text-[12px]' : 'text-[15px]'
            : fontSize1
          const currentPeriodFontSize2 = isCurrent
            ? compact ? 'text-[11px]' : 'text-[12px]'
            : 'text-[10px]'
          return (
            <th
              key={pk}
              colSpan={1}
              className={`px-0 ${py1} text-center ${currentPeriodFontSize1} font-bold uppercase tracking-wide border-l-2 border-slate-500 ${isCurrent ? CURRENT_PERIOD_BG : idx % 2 === 1 ? 'bg-slate-750' : ''} ${trustTop} ${isCurrent ? CURRENT_PERIOD_GLOW : ''}`}
              style={!isCurrent && idx % 2 === 1 ? { backgroundColor: 'rgb(40,50,70)' } : undefined}
              title={periodTrust && trustTip ? trustTip : undefined}
            >
              <div className={`flex flex-col items-center leading-tight ${isCurrent ? 'text-blue-100' : ''}`}>
                <span>{renderPeriodLabel(pk)}</span>
                {renderPeriodSecondary(pk) && (
                  <span className={`mt-0.5 ${currentPeriodFontSize2} font-medium normal-case tracking-normal ${isCurrent ? 'text-blue-300' : 'text-slate-200'}`}>
                    {renderPeriodSecondary(pk)}
                  </span>
                )}
              </div>
              {currentBadge && (
                <span className="ml-1.5 px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-500 text-white normal-case shadow-sm">
                  {currentBadge}
                </span>
              )}
              {!currentBadge && badge && (
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
          const isCurrent = currentPeriodKey ? (pk === currentPeriodKey) : isCurrentPeriod(pk, grain)
          const currentKpiFont = isCurrent
            ? compact ? 'text-[10px]' : 'text-[13px]'
            : fontSize2
          return (
            <Fragment key={`hdr-${pk}`}>
              <th
                key={`${pk}-${focusedKpi.key}`}
                className={`px-0.5 ${py2} text-center ${currentKpiFont} font-semibold uppercase tracking-wide whitespace-nowrap border-l-2 border-slate-500 ${trustTop} ${isCurrent ? CURRENT_PERIOD_BG : ''} ${isCurrent ? 'text-blue-100' : ''}`}
                style={!isCurrent && pIdx % 2 === 1 ? { backgroundColor: 'rgb(48,58,78)' } : undefined}
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
