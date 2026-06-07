function SourceBadge({ canonicalReady, className = '' }) {
  const status = canonicalReady ? 'canonical' : 'shadow';
  const label = canonicalReady ? 'CANONICAL' : 'SHADOW';
  return (
    <span className={`ov2-source-badge ov2-source-badge--${status} ${className}`}>
      {label}
    </span>
  );
}

export default SourceBadge;
