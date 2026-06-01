import { Fragment } from 'react'
import { periodLabel, periodSecondaryLabel, periodStateLabel, PERIOD_STATES, resolvePeriodTrustVisual, trustIssueSummaryForTooltip, periodHeaderPrimary, periodHeaderSecondary, isCurrentPeriod, getCurrentPeriodBadge, TEMPORAL_VISUAL_TIERS, temporalHeaderEmphasis, temporalTierLabel } from './omniview/omniviewMatrixUtils.js'
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

// UX-H2: LATEST_CLOSED gets emerald, CURRENT_PARTIAL gets sky badges
const TIER_BADGE_STYLES = {
  [TEMPORAL_VISUAL_TIERS.LATEST_CLOSED]: 'bg-emerald-600 text-white',
  [TEMPORAL_VISUAL_TIERS.CURRENT_PARTIAL]: 'bg-sky-600/90 text-white',
}

export default function BusinessSliceOmniviewMatrixHeader ({ allPeriods, grain, compact, periodStates, matrixTrust = null, focusedKpi, periodMeta = null, periodDayLabels = null, isProjection = false, currentPeriodKey = null, temporalTiers = null }) {
  const py1 = compact ? 'py-1' : 'py-2'
  const py2 = compact ? 'py-0.5' : 'py-1.5'
  const baseFont1 = compact ? 'text-[10px]' : 'text-[13px]'
  const baseFont2 = compact ? 'text-[9px]' : 'text-[11px]'
  const trustTip = trustIssueSummaryForTooltip(matrixTrust)
  const renderPeriodLabel = (pk) => (isProjection ? projectionPeriodLabel(pk, grain, periodMeta) : periodHeaderPrimary(pk, grain, periodDayLabels))
  const renderPeriodSecondary = (pk) => (isProjection ? projectionPeriodSecondaryLabel(pk, grain, periodMeta) : periodHeaderSecondary(pk, grain))

  return (
    <thead className="sticky top-0 z-20">
      <tr className="bg-slate-800 text-white">
        <th
          className={`sticky left-0 z-30 bg-slate-800 px-2 ${py1} text-left ${baseFont1} font-bold uppercase tracking-wider border-r border-slate-700`}
          rowSpan={2}
          style={{ width: COL1_W, minWidth: COL1_W }}
        >
          Ciudad
        </th>
        <th
          className={`sticky z-30 bg-slate-800 px-2 ${py1} text-left ${baseFont1} font-bold uppercase tracking-wider border-r border-slate-600`}
          rowSpan={2}
          style={{ left: COL1_W, width: COL2_W, minWidth: COL2_W }}
        >
          Línea
        </th>
        {allPeriods.map((pk, idx) => {
          const state = periodStates?.get(pk)
          const tier = temporalTiers?.get(pk)
          const tierEmphasis = temporalHeaderEmphasis(tier)
          const periodTrust = resolvePeriodTrustVisual(pk, grain, matrixTrust)
          const trustTop =
            periodTrust === 'blocked' ? 'border-t-[3px] border-t-red-500' : periodTrust === 'warning' ? 'border-t-[3px] border-t-amber-500' : ''

          const fontScale = tierEmphasis.scale
          const fontSize1 = tier === TEMPORAL_VISUAL_TIERS.LATEST_CLOSED
            ? compact ? 'text-[14px]' : 'text-[17px]'
            : tier === TEMPORAL_VISUAL_TIERS.CURRENT_PARTIAL
              ? compact ? 'text-[13px]' : 'text-[15px]'
              : tier === TEMPORAL_VISUAL_TIERS.FUTURE
                ? compact ? 'text-[8px]' : 'text-[10px]'
                : baseFont1
          const fontSize2 = tier === TEMPORAL_VISUAL_TIERS.LATEST_CLOSED
            ? compact ? 'text-[11px]' : 'text-[13px]'
            : tier === TEMPORAL_VISUAL_TIERS.CURRENT_PARTIAL
              ? compact ? 'text-[10px]' : 'text-[12px]'
              : tier === TEMPORAL_VISUAL_TIERS.FUTURE
                ? compact ? 'text-[7px]' : 'text-[9px]'
                : baseFont2

          const textColor = tierEmphasis.text || 'text-white'
          const secondaryColor = tier === TEMPORAL_VISUAL_TIERS.LATEST_CLOSED
            ? 'text-emerald-300'
            : tier === TEMPORAL_VISUAL_TIERS.CURRENT_PARTIAL
              ? 'text-sky-300'
              : tier === TEMPORAL_VISUAL_TIERS.FUTURE
                ? 'text-slate-500'
                : 'text-slate-200'

          const tierBg = tierEmphasis.bg
            || (tier === TEMPORAL_VISUAL_TIERS.FUTURE ? 'bg-slate-800/50' : '')
          const tierBorder = tierEmphasis.border || (idx % 2 === 1 ? '' : '')
          const tierGlow = tierEmphasis.glow || ''

          let bgStyle = {}
          if (tierBg) {
            // tier bg overrides zebra
          } else if (idx % 2 === 1) {
            bgStyle = { backgroundColor: 'rgb(40,50,70)' }
          }

          const tierBadge = TIER_BADGE_STYLES[tier] || ''
          const tierLabel = temporalTierLabel(tier)

          const badge = state && state !== PERIOD_STATES.CLOSED
          const badgeCls = STATE_BADGE_STYLES[state] || ''

          return (
            <th
              key={pk}
              colSpan={1}
              className={`px-0 ${py1} text-center ${fontSize1} font-bold uppercase tracking-wide border-l-2 border-slate-500 ${tierBg} ${tierBorder} ${tierGlow} ${trustTop} ${textColor}`}
              style={Object.keys(bgStyle).length ? bgStyle : undefined}
              title={periodTrust && trustTip ? trustTip : undefined}
            >
              <div className={`flex flex-col items-center leading-tight`}>
                <span className={tier === TEMPORAL_VISUAL_TIERS.FUTURE ? 'opacity-60' : ''}>{renderPeriodLabel(pk)}</span>
                {renderPeriodSecondary(pk) && tier !== TEMPORAL_VISUAL_TIERS.FUTURE && (
                  <span className={`mt-0.5 ${fontSize2} font-medium normal-case tracking-normal ${secondaryColor}`}>
                    {renderPeriodSecondary(pk)}
                  </span>
                )}
              </div>
              {tierLabel && (
                <span className={`ml-1.5 px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${tierBadge} normal-case shadow-sm`}>
                  {tierLabel}
                </span>
              )}
              {!tierLabel && badge && tier !== TEMPORAL_VISUAL_TIERS.FUTURE && (
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
          const tier = temporalTiers?.get(pk)
          const tierEmphasis = temporalHeaderEmphasis(tier)
          const periodTrust = resolvePeriodTrustVisual(pk, grain, matrixTrust)
          const trustTop =
            periodTrust === 'blocked' ? 'border-t-[2px] border-t-red-500/90' : periodTrust === 'warning' ? 'border-t-[2px] border-t-amber-500/90' : ''

          const kpiFont = tier === TEMPORAL_VISUAL_TIERS.LATEST_CLOSED
            ? compact ? 'text-[11px]' : 'text-[14px]'
            : tier === TEMPORAL_VISUAL_TIERS.FUTURE
              ? compact ? 'text-[8px]' : 'text-[10px]'
              : baseFont2

          const kpiTextColor = tier === TEMPORAL_VISUAL_TIERS.LATEST_CLOSED
            ? 'text-emerald-200'
            : tier === TEMPORAL_VISUAL_TIERS.FUTURE
              ? 'text-slate-500'
              : 'text-slate-300'

          const kpiBg = tier === TEMPORAL_VISUAL_TIERS.LATEST_CLOSED
            ? 'bg-emerald-900/80'
            : tier === TEMPORAL_VISUAL_TIERS.CURRENT_PARTIAL
              ? 'bg-sky-900/70'
              : tier === TEMPORAL_VISUAL_TIERS.FUTURE
                ? 'bg-slate-800/60'
                : ''

          return (
            <Fragment key={`hdr-${pk}`}>
              <th
                key={`${pk}-${focusedKpi.key}`}
                className={`px-0.5 ${py2} text-center ${kpiFont} font-semibold uppercase tracking-wide whitespace-nowrap border-l-2 border-slate-500 ${trustTop} ${kpiBg} ${kpiTextColor}`}
                style={!kpiBg && pIdx % 2 === 1 ? { backgroundColor: 'rgb(48,58,78)' } : undefined}
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
