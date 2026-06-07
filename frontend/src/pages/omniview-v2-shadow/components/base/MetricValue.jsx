import tokens from '../../design/omniviewV2Tokens';

const NUMERIC_FORMATS = {
  count: (v) => Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 }),
  pen: (v) => Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  percent: (v) => Number(v).toFixed(1) + '%',
  ratio: (v) => Number(v).toFixed(4),
  hours: (v) => Number(v).toLocaleString('en-US', { maximumFractionDigits: 1 }),
};

function formatValue(value, unit) {
  if (value == null) return '—';
  const fmt = NUMERIC_FORMATS[unit] || NUMERIC_FORMATS.count;
  try {
    return fmt(value);
  } catch {
    return String(value);
  }
}

function MetricValue({ value, unit = 'count', formattedValue, className = '' }) {
  const display = formattedValue || formatValue(value, unit);
  const isEmpty = value == null;

  return (
    <span
      className={`ov2-kpi-card__value ${isEmpty ? 'ov2-cell--muted' : ''} ${className}`}
      style={{ fontFamily: tokens.typography.fontFamilyMono }}
    >
      {display}
      {!isEmpty && unit && <span className="ov2-kpi-card__unit">{unit === 'pen' ? 'PEN' : ''}</span>}
    </span>
  );
}

export { formatValue };
export default MetricValue;
