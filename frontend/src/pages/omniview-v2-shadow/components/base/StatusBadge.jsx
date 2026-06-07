function StatusBadge({ status, label, className = '' }) {
  const statusClass = `ov2-badge--${status}`;
  return (
    <span className={`ov2-badge ${statusClass} ${className}`}>
      {label || status}
    </span>
  );
}

export default StatusBadge;
