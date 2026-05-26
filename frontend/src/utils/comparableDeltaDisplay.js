/**
 * comparableDeltaDisplay.js
 *
 * CANONICAL comparable delta engine for Omniview Vs Proyección cells.
 *
 * OBJETIVO:
 *   Aislar completamente el delta comparable (DoD/WoW/MoM) del resto de
 *   métricas de la celda (plan, attainment, gap, YTD).
 *
 * REGLA ABSOLUTA:
 *   El delta comparable SIEMPRE se deriva de period_over_period del backend.
 *   NUNCA se usa attainment, gap o YTD como sustituto visual del delta.
 *
 *   Si no hay periodPop, el delta es "—" (no comparable).
 *   Attainment/gap van a tooltip o línea terciaria, NUNCA a L2.
 *
 * Motor: Control Foundation
 */

import { getMomentumSeverityColor } from './operationalMomentumEmphasis.js'

/**
 * Comparable type enum — matches backend `periodPopKind` values.
 */
export const COMPARABLE_TYPE = Object.freeze({
  DOD_SAME_WEEKDAY: 'dod_same_weekday',
  WOW:              'wow',
  MOM:              'mom',
  DOD_SEQUENTIAL:   'dod_sequential',   // D-1 simple (no same-weekday)
  PARTIAL:          'partial',           // WoW/MoM parcial
  NONE:             'none',
})

/**
 * Direction enum.
 */
export const COMPARABLE_DIRECTION = Object.freeze({
  UP:   'up',
  DOWN: 'down',
  FLAT: 'flat',
})

/**
 * Severity enum for display purposes.
 */
export const COMPARABLE_SEVERITY = Object.freeze({
  CRITICAL:  'critical',
  ELEVATED:  'elevated',
  WARNING:   'warning',
  NORMAL:    'normal',
  UNKNOWN:   'unknown',
})

/**
 * HUMAN-READABLE LABELS per type.
 */
const TYPE_LABEL = {
  [COMPARABLE_TYPE.DOD_SAME_WEEKDAY]: 'DoD',
  [COMPARABLE_TYPE.WOW]:              'WoW',
  [COMPARABLE_TYPE.MOM]:              'MoM',
  [COMPARABLE_TYPE.DOD_SEQUENTIAL]:   'DoD',
  [COMPARABLE_TYPE.PARTIAL]:          'WoW',
}

/**
 * Derive comparable type from backend `periodPopKind` with grain fallback.
 *
 * Prioridad:
 *   1. `periodPopKind` del backend (fuente de verdad)
 *   2. Derivación del grain (fallback)
 *
 * @param {string|null} backendKind - delta.periodPopKind
 * @param {string} grain - 'daily' | 'weekly' | 'monthly'
 * @returns {string} COMPARABLE_TYPE value
 */
export function resolveComparableType(backendKind, grain) {
  if (backendKind === 'daily_same_weekday') return COMPARABLE_TYPE.DOD_SAME_WEEKDAY
  if (backendKind === 'daily' || backendKind === 'daily_sequential') return COMPARABLE_TYPE.DOD_SEQUENTIAL
  if (backendKind === 'weekly' || backendKind === 'weekly_partial' || backendKind === 'weekly_partial_equivalent')
    return COMPARABLE_TYPE.WOW
  if (backendKind === 'monthly' || backendKind === 'monthly_partial' || backendKind === 'monthly_partial_equivalent')
    return COMPARABLE_TYPE.MOM

  // Fallback: derive from grain
  if (grain === 'daily')   return COMPARABLE_TYPE.DOD_SAME_WEEKDAY
  if (grain === 'weekly')  return COMPARABLE_TYPE.WOW
  if (grain === 'monthly') return COMPARABLE_TYPE.MOM

  return COMPARABLE_TYPE.NONE
}

/**
 * Get human-readable short label for a comparable type.
 *
 * @param {string} type - COMPARABLE_TYPE value
 * @returns {string} Short label (DoD, WoW, MoM)
 */
export function getComparableLabel(type) {
  return TYPE_LABEL[type] || null
}

/**
 * Resolve direction from percentage value.
 *
 * @param {number} pct - Percentage change
 * @returns {string} COMPARABLE_DIRECTION value
 */
export function resolveDirection(pct) {
  if (!Number.isFinite(pct)) return COMPARABLE_DIRECTION.FLAT
  if (pct > 0.5)  return COMPARABLE_DIRECTION.UP
  if (pct < -0.5) return COMPARABLE_DIRECTION.DOWN
  return COMPARABLE_DIRECTION.FLAT
}

/**
 * Resolve severity level from absolute percentage.
 *
 * @param {number} pct - Percentage change
 * @returns {string} COMPARABLE_SEVERITY value
 */
export function resolveSeverityLevel(pct) {
  if (!Number.isFinite(pct)) return COMPARABLE_SEVERITY.UNKNOWN
  const absPct = Math.abs(pct)
  if (absPct > 30) return COMPARABLE_SEVERITY.CRITICAL
  if (absPct > 15) return COMPARABLE_SEVERITY.ELEVATED
  if (absPct > 5)  return COMPARABLE_SEVERITY.WARNING
  return COMPARABLE_SEVERITY.NORMAL
}

/**
 * Get arrow character for direction.
 *
 * @param {string} direction - COMPARABLE_DIRECTION value
 * @returns {string} Arrow character or empty string
 */
export function getDirectionArrow(direction) {
  if (direction === COMPARABLE_DIRECTION.UP)   return '▲'
  if (direction === COMPARABLE_DIRECTION.DOWN) return '▼'
  return ''
}

/**
 * Format the display string for L2: "{arrow} {pct}% {label}"
 *
 * @param {Object} params
 * @param {string} params.direction - COMPARABLE_DIRECTION
 * @param {number} params.pct - Percentage
 * @param {string} params.label - Short label (DoD/WoW/MoM)
 * @returns {string} Formatted display string
 */
export function formatComparableDisplay({ direction, pct, label }) {
  const arrow = getDirectionArrow(direction)
  const sign = pct > 0 ? '+' : ''
  const pctStr = Number.isFinite(pct) ? `${sign}${Number(pct).toFixed(0)}%` : '—'
  const suffix = label ? ` ${label}` : ''
  return `${arrow}${arrow ? ' ' : ''}${pctStr}${suffix}`
}

/**
 * Format the percentage string alone (no arrow, no label).
 *
 * @param {number} pct - Percentage
 * @returns {string} Formatted pct string
 */
export function formatComparablePct(pct) {
  if (!Number.isFinite(pct)) return null
  const sign = pct > 0 ? '+' : ''
  return `${sign}${Number(pct).toFixed(0)}%`
}

/**
 * CANONICAL: build a comparable delta display model from projection delta data.
 *
 * Este es el UNICO punto de entrada para determinar qué se muestra en L2.
 * NO hay fallback a attainment. NO hay mezcla con plan.
 *
 * @param {Object} delta - Projection delta object from computeProjectionDeltas
 * @param {string} grain - 'daily' | 'weekly' | 'monthly'
 * @returns {Object} Comparable delta display model
 *
 * Return shape:
 * {
 *   hasComparable: boolean,        // true si hay periodPop con pct válido
 *   type: string,                  // COMPARABLE_TYPE
 *   direction: string,             // COMPARABLE_DIRECTION
 *   pct: number|null,              // percentage change
 *   abs: number|null,              // absolute change
 *   label: string|null,            // "DoD" | "WoW" | "MoM"
 *   display: string,               // "▼ -21% DoD" (para L2)
 *   severity: string,              // COMPARABLE_SEVERITY
 *   severityColor: string,         // hex color from momentum emphasis
 *   deltaBold: string,             // Tailwind font weight class
 *   comparableDate: string|null,   // fecha del período comparado (para tooltip)
 * }
 */
export function buildComparableDelta(delta, grain) {
  // Default: no comparable
  const empty = {
    hasComparable: false,
    type: COMPARABLE_TYPE.NONE,
    direction: COMPARABLE_DIRECTION.FLAT,
    pct: null,
    abs: null,
    label: null,
    display: '—',
    severity: COMPARABLE_SEVERITY.UNKNOWN,
    severityColor: '#9ca3af',
    deltaBold: 'font-normal',
    comparableDate: null,
  }

  if (!delta) return empty

  const popObj = delta.periodPop

  // periodPop must be an object with a valid pct
  if (!popObj || typeof popObj !== 'object') return empty

  const pct = Number(popObj.pct)
  const abs = Number(popObj.abs)

  if (!Number.isFinite(pct)) return empty

  // Resolve type from backend kind, with grain fallback
  const type = resolveComparableType(delta.periodPopKind, grain)

  // Resolve direction, severity, label
  const direction = resolveDirection(pct)
  const severity = resolveSeverityLevel(pct)
  const label = delta.periodPopLabel || getComparableLabel(type)

  // Severity color via momentum emphasis
  const severityColorObj = getMomentumSeverityColor(pct)
  const severityColor = severityColorObj?.color || '#9ca3af'

  // Display string
  const display = formatComparableDisplay({ direction, pct, label })

  // Boldness
  const absPct = Math.abs(pct)
  const deltaBold = absPct > 15 ? 'font-extrabold'
    : absPct > 5 ? 'font-bold'
    : 'font-semibold'

  return {
    hasComparable: true,
    type,
    direction,
    pct,
    abs,
    label,
    display,
    severity,
    severityColor,
    deltaBold,
    comparableDate: delta.periodPopComparable || null,
  }
}

export default {
  COMPARABLE_TYPE,
  COMPARABLE_DIRECTION,
  COMPARABLE_SEVERITY,
  resolveComparableType,
  getComparableLabel,
  resolveDirection,
  resolveSeverityLevel,
  getDirectionArrow,
  formatComparableDisplay,
  formatComparablePct,
  buildComparableDelta,
}
