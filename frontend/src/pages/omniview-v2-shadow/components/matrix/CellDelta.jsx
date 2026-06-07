function CellDelta({ status, value, pct, className = '' }) {
  if (status === 'NOT_COMPARABLE' || (!value && !pct)) return null;

  let deltaClass = 'ov2-delta--minor';
  if (status === 'MATCH') deltaClass = 'ov2-delta--match';
  else if (status === 'MAJOR_DELTA') deltaClass = 'ov2-delta--major';

  const sign = value > 0 ? '+' : '';
  const displayPct = pct != null ? `${sign}${pct.toFixed(1)}%` : '';

  return (
    <span
      className={`ov2-delta ${deltaClass} ${className}`}
      style={{ position: 'absolute', bottom: 1, left: 4 }}
    >
      {displayPct}
    </span>
  );
}

export default CellDelta;
