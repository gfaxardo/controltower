function CoverageBadge({ pct, showLabel = true, className = '' }) {
  let status = 'ok';
  if (pct == null) status = 'blocked';
  else if (pct < 50) status = 'blocked';
  else if (pct < 95) status = 'warning';

  const statusClass = `ov2-badge--${status}`;
  const label = showLabel ? `${pct != null ? pct.toFixed(0) : '—'}%` : '';

  return (
    <span className={`ov2-badge ${statusClass} ${className}`} title={`Coverage: ${pct != null ? pct.toFixed(1) : 'N/A'}%`}>
      {label}
    </span>
  );
}

export default CoverageBadge;
