import { memo, useCallback, useMemo } from 'react';
import CellBadge from './CellBadge';
import CellDelta from './CellDelta';
import { formatValue } from '../base/MetricValue';

function _badgeForSource(sourceSystem, canonicalReady) {
  if (!canonicalReady) return 'SHADOW';
  if (sourceSystem === 'CT_TRIPS_2026') return 'CT_BRIDGE';
  if (sourceSystem === 'YANGO_API_RAW') return 'YANGO_API';
  return null;
}

function _badgeForFallback(fallbackUsed, canonicalReady) {
  if (fallbackUsed) return 'FALLBACK';
  return null;
}

function _signalColor(value, cellStatus, canonicalReady) {
  if (cellStatus === 'BLOCKED' || value == null) return 'ov2-cell--blocked';
  if (cellStatus === 'WARNING' || !canonicalReady) return 'ov2-cell--warning';
  if (cellStatus === 'NOT_COMPARABLE') return 'ov2-cell--not-comparable';
  return 'ov2-cell--ok';
}

function _deltaDirection(deltaValue, deltaPct) {
  const v = deltaValue != null ? deltaValue : deltaPct;
  if (v == null) return null;
  if (v > 0) return 'ov2-cell--delta-up';
  if (v < 0) return 'ov2-cell--delta-down';
  return 'ov2-cell--delta-flat';
}

const MatrixCell = memo(function MatrixCell({
  cell,
  rowId,
  columnId,
  grain = 'day',
  columnPeriodStatus,
  isSelected,
  onClick,
  density,
}) {
  const handleClick = useCallback(() => {
    if (cell && onClick) {
      onClick(cell);
    }
  }, [cell, onClick]);

  if (!cell) {
    return (
      <div className="ov2-cell ov2-cell--muted" style={{ minWidth: `var(--ov2-col-width-${grain})` }}>
        —
      </div>
    );
  }

  const cellStatus = cell.cell_status || 'OK';
  const isFuture = columnPeriodStatus === 'FUTURE';
  const canonicalReady = cell.canonical_ready ?? true;
  const fallbackUsed = cell.fallback_used || false;
  const valueNull = cell.value == null;

  let cellClass = 'ov2-cell';

  if (isFuture) {
    cellClass += ' ov2-cell--future';
  } else if (valueNull) {
    cellClass += ' ov2-cell--blocked';
  } else {
    cellClass += ' ' + _signalColor(cell.value, cellStatus, canonicalReady);
    const deltaDir = _deltaDirection(cell.delta_value, cell.delta_pct);
    if (deltaDir) cellClass += ' ' + deltaDir;
  }

  if (isSelected) cellClass += ' ov2-cell--selected';

  const sourceBadge = _badgeForSource(cell.source_system, canonicalReady);
  const fallbackBadge = _badgeForFallback(fallbackUsed, canonicalReady);
  const showEstimated = cell.is_estimated;
  const showDelta = cell.comparison_status != null || cell.delta_value != null || cell.delta_pct != null;
  const showPeriodBadge = columnPeriodStatus === 'PARTIAL';
  const showMissing = valueNull || cell.formatted_value === 'N/A';

  return (
    <div
      className={cellClass}
      style={{ minWidth: `var(--ov2-col-width-${grain})`, position: 'relative' }}
      onClick={handleClick}
      title={`${cell.metric_id || ''} — ${cell.label || ''} | ${columnPeriodStatus || ''} | ${canonicalReady ? 'CANONICAL' : 'SHADOW'}`}
    >
      {sourceBadge && !isFuture && <CellBadge type={sourceBadge} />}
      {fallbackBadge && !isFuture && <CellBadge type={fallbackBadge} />}

      <span style={{ fontWeight: 600 }}>
        {showMissing ? <span style={{ color: 'var(--ov2-text-muted)' }}>N/A</span> : (cell.formatted_value || formatValue(cell.value, cell.unit))}
      </span>

      {showEstimated && <CellBadge type="ESTIMATED" />}
      {showPeriodBadge && <CellBadge type="PARTIAL" />}

      {showDelta && !isFuture && !valueNull && (
        <CellDelta status={cell.comparison_status} value={cell.delta_value} pct={cell.delta_pct} />
      )}

      {showDelta && !isFuture && valueNull && (
        <span style={{ position: 'absolute', bottom: 1, left: 4, fontSize: 9, color: 'var(--ov2-text-muted)' }}>NO COMP</span>
      )}
    </div>
  );
});

export default MatrixCell;
