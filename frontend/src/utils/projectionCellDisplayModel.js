/**
 * projectionCellDisplayModel.js
 *
 * CANONICAL display model for Omniview Vs Proyección cells.
 *
 * REGLA ABSOLUTA:
 *   Momentum (DoD/WoW/MoM) = lectura dominante.
 *   Plan vs Real = contexto secundario.
 *
 * Jerarquía visual aprobada:
 *   L1: VALOR REAL (extrabold, grande)
 *   L2: DELTA MOMENTUM (▼/▲ + %, coloreado por severity)
 *   L3: vs [comparable] (pequeño, contextual)
 *   L4: Plan / parcial / avance (ultra-small)
 *   L5: Future / Pending (cuando no hay real)
 */
import { getMomentumSeverityColor, getMomentumSeverityBg } from './operationalMomentumEmphasis.js'
import { fmtValue, MATRIX_KPIS } from '../components/omniview/omniviewMatrixUtils.js'
import { fmtAttainment } from '../components/omniview/projectionMatrixUtils.js'

function deriveMomentumLabel(grain) {
  if (grain === 'daily') return 'DoD'
  if (grain === 'weekly') return 'WoW'
  if (grain === 'monthly') return 'MoM'
  return null
}

/**
 * Temporal comparable label for context line.
 */
function comparableContextLabel(grain) {
  if (grain === 'daily') return 'vs domingo comparable'
  if (grain === 'weekly') return 'vs semana anterior'
  if (grain === 'monthly') return 'vs mes anterior'
  return null
}

export function buildProjectionCellDisplay(delta, grain, kpiKey) {
  const actual    = delta?.value
  const projected = delta?.projected_total
  const att       = delta?.attainment_pct
  const isProjection = delta?.isProjection
  const weekState   = delta?.week_state

  const hasReal  = actual != null && Number(actual) > 0
  const hasPlan  = projected != null && Number(projected) > 0
  const hasNegActual = actual != null && Number(actual) < 0
  const isFuture = weekState === 'future' && !hasReal

  // ── MOMENTUM DETECTION ──
  // periodPop is { abs, pct, basis, cur_real, prev_real } from backend
  // Extract pct (percentage change) for display
  const popObj   = delta?.periodPop
  const popValue = (popObj && typeof popObj === 'object') ? Number(popObj.pct) : NaN
  const popAbs   = (popObj && typeof popObj === 'object') ? Number(popObj.abs) : NaN
  const hasMomentumData = Number.isFinite(popValue)

  let primaryDeltaPct    = null
  let primaryDeltaLabel  = null
  let primaryDirection   = 'neutral'
  let isMomentum   = false
  let isPlanFallback = false

  if (hasMomentumData) {
    const pct = Number(popValue)
    primaryDeltaPct   = pct
    primaryDirection  = pct > 0 ? 'up' : pct < 0 ? 'down' : 'neutral'
    primaryDeltaLabel = delta?.periodPopLabel || deriveMomentumLabel(grain) || null
    isMomentum = true
  } else if (isProjection && hasPlan) {
    isPlanFallback = true
  }

  // ── SEVERITY ──
  const severity = isMomentum
    ? getMomentumSeverityColor(primaryDeltaPct)
    : { color: '#9ca3af', level: 0 }
  const severityBg = isMomentum ? getMomentumSeverityBg(primaryDeltaPct) : ''

  // ── FORMATTED VALUES ──
  const realStr = hasReal ? fmtValue(actual, kpiKey)
    : hasNegActual ? fmtValue(actual, kpiKey)
    : (actual === 0 ? '0' : '—')

  const deltaArrow = primaryDirection === 'up' ? '▲' : primaryDirection === 'down' ? '▼' : ''
  const deltaPctStr = hasMomentumData && Number.isFinite(primaryDeltaPct)
    ? `${primaryDeltaPct > 0 ? '+' : ''}${Number(primaryDeltaPct).toFixed(0)}%`
    : null

  // ── ATTAINMENT ──
  const attainmentStr = hasPlan && isProjection
    ? fmtAttainment(hasReal && !hasNegActual ? att : 0)
    : null

  // ── COMPARABLE LABEL ──
  const comparableLabel = isMomentum ? comparableContextLabel(grain) : null

  // ── PLAN VALUE (context) ──
  const planStr = hasPlan ? fmtValue(projected, kpiKey) : null

  // ── STATUS ──
  const statusText = isFuture
    ? 'Pendiente'
    : (isProjection && !hasReal ? (weekState || 'Sin ejecución') : null)

  const deltaBold = Math.abs(primaryDeltaPct || 0) > 15 ? 'font-extrabold'
    : Math.abs(primaryDeltaPct || 0) > 5 ? 'font-bold' : 'font-semibold'

  return {
    realStr,
    deltaArrow,
    deltaPctStr,
    deltaLabel: primaryDeltaLabel,
    deltaColor: severity.color,
    deltaBold,

    comparableLabel,          // "vs domingo comparable"
    attainmentStr,            // "47.3%"
    planStr,                  // "59.6K"
    statusText,               // "Pendiente" | "Sin ejecución" | null

    hasReal,
    hasPlan,
    hasNegActual,
    isMomentum,
    isPlanFallback,
    isFuture,
    hasMomentumData,
    severity,
    severityBg,
    weekState,
  }
}

export function selectionHasMomentum(selection) {
  if (!selection) return false
  const raw = selection?.raw
  if (!raw) return false
  const pop = raw.period_over_period
  if (!pop) return false
  const metrics = pop.metrics || {}
  for (const key of MATRIX_KPIS.map(k => k.key)) {
    const v = metrics[key]
    // v is { abs, pct, basis, cur_real, prev_real }
    if (v && typeof v === 'object' && Number.isFinite(Number(v.pct))) return true
  }
  return false
}
