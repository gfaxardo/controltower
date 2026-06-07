function DeltaValue({ value, pct, status, className = '' }) {
  if (value == null && pct == null) return null;

  let statusClass = 'ov2-delta--minor';
  if (status === 'MATCH') statusClass = 'ov2-delta--match';
  else if (status === 'MAJOR_DELTA') statusClass = 'ov2-delta--major';

  const sign = value > 0 ? '+' : '';
  const valStr = value != null ? `${sign}${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '';
  const pctStr = pct != null ? ` (${sign}${pct.toFixed(2)}%)` : '';

  return (
    <span className={`ov2-delta ${statusClass} ${className}`}>
      {valStr}{pctStr}
    </span>
  );
}

export default DeltaValue;
