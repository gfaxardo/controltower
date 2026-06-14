/**
 * Omniview V2 — Sort Engine
 * OV2-UI-P1D: Client-side row sorting for matrix.
 *
 * Sorts matrix rows by label, selected metric volume, or delta impact.
 * No refetch. No backend. Deterministic with alpha tie-breaker.
 */
import { getCellToneClass } from './omniviewV2ColorSemantics';
import { getMetricById } from './omniviewV2Metrics';

const SORT_MODES = [
  { id: 'default', label: 'Original' },
  { id: 'alpha_asc', label: 'A -> Z' },
  { id: 'alpha_desc', label: 'Z -> A' },
  { id: 'volume_desc', label: 'Volume' },
  { id: 'impact_desc', label: 'Impact' },
  { id: 'critical_desc', label: 'Critical' },
];

function _getRowMetricTotal(cells, metricId) {
  let total = 0;
  let count = 0;
  for (const c of cells) {
    if (c.metric_id === metricId && c.value != null && !isNaN(c.value)) {
      total += c.value;
      count++;
    }
  }
  return count > 0 ? total : null;
}

function _getRowMaxAbsDelta(cells, metricId) {
  let maxAbs = 0;
  let count = 0;
  for (const c of cells) {
    if (c.metric_id !== metricId || c.delta_value == null || isNaN(c.delta_value)) continue;
    const abs = Math.abs(c.delta_value);
    if (abs > maxAbs) maxAbs = abs;
    count++;
  }
  return count > 0 ? maxAbs : null;
}

function _getRowCriticalCount(cells, metricId) {
  let critical = 0;
  for (const c of cells) {
    if (c.metric_id !== metricId) continue;
    const tone = getCellToneClass(c, metricId, false);
    if (tone === 'negative') critical++;
  }
  return critical;
}

export function sortMatrixRows(rows, cells, sortMode, metricId) {
  if (sortMode === 'default' || !sortMode) return rows;

  // Pre-index cells by row_id
  const cellsByRow = {};
  for (const c of cells) {
    if (!cellsByRow[c.row_id]) cellsByRow[c.row_id] = [];
    cellsByRow[c.row_id].push(c);
  }

  // Pre-compute values per row
  const cache = {};
  for (const r of rows) {
    const rowCells = cellsByRow[r.id] || [];
    cache[r.id] = {
      label: (r.label || '').toLowerCase(),
      volume: _getRowMetricTotal(rowCells, metricId),
      impact: _getRowMaxAbsDelta(rowCells, metricId),
      critical: _getRowCriticalCount(rowCells, metricId),
    };
  }

  const sorted = [...rows];

  switch (sortMode) {
    case 'alpha_asc':
      sorted.sort((a, b) => cache[a.id].label.localeCompare(cache[b.id].label));
      break;
    case 'alpha_desc':
      sorted.sort((a, b) => cache[b.id].label.localeCompare(cache[a.id].label));
      break;
    case 'volume_desc': {
      sorted.sort((a, b) => {
        const va = cache[a.id].volume;
        const vb = cache[b.id].volume;
        if (va == null && vb == null) return cache[a.id].label.localeCompare(cache[b.id].label);
        if (va == null) return 1;
        if (vb == null) return -1;
        if (vb !== va) return vb - va;
        return cache[a.id].label.localeCompare(cache[b.id].label);
      });
      break;
    }
    case 'impact_desc': {
      sorted.sort((a, b) => {
        const ia = cache[a.id].impact;
        const ib = cache[b.id].impact;
        if (ia == null && ib == null) return cache[a.id].label.localeCompare(cache[b.id].label);
        if (ia == null) return 1;
        if (ib == null) return -1;
        if (ib !== ia) return ib - ia;
        return cache[a.id].label.localeCompare(cache[b.id].label);
      });
      break;
    }
    case 'critical_desc': {
      sorted.sort((a, b) => {
        const ca = cache[a.id].critical;
        const cb = cache[b.id].critical;
        if (ca === cb) return cache[a.id].label.localeCompare(cache[b.id].label);
        return cb - ca;
      });
      break;
    }
    default:
      break;
  }

  return sorted;
}

export { SORT_MODES };
export default sortMatrixRows;
