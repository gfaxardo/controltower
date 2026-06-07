function PeriodBadge({ status, className = '' }) {
  if (!status || status === 'CURRENT') return null;

  let badgeStatus = 'warning';
  if (status === 'FUTURE' || status === 'NO_PLAN' || status === 'NO_REAL') {
    badgeStatus = 'blocked';
  } else if (status === 'PARTIAL') {
    badgeStatus = 'warning';
  } else if (status === 'CLOSED') {
    badgeStatus = 'ok';
  }

  return (
    <span
      className={`ov2-badge ov2-badge--${badgeStatus} ${className}`}
      style={{ position: 'absolute', top: '2px', right: '2px', fontSize: '9px', padding: '0 4px', height: '16px' }}
    >
      {status}
    </span>
  );
}

export default PeriodBadge;
