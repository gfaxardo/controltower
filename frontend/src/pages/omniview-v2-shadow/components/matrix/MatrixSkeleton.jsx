function MatrixSkeleton({ rows = 10, columns = 7 }) {
  return (
    <div className="ov2-matrix-shell">
      <div style={{ display: 'flex', marginBottom: 4 }}>
        <div className="ov2-skeleton" style={{ width: 160, height: 'var(--ov2-header-height)', marginRight: 4 }} />
        {Array.from({ length: columns }).map((_, i) => (
          <div key={i} className="ov2-skeleton" style={{ width: 90, height: 'var(--ov2-header-height)', marginRight: 1 }} />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, rowIdx) => (
        <div key={rowIdx} style={{ display: 'flex', marginBottom: 1 }}>
          <div className="ov2-skeleton" style={{ width: 160, height: 'var(--ov2-row-height)', marginRight: 4 }} />
          {Array.from({ length: columns }).map((_, colIdx) => (
            <div key={colIdx} className="ov2-skeleton" style={{ width: 90, height: 'var(--ov2-row-height)', marginRight: 1 }} />
          ))}
        </div>
      ))}
    </div>
  );
}

export default MatrixSkeleton;
