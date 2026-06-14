/**
 * Omniview V2 — Executive Visual Cockpit
 * OV2-VC1: Visual-first cockpit architecture. Matrix secondary.
 */
import { useState, useEffect, useMemo } from 'react';
import useOmniviewV2Shell from './hooks/useOmniviewV2Shell';
import useOmniviewV2Matrix from './hooks/useOmniviewV2Matrix';
import { useOmniviewV2PlanReal } from './hooks/useOmniviewV2PlanReal';
import { getOmniviewV2OperatingDate } from '../../services/api';
import { exportOmniviewV2Csv } from './omniviewV2Export';
import { getMetricById } from './omniviewV2Metrics';
import { getPresetRange, PERIOD_PRESETS } from './omniviewV2PeriodPresets';
import { sortMatrixRows, SORT_MODES } from './omniviewV2Sort';
import OMNIVIEW_V2_METRICS from './omniviewV2Metrics';
import { RouteStatusBadge } from './RouteStatusBadge';
import { buildTrendSeries, getComparableLabel } from './omniviewV2TrendSeries';
import TrendLayerPanel from './TrendLayerPanel';
import PlanRealVisualPanel from './PlanRealVisualPanel';
import SliceBreakdownVisualPanel from './SliceBreakdownVisualPanel';

function ExecutiveCockpit() {
  const today = new Date().toISOString().slice(0, 10);
  const [grain, setGrain] = useState('day');
  const [metricId, setMetricId] = useState('orders');
  const [viewMode, setViewMode] = useState('real');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [sortMode, setSortMode] = useState('default');
  const [activePreset, setActivePreset] = useState('');
  const [operatingDate, setOperatingDate] = useState(null);
  const [showMatrix, setShowMatrix] = useState(false);
  const [showDebug, setShowDebug] = useState(false);
  const [drillSlice, setDrillSlice] = useState(null);

  const { data: shellData, loading: shellLoading } = useOmniviewV2Shell('CT_TRIPS_2026', grain, dateFrom, dateTo, 'peru', 'lima');
  const { matrixData: realMatrixData, loading: matrixLoading } = useOmniviewV2Matrix('CT_TRIPS_2026', grain, metricId, dateFrom, dateTo, shellData, 'peru', 'lima');
  const { planData } = useOmniviewV2PlanReal(viewMode === 'plan_real' ? { metric_id: metricId, date_from: dateFrom || today, date_to: dateTo || today } : null);

  useEffect(() => {
    let c = false;
    getOmniviewV2OperatingDate({ source_system: 'CT_TRIPS_2026' }).then(d => {
      if (!c && d?.default_date) { setOperatingDate(d); if (!dateFrom) { setDateFrom(d.default_date); setDateTo(d.default_date); } }
    }).catch(() => {});
    return () => { c = true; };
  }, []);

  const matrixData = viewMode === 'plan_real' ? planData : realMatrixData;
  const sortedData = useMemo(() => {
    if (!matrixData?.rows || sortMode === 'default') return matrixData;
    return { ...matrixData, rows: sortMatrixRows(matrixData.rows, matrixData.cells, sortMode, metricId) };
  }, [matrixData, sortMode, metricId]);

  const freshness = shellData?.freshness?.last_refreshed_at || '';
  const coverage = shellData?.coverage || {};
  const canonicalReady = shellData?.canonical_ready ?? false;
  const loading = shellLoading || matrixLoading;
  const hasData = (matrixData?.cells?.length || 0) > 0;
  const metric = getMetricById(metricId);
  const freshnessStatus = operatingDate?.freshness_status;
  const isStale = freshnessStatus && freshnessStatus !== 'FRESH';
  const statusLabel = !canonicalReady ? 'Shadow mode' : isStale ? 'Data warning' : loading ? 'Loading...' : hasData ? 'Operational' : 'No data';
  const statusColor = !canonicalReady ? '#9ca3af' : isStale ? '#f59e0b' : hasData ? '#16a34a' : '#6b7280';

  // ── Trend series (VC2) ────────────────────────────────────────
  const trendData = useMemo(() => buildTrendSeries(matrixData, metricId, grain, operatingDate), [matrixData, metricId, grain, operatingDate]);
  const deltaLabel = getComparableLabel(grain);

  // ── KPI cards from shell data ──────────────────────────────────
  const kpiSection = shellData?.sections?.find(s => s.section_id === 'kpi_strip');
  const kpis = (kpiSection?.kpis || []).slice(0, 4);
  const primaryKpis = ['orders', 'revenue', 'active_drivers', 'cancel_rate_pct'];

  // ── Slice breakdown from matrix cells ──────────────────────────
  const sliceBreakdown = useMemo(() => {
    if (!matrixData?.cells || matrixData.cells.length === 0 || !matrixData.rows) return [];
    const sliceTotals = {};
    for (const c of matrixData.cells) {
      if (c.value == null || c.metric_id !== metricId) continue;
      const row = matrixData.rows.find(r => r.id === c.row_id);
      const label = row?.label || c.row_id;
      sliceTotals[label] = (sliceTotals[label] || 0) + c.value;
    }
    const entries = Object.entries(sliceTotals).sort((a, b) => b[1] - a[1]);
    const total = entries.reduce((s, [, v]) => s + v, 0);
    return entries.slice(0, 6).map(([label, val]) => ({ label, value: val, pct: total > 0 ? Math.round(val / total * 100) : 0 }));
  }, [matrixData, metricId]);

  const handlePreset = (pid) => { const r = getPresetRange(pid); if (r) { setDateFrom(r.from); setDateTo(r.to); setActivePreset(pid); } };
  const handleExport = () => {
    try { exportOmniviewV2Csv({ matrixData: sortedData, metric, grain, filters: { country: 'peru', city: 'lima', dateFrom, dateTo }, viewMode, canonicalReady, freshness, operatingDate, coverage, activePreset }); }
    catch (e) { console.error('Export failed:', e); }
  };

  if (loading && !hasData) return <div style={{ padding: 60, textAlign: 'center', color: '#374151', fontFamily: 'system-ui, sans-serif' }}><div style={{ fontSize: 16, fontWeight: 600 }}>Loading cockpit...</div></div>;
  if (!hasData && !loading) return <div style={{ padding: 60, textAlign: 'center', color: '#374151', fontFamily: 'system-ui, sans-serif' }}><div style={{ fontSize: 18, fontWeight: 600 }}>No operational data</div><div style={{ fontSize: 13, color: '#6b7280' }}>No data for {grain} / {metric?.label || 'Trips'}.</div></div>;

  const panelStyle = { background: '#fff', borderRadius: 8, border: '1px solid #e5e7eb', padding: 16, display: 'flex', flexDirection: 'column', overflow: 'hidden' };
  const kpiCardStyle = { ...panelStyle, alignItems: 'center', justifyContent: 'center', minWidth: 140, flex: 1 };
  const ss = { padding: '6px 8px', borderRadius: 4, border: '1px solid #d1d5db', fontSize: 13, background: '#fff', color: '#374151' };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', fontFamily: 'system-ui, -apple-system, sans-serif', background: '#f9fafb', overflow: 'auto' }}>
      {/* Header */}
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 24px', background: '#fff', borderBottom: '1px solid #e5e7eb', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontWeight: 700, fontSize: 16, color: '#111827' }}>Omniview V2</span>
          <RouteStatusBadge status="DEFAULT_CERTIFIED" />
          <span style={{ fontSize: 11, color: statusColor, fontWeight: 500 }}>● {statusLabel}</span>
          <span style={{ fontSize: 12, color: '#6b7280' }}>{grain === 'day' ? 'Daily' : grain === 'week' ? 'Weekly' : 'Monthly'} · {metric?.label || 'Trips'} · {dateFrom || '—'} → {dateTo || '—'}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 12, color: '#6b7280' }}>Coverage {coverage.coverage_pct ?? '-'}%</span>
          <button onClick={() => setShowDebug(!showDebug)} style={{ padding: '2px 6px', borderRadius: 3, border: '1px solid #d1d5db', fontSize: 10, background: '#fff', color: '#9ca3af', cursor: 'pointer' }}>D</button>
        </div>
      </header>

      {/* Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 24px', background: '#fff', borderBottom: '1px solid #e5e7eb', flexWrap: 'wrap', flexShrink: 0 }}>
        <select value={grain} onChange={e => setGrain(e.target.value)} style={ss}><option value="day">Daily</option><option value="week">Weekly</option><option value="month">Monthly</option></select>
        <select value={metricId} onChange={e => setMetricId(e.target.value)} style={{ ...ss, fontWeight: 600 }}>{OMNIVIEW_V2_METRICS.map(m => <option key={m.id} value={m.id} disabled={!m.available}>{m.label}</option>)}</select>
        {PERIOD_PRESETS.slice(0, 4).map(p => <button key={p.id} onClick={() => handlePreset(p.id)} style={{ padding: '4px 10px', borderRadius: 4, fontSize: 11, cursor: 'pointer', fontWeight: activePreset === p.id ? 600 : 400, border: `1px solid ${activePreset === p.id ? '#3b82f6' : '#d1d5db'}`, background: activePreset === p.id ? '#eff6ff' : '#fff', color: activePreset === p.id ? '#3b82f6' : '#6b7280' }}>{p.label}</button>)}
        <span style={{ color: '#d1d5db' }}>|</span>
        <select value={viewMode} onChange={e => setViewMode(e.target.value)} style={ss}><option value="real">Real</option><option value="plan_real">Plan vs Real</option></select>
        <select value={sortMode} onChange={e => setSortMode(e.target.value)} style={ss}>{SORT_MODES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}</select>
        <span style={{ flex: 1 }} />
        <button onClick={handleExport} disabled={!hasData} style={{ padding: '6px 14px', borderRadius: 4, border: 'none', fontSize: 12, fontWeight: 500, cursor: hasData ? 'pointer' : 'not-allowed', background: hasData ? '#3b82f6' : '#e5e7eb', color: hasData ? '#fff' : '#9ca3af' }}>Export CSV</button>
        <button onClick={() => setShowMatrix(!showMatrix)} style={{ padding: '6px 14px', borderRadius: 4, border: '1px solid #d1d5db', fontSize: 12, background: '#fff', color: '#374151', cursor: 'pointer', fontWeight: showMatrix ? 600 : 400 }}>{showMatrix ? 'Hide Detail' : 'Matrix Detail'}</button>
      </div>

      {/* Main cockpit area */}
      <div style={{ flex: 1, overflow: 'auto', padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
        {/* KPI Cards Row */}
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          {primaryKpis.map(kid => {
            const kpiMetric = getMetricById(kid);
            const kpiCells = (matrixData?.cells || []).filter(c => c.metric_id === kid && c.value != null);
            const total = kpiCells.reduce((s, c) => s + c.value, 0);
            return (
              <div key={kid} style={kpiCardStyle}>
                <div style={{ fontSize: 11, color: '#6b7280', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{kpiMetric?.label || kid}</div>
                <div style={{ fontSize: 28, fontWeight: 700, color: '#111827', margin: '4px 0' }}>{kpiMetric?.format ? kpiMetric.format(total) : total.toLocaleString()}</div>
                {kid === metricId && trendData?.currentDeltaPct != null ? (
                  <div style={{ fontSize: 11, fontWeight: 600, color: trendData.currentDeltaPct >= 0 ? (kpiMetric?.higherIsBetter === false ? '#dc2626' : '#16a34a') : (kpiMetric?.higherIsBetter === false ? '#16a34a' : '#dc2626') }}>
                    {trendData.currentDeltaPct > 0 ? '▲' : '▼'} {Math.abs(trendData.currentDeltaPct)}% {deltaLabel}
                  </div>
                ) : (
                  <div style={{ fontSize: 11, color: '#9ca3af' }}>{deltaLabel}</div>
                )}
              </div>
            );
          })}
        </div>

        {/* Visual Panels Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {/* Trend Panel — VC2 real chart */}
          <TrendLayerPanel trendData={trendData} metricId={metricId} grain={grain} />

          {/* Plan vs Real Panel — VC3 real attainment bars */}
          <PlanRealVisualPanel planData={planData} metricId={metricId} grain={grain} isActive={viewMode === 'plan_real'} />
        </div>

        {/* Slice Breakdown — VC4 enhanced with VC5 drill */}
        <SliceBreakdownVisualPanel matrixData={matrixData} metricId={metricId} grain={grain} onSliceClick={(slice) => { setDrillSlice(slice); setShowMatrix(true); }} />

        {/* Matrix Detail (secondary) */}
        {showMatrix && sortedData?.rows && (
          <div style={panelStyle}>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 8 }}>
              Matrix Detail
              {drillSlice && <span style={{ fontSize: 11, color: '#3b82f6', marginLeft: 8, fontWeight: 500 }}>Drill: {drillSlice.label}</span>}
            </div>
            <div style={{ overflow: 'auto', maxHeight: 400 }}>
              <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 12 }}>
                <thead>
                  <tr style={{ background: '#f3f4f6' }}>
                    <th style={{ padding: '6px 12px', textAlign: 'left', borderBottom: '2px solid #d1d5db', minWidth: 140, fontWeight: 600, color: '#374151', position: 'sticky', left: 0, background: '#f3f4f6' }}>Slice</th>
                    {(sortedData.columns || []).map(c => <th key={c.id} style={{ padding: '6px 12px', textAlign: 'right', borderBottom: '2px solid #d1d5db', minWidth: 90, fontWeight: 600, color: '#374151', fontSize: 11 }}>{c.period ? c.period.slice(5, 10) : c.label}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {(sortedData.rows || []).map((row, ri) => {
                    const rc = (sortedData.cells || []).filter(c => c.row_id === row.id);
                    return <tr key={row.id} style={{ background: ri % 2 === 0 ? '#fff' : '#f9fafb' }}><td style={{ padding: '6px 12px', borderBottom: '1px solid #e5e7eb', fontWeight: 500, color: '#111827' }}>{row.label}</td>{(sortedData.columns || []).map(col => { const cell = rc.find(c => c.column_id === col.id); const v = cell?.formatted_value || (cell?.value != null ? String(cell.value) : '—'); return <td key={col.id} style={{ padding: '6px 12px', textAlign: 'right', borderBottom: '1px solid #e5e7eb', color: cell?.value == null ? '#9ca3af' : '#111827' }}>{v}</td>; })}</tr>;
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Debug panel */}
      {showDebug && (
        <div style={{ padding: '8px 24px', background: '#1f2937', color: '#9ca3af', fontSize: 10, fontFamily: 'monospace', flexShrink: 0, borderTop: '1px solid #374151' }}>
          grain={grain} metric={metricId} view={viewMode} sort={sortMode} rows={sortedData?.rows?.length || 0} cells={sortedData?.cells?.length || 0} freshness={freshnessStatus || 'unknown'}
        </div>
      )}
    </div>
  );
}

export default ExecutiveCockpit;
