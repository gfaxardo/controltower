/**
 * Omniview V2 — Trend Series Engine
 * OV2-VC2: Derives trend series from certified matrix data.
 */
import { getMetricById } from './omniviewV2Metrics';
import { getDeltaTone } from './omniviewV2ColorSemantics';

const COMPARABLE_LABELS = { day: 'DoD', week: 'WoW', month: 'MoM' };
const CLOSED_PERIOD_COUNTS = { peak: 4, rolling: 4, rolling_month: 3 };

export function getComparableLabel(grain) { return COMPARABLE_LABELS[grain] || 'DoD'; }

function findComparable(period, periods, grain) {
  if (!period || !periods) return null;
  const d = new Date(period);
  if (isNaN(d.getTime())) return null;
  if (grain === 'day') { d.setDate(d.getDate() - 7); }
  else if (grain === 'week') { d.setDate(d.getDate() - 7); }
  else { d.setMonth(d.getMonth() - 1); }
  const target = d.toISOString().slice(0, 10);
  return periods.find(p => p === target || p.startsWith(target)) || null;
}

export function buildTrendSeries(matrixData, metricId, grain, operatingDate) {
  if (!matrixData?.cells || !matrixData?.columns) return null;
  const metric = getMetricById(metricId);
  const cols = [...(matrixData.columns || [])].sort((a, b) => (a.sort_key || a.period || '').localeCompare(b.sort_key || b.period || ''));
  const periods = cols.map(c => c.period || '');
  const rows = matrixData.rows || [];
  const cells = matrixData.cells || [];

  // Aggregate per period across all slices
  const periodValues = {};
  for (const c of cells) {
    if (c.metric_id !== metricId || c.value == null) continue;
    const p = c.period;
    if (!p) continue;
    periodValues[p] = (periodValues[p] || 0) + c.value;
  }

  // Build points
  const points = [];
  for (const col of cols) {
    const period = col.period || '';
    const value = periodValues[period];
    const isClosed = col.period_status === 'CLOSED';
    const isPartial = col.period_status === 'PARTIAL';
    const isFuture = col.period_status === 'FUTURE';
    const comparable = findComparable(period, periods, grain);
    const comparableValue = comparable ? periodValues[comparable] : null;
    const deltaAbs = value != null && comparableValue != null ? value - comparableValue : null;
    const deltaPct = value != null && comparableValue != null && comparableValue !== 0 ? Math.round((deltaAbs / comparableValue) * 1000) / 10 : null;
    const tone = getDeltaTone(metric, deltaAbs, deltaPct);

    points.push({
      period, label: col.label || period, value,
      isClosed, isPartial, isFuture,
      comparableValue, deltaAbs, deltaPct, tone,
      notComparable: comparable === null && !isFuture,
    });
  }

  // Peak last 4 closed
  const closedPoints = points.filter(p => p.isClosed && p.value != null);
  const peakPoints = closedPoints.slice(-CLOSED_PERIOD_COUNTS.peak);
  const peakLast4 = peakPoints.length > 0
    ? { value: Math.max(...peakPoints.map(p => p.value)), count: peakPoints.length, label: 'Peak last ' + peakPoints.length, limitedHistory: peakPoints.length < CLOSED_PERIOD_COUNTS.peak }
    : { value: null, count: 0, label: 'Peak last 4', limitedHistory: true };

  // Rolling average
  const rollCount = grain === 'month' ? CLOSED_PERIOD_COUNTS.rolling_month : CLOSED_PERIOD_COUNTS.rolling;
  const rollPoints = closedPoints.slice(-rollCount);
  const rollingAvg = rollPoints.length > 0
    ? { value: Math.round(rollPoints.reduce((s, p) => s + p.value, 0) / rollPoints.length), count: rollPoints.length, label: 'Avg last ' + rollPoints.length, limitedHistory: rollPoints.length < rollCount }
    : { value: null, count: 0, label: 'Avg last ' + rollCount, limitedHistory: true };

  return {
    grain, metricId,
    comparableLabel: getComparableLabel(grain),
    points,
    peakLast4,
    rollingAverage: rollingAvg,
    currentValue: points.length > 0 ? points[points.length - 1].value : null,
    currentComparable: points.length > 0 ? points[points.length - 1].comparableValue : null,
    currentDeltaAbs: points.length > 0 ? points[points.length - 1].deltaAbs : null,
    currentDeltaPct: points.length > 0 ? points[points.length - 1].deltaPct : null,
  };
}
