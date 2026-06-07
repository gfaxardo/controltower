import { memo, useCallback } from 'react';
import CellBadge from './CellBadge';
import CellDelta from './CellDelta';
import { formatValue } from '../base/MetricValue';

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

  let cellClass = 'ov2-cell';
  if (isFuture) cellClass += ' ov2-cell--future';
  else if (cellStatus === 'WARNING') cellClass += ' ov2-cell--warning';
  else if (cellStatus === 'BLOCKED') cellClass += ' ov2-cell--blocked';
  else if (cellStatus === 'NOT_COMPARABLE') cellClass += ' ov2-cell--not-comparable';
  else cellClass += ' ov2-cell--ok';

  if (isSelected) cellClass += ' ov2-cell--selected';

  const showEstimated = cell.is_estimated;
  const showDelta = cell.comparison_status != null;
  const showPeriodBadge = columnPeriodStatus === 'PARTIAL';

  return (
    <div
      className={cellClass}
      style={{ minWidth: `var(--ov2-col-width-${grain})`, position: 'relative' }}
      onClick={handleClick}
      title={`${cell.metric_id || ''} — ${cell.label || ''} | ${columnPeriodStatus || ''}`}
    >
      <span>{cell.formatted_value || formatValue(cell.value, cell.unit)}</span>

      {showEstimated && <CellBadge type="ESTIMATED" />}
      {showPeriodBadge && <CellBadge type="PARTIAL" />}

      {showDelta && cell.comparison_status && (
        <CellDelta status={cell.comparison_status} value={cell.delta_value} pct={cell.delta_pct} />
      )}
    </div>
  );
});

export default MatrixCell;
