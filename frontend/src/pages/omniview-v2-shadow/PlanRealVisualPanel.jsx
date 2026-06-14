/**
 * Omniview V2 — Plan vs Real Visual Panel
 * OV2-VC3: Attainment bars with plan, real, gap per slice.
 */
import { useMemo } from 'react';
import { getPlanRealDisplay } from './omniviewV2PlanReal';
import { getMetricById } from './omniviewV2Metrics';

function PlanRealVisualPanel({ planData, metricId, grain, isActive }) {
  const metric = getMetricById(metricId);

  const rows = useMemo(() => {
    if (!planData?.cells || !planData?.rows) return [];
    const sliceRows = planData.rows.map(row => {
      const rowCells = (planData.cells || []).filter(c => c.row_id === row.id);
      const latestCell = rowCells[rowCells.length - 1];
      if (!latestCell) return null;
      const pvr = getPlanRealDisplay(latestCell, metricId);
      return {
        label: row.label || row.id,
        planValue: pvr.planValue,
        realValue: pvr.realValue,
        deltaValue: pvr.deltaValue,
        deltaPct: pvr.deltaPct,
        attainmentPct: pvr.attainmentPct,
        status: pvr.status,
        tone: pvr.tone,
        isFuture: pvr.isFuture,
        isMissing: pvr.isMissing,
      };
    }).filter(Boolean);

    return sliceRows.sort((a, b) => {
      if (a.attainmentPct == null && b.attainmentPct == null) return 0;
      if (a.attainmentPct == null) return 1;
      if (b.attainmentPct == null) return -1;
      return a.attainmentPct - b.attainmentPct;
    });
  }, [planData, metricId]);

  if (!planData?.cells?.length) {
    return (
      <div style={{ background: '#fff', borderRadius: 8, border: '1px solid #e5e7eb', padding: 16, minHeight: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 13 }}>
        {isActive ? 'No plan-real data for selected period.' : 'Switch to Plan vs Real mode to see attainment.'}
      </div>
    );
  }

  return (
    <div style={{ background: '#fff', borderRadius: 8, border: '1px solid #e5e7eb', padding: 16, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Plan vs Real</span>
          <span style={{ fontSize: 11, color: '#6b7280', marginLeft: 8 }}>Attainment by slice</span>
        </div>
      </div>

      {rows.map(r => {
        const hasReal = r.realValue != null && r.status !== 'no_real' && r.status !== 'missing';
        const hasPlan = r.planValue != null && r.status !== 'no_plan';
        const isComparable = hasReal && hasPlan && r.attainmentPct != null && r.attainmentPct >= 0;
        const attainmentColor = !isComparable ? '#9ca3af' : r.attainmentPct >= 100 ? '#16a34a' : r.attainmentPct >= 80 ? '#f59e0b' : '#dc2626';
        const barWidth = isComparable ? Math.min(r.attainmentPct, 150) : 0;
        const isOverflow = r.attainmentPct != null && r.attainmentPct > 150;

        return (
          <div key={r.label} style={{ marginBottom: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 2 }}>
              <span style={{ fontSize: 12, color: '#374151', width: 110, textAlign: 'right', flexShrink: 0, fontWeight: 500 }}>{r.label}</span>
              <div style={{ flex: 1, height: 20, background: '#f3f4f6', borderRadius: 4, overflow: 'hidden', position: 'relative' }}>
                <div style={{ height: '100%', width: `${Math.min(barWidth, 100)}%`, background: attainmentColor, borderRadius: 4, transition: 'width 0.3s', position: 'absolute', left: 0 }} />
                {barWidth > 100 && <div style={{ height: '100%', width: `${barWidth - 100}%`, background: '#22c55e', borderRadius: 4, position: 'absolute', left: '100%' }} />}
              </div>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#111827', width: 50, textAlign: 'right' }}>{r.attainmentPct != null ? `${r.attainmentPct}%` : 'N/A'}</span>
            </div>
            <div style={{ display: 'flex', gap: 8, paddingLeft: 120, fontSize: 10, color: '#6b7280' }}>
              {r.planValue != null && <span>Plan: <strong style={{ color: '#374151' }}>{metric.format(r.planValue)}</strong></span>}
              {r.realValue != null && <span>Real: <strong style={{ color: r.tone === 'negative' ? '#dc2626' : r.tone === 'positive' ? '#16a34a' : '#374151' }}>{metric.format(r.realValue)}</strong></span>}
              {r.status === 'no_plan' && <span style={{ color: '#9ca3af' }}>No plan</span>}
              {r.status === 'no_real' && <span style={{ color: '#9ca3af' }}>No real</span>}
              {r.status === 'missing' && <span style={{ color: '#9ca3af' }}>No data</span>}
            </div>
          </div>
        );
      })}

      {planData?.generated_at && (
        <div style={{ marginTop: 8, fontSize: 10, color: '#9ca3af', textAlign: 'right' }}>
          Data: {planData.generated_at.slice(0, 10)}
        </div>
      )}
    </div>
  );
}

export default PlanRealVisualPanel;
