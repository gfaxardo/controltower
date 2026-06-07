import MetricValue from '../base/MetricValue';

function OmniviewV2ExecutiveState({ kpis = [], onMetricClick }) {
  const visible = kpis.slice(0, 5);
  if (visible.length === 0) return null;

  return (
    <div style={{ display: 'flex', gap: 'var(--ov2-section-gap)', padding: '12px 16px', flexWrap: 'wrap' }}>
      {visible.map((kpi) => (
        <div key={kpi.metric_id} className="ov2-kpi-card" onClick={() => onMetricClick?.(kpi)} style={{ cursor: 'pointer' }}>
          <div className="ov2-kpi-card__label">{kpi.label || kpi.metric_id}</div>
          <MetricValue value={kpi.value} unit={kpi.unit} formattedValue={kpi.formatted_value} />
          {kpi.is_estimated && (
            <span className="ov2-badge ov2-badge--estimated" style={{ marginTop: 4, fontSize: 9 }}>EST</span>
          )}
        </div>
      ))}
    </div>
  );
}

export default OmniviewV2ExecutiveState;
