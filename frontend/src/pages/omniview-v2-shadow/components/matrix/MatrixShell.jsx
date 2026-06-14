import { useState, useRef, useCallback, useEffect } from 'react';
import MatrixHeader from './MatrixHeader';
import MatrixRow from './MatrixRow';
import MatrixEmptyState from './MatrixEmptyState';
import MatrixSkeleton from './MatrixSkeleton';

function MatrixShell({
  matrixData,
  loading = false,
  metricId = 'orders',
  viewMode = 'real',
  selectedCell,
  onCellClick,
  density = 'comfortable',
}) {
  const bodyRef = useRef(null);
  const headerRef = useRef(null);
  const [scrollLeft, setScrollLeft] = useState(0);

  const handleBodyScroll = useCallback((e) => {
    setScrollLeft(e.target.scrollLeft);
  }, []);

  const isEmpty = !matrixData || !matrixData.metadata || matrixData.metadata.row_count === 0;
  const columns = matrixData?.columns || [];
  const rows = matrixData?.rows || [];
  const cells = matrixData?.cells || [];
  const grain = matrixData?.grain || 'day';

  if (loading) return <MatrixSkeleton />;
  if (isEmpty && !loading) return <MatrixEmptyState />;

  return (
    <div className="ov2-matrix-shell" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div ref={headerRef} style={{ overflow: 'hidden' }}>
        <div style={{ transform: `translateX(-${scrollLeft}px)` }}>
          <MatrixHeader columns={columns} grain={grain} />
        </div>
      </div>
      <div
        ref={bodyRef}
        onScroll={handleBodyScroll}
        style={{
          flex: 1,
          overflow: 'auto',
          position: 'relative',
        }}
      >
        <div style={{ minWidth: columns.length * 90 + 160 }}>
          {rows.map((row) => {
            const isSelected = selectedCell?.rowId === row.id;
            const rowCells = cells.filter((c) => c.row_id === row.id);
            return (
              <MatrixRow
                key={row.id}
                row={row}
                columns={columns}
                cells={rowCells}
                grain={grain}
                metricId={metricId}
                viewMode={viewMode}
                isSelected={isSelected}
                selectedColumnId={selectedCell?.columnId}
                onCellClick={onCellClick}
                density={density}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default MatrixShell;
