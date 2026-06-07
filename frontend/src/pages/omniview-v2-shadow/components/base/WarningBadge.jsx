const SEVERITY_LABELS = {
  critical: 'CRITICAL',
  warning: 'WARN',
  info: 'INFO',
};

function WarningBadge({ severity = 'warning', count, className = '' }) {
  const label = count != null ? `${SEVERITY_LABELS[severity] || severity} ${count}` : (SEVERITY_LABELS[severity] || severity);
  return (
    <span className={`ov2-badge ov2-badge--${severity === 'critical' ? 'blocked' : severity === 'warning' ? 'warning' : 'shadow'} ${className}`}>
      {label}
    </span>
  );
}

export default WarningBadge;
