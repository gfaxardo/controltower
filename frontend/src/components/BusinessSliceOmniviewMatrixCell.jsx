import { memo, useState, useCallback, useEffect } from 'react'
import { fmtValue, fmtDelta, signalColorForKpi, signalArrow, buildCellTooltip, trustPeriodCellOverlayClass, trustSegmentsDetailForTooltip } from './omniview/omniviewMatrixUtils.js'
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
      />
    )
  }

  const py = compact ? 'py-px' : 'py-1'
  const valSize = compact ? 'text-[11px]' : isCurrentPeriod ? 'text-[16px]' : 'text-[14px]'
  const deltaSize = compact ? 'text-[9px]' : isCurrentPeriod ? 'text-[12px]' : 'text-[11px]'
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
    return (
      <>
        <td
          data-matrix-cell-id={matrixCellId || undefined}
          className={`px-1 ${py} text-center ${valSize} text-gray-400 cursor-default select-none ${trustOverlay} ${isSelected ? 'bg-blue-50' : isCurrentPeriod ? 'bg-blue-50/50 ring-1 ring-inset ring-blue-300/30 shadow-[inset_0_0_20px_rgba(59,130,246,0.06)]' : zebra ? 'bg-slate-50/50' : ''} ${dimmed ? 'opacity-30' : ''} border-r border-gray-200/60`}
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
    : delta?.isProjection ? baseColor + '99' // subdued projection color
    : baseColor + '66' // very subtle for simple sequential
  const arrow = signalArrow(delta.signal)
  const tooltip = [buildCellTooltip(kpi, delta, cityName, lineName, periodLbl, periodState, grain, tipTrust), segDetail].filter(Boolean).join('\n\n')

  return (
    <>
      <td
        data-matrix-cell-id={matrixCellId || undefined}
        className={`px-1 ${py} text-center whitespace-nowrap cursor-pointer select-none border-r border-gray-200/60 transition-colors ${trustOverlay}
          ${isSelected ? 'bg-blue-50 ring-1 ring-inset ring-blue-300'
            : hasInsight ? insightBorder
            : isCurrentPeriod ? `bg-blue-50/40 ring-1 ring-inset ring-blue-400/30 shadow-[inset_0_0_20px_rgba(59,130,246,0.08)]`
            : zebra ? 'bg-slate-50/50 hover:bg-blue-50/40'
            : 'hover:bg-blue-50/40'}
          ${dimmed ? 'opacity-30' : ''}`}
        onClick={onClick}
        title={tooltip}
        onContextMenu={handleContextMenu}
      >
        <div className={`${valSize} font-semibold ${isCurrentPeriod ? 'font-extrabold text-gray-900' : 'text-gray-900'} leading-none`}>{val}</div>
        {deltaTxt && (() => {
          const momLabel = getComparisonLabel(delta, grain)
          return (
            <div
              className={`${deltaSize} leading-none ${isMomentum ? 'font-semibold' : 'font-normal'} ${isCurrentPeriod && isMomentum ? 'font-bold' : ''} mt-px`}
              style={{
                color,
                opacity: isPC ? 0.6 : isMomentum ? 1 : 0.55,
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
function ProjectionCellRender ({ kpiKey, kpi, delta, onClick, isSelected, compact, periodIdx, cityName, lineName, periodLbl, matrixCellId, isCurrentPeriod = false, periodKey = null, grain = 'daily' }) {
  const zebra = periodIdx % 2 === 1
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
        className={`px-1 ${py} text-center border-r border-gray-100/60 cursor-default select-none ${isSelected ? 'bg-blue-50' : isCurrentPeriod ? 'bg-emerald-50/30 border-l-2 border-r-2 border-emerald-300/60 shadow-[inset_0_0_12px_rgba(16,185,129,0.08)]' : zebra ? 'bg-slate-50/50' : ''}`}
        title={buildProjectionCellTooltip(kpi, null, cityName, lineName, periodLbl)}
      >
        <div className={`${szProy} text-gray-200 leading-none`}>—</div>
      </td>
    )
  }

  // ── Real sin plan ("missing_plan") — muestra real con badge "Sin proyección" ──
  if (comparisonStatus === 'missing_plan' && isProjectable) {
    const actual = delta.value
    const hasReal = actual != null && Number(actual) > 0
    const valStr = hasReal ? fmtValue(actual, kpiKey) : '—'
    return (
      <td
        data-matrix-cell-id={matrixCellId || undefined}
        className={`px-1 ${py} text-center whitespace-nowrap cursor-pointer select-none border-r border-gray-100/60 transition-colors
          ${isSelected ? 'bg-blue-50 ring-1 ring-inset ring-blue-300'
            : isCurrentPeriod ? 'bg-emerald-50/30 border-l-2 border-r-2 border-emerald-300/60 shadow-[inset_0_0_12px_rgba(16,185,129,0.08)]'
            : zebra ? 'bg-slate-50/50 hover:bg-blue-50/40' : 'hover:bg-blue-50/40'}`}
        onClick={onClick}
        title={`Sin proyección para este período.\nReal: ${valStr}\n${cityName} · ${lineName} · ${periodLbl}`}
      >
        {/* Real */}
        <div className={`${szReal} font-semibold leading-none ${hasReal ? 'text-gray-800' : 'text-gray-300'}`}>{valStr}</div>
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
        className={`px-1 ${py} text-center whitespace-nowrap cursor-pointer select-none border-r border-gray-100/60 transition-colors
          ${isSelected ? 'bg-blue-50 ring-1 ring-inset ring-blue-300'
            : isCurrentPeriod ? 'bg-emerald-50/30 border-l-2 border-r-2 border-emerald-300/60 shadow-[inset_0_0_12px_rgba(16,185,129,0.08)]'
            : zebra ? 'bg-slate-50/50 hover:bg-blue-50/40' : 'hover:bg-blue-50/40'}`}
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

  // Temporal degradation
  const temporalAge = periodKey
    ? computePastAgingOpacity(periodKey, grain)
    : 0
  const pastDegraded = temporalAge > 0 && !isCurrentPeriod && !isSelected

  // Confidence
  const conf    = delta.curve_confidence
  const lowConf = conf === 'low' || conf === 'fallback'
  const medConf = conf === 'medium'
  const confBorder = lowConf
    ? 'ring-1 ring-inset ring-dashed ring-red-300/70'
    : medConf
      ? 'ring-1 ring-inset ring-dashed ring-amber-300/60'
      : ''

  // Critical alert — only for real deterioration, not future
  const criticalAlert = !dm.isFuture && (dm.hasNegActual || (dm.hasPlan && !dm.hasReal && delta.attainment_pct != null && delta.attainment_pct < 75))

  // Future/pending: ghosted, muted. Real: full intensity.
  const futureDim = dm.isFuture ? 'opacity-45 grayscale-[30%]' : ''

  return (
    <td
      data-matrix-cell-id={matrixCellId || undefined}
      className={`px-1 ${py} text-center whitespace-nowrap cursor-pointer select-none border-r border-gray-100/60 transition-colors relative
        ${isSelected
          ? 'bg-blue-50 ring-1 ring-inset ring-blue-300'
          : isCurrentPeriod && !dm.isFuture
            ? `${dm.severityBg || ''} bg-gradient-to-b from-emerald-50/40 to-emerald-50/20 border-l-2 border-r-2 border-emerald-400/60 shadow-[inset_0_0_18px_rgba(16,185,129,0.12),0_0_10px_rgba(16,185,129,0.10)]`
            : isCurrentPeriod && dm.isFuture
              ? 'bg-slate-100/40 border-l border-r border-slate-200/60'  // future current: muted, NOT green
            : dm.isFuture
              ? 'bg-slate-50/30'
              : `${dm.isMomentum ? dm.severityBg : ''} ${zebra && !dm.severityBg ? 'bg-slate-50/50' : ''} hover:bg-blue-50/40`}
        ${futureDim}
        ${!isSelected && !dm.isFuture ? confBorder : ''}`}
      style={pastDegraded && !dm.isFuture ? { opacity: 1 - temporalAge } : undefined}
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

      {/* ── L1: HOY badge ── */}
      {isCurrentPeriod && !dm.isFuture && (
        <div className={`${szStatus} leading-none mb-0.5`}>
          <span className="inline-block px-1 py-px rounded text-[7px] font-bold uppercase leading-none bg-emerald-500 text-white">
            {grain === 'daily' ? 'HOY' : grain === 'weekly' ? 'SEM ACT' : 'MES ACT'}
          </span>
        </div>
      )}

      {/* ── L2: REAL VALUE — DOMINANTE ── */}
      <div className={`${isCurrentPeriod && !dm.isFuture ? (compact ? 'text-[12px]' : 'text-[16px]') : szReal} font-extrabold leading-tight ${dm.hasReal || dm.hasNegActual ? (dm.hasNegActual ? 'text-red-700' : dm.isFuture ? 'text-gray-400' : 'text-gray-900') : 'text-gray-400'}`}>
        {dm.realStr}
      </div>

      {/* ── L3: DELTA MOMENTUM — DOMINANTE ── */}
      <div className="leading-none mt-0.5 flex items-center justify-center">
        {dm.isMomentum ? (
          /* MOMENTUM: colored, bold, arrow + pct. SIMPLE. */
          <span className={`${szAv} ${dm.deltaBold}`} style={{ color: dm.deltaColor }}>
            {dm.deltaArrow}{dm.deltaPctStr}
          </span>
        ) : dm.isPlanFallback ? (
          /* PLAN FALLBACK: attainment, muted, small */
          <span className={`${szStatus} font-semibold text-gray-400`}>
            {dm.attainmentStr || '—'}
          </span>
        ) : dm.isFuture ? (
          /* FUTURE: pending, no delta */
          <span className={`${szStatus} font-medium text-slate-300`}>—</span>
        ) : (
          <span className={`${szStatus} text-gray-300`}>—</span>
        )}
      </div>

      {/* ── L4: COMPARABLE CONTEXT ── */}
      {dm.comparableLabel && (
        <div className={`${szStatus} leading-none mt-0.5 text-gray-400`}>
          {dm.comparableLabel}
        </div>
      )}

      {/* ── L5: PLAN / AVANCE CONTEXT ── */}
      {dm.isMomentum && dm.attainmentStr && (
        <div className={`text-[7px] leading-none mt-px text-gray-300`}>
          Plan {dm.attainmentStr}
        </div>
      )}
      {dm.isPlanFallback && dm.planStr && (
        <div className={`${szStatus} leading-none mt-0.5 text-gray-400`}>
          Plan {dm.planStr}
        </div>
      )}

      {/* ── L6: STATUS / PENDING ── */}
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
      ? Math.min(Math.floor(diffDays / 1), 60)
      : grain === 'weekly'
        ? Math.min(Math.floor(diffDays / 7), 40)
        : Math.min(Math.floor(diffDays / 30), 24)
    return Math.min(steps * 0.025, 0.55)
  } catch {
    return 0
  }
}
