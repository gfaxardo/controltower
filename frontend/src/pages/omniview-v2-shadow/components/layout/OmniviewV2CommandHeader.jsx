import SourceBadge from '../base/SourceBadge';
import CoverageBadge from '../base/CoverageBadge';
import FreshnessBadge from '../base/FreshnessBadge';

function OmniviewV2CommandHeader({
  sourceSystem = 'CT_TRIPS_2026',
  canonicalReady = true,
  grain = 'day',
  dateFrom = '',
  dateTo = '',
  coveragePct = 100,
  freshness = '',
  onSourceChange,
  onGrainChange,
  onDateFromChange,
  onDateToChange,
}) {
  const sources = [
    { value: 'CT_TRIPS_2026', label: 'CT Trips 2026' },
    { value: 'YANGO_API_RAW', label: 'Yango API (Shadow)' },
  ];

  const grains = [
    { value: 'day', label: 'Daily' },
    { value: 'week', label: 'Weekly' },
    { value: 'month', label: 'Monthly' },
  ];

  return (
    <div className="ov2-command-header">
      <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--ov2-text-primary)', marginRight: 8 }}>
        OV2 Shadow
      </span>

      <SourceBadge canonicalReady={canonicalReady} />

      <select
        value={sourceSystem}
        onChange={(e) => onSourceChange?.(e.target.value)}
        style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--ov2-border-color)', fontSize: 12, background: '#fff' }}
      >
        {sources.map((s) => (
          <option key={s.value} value={s.value}>{s.label}</option>
        ))}
      </select>

      <select
        value={grain}
        onChange={(e) => onGrainChange?.(e.target.value)}
        style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--ov2-border-color)', fontSize: 12, background: '#fff' }}
      >
        {grains.map((g) => (
          <option key={g.value} value={g.value}>{g.label}</option>
        ))}
      </select>

      <input
        type="date"
        value={dateFrom}
        onChange={(e) => onDateFromChange?.(e.target.value)}
        style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--ov2-border-color)', fontSize: 12, background: '#fff' }}
      />
      <span style={{ fontSize: 12, color: 'var(--ov2-text-secondary)' }}>to</span>
      <input
        type="date"
        value={dateTo}
        onChange={(e) => onDateToChange?.(e.target.value)}
        style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--ov2-border-color)', fontSize: 12, background: '#fff' }}
      />

      <span style={{ flex: 1 }} />

      <CoverageBadge pct={coveragePct} />
      <FreshnessBadge lastRefreshedAt={freshness} />
    </div>
  );
}

export default OmniviewV2CommandHeader;
