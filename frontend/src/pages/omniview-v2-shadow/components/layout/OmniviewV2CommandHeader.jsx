import SourceBadge from '../base/SourceBadge';
import CoverageBadge from '../base/CoverageBadge';
import FreshnessBadge from '../base/FreshnessBadge';

function OmniviewV2CommandHeader({
  sourceSystem = 'CT_TRIPS_2026',
  canonicalReady = true,
  grain = 'day',
  dateFrom = '',
  dateTo = '',
  country = 'peru',
  city = 'lima',
  businessSlice = '',
  parkId = '',
  coveragePct = 100,
  freshness = '',
  onSourceChange,
  onGrainChange,
  onDateFromChange,
  onDateToChange,
  onCountryChange,
  onCityChange,
  onBusinessSliceChange,
  onParkIdChange,
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

      <input type="date" value={dateFrom} onChange={(e) => onDateFromChange?.(e.target.value)}
        style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--ov2-border-color)', fontSize: 12, background: '#fff' }} />
      <span style={{ fontSize: 12, color: 'var(--ov2-text-secondary)' }}>to</span>
      <input type="date" value={dateTo} onChange={(e) => onDateToChange?.(e.target.value)}
        style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--ov2-border-color)', fontSize: 12, background: '#fff' }} />

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

      <CoverageBadge pct={coveragePct} />
      <FreshnessBadge lastRefreshedAt={freshness} />
    </div>
  );
}

export default OmniviewV2CommandHeader;
