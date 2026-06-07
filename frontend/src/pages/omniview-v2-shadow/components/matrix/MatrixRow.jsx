import { memo } from 'react';
import MatrixCell from './MatrixCell';

function getCellByColumnId(cells, columnId) {
  return cells.find((c) => c.column_id === columnId) || null;
}

const MatrixRow = memo(function MatrixRow({
  row,
  columns,
  cells,
  grain,
  isSelected,
  selectedColumnId,
  onCellClick,
  density,
}) {
  const rowLabelClass = [
    'ov2-row-label',
    isSelected ? 'ov2-row-label--selected' : `ov2-row-label--${row.row_status.toLowerCase()}`,
  ].join(' ');

  return (
    <div style={{ display: 'flex', position: 'relative' }}>
      <div
        className={rowLabelClass}
        style={{
          paddingLeft: 8 + row.depth * 16,
        }}
      >
        {row.label}
      </div>
      {columns.map((col) => {
        const cell = getCellByColumnId(cells, col.id);
        const isSelectedCell = isSelected && col.id === selectedColumnId;
        return (
          <MatrixCell
            key={`${row.id}_${col.id}`}
            cell={cell}
            rowId={row.id}
            columnId={col.id}
            grain={grain}
            columnPeriodStatus={col.period_status}
            isSelected={isSelectedCell}
            onClick={onCellClick}
            density={density}
          />
        );
      })}
    </div>
  );
});

export default MatrixRow;
