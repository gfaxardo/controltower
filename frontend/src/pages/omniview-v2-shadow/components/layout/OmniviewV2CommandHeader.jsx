import SourceBadge from '../base/SourceBadge';
import CoverageBadge from '../base/CoverageBadge';
import FreshnessBadge from '../base/FreshnessBadge';
import OMNIVIEW_V2_METRICS from '../../omniviewV2Metrics';
import { TONE_LEGEND } from '../../omniviewV2ColorSemantics';
import { SORT_MODES } from '../../omniviewV2Sort';
import { PERIOD_PRESETS } from '../../omniviewV2PeriodPresets';

function OmniviewV2CommandHeader({
  sourceSystem = 'CT_TRIPS_2026',
  canonicalReady = true,
  grain = 'day',
  metricId = 'orders',
  dateFrom = '',
  dateTo = '',
  country = 'peru',
  city = 'lima',
  businessSlice = '',
  parkId = '',
  coveragePct = 100,
  freshness = '',
  hasData = true,
  sortMode = 'default',
  activePreset = '',
  onSourceChange,
  onGrainChange,
  onMetricChange,
  onSortChange,
  onPresetSelect,
  onDateFromChange,
  onDateToChange,
  onCountryChange,
  onCityChange,
  onBusinessSliceChange,
  onParkIdChange,
  onExportCsv,
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

  const countries = [
    { value: 'peru', label: 'Peru' },
    { value: 'colombia', label: 'Colombia' },
  ];

  const cities = [
    { value: 'lima', label: 'Lima' },
    { value: 'trujillo', label: 'Trujillo' },
    { value: 'arequipa', label: 'Arequipa' },
    { value: 'bogota', label: 'Bogota' },
    { value: 'barranquilla', label: 'Barranquilla' },
  ];

  const slices = [
    { value: '', label: 'All Slices' },
    { value: 'autos regular', label: 'Auto Regular' },
    { value: 'delivery', label: 'Delivery' },
    { value: 'pro', label: 'PRO' },
    { value: 'tuktuk', label: 'TukTuk' },
    { value: 'carga', label: 'Carga' },
  ];

  const parks = [
    { value: '', label: 'All Parks' },
    { value: '08e20910d81d42658d4334d3f6d10ac0', label: 'Lima' },
    { value: '851e30755bba4d298e2e837f571b4ab8', label: 'Trujillo' },
    { value: '56e4607dfc354e0a9cde4f0aa7973003', label: 'Arequipa' },
    { value: '64085dd85e124e2c808806f70d527ea8', label: 'Pro' },
    { value: 'e3e07c00ed914f82a59c03283a178d6e', label: 'TukTuk' },
  ];

  return (
    <div className="ov2-command-header" style={{ flexWrap: 'wrap', gap: 4 }}>
      <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--ov2-text-primary)', marginRight: 8 }}>
        OV2 Shadow
      </span>

      <SourceBadge canonicalReady={canonicalReady} />

      <select value={sourceSystem} onChange={(e) => onSourceChange?.(e.target.value)}
        style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--ov2-border-color)', fontSize: 12, background: '#fff' }}>
        {sources.map((s) => (<option key={s.value} value={s.value}>{s.label}</option>))}
      </select>

      <select value={grain} onChange={(e) => onGrainChange?.(e.target.value)}
        style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--ov2-border-color)', fontSize: 12, background: '#fff' }}>
        {grains.map((g) => (<option key={g.value} value={g.value}>{g.label}</option>))}
      </select>

      {/* OV2-UI-P1A: Multi-metric selector */}
      <select value={metricId} onChange={(e) => onMetricChange?.(e.target.value)}
        style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--ov2-border-color)', fontSize: 12, background: '#fff', fontWeight: 600 }}>
        {OMNIVIEW_V2_METRICS.map((m) => (
          <option key={m.id} value={m.id} disabled={!m.available}
            title={!m.available ? m.disabledReason : m.description}>
            {m.label}{!m.available ? ' (N/A)' : ''}
          </option>
        ))}
      </select>

      {/* OV2-UI-P1D: Sort controls */}
      <select value={sortMode} onChange={(e) => onSortChange?.(e.target.value)}
        style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--ov2-border-color)', fontSize: 12, background: '#fff' }}>
        {SORT_MODES.map((s) => (
          <option key={s.id} value={s.id}>{s.label}</option>
        ))}
      </select>

      <input type="date" value={dateFrom} onChange={(e) => onDateFromChange?.(e.target.value)}
        style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--ov2-border-color)', fontSize: 12, background: '#fff' }} />
      <span style={{ fontSize: 12, color: 'var(--ov2-text-secondary)' }}>to</span>
      <input type="date" value={dateTo} onChange={(e) => onDateToChange?.(e.target.value)}
        style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--ov2-border-color)', fontSize: 12, background: '#fff' }} />

      {/* OV2-UI-P1E: Period presets */}
      <span style={{ display: 'flex', gap: 3, marginLeft: 4 }}>
        {PERIOD_PRESETS.map((p) => (
          <button
            key={p.id}
            onClick={() => onPresetSelect?.(p.id)}
            style={{
              padding: '3px 7px',
              borderRadius: 3,
              border: `1px solid ${activePreset === p.id ? 'var(--ov2-status-selected, #3b82f6)' : 'var(--ov2-border-color)'}`,
              fontSize: 11,
              background: activePreset === p.id ? '#eff6ff' : '#fff',
              color: activePreset === p.id ? 'var(--ov2-status-selected, #3b82f6)' : 'var(--ov2-text-secondary)',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              fontWeight: activePreset === p.id ? 600 : 400,
            }}
          >
            {p.label}
          </button>
        ))}
      </span>

      <span style={{ color: 'var(--ov2-border-color)', margin: '0 2px' }}>|</span>

      <select value={country} onChange={(e) => onCountryChange?.(e.target.value)}
        style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--ov2-border-color)', fontSize: 12, background: '#fff' }}>
        {countries.map((c) => (<option key={c.value} value={c.value}>{c.label}</option>))}
      </select>

      <select value={city} onChange={(e) => onCityChange?.(e.target.value)}
        style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--ov2-border-color)', fontSize: 12, background: '#fff' }}>
        {cities.map((c) => (<option key={c.value} value={c.value}>{c.label}</option>))}
      </select>

      <select value={businessSlice} onChange={(e) => onBusinessSliceChange?.(e.target.value)}
        style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--ov2-border-color)', fontSize: 12, background: '#fff' }}>
        {slices.map((s) => (<option key={s.value} value={s.value}>{s.label}</option>))}
      </select>

      <select value={parkId} onChange={(e) => onParkIdChange?.(e.target.value)}
        style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--ov2-border-color)', fontSize: 12, background: '#fff' }}>
        {parks.map((p) => (<option key={p.value} value={p.value}>{p.label}</option>))}
      </select>

      <span style={{ flex: 1 }} />

      {/* Color semantics legend (OV2-UI-P1B) */}
      <span style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: 10, color: 'var(--ov2-text-secondary)' }}>
        {TONE_LEGEND.map((t) => (
          <span key={t.tone} style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
            <span style={{ width: 10, height: 10, borderRadius: 2, background: t.color, display: 'inline-block' }} />
            {t.label}
          </span>
        ))}
      </span>

      <CoverageBadge pct={coveragePct} />
      <FreshnessBadge lastRefreshedAt={freshness} />

      {/* OV2-UI-P1C: CSV Export */}
      <button
        onClick={onExportCsv}
        disabled={!hasData}
        title={!hasData ? 'No data available to export' : 'Export current view as CSV'}
        style={{
          padding: '4px 12px',
          borderRadius: 4,
          border: '1px solid var(--ov2-border-color)',
          fontSize: 12,
          background: hasData ? 'var(--ov2-status-selected, #3b82f6)' : 'var(--ov2-bg-disabled, #e5e7eb)',
          color: hasData ? '#fff' : 'var(--ov2-text-muted)',
          cursor: hasData ? 'pointer' : 'not-allowed',
          fontWeight: 500,
        }}
      >
        Export CSV
      </button>
    </div>
  );
}

export default OmniviewV2CommandHeader;
