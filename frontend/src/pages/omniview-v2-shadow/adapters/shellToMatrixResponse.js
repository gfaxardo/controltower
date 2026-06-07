/**
 * TEMPORARY adapter: converts Omniview V2 Shell response into MatrixResponse.
 *
 * This adapter bridges the gap between the current Shell API (which returns
 * section-based data) and the MatrixZone (which expects MatrixResponse).
 *
 * It will be REMOVED when the backend /matrix endpoint is fully implemented
 * and returns native MatrixResponse (OV2-C.3A contract).
 *
 * Rules:
 * - No business calculations
 * - No contract duplication
 * - Pure visual mapping
 * - Documented as TEMPORARY
 */

function shellToMatrixResponse(shellData, metricId = 'orders') {
  if (!shellData) return null;

  const kpiStrip = shellData.sections?.find((s) => s.section_id === 'kpi_strip');
  const kpis = kpiStrip?.kpis || [];

  const targetKpi = kpis.find((k) => k.metric_id === metricId) || kpis[0];
  if (!targetKpi) return { metadata: { row_count: 0, column_count: 0, cell_count: 0 }, columns: [], rows: [], cells: [] };

  const period = shellData.period || {};
  const dateFrom = period.from || '';
  const dateTo = period.to || '';

  const columns = [];
  if (dateFrom && dateTo) {
    const from = new Date(dateFrom);
    const to = new Date(dateTo);
    const dayMs = 86400000;
    const diffDays = Math.min(Math.round((to - from) / dayMs) + 1, 30);

    for (let i = 0; i < diffDays; i++) {
      const d = new Date(from.getTime() + i * dayMs);
      const periodStr = d.toISOString().slice(0, 10);
      const isFuture = d > new Date();
      const month = d.toLocaleDateString('en-US', { month: 'short' });
      const day = d.getDate();
      columns.push({
        id: `col_${periodStr}`,
        label: `${month} ${day}`,
        grain: shellData.grain || 'day',
        period: periodStr,
        period_status: isFuture ? 'FUTURE' : 'PARTIAL',
        sort_key: periodStr,
        width: 90,
        is_current: false,
        is_future: isFuture,
      });
    }
  } else {
    columns.push({
      id: 'col_current',
      label: 'Current',
      grain: shellData.grain || 'day',
      period: dateFrom || 'today',
      period_status: 'CURRENT',
      sort_key: dateFrom || 'today',
      width: 90,
      is_current: true,
      is_future: false,
    });
  }

  const rows = [
    {
      id: 'row_kpi',
      label: targetKpi.label || targetKpi.metric_id,
      row_type: 'metric',
      row_status: 'OK',
      depth: 0,
      sort_key: '00_kpi',
      is_expandable: false,
      is_expanded: true,
    },
  ];

  const cells = [];
  columns.forEach((col) => {
    cells.push({
      row_id: 'row_kpi',
      column_id: col.id,
      metric_id: targetKpi.metric_id,
      label: targetKpi.label,
      value: targetKpi.value,
      formatted_value: targetKpi.value != null ? Number(targetKpi.value).toLocaleString('en-US') : '\u2014',
      unit: targetKpi.unit || 'count',
      source_system: shellData.source_system,
      source_table: targetKpi.lineage?.origin_table || '',
      grain: shellData.grain || 'day',
      period: col.period,
      period_status: col.period_status,
      canonical_ready: shellData.canonical_ready,
      coverage_pct: shellData.coverage?.coverage_pct || 100,
      freshness: shellData.freshness?.last_refreshed_at || '',
      confidence: targetKpi.confidence || 'MEDIUM',
      is_estimated: targetKpi.is_estimated || false,
      warning_codes: targetKpi.warning_codes || [],
      lineage_refs: targetKpi.lineage || {},
      comparison_status: null,
      delta_value: null,
      delta_pct: null,
      cell_status: targetKpi.value != null ? 'OK' : 'BLOCKED',
    });
  });

  const allWarnings = [];
  shellData.sections?.forEach((sec) => {
    (sec.warnings || []).forEach((w) => {
      allWarnings.push({
        code: w.code || 'UNKNOWN',
        message: w.message || '',
        severity: w.severity || 'warning',
        target_row_id: null,
        target_column_id: null,
        affected_cell_count: 1,
      });
    });
  });

  return {
    matrix_id: 'ov2_shell',
    source_system: shellData.source_system,
    canonical_ready: shellData.canonical_ready,
    grain: shellData.grain || 'day',
    period_range: { from: dateFrom, to: dateTo },
    filters: shellData.filters || {},
    metadata: {
      source_status: shellData.source_status || 'UNKNOWN',
      source_table: targetKpi.lineage?.origin_table || '',
      coverage_pct: shellData.coverage?.coverage_pct || 100,
      freshness: shellData.freshness?.last_refreshed_at || '',
      data_date: dateTo || dateFrom || '',
      refreshed_at: shellData.generated_at || '',
      row_count: rows.length,
      column_count: columns.length,
      cell_count: cells.length,
      comparable: false,
    },
    columns,
    rows,
    cells,
    warnings: allWarnings,
    lineage: (kpis || []).map((k) => ({
      metric_id: k.metric_id,
      origin_table: k.lineage?.origin_table || '',
      origin_field: k.lineage?.origin_field || '',
      aggregation: k.lineage?.aggregation || 'SUM',
      filters_applied: k.lineage?.filters_applied || {},
    })),
  };
}

export default shellToMatrixResponse;
