function makeCell(rowId, columnId, overrides = {}) {
  return {
    row_id: rowId,
    column_id: columnId,
    metric_id: overrides.metric_id || 'orders',
    label: overrides.label || 'Orders Completed',
    slice_id: null,
    slice_label: null,
    value: overrides.value != null ? overrides.value : 14213,
    formatted_value: overrides.formatted_value || '',
    unit: overrides.unit || 'count',
    source_system: overrides.source_system || 'CT_TRIPS_2026',
    source_table: overrides.source_table || 'ops.real_business_slice_day_fact',
    grain: overrides.grain || 'day',
    period: overrides.period || '2026-06-04',
    period_status: overrides.period_status || 'CLOSED',
    canonical_ready: overrides.canonical_ready != null ? overrides.canonical_ready : true,
    coverage_pct: overrides.coverage_pct != null ? overrides.coverage_pct : 100,
    freshness: overrides.freshness || 'Updated 5m ago',
    confidence: overrides.confidence || 'HIGH',
    is_estimated: overrides.is_estimated || false,
    warning_codes: overrides.warning_codes || [],
    lineage_refs: overrides.lineage_refs || {
      origin_table: 'ops.real_business_slice_day_fact',
      origin_field: 'trips_completed',
      aggregation: 'SUM',
      filters_applied: { country: 'peru', city: 'lima' },
    },
    comparison_status: overrides.comparison_status || null,
    delta_value: overrides.delta_value || null,
    delta_pct: overrides.delta_pct || null,
    cell_status: overrides.cell_status || 'OK',
  };
}

function generateDateColumns(count, startDate, grain) {
  const cols = [];
  const base = new Date(startDate);
  for (let i = 0; i < count; i++) {
    const d = new Date(base);
    if (grain === 'day') d.setDate(d.getDate() + i);
    else if (grain === 'week') d.setDate(d.getDate() + i * 7);
    else if (grain === 'month') d.setMonth(d.getMonth() + i);

    const period = d.toISOString().slice(0, 10);
    const isFuture = d > new Date();
    const isCurrent = d.toISOString().slice(0, 10) === '2026-06-05';

    let label;
    if (grain === 'day') label = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    else if (grain === 'week') label = `W${Math.ceil(d.getDate() / 7)}`;
    else label = d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });

    cols.push({
      id: `col_${period}`,
      label,
      grain,
      period,
      period_status: isFuture ? 'FUTURE' : isCurrent ? 'PARTIAL' : 'CLOSED',
      sort_key: period,
      width: grain === 'hour' ? 70 : grain === 'day' ? 90 : 100,
      is_current: isCurrent,
      is_future: isFuture,
    });
  }
  return cols;
}

const SLICES = [
  { id: 'row_auto_regular', label: 'Auto regular', row_status: 'OK' },
  { id: 'row_yma', label: 'YMA', row_status: 'OK' },
  { id: 'row_tuk_tuk', label: 'Tuk Tuk', row_status: 'WARNING' },
  { id: 'row_pro', label: 'PRO', row_status: 'OK' },
  { id: 'row_delivery', label: 'Delivery', row_status: 'OK' },
  { id: 'row_carga', label: 'Carga', row_status: 'BLOCKED' },
];

function generateRows() {
  return SLICES.map((s, i) => ({
    id: s.id,
    label: s.label,
    row_type: 'slice',
    row_status: s.row_status,
    parent_id: null,
    depth: 0,
    sort_key: String(i).padStart(2, '0') + '_' + s.id,
    is_expandable: false,
    is_expanded: true,
  }));
}

const baseRevenue = 1000;
const baseDrivers = 300;
const baseOrders = 2400;

function randomAround(base, variance = 0.15) {
  return Math.round(base * (1 + (Math.random() - 0.5) * 2 * variance));
}

export function mockCTDay() {
  const cols = generateDateColumns(7, '2026-06-01', 'day');
  const rows = generateRows();
  const cells = [];

  rows.forEach((row) => {
    cols.forEach((col) => {
      const isFuture = col.period_status === 'FUTURE';
      const periodDate = col.period;
      const dayOffset = (new Date(periodDate) - new Date('2026-06-01')) / 86400000;

      let status = row.row_status === 'BLOCKED' ? 'BLOCKED' :
        row.row_status === 'WARNING' && dayOffset > 4 ? 'WARNING' : 'OK';

      if (isFuture) status = 'NOT_COMPARABLE';

      const ordersVal = isFuture ? null : randomAround(baseOrders + dayOffset * 100);

      cells.push(makeCell(row.id, col.id, {
        metric_id: 'orders',
        label: 'Orders Completed',
        value: ordersVal,
        formatted_value: ordersVal != null ? ordersVal.toLocaleString() : '—',
        unit: 'count',
        grain: 'day',
        period: periodDate,
        period_status: col.period_status,
        canonical_ready: true,
        coverage_pct: isFuture ? 0 : (row.row_status === 'BLOCKED' ? 0 : 100),
        cell_status: status,
      }));
    });
  });

  return {
    matrix_id: 'ov2_ct_day',
    source_system: 'CT_TRIPS_2026',
    canonical_ready: true,
    grain: 'day',
    period_range: { from: '2026-06-01', to: '2026-06-07' },
    filters: { country: 'peru', city: 'lima' },
    metadata: {
      source_status: 'CURRENT_BASELINE',
      source_table: 'ops.real_business_slice_day_fact',
      coverage_pct: 100,
      freshness: 'Updated 5m ago',
      data_date: '2026-06-05',
      refreshed_at: '2026-06-06T12:00:00Z',
      row_count: rows.length,
      column_count: cols.length,
      cell_count: rows.length * cols.length,
      comparable: true,
      comparison_basis: null,
    },
    columns: cols,
    rows,
    cells,
    warnings: [],
    lineage: [
      { metric_id: 'orders', origin_table: 'ops.real_business_slice_day_fact', origin_field: 'trips_completed', aggregation: 'SUM', filters_applied: { country: 'peru', city: 'lima' } },
    ],
  };
}

export function mockCTWeek() {
  const cols = generateDateColumns(12, '2026-04-01', 'week');
  const rows = generateRows();
  const cells = [];

  rows.forEach((row) => {
    cols.forEach((col) => {
      const ordersVal = col.period_status === 'FUTURE' ? null : randomAround(baseOrders * 7);
      cells.push(makeCell(row.id, col.id, {
        metric_id: 'orders',
        value: ordersVal,
        formatted_value: ordersVal != null ? ordersVal.toLocaleString() : '—',
        grain: 'week',
        period: col.period,
        period_status: col.period_status,
        cell_status: row.row_status === 'BLOCKED' ? 'BLOCKED' : 'OK',
      }));
    });
  });

  return {
    matrix_id: 'ov2_ct_week',
    source_system: 'CT_TRIPS_2026',
    canonical_ready: true,
    grain: 'week',
    period_range: { from: '2026-04-01', to: '2026-06-18' },
    filters: { country: 'peru', city: 'lima' },
    metadata: {
      source_status: 'CURRENT_BASELINE',
      source_table: 'ops.real_business_slice_week_fact',
      coverage_pct: 100,
      freshness: 'Updated 1h ago',
      data_date: '2026-06-05',
      refreshed_at: '2026-06-06T11:00:00Z',
      row_count: rows.length,
      column_count: cols.length,
      cell_count: rows.length * cols.length,
      comparable: false,
    },
    columns: cols,
    rows,
    cells,
    warnings: [],
    lineage: [],
  };
}

export function mockCTMonth() {
  const cols = generateDateColumns(12, '2025-07-01', 'month');
  const rows = generateRows();
  const cells = [];

  rows.forEach((row) => {
    cols.forEach((col) => {
      const ordersVal = col.period_status === 'FUTURE' ? null : randomAround(baseOrders * 30);
      cells.push(makeCell(row.id, col.id, {
        metric_id: 'orders',
        value: ordersVal,
        formatted_value: ordersVal != null ? ordersVal.toLocaleString() : '—',
        grain: 'month',
        period: col.period,
        period_status: col.period_status,
        cell_status: row.row_status === 'BLOCKED' ? 'BLOCKED' : 'OK',
      }));
    });
  });

  return {
    matrix_id: 'ov2_ct_month',
    source_system: 'CT_TRIPS_2026',
    canonical_ready: true,
    grain: 'month',
    period_range: { from: '2025-07-01', to: '2026-06-01' },
    filters: { country: 'peru', city: 'lima' },
    metadata: {
      source_status: 'CURRENT_BASELINE',
      source_table: 'ops.real_business_slice_month_fact',
      coverage_pct: 100,
      freshness: 'Updated 2h ago',
      data_date: '2026-06-01',
      refreshed_at: '2026-06-06T10:00:00Z',
      row_count: rows.length,
      column_count: cols.length,
      cell_count: rows.length * cols.length,
      comparable: false,
    },
    columns: cols,
    rows,
    cells,
    warnings: [],
    lineage: [],
  };
}

export function mockYangoDay() {
  const cols = generateDateColumns(5, '2026-06-03', 'day');
  const rows = [
    { id: 'row_lima_fleet', label: 'Lima Fleet', row_type: 'slice', row_status: 'WARNING', parent_id: null, depth: 0, sort_key: '00_lima', is_expandable: false, is_expanded: true },
  ];
  const cells = [];

  rows.forEach((row) => {
    cols.forEach((col, i) => {
      const isFuture = col.period_status === 'FUTURE';
      const ordersVal = isFuture ? null : randomAround(9500 + i * 200);

      cells.push(makeCell(row.id, col.id, {
        metric_id: 'orders',
        label: 'Orders Completed',
        value: ordersVal,
        formatted_value: ordersVal != null ? ordersVal.toLocaleString() : '—',
        unit: 'count',
        source_system: 'YANGO_API_RAW',
        source_table: 'raw_yango.mv_orders_day',
        grain: 'day',
        period: col.period,
        period_status: col.period_status,
        canonical_ready: false,
        coverage_pct: isFuture ? 0 : 100,
        confidence: 'MEDIUM',
        warning_codes: ['CANONICAL_NOT_READY', 'API_COVERAGE_WARNING'],
        cell_status: 'WARNING',
      }));
    });
  });

  return {
    matrix_id: 'ov2_yango_day',
    source_system: 'YANGO_API_RAW',
    canonical_ready: false,
    grain: 'day',
    period_range: { from: '2026-06-03', to: '2026-06-07' },
    filters: { park_id: '08e20910***' },
    metadata: {
      source_status: 'FUTURE_CANDIDATE',
      source_table: 'raw_yango.mv_orders_day',
      coverage_pct: 100,
      freshness: 'Updated 10m ago',
      data_date: '2026-06-05',
      refreshed_at: '2026-06-06T12:05:00Z',
      row_count: rows.length,
      column_count: cols.length,
      cell_count: rows.length * cols.length,
      comparable: true,
      comparison_basis: 'CT_TRIPS_2026',
    },
    columns: cols,
    rows,
    cells,
    warnings: [
      { code: 'CANONICAL_NOT_READY', message: 'Source is NOT certified for operational decisions.', severity: 'critical', target_row_id: 'row_lima_fleet' },
      { code: 'API_COVERAGE_WARNING', message: 'API coverage ~98.88% for orders.', severity: 'warning' },
    ],
    lineage: [
      { metric_id: 'orders', origin_table: 'raw_yango.mv_orders_day', origin_field: 'orders_completed', aggregation: 'SUM', filters_applied: { park_id: '08e20910***' } },
    ],
  };
}

export function mockWarnings() {
  const data = mockCTDay();
  data.warnings = [
    { code: 'PARTIAL_COVERAGE', message: 'Coverage at 87% for Jun 4.', severity: 'warning', target_column_id: 'col_2026-06-04', affected_cell_count: 3 },
    { code: 'REVENUE_DELTA', message: 'Revenue delta vs CT is -78.46%.', severity: 'warning', target_row_id: 'row_carga' },
    { code: 'SHORT_SERIES', message: 'Only 2 days of data. Minimum 7 recommended.', severity: 'warning' },
  ];

  const cargaRow = data.rows.find((r) => r.id === 'row_carga');
  if (cargaRow) cargaRow.row_status = 'BLOCKED';

  data.cells.forEach((cell) => {
    if (cell.row_id === 'row_carga' && cell.column_id === 'col_2026-06-04') {
      cell.cell_status = 'BLOCKED';
      cell.warning_codes = ['REVENUE_DELTA'];
    }
    if (cell.column_id === 'col_2026-06-04') {
      cell.coverage_pct = 87;
    }
  });

  return data;
}

export function mockCompareMode() {
  const data = mockCTDay();
  data.metadata.comparable = true;
  data.metadata.comparison_basis = 'YANGO_API_RAW';
  data.cells.forEach((cell, i) => {
    if (cell.cell_status === 'OK' && i % 3 === 0) {
      cell.comparison_status = 'MATCH';
      cell.delta_pct = 1.2;
    } else if (i % 3 === 1) {
      cell.comparison_status = 'MINOR_DELTA';
      cell.delta_value = -45;
      cell.delta_pct = -3.7;
    } else if (i % 3 === 2 && cell.cell_status === 'OK') {
      cell.comparison_status = 'MAJOR_DELTA';
      cell.delta_value = -350;
      cell.delta_pct = -12.5;
    }
  });
  return data;
}

export const ALL_MOCKS = {
  'CT_TRIPS_2026_day': mockCTDay,
  'CT_TRIPS_2026_week': mockCTWeek,
  'CT_TRIPS_2026_month': mockCTMonth,
  'YANGO_API_RAW_day': mockYangoDay,
  'warnings': mockWarnings,
  'compare': mockCompareMode,
};
