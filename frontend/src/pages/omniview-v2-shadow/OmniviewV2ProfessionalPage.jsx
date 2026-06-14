/**
 * Omniview V2 — Professional Page
 * OV2-UI-R4: Professional matrix with color semantics + Plan vs Real.
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
import { getCellToneClass } from './omniviewV2ColorSemantics';
import { getPlanRealDisplay } from './omniviewV2PlanReal';
import { RouteStatusBadge } from './RouteStatusBadge';

function ProfessionalPage() {
  const today = new Date().toISOString().slice(0, 10);
  const [sourceSystem] = useState('CT_TRIPS_2026');
  const [grain, setGrain] = useState('day');
  const [metricId, setMetricId] = useState('orders');
  const [viewMode, setViewMode] = useState('real');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [country] = useState('peru');
  const [city] = useState('lima');
  const [businessSlice] = useState('');
  const [sortMode, setSortMode] = useState('default');
  const [activePreset, setActivePreset] = useState('');
  const [operatingDate, setOperatingDate] = useState(null);

  const { data: shellData, loading: shellLoading } = useOmniviewV2Shell(sourceSystem, grain, dateFrom, dateTo, country, city);
  const { matrixData: realMatrixData, loading: matrixLoading } = useOmniviewV2Matrix(sourceSystem, grain, metricId, dateFrom, dateTo, shellData, country, city);
  const { planData } = useOmniviewV2PlanReal(viewMode === 'plan_real' ? { metric_id: metricId, date_from: dateFrom || today, date_to: dateTo || today } : null);

  useEffect(() => {
    let cancelled = false;
    getOmniviewV2OperatingDate({ source_system: sourceSystem }).then((data) => {
      if (!cancelled && data?.default_date) { setOperatingDate(data); if (!dateFrom) { setDateFrom(data.default_date); setDateTo(data.default_date); } }
    }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const activeMatrixData = viewMode === 'plan_real' ? planData : realMatrixData;
  const matrixData = activeMatrixData;
  const sortedData = useMemo(() => {
    if (!matrixData?.rows || sortMode === 'default') return matrixData;
    return { ...matrixData, rows: sortMatrixRows(matrixData.rows, matrixData.cells, sortMode, metricId) };
  }, [matrixData, sortMode, metricId]);

  const freshness = shellData?.freshness?.last_refreshed_at || '';
  const coverage = shellData?.coverage || {};
  const canonicalReady = shellData?.canonical_ready ?? false;
  const loading = shellLoading || matrixLoading;
  const hasData = (matrixData?.cells?.length || 0) > 0;
  const freshnessStatus = operatingDate?.freshness_status;
  const isStale = freshnessStatus && freshnessStatus !== 'FRESH';
  const statusLabel = !canonicalReady ? 'Shadow mode' : isStale ? 'Data warning' : loading ? 'Loading...' : hasData ? 'Operational' : 'No data';
  const statusColor = !canonicalReady ? '#9ca3af' : isStale ? '#f59e0b' : hasData ? '#16a34a' : '#6b7280';
  const [showDebug, setShowDebug] = useState(false);
  const isPlanReal = viewMode === 'plan_real';

  const handlePreset = (pid) => { const r = getPresetRange(pid); if (r) { setDateFrom(r.from); setDateTo(r.to); setActivePreset(pid); } };
  const handleExport = () => {
    try { exportOmniviewV2Csv({ matrixData: sortedData, metric, grain, filters: { country, city, businessSlice, dateFrom, dateTo }, viewMode, canonicalReady, freshness, operatingDate, coverage, activePreset }); }
    catch (e) { console.error('Export failed:', e); }
  };

  const ss = { padding: '6px 8px', borderRadius: 4, border: '1px solid #d1d5db', fontSize: 13, background: '#fff', color: '#374151' };
  const tdStyle = { padding: '6px 10px', textAlign: 'right', borderBottom: '1px solid #e5e7eb', fontSize: 13, minWidth: 110 };
  const toneMap = { positive: '#16a34a', negative: '#dc2626', neutral: '#9ca3af', warning: '#f59e0b', blocked: '#ef4444', 'not-comparable': '#9ca3af', future: '#d1d5db', disabled: '#d1d5db', muted: '#d1d5db' };

  if (loading && !hasData) return <div style={{ padding: 60, textAlign: 'center', color: '#374151', fontFamily: 'system-ui, sans-serif' }}><div style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Loading operational data...</div></div>;
  if (!hasData && !loading) return <div style={{ padding: 60, textAlign: 'center', color: '#374151', fontFamily: 'system-ui, sans-serif' }}><div style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>No operational data</div><div style={{ fontSize: 13, color: '#6b7280' }}>No data for {grain} / {country} / {city} / {metric?.label || 'Trips'}.</div></div>;

  const cols = sortedData?.columns || [];
  const rows = sortedData?.rows || [];
  const cells = sortedData?.cells || [];

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', fontFamily: 'system-ui, -apple-system, sans-serif', background: '#f9fafb' }}>
      <header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 24px', background: '#fff', borderBottom: '1px solid #e5e7eb', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontWeight: 700, fontSize: 16, color: '#111827' }}>Omniview V2</span>
          <RouteStatusBadge status="DEFAULT_CERTIFIED" style={{ marginLeft: 4 }} />
          <span style={{ fontSize: 11, color: canonicalReady ? '#16a34a' : '#9ca3af', background: canonicalReady ? '#f0fdf4' : '#f3f4f6', padding: '2px 8px', borderRadius: 3 }}>{canonicalReady ? 'CANONICAL' : 'SHADOW'}</span>
          <span style={{ fontSize: 12, color: '#6b7280' }}>{grain === 'day' ? 'Daily' : grain === 'week' ? 'Weekly' : 'Monthly'} · {metric?.label || 'Trips'} · {dateFrom || '—'} → {dateTo || '—'}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 12, color: '#6b7280' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontWeight: 500, color: statusColor }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: statusColor, display: 'inline-block' }} />{statusLabel}
          </span>
          {freshness && <span>Updated {freshness}</span>}
          <span>Coverage {coverage.coverage_pct ?? '-'}%</span>
        </div>
      </header>
      {operatingDate && (
        <div style={{ display: 'flex', gap: 16, padding: '4px 24px', background: '#f3f4f6', borderBottom: '1px solid #e5e7eb', fontSize: 11, color: '#6b7280', flexShrink: 0 }}>
          <span>Latest closed: <strong>{operatingDate.latest_closed_date || '—'}</strong></span>
          <span>Default date: <strong>{operatingDate.default_date || '—'}</strong></span>
          <span>Freshness: <strong style={{ color: operatingDate.freshness_status === 'FRESH' ? '#16a34a' : '#dc2626' }}>{operatingDate.freshness_status || '—'}</strong></span>
          <span>Lag: <strong>{operatingDate.lag_days != null ? `${operatingDate.lag_days}d` : '—'}</strong></span>
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 24px', background: '#fff', borderBottom: '1px solid #e5e7eb', flexWrap: 'wrap', flexShrink: 0 }}>
        <select value={grain} onChange={e => setGrain(e.target.value)} style={ss}><option value="day">Daily</option><option value="week">Weekly</option><option value="month">Monthly</option></select>
        <select value={metricId} onChange={e => setMetricId(e.target.value)} style={{ ...ss, fontWeight: 600 }}>{OMNIVIEW_V2_METRICS.map(m => <option key={m.id} value={m.id} disabled={!m.available}>{m.label}{!m.available ? ' (N/A)' : ''}</option>)}</select>
        {PERIOD_PRESETS.map(p => <button key={p.id} onClick={() => handlePreset(p.id)} style={{ padding: '4px 10px', borderRadius: 4, fontSize: 11, cursor: 'pointer', fontWeight: activePreset === p.id ? 600 : 400, border: `1px solid ${activePreset === p.id ? '#3b82f6' : '#d1d5db'}`, background: activePreset === p.id ? '#eff6ff' : '#fff', color: activePreset === p.id ? '#3b82f6' : '#6b7280' }}>{p.label}</button>)}
        <span style={{ color: '#d1d5db', margin: '0 4px' }}>|</span>
        <select value={viewMode} onChange={e => setViewMode(e.target.value)} style={ss}><option value="real">Real</option><option value="plan_real">Plan vs Real</option></select>
        <select value={sortMode} onChange={e => setSortMode(e.target.value)} style={ss}>{SORT_MODES.map(s => <option key={s.id} value={s.id}>{s.label}</option>)}</select>
        <span style={{ flex: 1 }} />
        <button onClick={handleExport} disabled={!hasData} style={{ padding: '6px 14px', borderRadius: 4, border: 'none', fontSize: 12, fontWeight: 500, cursor: hasData ? 'pointer' : 'not-allowed', background: hasData ? '#3b82f6' : '#e5e7eb', color: hasData ? '#fff' : '#9ca3af' }}>Export CSV</button>
        <button onClick={() => setShowDebug(!showDebug)} style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid #d1d5db', fontSize: 10, background: '#fff', color: '#9ca3af', cursor: 'pointer' }}>D</button>
      </div>
      <div style={{ flex: 1, overflow: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 13, fontFamily: 'system-ui, -apple-system, sans-serif' }}>
          <thead>
            <tr style={{ background: '#f3f4f6', position: 'sticky', top: 0, zIndex: 10 }}>
              <th style={{ padding: '8px 14px', textAlign: 'left', borderBottom: '2px solid #d1d5db', minWidth: 160, fontWeight: 600, color: '#374151', position: 'sticky', left: 0, background: '#f3f4f6', zIndex: 11 }}>Business Slice</th>
              {cols.map(c => <th key={c.id} style={{ padding: '8px 14px', textAlign: 'right', borderBottom: '2px solid #d1d5db', minWidth: 110, fontWeight: 600, color: '#374151', fontSize: 12 }}>{c.period ? c.period.slice(c.period.length > 7 ? 5 : 0, 10) : c.label}{c.period_status === 'PARTIAL' && <span style={{ fontSize: 9, color: '#f59e0b', marginLeft: 4 }}>PAR</span>}{c.period_status === 'FUTURE' && <span style={{ fontSize: 9, color: '#9ca3af', marginLeft: 4 }}>FUT</span>}</th>)}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => {
              const rowCells = cells.filter(c => c.row_id === row.id);
              const bg = ri % 2 === 0 ? '#fff' : '#f9fafb';
              return (
                <tr key={row.id} style={{ background: bg }}>
                  <td style={{ padding: '8px 14px', borderBottom: '1px solid #e5e7eb', fontWeight: 500, color: '#111827', position: 'sticky', left: 0, background: bg, zIndex: 5 }}>{row.label}</td>
                  {cols.map(col => {
                    const cell = rowCells.find(c => c.column_id === col.id);
                    if (!cell || cell.value == null) return <td key={col.id} style={{ ...tdStyle, color: '#9ca3af' }}>—</td>;
                    const isFuture = col.period_status === 'FUTURE';
                    const tone = getCellToneClass(cell, metricId, isFuture);
                    const bc = toneMap[tone] || '#d1d5db';
                    if (isPlanReal) {
                      const pvr = getPlanRealDisplay(cell, metricId);
                      return <td key={col.id} style={{ ...tdStyle, borderLeft: `3px solid ${bc}` }}><div style={{ fontWeight: 600, color: '#111827' }}>{cell.formatted_value || String(cell.value)}</div>{pvr.attainmentPct != null && <div style={{ fontSize: 10, color: tone === 'negative' ? '#dc2626' : tone === 'positive' ? '#16a34a' : '#6b7280', marginTop: 1 }}>{pvr.attainmentFormatted} · {tone === 'negative' ? 'Behind' : tone === 'positive' ? 'Ahead' : 'OK'}</div>}</td>;
                    }
                    return <td key={col.id} style={{ ...tdStyle, borderLeft: `3px solid ${bc}`, color: '#111827', fontWeight: 500 }}>{cell.formatted_value || String(cell.value)}</td>;
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {showDebug && (
        <div style={{ padding: '8px 24px', background: '#1f2937', color: '#9ca3af', fontSize: 10, fontFamily: 'monospace', flexShrink: 0, maxHeight: 120, overflow: 'auto', borderTop: '1px solid #374151' }}>
          <div><strong style={{ color: '#e5e7eb' }}>Debug</strong> · grain={grain} metric={metricId} view={viewMode} sort={sortMode} preset={activePreset || 'none'}</div>
          <div>freshness={freshnessStatus || 'unknown'} canonical={String(canonicalReady)} coverage={coverage.coverage_pct} lag={operatingDate?.lag_days ?? '—'}d</div>
          <div>rows={sortedData?.rows?.length || 0} cols={sortedData?.columns?.length || 0} cells={sortedData?.cells?.length || 0} loading={String(loading)} hasData={String(hasData)}</div>
          <div>shell={shellData ? 'ok' : 'null'} matrix={matrixData ? 'ok' : 'null'} plan={planData ? 'ok' : 'null'} opDate={operatingDate ? 'ok' : 'null'}</div>
        </div>
      )}
    </div>
  );
}

export default ProfessionalPage;
