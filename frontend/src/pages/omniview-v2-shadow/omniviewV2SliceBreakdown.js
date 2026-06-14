/**
 * Omniview V2 — Slice Breakdown Engine
 * OV2-VC4: Aggregation-aware slice ranking.
 */
import { getMetricById } from './omniviewV2Metrics';
import { getCellToneClass } from './omniviewV2ColorSemantics';

const NO_SUM_METRICS = new Set(['trips_per_driver', 'avg_ticket', 'cancel_rate_pct', 'commission_pct']);

function isMetricAdditive(metricId) { return !NO_SUM_METRICS.has(metricId); }

export function buildSliceBreakdown(matrixData, metricId, grain) {
  if (!matrixData?.cells || !matrixData?.rows) return null;
  const metric = getMetricById(metricId);
  const isAdditive = isMetricAdditive(metricId);
  const cells = matrixData.cells.filter(c => c.metric_id === metricId);
  const rows = matrixData.rows || [];

  // Aggregate per slice
  const sliceMap = {};
  for (const r of rows) {
    const rowCells = cells.filter(c => c.row_id === r.id);
    const label = r.label || r.id;

    if (isAdditive) {
      let sum = 0; let count = 0;
      for (const c of rowCells) {
        if (c.value != null && !isNaN(c.value) && c.value >= 0) { sum += c.value; count++; }
      }
      if (count > 0) sliceMap[r.id] = { label, value: sum, count, isInvalid: false };
      else sliceMap[r.id] = { label, value: null, count: 0, isInvalid: false, missing: true };
    } else {
      // Non-additive: use latest period value
      const sorted = [...rowCells].sort((a, b) => (b.period || '').localeCompare(a.period || ''));
      const latest = sorted[0];
      const val = latest?.value;
      const valid = val != null && !isNaN(val) && val >= 0;
      sliceMap[r.id] = { label, value: valid ? val : null, count: sorted.length, isInvalid: !valid && val != null, missing: val == null, isRatio: true };
    }
  }

  // Compute contributions
  const validSlices = Object.values(sliceMap).filter(s => s.value != null && s.value > 0 && !s.isInvalid);
  const totalValue = validSlices.reduce((sum, s) => sum + s.value, 0);

  const breakdownRows = Object.values(sliceMap).map(s => ({
    ...s,
    contributionPct: totalValue > 0 && s.value != null && s.value > 0 ? Math.round(s.value / totalValue * 100) : 0,
  }));

  // Sort by value desc, invalid/missing last
  breakdownRows.sort((a, b) => {
    if (a.isInvalid || a.missing) return 1;
    if (b.isInvalid || b.missing) return -1;
    return (b.value || 0) - (a.value || 0);
  });

  return {
    metricId, grain, isAdditive, totalValue,
    validCount: validSlices.length,
    invalidCount: breakdownRows.filter(s => s.isInvalid).length,
    missingCount: breakdownRows.filter(s => s.missing).length,
    rows: breakdownRows,
  };
}
