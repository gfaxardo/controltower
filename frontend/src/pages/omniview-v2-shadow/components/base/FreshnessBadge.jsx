function FreshnessBadge({ lastRefreshedAt, stale, className = '' }) {
  if (!lastRefreshedAt && !stale) return null;

  let status = 'ok';
  let label = '';

  if (stale) {
    status = 'warning';
    label = stale;
  } else if (lastRefreshedAt) {
    status = 'ok';
    label = `Updated ${lastRefreshedAt}`;
  }

  return (
    <span className={`ov2-badge ov2-badge--${status} ${className}`} title={lastRefreshedAt || stale}>
      {label}
    </span>
  );
}

export default FreshnessBadge;
