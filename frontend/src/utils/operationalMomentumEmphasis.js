/**
 * OPERATIONAL MOMENTUM EMPHASIS
 * 
 * Sistema de énfasis visual para comparaciones operacionales.
 * Determina el peso visual de cada delta basado en su tipo de comparación.
 * 
 * Jerarquía de urgencia operacional:
 * Nivel 1 (máximo) — DoD same-weekday, WoW, MoM → ACCIÓN INMEDIATA
 * Nivel 2 (medio)   — Plan vs Real, YTD → CONTEXTO
 * Nivel 3 (sutil)   — Sequencial simple → OBSERVACIÓN
 * 
 * Motor: Control Foundation + Diagnostic Engine Temprano
 */

/* ── TIPOS DE COMPARACIÓN ── */

export const COMPARISON_CLASS = Object.freeze({
  MOMENTUM_SAME_WEEKDAY: 'momentum_same_weekday',    // DoD mismo día de semana
  MOMENTUM_WOW:          'momentum_wow',              // Week over Week
  MOMENTUM_MOM:          'momentum_mom',              // Month over Month
  MOMENTUM_PARTIAL:      'momentum_partial',          // WoW/MoM parcial (semana/mes en curso)
  PLAN_VS_REAL:          'plan_vs_real',              // Plan vs Real
  YTD:                   'ytd',                       // Year to Date
  SEQUENTIAL:            'sequential',                // Periodo anterior simple
})

/** Mapping from backend comparison_mode to our classification */
const MODE_TO_CLASS = {
  daily_same_weekday:       COMPARISON_CLASS.MOMENTUM_SAME_WEEKDAY,
  weekly_partial_equivalent: COMPARISON_CLASS.MOMENTUM_PARTIAL,
  monthly_partial_equivalent: COMPARISON_CLASS.MOMENTUM_PARTIAL,
  // Default/sequential: we classify based on grain
}

/* ── EMPHASIS LEVELS ── */

export const EMPHASIS_LEVEL = Object.freeze({
  MAXIMUM:  3,  // Momentum comparisons — maximum visual weight
  MEDIUM:   2,  // Plan vs Real, YTD — contextual weight
  SUBTLE:   1,  // Simple sequential — observation weight
  HIDDEN:   0,  // Not shown
})

const EMPHASIS_MAP = {
  [COMPARISON_CLASS.MOMENTUM_SAME_WEEKDAY]: EMPHASIS_LEVEL.MAXIMUM,
  [COMPARISON_CLASS.MOMENTUM_WOW]:          EMPHASIS_LEVEL.MAXIMUM,
  [COMPARISON_CLASS.MOMENTUM_MOM]:          EMPHASIS_LEVEL.MAXIMUM,
  [COMPARISON_CLASS.MOMENTUM_PARTIAL]:      EMPHASIS_LEVEL.MAXIMUM,
  [COMPARISON_CLASS.PLAN_VS_REAL]:          EMPHASIS_LEVEL.MEDIUM,
  [COMPARISON_CLASS.YTD]:                   EMPHASIS_LEVEL.MEDIUM,
  [COMPARISON_CLASS.SEQUENTIAL]:            EMPHASIS_LEVEL.SUBTLE,
}

/* ── VISUAL STYLES PER EMPHASIS ── */

const EMPHASIS_STYLE = {
  [EMPHASIS_LEVEL.MAXIMUM]: {
    fontWeight:  600,
    opacity:     1,
    saturation:  1,     // Full color saturation
    sizeScale:   1.0,   // Use default compact/normal sizing
    prefix:      '',    // No special prefix
  },
  [EMPHASIS_LEVEL.MEDIUM]: {
    fontWeight:  500,
    opacity:     0.85,
    saturation:  0.8,
    sizeScale:   0.95,
    prefix:      '',
  },
  [EMPHASIS_LEVEL.SUBTLE]: {
    fontWeight:  400,
    opacity:     0.65,
    saturation:  0.6,
    sizeScale:   0.88,
    prefix:      '',
  },
  [EMPHASIS_LEVEL.HIDDEN]: {
    fontWeight:  400,
    opacity:     0,
    saturation:  0,
    sizeScale:   0,
    prefix:      '',
  },
}

/* ── LABELS ── */

const COMPARISON_LABEL = {
  [COMPARISON_CLASS.MOMENTUM_SAME_WEEKDAY]: 'DoD',
  [COMPARISON_CLASS.MOMENTUM_WOW]:          'WoW',
  [COMPARISON_CLASS.MOMENTUM_MOM]:          'MoM',
  [COMPARISON_CLASS.MOMENTUM_PARTIAL]:      'WoW',
  [COMPARISON_CLASS.PLAN_VS_REAL]:          'vPlan',
  [COMPARISON_CLASS.YTD]:                   'YTD',
  [COMPARISON_CLASS.SEQUENTIAL]:            'Δ',
}

/* ── PURE FUNCTIONS ── */

/**
 * Clasifica un delta por su tipo de comparación.
 * Recibe el objeto delta completo de computeDeltas().
 */
export function classifyComparison(delta = {}, grain = 'monthly') {
  if (!delta) return COMPARISON_CLASS.SEQUENTIAL

  const mode = delta.comparison_mode

  // Explicitly tagged by backend
  if (mode && MODE_TO_CLASS[mode]) {
    return MODE_TO_CLASS[mode]
  }

  // Projection delta: plan vs real
  if (delta.isProjection || delta.attainment_pct != null) {
    return COMPARISON_CLASS.PLAN_VS_REAL
  }

  // Sequential delta: classify by grain to give momentum label
  if (grain === 'daily') {
    return COMPARISON_CLASS.MOMENTUM_SAME_WEEKDAY  // D-1 or same-weekday — both are momentum for daily
  }
  if (grain === 'weekly') {
    return COMPARISON_CLASS.MOMENTUM_WOW            // Previous week = WoW
  }
  if (grain === 'monthly') {
    return COMPARISON_CLASS.MOMENTUM_MOM            // Previous month = MoM
  }

  return COMPARISON_CLASS.SEQUENTIAL
}

/**
 * Retorna el nivel de énfasis para un delta.
 */
export function getMomentumEmphasis(delta = {}, grain = 'monthly') {
  const cls = classifyComparison(delta, grain)
  return EMPHASIS_MAP[cls] || EMPHASIS_LEVEL.SUBTLE
}

/**
 * Retorna estilo visual (fontWeight, opacity, saturation, sizeScale).
 */
export function getMomentumStyle(delta = {}, grain = 'monthly') {
  const emphasis = getMomentumEmphasis(delta, grain)
  return EMPHASIS_STYLE[emphasis] || EMPHASIS_STYLE[EMPHASIS_LEVEL.SUBTLE]
}

/**
 * Retorna label corto para el tipo de comparación.
 */
export function getComparisonLabel(delta = {}, grain = 'monthly') {
  const cls = classifyComparison(delta, grain)
  return COMPARISON_LABEL[cls] || 'Δ'
}

/**
 * Determina si un delta es un momentum comparison (Nivel 1).
 */
export function isMomentumComparison(delta = {}, grain = 'monthly') {
  return getMomentumEmphasis(delta, grain) === EMPHASIS_LEVEL.MAXIMUM
}

export { COMPARISON_LABEL }

/* ── MOMENTUM COLOR SEVERITY SCALE ── */

/**
 * Negative severity levels (downward momentum).
 * Higher number = more severe.
 */
const NEGATIVE_SEVERITY = [
  { maxPct: 5,   color: '#fca5a5', label: 'tenue' },
  { maxPct: 15,  color: '#f87171', label: 'suave' },
  { maxPct: 30,  color: '#ef4444', label: 'medio' },
  { maxPct: 50,  color: '#dc2626', label: 'fuerte' },
  { maxPct: Infinity, color: '#991b1b', label: 'crítico' },
]

/**
 * Positive severity levels (upward momentum).
 */
const POSITIVE_SEVERITY = [
  { maxPct: 5,   color: '#6ee7b7', label: 'tenue' },
  { maxPct: 15,  color: '#34d399', label: 'suave' },
  { maxPct: 30,  color: '#10b981', label: 'medio' },
  { maxPct: 50,  color: '#059669', label: 'fuerte' },
  { maxPct: Infinity, color: '#047857', label: 'fuerte' },
]

/**
 * Returns the severity color for a momentum percentage change.
 * The color communicates severity automatically — no manual color selection needed.
 *
 * @param {number} pct - Percentage change (e.g., -21.6, +12, 0)
 * @returns {{ color: string, label: string, level: number }} severity info
 */
export function getMomentumSeverityColor(pct) {
  if (pct == null || !Number.isFinite(pct)) return { color: '#9ca3af', label: 'neutral', level: 0 }

  const absPct = Math.abs(pct)

  if (pct < 0) {
    for (let i = 0; i < NEGATIVE_SEVERITY.length; i++) {
      if (absPct <= NEGATIVE_SEVERITY[i].maxPct) {
        return { color: NEGATIVE_SEVERITY[i].color, label: NEGATIVE_SEVERITY[i].label, level: -(i + 1) }
      }
    }
  }

  if (pct > 0) {
    for (let i = 0; i < POSITIVE_SEVERITY.length; i++) {
      if (absPct <= POSITIVE_SEVERITY[i].maxPct) {
        return { color: POSITIVE_SEVERITY[i].color, label: POSITIVE_SEVERITY[i].label, level: i + 1 }
      }
    }
  }

  return { color: '#9ca3af', label: 'neutral', level: 0 }
}

/**
 * Returns a Tailwind-like background color class for momentum severity.
 * Used for cell background tinting based on momentum direction+severity.
 *
 * @param {number} pct - Percentage change
 * @returns {string} Tailwind-like class for bg opacity
 */
export function getMomentumSeverityBg(pct) {
  if (pct == null || !Number.isFinite(pct) || pct === 0) return ''
  const absPct = Math.abs(pct)
  if (pct < 0) {
    if (absPct > 30) return 'bg-red-50/50'
    if (absPct > 15) return 'bg-red-50/40'
    if (absPct > 5)  return 'bg-red-50/30'
    return 'bg-red-50/20'
  }
  if (pct > 0) {
    if (absPct > 30) return 'bg-emerald-50/50'
    if (absPct > 15) return 'bg-emerald-50/40'
    if (absPct > 5)  return 'bg-emerald-50/30'
    return 'bg-emerald-50/20'
  }
  return ''
}

export default {
  COMPARISON_CLASS,
  EMPHASIS_LEVEL,
  classifyComparison,
  getMomentumEmphasis,
  getMomentumStyle,
  getComparisonLabel,
  isMomentumComparison,
}
