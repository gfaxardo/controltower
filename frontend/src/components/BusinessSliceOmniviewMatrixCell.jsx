import { memo } from 'react'
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
function ProjectionCellRender ({ kpiKey, kpi, delta, onClick, isSelected, compact, periodIdx, cityName, lineName, periodLbl, matrixCellId }) {
  const zebra = periodIdx % 2 === 1
  const isProjectable = PROJECTION_KPIS.includes(kpiKey)

  // Tamaños tipográficos adaptados al modo compact
  const szProy   = compact ? 'text-[7px]' : 'text-[8px]'
  const szReal   = compact ? 'text-[9px]' : 'text-[9px]'
  const szAv     = compact ? 'text-[8px]' : 'text-[8px]'
  const szGap    = compact ? 'text-[7px]' : 'text-[7px]'
  const szStatus = compact ? 'text-[7px]' : 'text-[7px]'
  const py       = compact ? 'py-0.5' : 'py-1'

  // Extraer comparison_status de cualquier delta disponible (todos los KPIs del período tienen el mismo)
  const comparisonStatus = delta?.comparison_status

  // ── Sin datos de ningún tipo ──────────────────────────────────────────────
  if (!delta) {
    return (
      <td
        data-matrix-cell-id={matrixCellId || undefined}
        className={`px-1 ${py} text-center border-r border-gray-100/60 cursor-default select-none ${isSelected ? 'bg-blue-50' : zebra ? 'bg-slate-50/50' : ''}`}
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
          ${isSelected ? 'bg-blue-50 ring-1 ring-inset ring-blue-300' : zebra ? 'bg-slate-50/50 hover:bg-blue-50/40' : 'hover:bg-blue-50/40'}`}
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
          ${isSelected ? 'bg-blue-50 ring-1 ring-inset ring-blue-300' : zebra ? 'bg-slate-50/50 hover:bg-blue-50/40' : 'hover:bg-blue-50/40'}`}
        onClick={onClick}
        title={tooltip}
      >
        <div className={`${szReal} font-semibold text-gray-800 leading-none`}>{val}</div>
        <div className={`${szStatus} leading-none text-gray-300 mt-px`}>sin plan</div>
      </td>
    )
  }

  // ── KPI proyectable ───────────────────────────────────────────────────────
  const projected = delta.projected_total
  const actual    = delta.value
  const att       = delta.attainment_pct  // canónico: NUNCA negativo (null si actual < 0)
  const gap       = delta.gap_to_expected // gap_abs
  const gapPct    = delta.gap_pct         // gap%: puede ser negativo

  const hasPlan         = projected != null && Number(projected) > 0
  const hasReal         = actual != null && Number(actual) > 0
  const hasNegActual    = actual != null && Number(actual) < 0

  // Formato de valores mostrados
  const projStr = hasPlan ? fmtValue(projected, kpiKey) : '—'
  const realStr = hasReal
    ? fmtValue(actual, kpiKey)
    : hasNegActual
      ? fmtValue(actual, kpiKey)   // revenue negativo: mostrar el valor (ej: -5.2K)
      : (actual === 0 || actual === null ? '0' : '—')

  // Sufijo de base: (E) = expected_to_date, (F) = full period
  const basis   = delta.comparison_basis
  const sfx     = basisSuffix(basis)           // '(E)', '(F)', o ''

  // Avance %: NUNCA negativo. Si actual < 0 → mostrar gap% en su lugar.
  // El sufijo (E)/(F) se añade cuando el avance es un valor real (no '—' ni '0.0%' de sin ejecución).
  const rawAvStr = hasNegActual
    ? '—'
    : hasPlan
      ? fmtAttainment(hasReal ? att : 0)
      : '—'
  const avStr = (rawAvStr !== '—' && sfx)
    ? `${rawAvStr} ${sfx}`
    : rawAvStr

  // Si avance_pct es null por actual negativo, mostramos gap% como fallback informativo
  const showGapPctFallback = hasNegActual && gapPct != null
  const gapPctStr = fmtGapPct(gapPct)

  const gapStr = gap != null ? fmtGap(gap, kpiKey) : null

  // Señal: si sin real forzamos no_data para coloración neutra
  // Si actual < 0 → danger (problema real, aunque avance no aplique)
  const signal = hasNegActual
    ? 'danger'
    : (hasPlan && !hasReal) ? 'no_data' : (delta.signal || 'no_data')
  const dotClass = SIGNAL_DOT[signal] || SIGNAL_DOT.no_data
  const attColor = projectionSignalColor(signal)

  // Fondo semántico por señal
  const signalBg = signal === 'danger'  ? 'bg-red-50/60'
    : signal === 'warning' ? 'bg-amber-50/40'
    : signal === 'green'   ? 'bg-emerald-50/30'
    : ''

  // Confianza de la curva
  const conf    = delta.curve_confidence
  const lowConf = conf === 'low' || conf === 'fallback'
  const medConf = conf === 'medium'
  const confBorder = lowConf
    ? 'ring-1 ring-inset ring-dashed ring-red-300/70'
    : medConf
      ? 'ring-1 ring-inset ring-dashed ring-amber-300/60'
      : ''

  // Alerta crítica: < 75% o actual negativo
  const criticalAlert = signal === 'danger' && (hasNegActual || (att != null && att < 75))

  // Estado semántico
  const attPctForStatus = hasReal && !hasNegActual ? att : (hasPlan ? 0 : null)
  const statusLabel = getProjectionStatusLabel(attPctForStatus, hasPlan, hasReal)
  const statusColors = getProjectionStatusColors(statusLabel)

  // Solo mostrar el estado si sin real (con real lo indica el color/señal)
  const showStatusLabel = statusLabel && !hasReal

  return (
    <td
      data-matrix-cell-id={matrixCellId || undefined}
      className={`px-1 ${py} text-center whitespace-nowrap cursor-pointer select-none border-r border-gray-100/60 transition-colors relative
        ${isSelected
          ? 'bg-blue-50 ring-1 ring-inset ring-blue-300'
          : `${signalBg} ${zebra && !signalBg ? 'bg-slate-50/50' : ''} hover:bg-blue-50/40`}
        ${!isSelected ? confBorder : ''}`}
      onClick={onClick}
      title={tooltip}
    >
      {/* Alerta crítica < 75% o negativo */}
      {criticalAlert && (
        <span
          className="absolute top-0.5 right-0.5 w-1.5 h-1.5 rounded-full bg-red-600 ring-1 ring-white shadow-sm"
          title={hasNegActual ? 'Alerta: valor real negativo' : 'Alerta: cumplimiento bajo 75%'}
          aria-hidden
        />
      )}
      {(delta?.projection_confidence === 'low' || delta?.projection_anomaly) && (
        <span
          className="absolute top-0.5 left-0.5 w-1 h-1 rounded-full bg-amber-500 ring-1 ring-white shadow-sm"
          title={delta.projection_anomaly ? 'Anomalía de volatilidad en derivación' : 'Baja confianza de proyección (fallback/ajuste)'}
          aria-hidden
        />
      )}
      {/* FASE_KPI_CONSISTENCY: badge discreto cuando el KPI no es comparable por suma entre granos */}
      {!isKpiComparableAcrossGrains(kpiKey) && (
        <span
          className="absolute bottom-0.5 right-0.5 px-0.5 text-[6px] font-semibold leading-none rounded-sm bg-slate-200/80 text-slate-600"
          title={`${getKpiComparabilityBadge(kpiKey)?.label || ''}: comparación por scope, no por suma entre granos.`}
          aria-hidden
        >
          {getKpiComparabilityBadge(kpiKey)?.short || '≠Σ'}
        </span>
      )}

      {/* Fila 1: Proyectado */}
      <div className={`${szProy} text-gray-400 leading-none`}>
        <span className="text-gray-300">↑</span> {projStr}
      </div>

      {/* Fila 2: Real alcanzado */}
      <div className={`${szReal} font-semibold leading-none mt-px ${(hasReal || hasNegActual) ? (hasNegActual ? 'text-red-700' : 'text-gray-800') : 'text-gray-400'}`}>
        {realStr}
      </div>

      {/* Fila 3: Avance % con señal (o gap% si actual negativo) */}
      <div className={`${szAv} leading-none font-semibold mt-px flex items-center justify-center gap-0.5`}>
        <span className={`inline-block w-1.5 h-1.5 rounded-full ${dotClass} flex-shrink-0`} />
        {showGapPctFallback
          ? <span style={{ color: attColor }} title="Gap% (avance no aplica con valor negativo)">{gapPctStr}</span>
          : <span style={{ color: attColor }}>{avStr}</span>
        }
        {lowConf && (
          <span className="text-[6px] text-red-400 font-bold" title="Baja confianza en curva de distribución">?</span>
        )}
      </div>

      {/* Fila 4: Gap absoluto (solo si disponible y no es caso negativo) */}
      {gapStr && !showGapPctFallback && (
        <div className={`${szGap} leading-none mt-px text-gray-400`}>{gapStr}</div>
      )}

      {/* Etiqueta de estado "Sin ejecución" (solo cuando no hay real) */}
      {showStatusLabel && (
        <div className={`${szStatus} leading-none mt-px font-medium truncate ${statusColors.text}`}>
          {statusLabel}
        </div>
      )}
    </td>
  )
}
