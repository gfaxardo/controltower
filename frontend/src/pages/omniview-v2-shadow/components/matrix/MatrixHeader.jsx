function MatrixHeader({ columns, grain = 'day' }) {
  return (
    <div className="ov2-header">
      <div
        className="ov2-header-cell ov2-header-cell--sticky"
        style={{ minWidth: 'var(--ov2-sticky-col-width)' }}
      >
        {grain === 'day' ? 'Slice / Metric' : grain === 'week' ? 'Week' : grain === 'month' ? 'Month' : 'Period'}
      </div>
      {columns.map((col) => (
        <div
          key={col.id}
          className={`ov2-header-cell ${col.is_current ? 'ov2-header-cell--current' : ''} ${col.is_future ? 'ov2-header-cell--future' : ''}`}
          style={{ minWidth: `var(--ov2-col-width-${grain})` }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <span>{col.label}</span>
            {col.period_status && col.period_status !== 'CURRENT' && (
              <span style={{ fontSize: '9px', opacity: 0.7 }}>{col.period_status}</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

export default MatrixHeader;
