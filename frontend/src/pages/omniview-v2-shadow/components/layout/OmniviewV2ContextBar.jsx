function OmniviewV2ContextBar({ sourceSystem, grain, dateFrom, dateTo, selectedSection }) {
  const parts = [
    'Omniview V2',
    sourceSystem,
    grain,
    dateFrom && dateTo ? `${dateFrom} \u2013 ${dateTo}` : '',
    selectedSection || '',
  ].filter(Boolean);

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 4,
      padding: '4px 16px',
      fontSize: 11,
      color: 'var(--ov2-text-secondary)',
      background: 'var(--ov2-bg-muted)',
      borderBottom: '1px solid var(--ov2-border-color)',
    }}>
      {parts.map((part, i) => (
        <span key={i}>
          {i > 0 && <span style={{ margin: '0 4px', color: 'var(--ov2-text-muted)' }}>\u203A</span>}
          {part}
        </span>
      ))}
    </div>
  );
}

export default OmniviewV2ContextBar;
