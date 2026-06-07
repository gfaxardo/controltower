function CellBadge({ type, className = '' }) {
  if (!type) return null;

  const labelMap = {
    PARTIAL: 'PARTIAL',
    ESTIMATED: 'EST',
    SHADOW: 'SHADOW',
    DELTA: '\u0394',
    FUTURE: 'FUTURE',
  };

  const label = labelMap[type] || type;
  const badgeClass = type === 'PARTIAL' ? 'ov2-badge--warning' :
    type === 'ESTIMATED' ? 'ov2-badge--estimated' :
    type === 'SHADOW' ? 'ov2-badge--shadow' :
    type === 'DELTA' ? 'ov2-badge--blocked' :
    'ov2-badge--shadow';

  return (
    <span
      className={`ov2-badge ${badgeClass} ${className}`}
      style={{
        position: 'absolute',
        top: 2,
        right: type === 'DELTA' ? undefined : 2,
        left: type === 'DELTA' ? 2 : undefined,
        fontSize: '8px',
        padding: '0 3px',
        height: '14px',
        lineHeight: '14px',
        fontWeight: 600,
        letterSpacing: '0.05em',
      }}
    >
      {label}
    </span>
  );
}

export default CellBadge;
