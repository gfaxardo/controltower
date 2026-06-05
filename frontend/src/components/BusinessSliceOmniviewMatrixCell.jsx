import { memo, useState, useCallback, useEffect } from 'react'
import { fmtValue, fmtDelta, signalColorForKpi, signalArrow, buildCellTooltip, trustPeriodCellOverlayClass, trustSegmentsDetailForTooltip, TEMPORAL_VISUAL_TIERS, temporalCellBorder, timelineOpacityDecay, outlierEmphasisClass } from './omniview/omniviewMatrixUtils.js'
import {
  fmtAttainment,
  fmtGap,
  fmtGapPct,
  basisSuffix,
  projectionSignalColor,
  SIGNAL_DOT,
  buildProjectionCellTooltip,
  PROJECTION_KPIS,
  getProjectionStatusLabel,
  getProjectionStatusColors,
  isKpiComparableAcrossGrains,
  getKpiComparabilityBadge,
} from './omniview/projectionMatrixUtils.js'
import { getComparisonLabel, isMomentumComparison } from '../utils/operationalMomentumEmphasis.js'
import { getMomentumSeverityColor, getMomentumSeverityBg } from '../utils/operationalMomentumEmphasis.js'
import { buildProjectionCellDisplay } from '../utils/projectionCellDisplayModel.js'

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
  isCurrentPeriod = false,
  isWorstInRow = false,
  isCalendarCurrentPartial = false,
  temporalTier = null,
  temporalDistance = 0,
}) {
  const [ctxMenu, setCtxMenu] = useState(null)

  const handleContextMenu = useCallback((e) => {
    e.preventDefault()
    const val = delta ? fmtValue(delta.value, kpiKey) : '—'
    setCtxMenu({ x: e.clientX, y: e.clientY, value: val, label: `${lineName} · ${periodLbl} · ${kpi.label}` })
  }, [delta, kpiKey, kpi, lineName, periodLbl])

  const copyValue = useCallback(async () => {
    if (ctxMenu) {
      try { await navigator.clipboard.writeText(ctxMenu.value) } catch {}
      setCtxMenu(null)
    }
  }, [ctxMenu])

  useEffect(() => {
    if (!ctxMenu) return
    const close = () => setCtxMenu(null)
    window.addEventListener('click', close)
    window.addEventListener('scroll', close, { capture: true })
    return () => {
      window.removeEventListener('click', close)
      window.removeEventListener('scroll', close, { capture: true })
    }
  }, [ctxMenu])
  if (mode === 'projection') {
    return (
      <ProjectionCellRender
        kpiKey={kpiKey} kpi={kpi} delta={delta} onClick={onClick}
        isSelected={isSelected} compact={compact} periodIdx={periodIdx}
        cityName={cityName} lineName={lineName} periodLbl={periodLbl}
        matrixCellId={matrixCellId}
        isCurrentPeriod={isCurrentPeriod}
        periodKey={periodKey}
        grain={grain}
        isWorstInRow={isWorstInRow}
        isCalendarCurrentPartial={isCalendarCurrentPartial}
        temporalTier={temporalTier}
        temporalDistance={temporalDistance}
      />
    )
  }

  const py = compact ? 'py-px' : 'py-1'
  const valSize = compact ? 'text-[11px]' : temporalTier === TEMPORAL_VISUAL_TIERS.LATEST_CLOSED ? 'text-[16px]' : 'text-[14px]'
  const deltaSize = compact ? 'text-[9px]' : temporalTier === TEMPORAL_VISUAL_TIERS.LATEST_CLOSED ? 'text-[12px]' : 'text-[11px]'
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

  const tierBorder = temporalCellBorder(temporalTier)
  const isLatestClosed = temporalTier === TEMPORAL_VISUAL_TIERS.LATEST_CLOSED
  const isFuture = temporalTier === TEMPORAL_VISUAL_TIERS.FUTURE
  const isHistorical = temporalTier === TEMPORAL_VISUAL_TIERS.HISTORICAL_CLOSED
  const isCurrentPartial = temporalTier === TEMPORAL_VISUAL_TIERS.CURRENT_PARTIAL

  const distance = temporalDistance || 0
  const pastOpacity = isHistorical ? timelineOpacityDecay(distance) : 0
  const pastOpacityStyle = pastOpacity > 0 ? { opacity: 1 - pastOpacity } : undefined

  const outlierClass = outlierEmphasisClass(delta)

  function renderCtxMenu () {
    if (!ctxMenu) return null
    return (
      <div className="fixed z-[100] bg-white border border-gray-300 rounded-lg shadow-xl py-1 min-w-[160px]"
        style={{ left: ctxMenu.x, top: ctxMenu.y }}>
        <div className="px-3 py-1 text-[9px] text-gray-400 border-b border-gray-100 truncate">{ctxMenu.label}</div>
        <button onClick={copyValue}
          className="w-full text-left px-3 py-1.5 text-[11px] text-gray-700 hover:bg-blue-50 flex items-center gap-2">
          <svg className="w-3 h-3 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
          Copiar valor
        </button>
      </div>
    )
  }

  if (!delta) {
    const emptyTooltip = [buildCellTooltip(kpi, null, cityName, lineName, periodLbl, periodState, grain, tipTrust), segDetail].filter(Boolean).join('\n\n')
    const emptyBg = isLatestClosed
      ? 'bg-white/90'
      : isCurrentPartial
        ? 'bg-white'
        : isFuture
          ? 'bg-slate-50/10'
          : zebra ? 'bg-slate-50/50' : ''
    const emptyOpacity = isFuture ? 'opacity-30' : dimmed ? 'opacity-30' : ''
    return (
      <>
        <td
          data-matrix-cell-id={matrixCellId || undefined}
          className={`px-1 ${py} text-center ${valSize} text-gray-400 cursor-default select-none ${trustOverlay} ${tierBorder} ${outlierClass}
            ${isSelected ? 'bg-blue-50'
              : emptyBg}
            ${emptyOpacity} border-r border-gray-200/60`}
          style={pastOpacityStyle}
          title={emptyTooltip || undefined}
          onContextMenu={handleContextMenu}
        >
          —
        </td>
        {renderCtxMenu()}
      </>
    )
  }

  const val = fmtValue(delta.value, kpiKey)
  const deltaTxt = fmtDelta(delta)
  const isMomentum = isMomentumComparison(delta, grain)
  const baseColor = signalColorForKpi(delta.signal, kpiKey)
  // Momentum comparisons get full color authority; sequential get subdued
  const color = isMomentum ? baseColor
    : delta?.isProjection ? baseColor + '99'
    : baseColor + '66'
  const arrow = signalArrow(delta.signal)
  const tooltip = [buildCellTooltip(kpi, delta, cityName, lineName, periodLbl, periodState, grain, tipTrust), segDetail].filter(Boolean).join('\n\n')

  const cellBg = isSelected
    ? 'bg-blue-50 ring-1 ring-inset ring-blue-300'
    : isCurrentPeriod
      ? 'bg-blue-50/50 ring-1 ring-inset ring-blue-400/40 shadow-[inset_0_0_16px_rgba(59,130,246,0.06)]'
      : hasInsight
        ? insightBorder
        : isLatestClosed
          ? `bg-white/95 shadow-[inset_0_0_0_1px_rgba(16,185,129,0.15)]`
          : isCurrentPartial
            ? `bg-sky-50/20 ${zebra ? '' : ''}`
            : isFuture
              ? 'bg-slate-50/10'
              : zebra
                ? 'bg-slate-50/50 hover:bg-blue-50/40'
                : 'hover:bg-blue-50/40'

  const valueColor = isFuture ? 'text-gray-400' : 'text-gray-900'

  return (
    <>
      <td
        data-matrix-cell-id={matrixCellId || undefined}
        className={`px-1 ${py} text-center whitespace-nowrap cursor-pointer select-none border-r border-gray-200/60 transition-colors ${trustOverlay} ${tierBorder} ${outlierClass}
          ${cellBg}
          ${dimmed ? 'opacity-30' : ''}
          ${isFuture ? 'opacity-35' : ''}`}
        style={isFuture ? undefined : pastOpacityStyle}
        onClick={onClick}
        title={tooltip}
        onContextMenu={handleContextMenu}
      >
        <div className={`${valSize} font-semibold ${isLatestClosed ? 'font-extrabold' : ''} ${valueColor} leading-none`}>{val}</div>
        {deltaTxt && (() => {
          const momLabel = getComparisonLabel(delta, grain)
          return (
            <div
              className={`${deltaSize} leading-none ${isMomentum ? 'font-semibold' : 'font-normal'} ${isLatestClosed && isMomentum ? 'font-bold' : ''} mt-px`}
              style={{
                color,
                opacity: isFuture ? 0.4 : isPC ? 0.6 : isMomentum ? 1 : 0.55,
              }}
            >
              {isMomentum && momLabel !== 'Δ' && (
                <span className="text-[0.7em] opacity-70 mr-0.5">{momLabel}</span>
              )}
              {arrow}{deltaTxt}{isPC ? '~' : ''}
            </div>
          )
        })()}
      </td>
      {renderCtxMenu()}
    </>
  )
})

/**
 * Render de celda en modo Proyección.
 *
 * Para KPIs proyectables (trips, revenue, drivers):
 *   ↑ {Proy}        ← plan proyectado
 *   {Real}          ← valor real (negrita, muted si sin ejecución)
 *   ● {Av%}         ← avance vs expected (coloreado por señal)
 *   {Gap}           ← gap absoluto (opcional)
 *   [estado]        ← etiqueta si sin ejecución
 *
 * Para KPIs no proyectables (avg_ticket, TPD, cancel_rate, commission):
 *   {Real}          ← valor real
 *   sin plan        ← indicador muted
 *
 * Si no hay datos (delta = null):
 *   —               ← celda vacía, sin plan ni real
 */
function ProjectionCellRender ({ kpiKey, kpi, delta, onClick, isSelected, compact, periodIdx, cityName, lineName, periodLbl, matrixCellId, isCurrentPeriod = false, periodKey = null, grain = 'daily', isWorstInRow = false, isCalendarCurrentPartial = false, temporalTier = null, temporalDistance = 0 }) {
  const zebra = periodIdx % 2 === 1
  const isHistorical = temporalTier === TEMPORAL_VISUAL_TIERS.HISTORICAL_CLOSED
  const isFuture = temporalTier === TEMPORAL_VISUAL_TIERS.FUTURE
  const tDist = temporalDistance || 0
  const isProjectable = PROJECTION_KPIS.includes(kpiKey)

  // Tamaños tipográficos adaptados al modo compact
  const szProy   = compact ? 'text-[7px]' : 'text-[10px]'
  const szReal   = compact ? 'text-[9px]' : 'text-[13px]'
  const szAv     = compact ? 'text-[8px]' : 'text-[11px]'
  const szGap    = compact ? 'text-[7px]' : 'text-[10px]'
  const szStatus = compact ? 'text-[7px]' : 'text-[9px]'
  const py       = compact ? 'py-px' : 'py-1.5'

  // Extraer comparison_status de cualquier delta disponible (todos los KPIs del período tienen el mismo)
  const comparisonStatus = delta?.comparison_status

  // ── Sin datos de ningún tipo ──────────────────────────────────────────────
  if (!delta) {
    return (
      <td
        data-matrix-cell-id={matrixCellId || undefined}
        className={`px-1 ${py} text-center border-r border-gray-100/20 cursor-default select-none ${isSelected ? 'bg-blue-50' : isCurrentPeriod ? 'bg-emerald-50/30 border-l-2 border-r-2 border-emerald-300/60 shadow-[inset_0_0_12px_rgba(16,185,129,0.08)]' : zebra ? 'bg-slate-50/25' : ''}`}
        title={buildProjectionCellTooltip(kpi, null, cityName, lineName, periodLbl)}
      >
        <div className={`${szProy} text-gray-200 leading-none`}>—</div>
      </td>
    )
  }

  // ── Real sin plan ("missing_plan") — muestra real con badge "Sin proyección" ──
  if (comparisonStatus === 'missing_plan' && isProjectable) {
    const actual = delta.value
    const hasReal = actual != null && !isNaN(Number(actual))
    const hasPositiveReal = hasReal && Number(actual) > 0
    const valStr = hasReal ? fmtValue(actual, kpiKey) : '—'
    return (
      <td
        data-matrix-cell-id={matrixCellId || undefined}
        className={`px-1 ${py} text-center whitespace-nowrap cursor-pointer select-none border-r border-gray-100/20 transition-colors
          ${isSelected ? 'bg-blue-50 ring-1 ring-inset ring-blue-300'
            : isCurrentPeriod ? 'bg-emerald-50/30 border-l-2 border-r-2 border-emerald-300/60 shadow-[inset_0_0_12px_rgba(16,185,129,0.08)]'
            : zebra ? 'bg-slate-50/25 hover:bg-blue-50/40' : 'hover:bg-blue-50/40'}`}
        onClick={onClick}
        title={`Sin proyección para este período.\nReal: ${valStr}\n${cityName} · ${lineName} · ${periodLbl}`}
      >
        {/* Real */}
        <div className={`${szReal} font-semibold leading-none ${hasPositiveReal ? 'text-gray-800' : 'text-gray-400'}`}>{valStr}</div>
        {/* Badge "Sin proy." */}
        <div className={`${szStatus} leading-none mt-px text-slate-400 italic`}>Sin proy.</div>
      </td>
    )
  }

  const tooltip = buildProjectionCellTooltip(kpi, delta, cityName, lineName, periodLbl)

  // ── KPI no proyectable (avg_ticket, TPD, cancel_rate, commission_pct) ────
  if (!isProjectable || !delta.isProjection) {
    const val = fmtValue(delta.value, kpiKey)
    return (
      <td
        data-matrix-cell-id={matrixCellId || undefined}
        className={`px-1 ${py} text-center whitespace-nowrap cursor-pointer select-none border-r border-gray-100/20 transition-colors
          ${isSelected ? 'bg-blue-50 ring-1 ring-inset ring-blue-300'
            : isCurrentPeriod ? 'bg-emerald-50/30 border-l-2 border-r-2 border-emerald-300/60 shadow-[inset_0_0_12px_rgba(16,185,129,0.08)]'
            : zebra ? 'bg-slate-50/25 hover:bg-blue-50/40' : 'hover:bg-blue-50/40'}`}
        onClick={onClick}
        title={tooltip}
      >
        <div className={`${szReal} font-semibold text-gray-800 leading-none`}>{val}</div>
        <div className={`${szStatus} leading-none text-gray-300 mt-px`}>sin plan</div>
      </td>
    )
  }

  // ── KPI proyectable ───────────────────────────────────────────────────────
  // CANONICAL: build display model → momentum always dominates when data exists
  const dm = buildProjectionCellDisplay(delta, grain, kpiKey)

  // ── PAST DEGRADATION: use timeline gradient when available ──
  const pastDecay = isHistorical
    ? timelineOpacityDecay(tDist)
    : computePastAgingOpacity(periodKey, grain)

  const pastDegraded = pastDecay > 0 && !dm.isFuture && !isSelected

  // ── SEVERITY-BASED EMPHASIS (per-cell, self-limiting) ──
  const sev = dm.hasComparable ? dm.comparableDelta.severity : null
  const severityEmphasis = sev === 'critical'  ? 'ring-1 ring-inset ring-red-300/30 border-l-2 border-red-300/45'
    : sev === 'elevated'  ? 'border-l-2 border-amber-300/25'
    : sev === 'warning'   ? 'border-l border-amber-200/15'
    : ''
  const severityBg     = sev === 'critical'  ? 'bg-red-50/25'
    : sev === 'elevated'  ? 'bg-amber-50/15'
    : sev === 'warning'   ? 'bg-amber-50/8'
    : ''

  // ── TEMPORAL SCAN: worst in visible row gets extra signal ──
  const worstEmphasis = isWorstInRow && sev && !isCurrentPeriod && !isSelected
    ? 'ring-2 ring-inset ring-red-300/55 border-l-2 border-red-400/70 shadow-[inset_0_0_6px_rgba(239,68,68,0.10)]'
    : ''

  // ── BASE BORDER — softer, lower contrast ──
  const baseBorder = 'border-r border-gray-100/25'

  // ── ZEBRA — ultra subtle ──
  const zebraBg = zebra ? 'bg-slate-50/25' : ''

  // Confidence
  const conf    = delta.curve_confidence
  const lowConf = conf === 'low' || conf === 'fallback'
  const medConf = conf === 'medium'
  const confBorder = lowConf
    ? 'ring-1 ring-inset ring-dashed ring-red-300/50'
    : medConf
      ? 'ring-1 ring-inset ring-dashed ring-amber-300/40'
      : ''

  // Critical alert — only for real deterioration, not future
  const criticalAlert = !dm.isFuture && (dm.hasNegActual || (dm.hasPlan && !dm.hasReal && delta.attainment_pct != null && delta.attainment_pct < 75))

  // Future/pending: ghosted, muted. Real: full intensity.
  const futureDim = dm.isFuture ? 'opacity-35 grayscale-[40%]' : ''

  // ── PAST DEGRADATION ── applies to border too
  const pastStyle = pastDegraded
    ? { opacity: 1 - pastDecay, borderRightColor: 'rgba(243,244,246,0.15)' }
    : undefined

  return (
    <td
      data-matrix-cell-id={matrixCellId || undefined}
      className={`px-1 ${py} text-center whitespace-nowrap cursor-pointer select-none transition-colors relative
        ${baseBorder}
        ${isSelected
          ? 'bg-blue-50 ring-1 ring-inset ring-blue-300'
          : isCurrentPeriod && !dm.isFuture
            ? `bg-gradient-to-b from-emerald-50/40 to-emerald-50/20 border-l-2 border-r-2 border-emerald-400/60 shadow-[inset_0_0_18px_rgba(16,185,129,0.12),0_0_10px_rgba(16,185,129,0.10)]`
            : isCurrentPeriod && dm.isFuture
              ? 'bg-slate-100/40 border-l border-r border-slate-200/60'  // future: muted
            : dm.isFuture
              ? 'bg-slate-50/20'
              : `${sev ? severityBg : zebraBg} hover:bg-blue-50/40`}
        ${!isSelected && !isCurrentPeriod ? severityEmphasis : ''}
        ${worstEmphasis}
        ${futureDim}
        ${!isSelected && !dm.isFuture ? confBorder : ''}`}
      style={pastStyle}
      onClick={onClick}
      title={tooltip}
    >
      {/* Alerta crítica — ONLY for real deterioration */}
      {criticalAlert && (
        <span className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-red-600 ring-1 ring-white shadow-sm"
          title={dm.hasNegActual ? 'Alerta: valor real negativo' : 'Alerta: cumplimiento bajo 75%'} aria-hidden />
      )}
      {(delta?.projection_confidence === 'low' || delta?.projection_anomaly) && !dm.isFuture && (
        <span className="absolute top-0.5 left-0.5 w-1 h-1 rounded-full bg-amber-500 ring-1 ring-white shadow-sm"
          title={delta.projection_anomaly ? 'Anomalía de volatilidad' : 'Baja confianza'} aria-hidden />
      )}
      {!isKpiComparableAcrossGrains(kpiKey) && (
        <span className="absolute bottom-0.5 right-0.5 px-0.5 text-[6px] font-semibold leading-none rounded-sm bg-slate-200/80 text-slate-600"
          title={`${getKpiComparabilityBadge(kpiKey)?.label || ''}`} aria-hidden>
          {getKpiComparabilityBadge(kpiKey)?.short || '≠Σ'}
        </span>
      )}

      {/* ── L0: PERIOD BADGE ── */}
      {isCurrentPeriod && !dm.isFuture && (
        <div className={`${szStatus} leading-none mb-0.5`}>
          <span className="inline-block px-1 py-px rounded text-[7px] font-bold uppercase leading-none bg-emerald-500 text-white">
            {grain === 'daily' ? 'ÚLTIMO CIERRE' : grain === 'weekly' ? 'SEM. CERRADA' : 'MES CERRADO'}
          </span>
        </div>
      )}
      {isCalendarCurrentPartial && !dm.isFuture && (
        <div className={`${szStatus} leading-none mb-0.5`}>
          <span className="inline-block px-1 py-px rounded text-[7px] font-bold uppercase leading-none bg-amber-500/70 text-white">
            PARCIAL
          </span>
        </div>
      )}

      {/* ── L2: REAL VALUE — DOMINANTE ── */}
      <div className={`${isCurrentPeriod && !dm.isFuture ? (compact ? 'text-[12px]' : 'text-[16px]') : szReal} font-extrabold leading-tight ${dm.hasReal || dm.hasNegActual ? (dm.hasNegActual ? 'text-red-700' : dm.isFuture ? 'text-gray-400' : 'text-gray-900') : 'text-gray-400'}`}>
        {dm.realStr}
      </div>

      {/* ── L2: DELTA COMPARABLE (DoD/WoW/MoM) — DOMINANTE ── */}
      <div className="leading-none mt-0.5 flex items-center justify-center">
        {dm.hasComparable ? (
          <span className={`${szAv} ${dm.comparableDelta.deltaBold}`}
            style={{ color: dm.comparableDelta.severityColor }}>
            {dm.comparableDelta.display}
          </span>
        ) : dm.isFuture ? (
          <span className={`${szStatus} font-medium text-slate-300`}>—</span>
        ) : (
          <span className={`${szStatus} text-gray-300`}>—</span>
        )}
      </div>

      {/* ── L3: CONTEXTO SECUNDARIO — solo cuando no hay momentum ── */}
      {dm.contextStr && !dm.hasComparable && !dm.isFuture && (
        <div className={`text-[7px] leading-none mt-px text-gray-300`}>
          Avance {dm.contextStr}
        </div>
      )}
      {dm.isPlanFallback && dm.planStr && (
        <div className={`text-[7px] leading-none mt-px text-gray-300`}>
          Plan {dm.planStr}
        </div>
      )}

      {/* ── L4: STATUS / PENDING ── */}
      {dm.statusText && (
        <div className={`${szStatus} leading-none mt-px font-medium ${dm.isFuture ? 'text-slate-300' : 'text-slate-400'}`}>
          {dm.statusText}
        </div>
      )}
    </td>
  )
}

/**
 * Compute opacity for past periods based on temporal distance from current period.
 * Returns 0 for current period, 0.08 per period away from current (max 0.6 opacity reduction).
 */
function computePastAgingOpacity(periodKey, grain) {
  if (!periodKey || typeof periodKey !== 'string') return 0
  try {
    const d = new Date(periodKey + 'T00:00:00')
    if (isNaN(d)) return 0
    const now = new Date()
    now.setHours(0, 0, 0, 0)
    d.setHours(0, 0, 0, 0)
    if (d >= now) return 0
    const diffDays = Math.floor((now - d) / (1000 * 60 * 60 * 24))
    if (diffDays <= 0) return 0
    const steps = grain === 'daily'
      ? Math.min(Math.floor(diffDays / 1), 90)
      : grain === 'weekly'
        ? Math.min(Math.floor(diffDays / 7), 52)
        : Math.min(Math.floor(diffDays / 30), 36)
    return Math.min(steps * 0.025, 0.55)
  } catch {
    return 0
  }
}
