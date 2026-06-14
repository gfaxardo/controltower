/**
 * Omniview V2 — Trend Layer Panel
 * OV2-VC2: ECharts trend chart with comparable periods.
 */
import { useEffect, useRef, useMemo } from 'react';

function TrendLayerPanel({ trendData, metricId, grain }) {
  const chartRef = useRef(null);
  const instanceRef = useRef(null);

  const option = useMemo(() => {
    if (!trendData?.points?.length) return null;
    const pts = trendData.points;
    const labels = pts.map(p => p.label || p.period?.slice(5, 10) || '');
    const values = pts.map(p => p.value);
    const comparableLabel = trendData.comparableLabel || 'DoD';
    const avgVal = trendData.rollingAverage?.value;
    const peakVal = trendData.peakLast4?.value;
    const avgLine = avgVal != null ? Array(pts.length).fill(avgVal) : null;
    const peakMarker = peakVal != null ? { name: trendData.peakLast4.label, coord: [labels.length - 1, peakVal] } : null;

    let markLine = {};
    if (peakMarker) markLine = { silent: true, symbol: 'none', lineStyle: { type: 'dashed', color: '#f59e0b', width: 1.5 }, label: { formatter: trendData.peakLast4.label, fontSize: 10 }, data: [{ yAxis: peakVal, name: trendData.peakLast4.label }] };

    return {
      tooltip: { trigger: 'axis' },
      legend: { show: true, data: [comparableLabel, avgLine ? trendData.rollingAverage.label : '', peakVal != null ? trendData.peakLast4.label : ''].filter(Boolean), bottom: 0, textStyle: { fontSize: 10 } },
      grid: { top: 10, right: 20, bottom: 30, left: 50 },
      xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 10, rotate: grain === 'day' ? 45 : 0 } },
      yAxis: { type: 'value', axisLabel: { fontSize: 10 } },
      series: [
        { name: comparableLabel, type: 'line', data: values, smooth: true, lineStyle: { width: 2.5, color: '#3b82f6' }, itemStyle: { color: '#3b82f6' }, markLine },
        ...(avgLine ? [{ name: trendData.rollingAverage.label, type: 'line', data: avgLine, smooth: false, lineStyle: { width: 1.5, color: '#9ca3af', type: 'dotted' }, itemStyle: { color: '#9ca3af' }, symbol: 'none' }] : []),
        ...(peakVal != null ? [{ name: trendData.peakLast4.label, type: 'scatter', data: [[labels.length - 1, peakVal]], symbolSize: 10, itemStyle: { color: '#f59e0b' }, markLine: { silent: true, symbol: 'none', lineStyle: { type: 'dashed', color: '#f59e0b', width: 1 }, data: [{ yAxis: peakVal }] } }] : []),
      ],
    };
  }, [trendData, grain]);

  useEffect(() => {
    let cancelled = false;
    const loadChart = async () => {
      try {
        const echarts = await import('echarts');
        if (cancelled || !chartRef.current || !option) return;
        if (instanceRef.current) instanceRef.current.dispose();
        const inst = echarts.init(chartRef.current);
        inst.setOption(option);
        instanceRef.current = inst;
        const ro = new ResizeObserver(() => inst.resize());
        ro.observe(chartRef.current);
        return () => { ro.disconnect(); inst.dispose(); };
      } catch (e) { console.error('ECharts load failed:', e); }
    };
    loadChart();
    return () => { cancelled = true; if (instanceRef.current) { instanceRef.current.dispose(); instanceRef.current = null; } };
  }, [option]);

  if (!trendData?.points?.length) {
    return <div style={{ background: '#fff', borderRadius: 8, border: '1px solid #e5e7eb', padding: 16, minHeight: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 13 }}>No trend data available.</div>;
  }

  const label = trendData.comparableLabel || 'DoD';
  const cur = trendData.currentValue;
  const delta = trendData.currentDeltaPct;
  const peak = trendData.peakLast4;
  const avg = trendData.rollingAverage;

  return (
    <div style={{ background: '#fff', borderRadius: 8, border: '1px solid #e5e7eb', padding: 16, display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div>
          <span style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Trend</span>
          <span style={{ fontSize: 11, color: '#6b7280', marginLeft: 8 }}>{grain === 'day' ? 'Day over day' : grain === 'week' ? 'Week over week' : 'Month over month'}</span>
        </div>
        <div style={{ display: 'flex', gap: 12, fontSize: 11, color: '#6b7280' }}>
          {cur != null && <span>Current: <strong style={{ color: '#111827' }}>{cur.toLocaleString()}</strong></span>}
          {delta != null && <span>{label}: <strong style={{ color: delta >= 0 ? '#16a34a' : '#dc2626' }}>{delta > 0 ? '+' : ''}{delta}%</strong></span>}
          {peak.value != null && <span>{peak.label}: <strong style={{ color: '#f59e0b' }}>{peak.value.toLocaleString()}</strong></span>}
          {avg.value != null && <span>{avg.label}: <strong style={{ color: '#9ca3af' }}>{avg.value.toLocaleString()}</strong></span>}
        </div>
      </div>
      <div ref={chartRef} style={{ flex: 1, minHeight: 180 }} />
    </div>
  );
}

export default TrendLayerPanel;
