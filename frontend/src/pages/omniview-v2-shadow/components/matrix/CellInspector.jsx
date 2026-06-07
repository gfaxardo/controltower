import SourceBadge from '../base/SourceBadge';
import CoverageBadge from '../base/CoverageBadge';
import StatusBadge from '../base/StatusBadge';
import { formatValue } from '../base/MetricValue';

function CellInspector({ cell, isOpen, onClose }) {
  if (!isOpen || !cell) return null;

  return (
    <>
      <div className="ov2-inspector-backdrop" onClick={onClose} />
      <div className="ov2-inspector-drawer">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Cell Inspector</h3>
          <button
            onClick={onClose}
            style={{ background: 'none', border: '1px solid var(--ov2-border-color)', borderRadius: 4, padding: '4px 10px', cursor: 'pointer', fontSize: 14 }}
          >
            ✕
          </button>
        </div>

        <InspectorSection title="Value">
          <div className="ov2-kpi-card__value">{cell.formatted_value || formatValue(cell.value, cell.unit)}</div>
          <div style={{ fontSize: 12, color: 'var(--ov2-text-secondary)', marginTop: 4 }}>
            {cell.label || cell.metric_id} · {cell.unit || 'count'}
          </div>
        </InspectorSection>

        <InspectorSection title="Source">
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <SourceBadge canonicalReady={cell.canonical_ready} />
            <CoverageBadge pct={cell.coverage_pct} />
            <StatusBadge status={cell.cell_status?.toLowerCase() || 'ok'} label={cell.cell_status || 'OK'} />
          </div>
          <div style={{ fontSize: 12, color: 'var(--ov2-text-secondary)', marginTop: 8 }}>
            {cell.source_system} · {cell.source_table || '—'}
          </div>
        </InspectorSection>

        <InspectorSection title="Period">
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <span>{cell.period || '—'}</span>
            {cell.period_status && <StatusBadge status={cell.period_status === 'CLOSED' ? 'ok' : 'warning'} label={cell.period_status} />}
          </div>
        </InspectorSection>

        <InspectorSection title="Trust">
          <InfoRow label="Confidence" value={cell.confidence} />
          <InfoRow label="Estimated" value={cell.is_estimated ? 'Yes' : 'No'} />
          <InfoRow label="Freshness" value={cell.freshness || '—'} />
          <InfoRow label="Canonical ready" value={cell.canonical_ready ? 'Yes' : 'No'} />
        </InspectorSection>

        {cell.warning_codes && cell.warning_codes.length > 0 && (
          <InspectorSection title="Warnings">
            {cell.warning_codes.map((code, i) => (
              <span key={i} className="ov2-badge ov2-badge--warning" style={{ marginRight: 4, marginBottom: 4, display: 'inline-block' }}>
                {code}
              </span>
            ))}
          </InspectorSection>
        )}

        {cell.lineage_refs && cell.lineage_refs.origin_table && (
          <InspectorSection title="Lineage">
            <div style={{ fontSize: 12 }}>
              <InfoRow label="Table" value={cell.lineage_refs.origin_table} />
              <InfoRow label="Field" value={cell.lineage_refs.origin_field} />
              <InfoRow label="Aggregation" value={cell.lineage_refs.aggregation} />
            </div>
          </InspectorSection>
        )}

        {cell.comparison_status && (
          <InspectorSection title="Comparison">
            <InfoRow label="Status" value={cell.comparison_status} />
            <InfoRow label="Delta" value={cell.delta_value != null ? `${cell.delta_value}` : '—'} />
            <InfoRow label="Delta %" value={cell.delta_pct != null ? `${cell.delta_pct}%` : '—'} />
          </InspectorSection>
        )}
      </div>
    </>
  );
}

function InspectorSection({ title, children }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 10, fontWeight: 600, textTransform: 'uppercase', color: 'var(--ov2-text-secondary)', marginBottom: 8, letterSpacing: '0.05em' }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 13 }}>
      <span style={{ color: 'var(--ov2-text-secondary)' }}>{label}</span>
      <span style={{ fontWeight: 500 }}>{value}</span>
    </div>
  );
}

export default CellInspector;
