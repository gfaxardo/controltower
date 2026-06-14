/**
 * Omniview V2 — Slice Breakdown Visual Panel
 * OV2-VC4: Ranking/contribution bars per slice.
 */
import { useMemo } from 'react';
import { buildSliceBreakdown } from './omniviewV2SliceBreakdown';
import { getMetricById } from './omniviewV2Metrics';

function SliceBreakdownVisualPanel({ matrixData, metricId, grain }) {
  const metric = getMetricById(metricId);
  const breakdown = useMemo(() => buildSliceBreakdown(matrixData, metricId, grain), [matrixData, metricId, grain]);

  if (!breakdown || breakdown.rows.length === 0) {
    return (
      <div style={{ background: '#fff', borderRadius: 8, border: '1px solid #e5e7eb', padding: 16, minHeight: 160, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 13 }}>
        No slice breakdown data available.
      </div>
    );
  }

  const topRows = breakdown.rows.slice(0, 6);
  const displayRows = topRows.filter(r => r.value != null && r.value > 0 && !r.isInvalid);
  const maxVal = displayRows.length > 0 ? Math.max(...displayRows.map(r => r.value)) : 1;

  return (
    <div style={{ background: '#fff', borderRadius: 8, border: '1px solid #e5e7eb', padding: 16, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Slice Breakdown</span>
          <span style={{ fontSize: 11, color: '#6b7280', marginLeft: 8 }}>Contribution by slice</span>
        </div>
        <div style={{ fontSize: 10, color: '#9ca3af' }}>
          {breakdown.isAdditive ? 'SUM' : 'Latest period'} · {breakdown.validCount} valid{breakdown.invalidCount > 0 ? ` · ${breakdown.invalidCount} invalid` : ''}{breakdown.missingCount > 0 ? ` · ${breakdown.missingCount} missing` : ''}
        </div>
      </div>

      {!breakdown.isAdditive && (
        <div style={{ fontSize: 10, color: '#f59e0b', background: '#fffbeb', padding: '4px 8px', borderRadius: 4, marginBottom: 8 }}>
          {metric.label} is a ratio metric — showing latest period value. Contribution % not applicable.
        </div>
      )}

      {topRows.map((r, i) => {
        const isInvalid = r.isInvalid || (r.value != null && r.value < 0);
        const isMissing = r.missing;
        const barWidth = !isInvalid && !isMissing && maxVal > 0 ? Math.round((r.value || 0) / maxVal * 100) : 0;

        return (
          <div key={r.label} style={{ marginBottom: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 11, color: '#9ca3af', width: 18, textAlign: 'right' }}>{i + 1}</span>
              <span style={{ fontSize: 12, color: '#374151', width: 110, textAlign: 'right', flexShrink: 0, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.label}</span>
              <div style={{ flex: 1, height: 18, background: '#f3f4f6', borderRadius: 4, overflow: 'hidden' }}>
                {isInvalid ? (
                  <div style={{ height: '100%', width: '100%', background: '#fef2f2', display: 'flex', alignItems: 'center', paddingLeft: 8, fontSize: 10, color: '#dc2626' }}>Invalid data</div>
                ) : isMissing ? (
                  <div style={{ height: '100%', width: '100%', background: '#f9fafb', display: 'flex', alignItems: 'center', paddingLeft: 8, fontSize: 10, color: '#9ca3af' }}>No data</div>
                ) : (
                  <div style={{ height: '100%', width: `${barWidth}%`, background: '#3b82f6', borderRadius: 4, transition: 'width 0.3s', minWidth: r.value > 0 ? 2 : 0 }} />
                )}
              </div>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#111827', width: 90, textAlign: 'right' }}>{r.value != null ? metric.format(r.value) : '—'}</span>
              {breakdown.isAdditive && r.contributionPct > 0 && <span style={{ fontSize: 11, color: '#6b7280', width: 36, textAlign: 'right' }}>{r.contributionPct}%</span>}
            </div>
          </div>
        );
      })}

      {breakdown.rows.length > 6 && (
        <div style={{ fontSize: 10, color: '#9ca3af', textAlign: 'center', marginTop: 4 }}>
          + {breakdown.rows.length - 6} more slices · use Matrix Detail for full view
        </div>
      )}
    </div>
  );
}

export default SliceBreakdownVisualPanel;
