function OmniviewV2GlobalEmptyState({
  sourceSystem,
  grain,
  dateFrom,
  dateTo,
  latestAvailableDate,
  isToday,
  onGoToLatestDate,
  onViewSourceHealth,
  onChangeDateRange,
}) {
  return (
    <div style={{
      margin: '16px',
      padding: '24px',
      background: '#fefce8',
      border: '1px solid #fde047',
      borderRadius: 8,
      display: 'flex',
      flexDirection: 'column',
      gap: 12,
    }}>
      {/* Icon + Title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 40, height: 40, borderRadius: 20,
          background: '#fef3c7', display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 20, color: '#d97706', fontWeight: 700,
        }}>
          i
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15, color: '#92400e' }}>
            No data available for the selected period
          </div>
          <div style={{ fontSize: 12, color: '#a16207', marginTop: 2 }}>
            {sourceSystem} · {grain} · {dateFrom} – {dateTo}
          </div>
        </div>
      </div>

      {/* Context info */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
        gap: 8, padding: '12px 0', borderTop: '1px solid #fde047', borderBottom: '1px solid #fde047',
        fontSize: 12,
      }}>
        <InfoItem label="Source" value={sourceSystem} />
        <InfoItem label="Grain" value={grain} />
        <InfoItem label="Period" value={`${dateFrom || '?'} – ${dateTo || '?'}`} />
        <InfoItem label="Latest data" value={latestAvailableDate || 'Unknown'} highlight />
      </div>

      {/* Operational explanation */}
      {isToday && (
        <div style={{ fontSize: 12, color: '#92400e', opacity: 0.75, lineHeight: 1.5 }}>
          Today's data is still being processed by the ingestion pipeline. Data typically becomes available with a 1-day lag. The source is healthy — there is simply no data for this date yet.
        </div>
      )}

      {/* CTAs */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {latestAvailableDate && (
          <button
            onClick={onGoToLatestDate}
            style={{
              padding: '8px 16px',
              background: '#d97706',
              color: '#fff',
              border: 'none',
              borderRadius: 6,
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 600,
              transition: 'background 100ms',
            }}
            onMouseEnter={(e) => e.target.style.background = '#b45309'}
            onMouseLeave={(e) => e.target.style.background = '#d97706'}
          >
            Go to latest data ({latestAvailableDate})
          </button>
        )}
        <button
          onClick={onViewSourceHealth}
          style={{
            padding: '8px 16px',
            background: '#fff',
            color: '#92400e',
            border: '1px solid #fcd34d',
            borderRadius: 6,
            cursor: 'pointer',
            fontSize: 13,
            fontWeight: 500,
          }}
        >
          View source health
        </button>
        <button
          onClick={onChangeDateRange}
          style={{
            padding: '8px 16px',
            background: '#fff',
            color: '#78716c',
            border: '1px solid #e7e5e4',
            borderRadius: 6,
            cursor: 'pointer',
            fontSize: 13,
          }}
        >
          Change date range
        </button>
      </div>
    </div>
  );
}

function InfoItem({ label, value, highlight }) {
  return (
    <div>
      <div style={{ color: '#a8a29e', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>
        {label}
      </div>
      <div style={{
        fontWeight: highlight ? 700 : 500,
        color: highlight ? '#92400e' : '#44403c',
      }}>
        {value}
      </div>
    </div>
  );
}

export default OmniviewV2GlobalEmptyState;
