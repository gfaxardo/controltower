/**
 * Omniview V2 — Color Semantics Engine
 * OV2-UI-P1B: Deterministic visual tone classification.
 *
 * Maps metric direction (higherIsBetter / lowerIsBetter / neutral)
 * to semantic tone outputs for cell rendering, deltas, and status.
 *
 * Import tokens for color references; components use CSS class names.
 */
import tokens from './design/omniviewV2Tokens';
import { getMetricById } from './omniviewV2Metrics';

const { ok, warning, blocked, notComparable, mutedBg } = tokens.colors;

/**
 * Returns the semantic tone for a metric delta or value comparison.
 * @param {object} metric - metric config from omniviewV2Metrics (must have higherIsBetter)
 * @param {number|null} deltaValue - absolute delta value
 * @param {number|null} deltaPct - percentage delta
 * @returns {'positive'|'negative'|'neutral'|'not_comparable'|'disabled'}
 */
export function getDeltaTone(metric, deltaValue, deltaPct) {
  if (!metric || !metric.available) return 'disabled';
  if (deltaValue == null && deltaPct == null) return 'not_comparable';

  const raw = deltaValue != null ? deltaValue : deltaPct;
  if (raw == null || isNaN(raw)) return 'not_comparable';
  if (Math.abs(raw) < 0.001) return 'neutral';

  const higherIsBetter = metric.higherIsBetter !== false; // default true
  const isPositive = raw > 0;

  if (isPositive) {
    return higherIsBetter ? 'positive' : 'negative';
  } else {
    return higherIsBetter ? 'negative' : 'positive';
  }
}

/**
 * Returns the CSS class suffix for a cell based on its value and metric.
 * @param {object} cell - matrix cell object with cell_status, value, delta_value, delta_pct
 * @param {string} metricId - current metric_id
 * @param {boolean} isFuture - whether the period is in the future
 * @returns {string} CSS class name segment (e.g., 'positive', 'negative', 'neutral', 'blocked', 'future')
 */
export function getCellToneClass(cell, metricId, isFuture) {
  if (!cell) return 'muted';
  if (isFuture) return 'future';
  if (cell.value == null) return 'blocked';

  const cellStatus = cell.cell_status || 'OK';
  if (cellStatus === 'BLOCKED') return 'blocked';
  if (cellStatus === 'NOT_COMPARABLE') return 'not-comparable';

  const metric = getMetricById(metricId);
  const tone = getDeltaTone(metric, cell.delta_value, cell.delta_pct);

  if (cellStatus === 'WARNING') return 'warning';
  if (!metric.available) return 'disabled';

  return tone; // 'positive' | 'negative' | 'neutral'
}

/**
 * Returns a semantic label for the current tone.
 * @param {string} tone - from getDeltaTone or getCellToneClass
 * @returns {string} human-readable label
 */
export function getToneLabel(tone) {
  const labels = {
    positive: 'Favorable',
    negative: 'Desfavorable',
    neutral: 'Neutral',
    'not_comparable': 'No comparable',
    disabled: 'No disponible',
    blocked: 'Bloqueado',
    warning: 'Advertencia',
    future: 'Futuro',
    muted: 'Sin datos',
  };
  return labels[tone] || tone;
}

/**
 * Minimal legend array for rendering in header/footer.
 */
export const TONE_LEGEND = [
  { tone: 'positive', label: 'Favorable', color: '#16a34a' },
  { tone: 'negative', label: 'Desfavorable', color: '#dc2626' },
  { tone: 'neutral', label: 'Neutral', color: '#9ca3af' },
  { tone: 'not_comparable', label: 'N/A', color: '#9ca3af' },
];

export default { getDeltaTone, getCellToneClass, getToneLabel, TONE_LEGEND };
