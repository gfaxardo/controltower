function OmniviewV2AlertStrip({ warnings = [], onAlertClick }) {
  if (!warnings || warnings.length === 0) return null;

  const sorted = [...warnings].sort((a, b) => {
    const order = { critical: 0, warning: 1, info: 2 };
    return (order[a.severity] || 2) - (order[b.severity] || 2);
  });

  const visible = sorted.slice(0, 3);
  const overflow = sorted.length - 3;

  return (
    <div className="ov2-alert-strip">
      {visible.map((w, i) => (
        <div
          key={i}
          className={`ov2-alert ov2-alert--${w.severity || 'warning'}`}
          onClick={() => onAlertClick?.(w)}
        >
          <span style={{ fontWeight: 600, fontSize: 11 }}>
            {w.severity === 'critical' ? '\u26A0' : '\u2139'}
          </span>
          <span>{w.message}</span>
        </div>
      ))}
      {overflow > 0 && (
        <div style={{ fontSize: 11, color: 'var(--ov2-text-muted)', padding: '2px 12px' }}>
          +{overflow} more warnings
        </div>
      )}
    </div>
  );
}

export default OmniviewV2AlertStrip;
