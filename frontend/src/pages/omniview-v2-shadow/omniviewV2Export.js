/**
 * Omniview V2 — CSV Export Engine
 * OV2-UI-P1C: Ports safe patterns from V1 omniviewExport.js.
 *
 * Exports current V2 matrix view to CSV.
 * No backend calls. No recalculation. No raw/PII data.
 * Uses formula injection protection and safe escaping.
 */

// ─── Helpers (ported from V1, generic) ──────────────────────────────

function csvEscape(v) {
  let s = String(v === null || v === undefined ? '' : v);
  if (/^[=+@\t\r]/.test(s) || /^-(?![\d.])/.test(s)) {
    s = "'" + s;
  }
  if (s.includes(',') || s.includes('"') || s.includes('\n') || s.includes('\r')) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

function csvRow(cells) {
  return cells.map(csvEscape).join(',');
}

function csvSection(title, columns, rows) {
  const lines = [];
  lines.push('');
  lines.push('# ' + title);
  lines.push(csvRow(columns));
  for (const row of rows) {
    lines.push(csvRow(row));
  }
  return lines.join('\n');
}

function timestamp() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function safeFilename(metricId, grain) {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, '0');
  const dateStr = `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}_${pad(d.getHours())}${pad(d.getMinutes())}`;
  return `omniview_v2_${grain}_${metricId}_${dateStr}.csv`;
}

// ─── Section builders ───────────────────────────────────────────────

function buildMetadataSection({ metric, grain, filters, viewMode, canonicalReady, freshness, operatingDate, metadata, cells, activePreset }) {
  const rows = [
    ['export_generated_at', timestamp()],
    ['product', 'Omniview V2'],
    ['grain', grain],
    ['selected_metric_id', metric?.id || 'orders'],
    ['selected_metric_label', metric?.label || 'Trips'],
    ['selected_metric_unit', metric?.unit || 'count'],
    ['selected_metric_polarity', metric?.higherIsBetter ? 'higherIsBetter' : 'lowerIsBetter'],
    ['view_mode', viewMode || 'real'],
    ['country', filters?.country || 'peru'],
    ['city', filters?.city || 'lima'],
    ['business_slice', filters?.businessSlice || '(all)'],
    ['park_id', filters?.parkId || '(all)'],
    ['date_from', filters?.dateFrom || ''],
    ['date_to', filters?.dateTo || ''],
    ['active_period_preset', activePreset || 'custom'],
    ['source_system', metadata?.source_system || 'CT_TRIPS_2026'],
    ['canonical_ready', canonicalReady ? 'true' : 'false'],
    ['freshness_status', freshness || 'unknown'],
    ['row_count', metadata?.row_count || cells?.length || 0],
    ['column_count', metadata?.column_count || 0],
  ];
  if (operatingDate) {
    rows.push(['latest_closed_date', operatingDate.latest_closed_date || '']);
    rows.push(['operating_date_status', operatingDate.freshness_status || '']);
  }
  return csvSection('Metadata', ['Key', 'Value'], rows);
}

function buildMatrixSection({ columns, rows: matrixRows, cells, grain, metricId }) {
  if (!columns || !rows || !cells) return '';

  // Build lookup: (rowId, columnId) -> cell
  const cellMap = {};
  for (const c of cells) {
    cellMap[c.row_id + '|' + c.column_id] = c;
  }

  // Wide format: row_label | col1_period | col2_period | ...
  const header = ['Business Slice', ...columns.map((c) => c.period || c.label || c.id)];
  const dataRows = matrixRows.map((r) => {
    const values = [r.label || r.id];
    for (const col of columns) {
      const cell = cellMap[r.id + '|' + col.id];
      if (!cell || cell.value == null) {
        values.push('N/A');
      } else {
        values.push(cell.formatted_value || String(cell.value));
      }
    }
    return values;
  });

  const parts = [];
  parts.push(csvSection('Matrix (wide)', header, dataRows));

  // Long format: row_label | period | value | formatted | delta | delta_pct | cell_status
  const longHeader = ['Business Slice', 'Period', 'Value', 'Formatted', 'Delta', 'Delta %', 'Status'];
  const longRows = [];
  for (const r of matrixRows) {
    for (const col of columns) {
      const cell = cellMap[r.id + '|' + col.id];
      longRows.push([
        r.label || r.id,
        col.period || col.label || col.id,
        cell?.value != null ? String(cell.value) : 'N/A',
        cell?.formatted_value || (cell?.value != null ? String(cell.value) : 'N/A'),
        cell?.delta_value != null ? String(cell.delta_value) : '',
        cell?.delta_pct != null ? String(cell.delta_pct) : '',
        cell?.cell_status || 'OK',
      ]);
    }
  }
  parts.push(csvSection('Matrix (long)', longHeader, longRows));

  return parts.join('\n');
}

function buildFreshnessSection({ freshness, coverage, canonicalReady }) {
  const rows = [];
  if (freshness) rows.push(['freshness_status', freshness]);
  if (coverage != null) rows.push(['coverage_pct', String(coverage)]);
  if (canonicalReady != null) rows.push(['canonical_ready', canonicalReady ? 'true' : 'false']);
  if (rows.length === 0) return '';
  return csvSection('Freshness & Governance', ['Key', 'Value'], rows);
}

// ─── Main export function ───────────────────────────────────────────

export function exportOmniviewV2Csv({
  matrixData,
  metric,
  grain,
  filters,
  viewMode,
  canonicalReady,
  freshness,
  operatingDate,
  coverage,
  activePreset,
}) {
  if (!matrixData || !matrixData.cells || matrixData.cells.length === 0) {
    throw new Error('No matrix data available for export.');
  }

  const sections = [
    buildMetadataSection({
      metric,
      grain,
      filters,
      viewMode,
      canonicalReady,
      freshness,
      operatingDate,
      metadata: matrixData.metadata,
      cells: matrixData.cells,
      activePreset,
    }),
    buildFreshnessSection({ freshness, coverage, canonicalReady }),
    buildMatrixSection({
      columns: matrixData.columns || [],
      rows: matrixData.rows || [],
      cells: matrixData.cells,
      grain,
      metricId: metric?.id || 'orders',
    }),
  ];

  const csv = sections.filter(Boolean).join('\n');

  const filename = safeFilename(metric?.id || 'orders', grain);
  const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);

  return { ok: true, filename };
}
