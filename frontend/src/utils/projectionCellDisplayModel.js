/**
 * projectionCellDisplayModel.js
 *
 * CANONICAL display model for Omniview Vs Proyección cells.
 *
 * REGLA ABSOLUTA (v2.0 — Delta Comparable Isolation):
 *   L1: VALOR REAL — ejecución, extrabold, grande
 *   L2: DELTA COMPARABLE — DoD/WoW/MoM, coloreado, arrow + pct + label
 *       NUNCA attainment. NUNCA gap. NUNCA YTD.
 *   L3: CONTEXTO SECUNDARIO — attainment o plan, ultra-small, muted
 *   L4: STATUS — Pendiente / Sin ejecución
 *
 * La delta comparable se resuelve EXCLUSIVAMENTE vía comparableDeltaDisplay.js.
 * Si no hay periodPop del backend, L2 muestra "—", no attainment.
 */
import { getMomentumSeverityBg } from './operationalMomentumEmphasis.js'
import { fmtValue, MATRIX_KPIS } from '../components/omniview/omniviewMatrixUtils.js'
import { fmtAttainment } from '../components/omniview/projectionMatrixUtils.js'
import { buildComparableDelta } from './comparableDeltaDisplay.js'

export function buildProjectionCellDisplay(delta, grain, kpiKey) {
  const actual    = delta?.value
  const projected = delta?.projected_total
  const att       = delta?.attainment_pct
  const isProjection = delta?.isProjection
  const weekState   = delta?.week_state

  const hasReal  = actual != null && !isNaN(Number(actual))
  const hasPlan  = projected != null && Number(projected) > 0
  const hasNegActual = actual != null && Number(actual) < 0
  const isFuture = weekState === 'future' && !hasReal

  // ── COMPARABLE DELTA — resuelto por el engine canónico ──
  const comparableDelta = buildComparableDelta(delta, grain)
  const hasComparable = comparableDelta.hasComparable

  // ── SEVERITY BG — solo si hay momentum ──
  const severityBg = hasComparable
    ? getMomentumSeverityBg(comparableDelta.pct)
    : ''

  // ── L1: REAL VALUE ──
  const realStr = hasReal ? fmtValue(actual, kpiKey)
    : hasNegActual ? fmtValue(actual, kpiKey)
    : (actual === 0 ? '0' : '—')

  // ── L3: ATTAINMENT (contexto secundario, NUNCA en L2) ──
  const attainmentStr = hasPlan && isProjection
    ? fmtAttainment(hasReal && !hasNegActual ? att : 0)
    : null

  // ── L3: PLAN VALUE (contexto secundario) ──
  const planStr = hasPlan ? fmtValue(projected, kpiKey) : null

  // ── L3: CONTEXT STRING — attainment o plan, según el caso ──
  let contextStr = null
  if (hasComparable && attainmentStr) {
    // Hay momentum → attainment es contexto terciario
    contextStr = attainmentStr
  } else if (!hasComparable && hasPlan && attainmentStr) {
    // Sin momentum → mostrar attainment como contexto (NO como delta)
    contextStr = attainmentStr
  } else if (!hasComparable && hasPlan && planStr) {
    // Sin momentum ni attainment → mostrar plan
    contextStr = planStr
  }

  // ── L4: STATUS ──
  const statusText = isFuture
    ? 'Pendiente'
    : (isProjection && !hasReal ? (weekState || 'Sin ejecución') : null)

  return {
    // L1
    realStr,
    hasReal,
    hasNegActual,

    // L2 — comparable delta (canónico, aislado)
    comparableDelta,
    hasComparable,

    // L3 — contexto secundario
    contextStr,
    attainmentStr,
    planStr,
    hasPlan,

    // L4 — status
    statusText,

    // Estados
    isFuture,
    weekState,
    severityBg,

    // Retenido para compatibilidad con cell renderer existente
    isMomentum: hasComparable,
    isPlanFallback: !hasComparable && hasPlan && isProjection,
    hasMomentumData: hasComparable,
    severity: hasComparable
      ? { color: comparableDelta.severityColor, level: 0 }
      : { color: '#9ca3af', level: 0 },
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
