/**
 * Omniview V2 — Plan vs Real Display Engine
 * OV2-UI-P1F: Deterministic display logic for plan vs real cells.
 *
 * No forecast. No diagnostic. No recommendations.
 * Only displays certified plan vs real comparison.
 */
import { getMetricById } from './omniviewV2Metrics';
import { getDeltaTone } from './omniviewV2ColorSemantics';

/**
 * @param {object} cell - Matrix cell from plan_real endpoint
 * @param {string} metricId
 * @returns {object} display state
 */
export function getPlanRealDisplay(cell, metricId) {
  const metric = getMetricById(metricId);
  const planValue = cell?.value;
  const deltaValue = cell?.delta_value;
  const deltaPct = cell?.delta_pct;
  const comparisonStatus = cell?.comparison_status;

  // Real = plan + delta (positive delta = real > plan)
  const realValue = (planValue != null && deltaValue != null)
    ? planValue + deltaValue
    : null;

  // Attainment % = real / plan * 100
  const attainmentPct = (realValue != null && planValue != null && planValue !== 0)
    ? Math.round((realValue / planValue) * 100)
    : null;

  const tone = getDeltaTone(metric, deltaValue, deltaPct);

  let status = 'comparable';
  if (planValue == null && realValue == null) status = 'missing';
  else if (planValue == null) status = 'no_plan';
  else if (realValue == null) status = 'no_real';
  else if (comparisonStatus === 'NOT_COMPARABLE') status = 'not_comparable';
  else if (deltaValue != null) status = 'comparable';

  const format = metric.format || ((v) => String(v));

  return {
    planValue,
    realValue,
    deltaValue,
    deltaPct,
    attainmentPct,
    comparisonStatus,
    status,
    tone,
    planFormatted: planValue != null ? format(planValue) : 'N/A',
    realFormatted: realValue != null ? format(realValue) : 'N/A',
    attainmentFormatted: attainmentPct != null ? `${attainmentPct}%` : 'N/A',
    isFuture: cell?.period_status === 'FUTURE',
    isMissing: status === 'missing' || status === 'no_plan' || status === 'no_real',
  };
}

/**
 * CSV row fields for Plan vs Real export
 */
export function getPlanRealExportFields({ planValue, realValue, deltaValue, deltaPct, attainmentPct, comparisonStatus, status }) {
  return {
    plan_value: planValue != null ? String(planValue) : 'N/A',
    real_value: realValue != null ? String(realValue) : 'N/A',
    delta_value: deltaValue != null ? String(deltaValue) : '',
    delta_pct: deltaPct != null ? String(deltaPct) : '',
    attainment_pct: attainmentPct != null ? String(attainmentPct) : '',
    comparison_status: comparisonStatus || status,
  };
}
