function CellBadge({ type, className = '' }) {
  if (!type) return null;

  const config = {
    PARTIAL: { label: 'PARTIAL', cls: 'ov2-badge--warning' },
    ESTIMATED: { label: 'EST', cls: 'ov2-badge--estimated' },
    SHADOW: { label: 'SHADOW', cls: 'ov2-badge--shadow' },
    FALLBACK: { label: 'FB', cls: 'ov2-badge--warning' },
    STALE: { label: 'STALE', cls: 'ov2-badge--blocked' },
    MISSING: { label: 'N/A', cls: 'ov2-badge--blocked' },
    HEALTHY: { label: 'OK', cls: 'ov2-badge--ok' },
    NOT_AVAILABLE: { label: 'N/A', cls: 'ov2-badge--blocked' },
    CT_BRIDGE: { label: 'CT', cls: 'ov2-badge--ok' },
    YANGO_API: { label: 'YAN', cls: 'ov2-badge--shadow' },
  };

  const { label, cls } = config[type] || { label: type, cls: 'ov2-badge--shadow' };

  return (
    <span
      className={`ov2-badge ${cls} ${className}`}
      style={{
        position: 'absolute',
        top: 2,
        right: 2,
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
