function CellDelta({ status, value, pct, className = '' }) {
  if (status === 'NOT_COMPARABLE' || (!value && !pct)) return null;

  const isUp = (value != null && value > 0) || (pct != null && pct > 0);
  const isDown = (value != null && value < 0) || (pct != null && pct < 0);
  const isFlat = !isUp && !isDown;

  let arrow = '\u2192';
  let colorClass = 'ov2-delta--flat';
  if (isUp) { arrow = '\u25B2'; colorClass = 'ov2-delta--up'; }
  else if (isDown) { arrow = '\u25BC'; colorClass = 'ov2-delta--down'; }

  const sign = value > 0 ? '+' : '';
  const displayPct = pct != null ? `${sign}${pct.toFixed(1)}%` : '';

  return (
    <span
      className={`ov2-delta ${colorClass} ${className}`}
      style={{
        position: 'absolute',
        bottom: 1,
        left: 4,
        fontSize: 9,
        fontWeight: 600,
        display: 'flex',
        alignItems: 'center',
        gap: 1,
      }}
    >
      <span style={{ fontSize: 7 }}>{arrow}</span>
      <span>{displayPct}</span>
    </span>
  );
}

export default CellDelta;
