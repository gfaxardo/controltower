/**
 * Omniview V2 — Metric Definitions
 * OV2-UI-P1A: Multi-metric foundation.
 *
 * Defines all 7 V1-parity KPIs with their V2 field mappings,
 * formatting, availability status, and color semantics.
 *
 * Backend contract (omniview_v2_matrix_view_model_service.py):
 *   CT_TRIPS_2026: orders, revenue, active_drivers, avg_ticket, trips_per_driver, commission_pct
 *   YANGO_API_RAW: orders, revenue, active_drivers, revenue_per_order, trips_per_driver
 *
 * cancel_rate_pct is NOT available in the V2 backend — disabled until backend adds support.
 */
const OMNIVIEW_V2_METRICS = [
  {
    id: 'orders',
    label: 'Trips',
    shortLabel: 'Trips',
    description: 'Trips completed',
    field: 'trips_completed',
    unit: 'count',
    format: (v) => (v != null ? v.toLocaleString() : 'N/A'),
    valueType: 'integer',
    higherIsBetter: true,
    colorGroup: 'positive',
    grains: ['day', 'week', 'month'],
    available: true,
    isDefault: true,
  },
  {
    id: 'revenue',
    label: 'Revenue',
    shortLabel: 'Rev.',
    description: 'Revenue YEGO net (final)',
    field: 'revenue_yego_final',
    unit: 'PEN',
    format: (v) => (v != null ? `S/ ${v.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : 'N/A'),
    valueType: 'currency',
    higherIsBetter: true,
    colorGroup: 'positive',
    grains: ['day', 'week', 'month'],
    available: true,
    isDefault: false,
  },
  {
    id: 'active_drivers',
    label: 'Drivers',
    shortLabel: 'Cond.',
    description: 'Active drivers (COUNT DISTINCT)',
    field: 'active_drivers',
    unit: 'count',
    format: (v) => (v != null ? v.toLocaleString() : 'N/A'),
    valueType: 'integer',
    higherIsBetter: true,
    colorGroup: 'positive',
    grains: ['day', 'week', 'month'],
    available: true,
    isDefault: false,
  },
  {
    id: 'avg_ticket',
    label: 'Ticket',
    shortLabel: 'Ticket',
    description: 'Average ticket per completed trip',
    field: 'avg_ticket',
    unit: 'PEN',
    format: (v) => (v != null ? `S/ ${v.toFixed(2)}` : 'N/A'),
    valueType: 'decimal',
    higherIsBetter: true,
    colorGroup: 'positive',
    grains: ['day', 'week', 'month'],
    available: true,
    isDefault: false,
  },
  {
    id: 'commission_pct',
    label: 'Commission %',
    shortLabel: '%',
    description: 'Commission rate (revenue / fare)',
    field: 'commission_pct',
    unit: 'pct',
    format: (v) => (v != null ? `${v.toFixed(1)}%` : 'N/A'),
    valueType: 'percent',
    higherIsBetter: false,
    colorGroup: 'neutral',
    grains: ['day', 'week', 'month'],
    available: true,
    isDefault: false,
  },
  {
    id: 'trips_per_driver',
    label: 'TPD',
    shortLabel: 'TPD',
    description: 'Trips per driver',
    field: 'trips_per_driver',
    unit: 'ratio',
    format: (v) => (v != null ? v.toFixed(2) : 'N/A'),
    valueType: 'decimal',
    higherIsBetter: true,
    colorGroup: 'positive',
    grains: ['day', 'week', 'month'],
    available: true,
    isDefault: false,
  },
  {
    id: 'cancel_rate_pct',
    label: 'Cancel %',
    shortLabel: 'Canc.',
    description: 'Cancellation rate',
    field: 'cancelled_trips',
    unit: 'pct',
    format: (v) => (v != null ? `${v.toFixed(1)}%` : 'N/A'),
    valueType: 'percent',
    higherIsBetter: false,
    colorGroup: 'negative',
    grains: ['day', 'week', 'month'],
    available: true,
    disabledReason: null,
    isDefault: false,
  },
];

export function getMetricById(id) {
  return OMNIVIEW_V2_METRICS.find((m) => m.id === id) || OMNIVIEW_V2_METRICS[0];
}

export function getDefaultMetric() {
  return OMNIVIEW_V2_METRICS.find((m) => m.isDefault) || OMNIVIEW_V2_METRICS[0];
}

export function getAvailableMetrics() {
  return OMNIVIEW_V2_METRICS.filter((m) => m.available);
}

export default OMNIVIEW_V2_METRICS;
