export const HISTORICAL_METRICS = [
  {
    key: 'active_drivers',
    label: 'Active Drivers',
    universe: 'official_yango_aligned',
    internal: false,
    supports_history: true,
    supports_city_chart: true,
    default_window_months: 3,
    color: '#60a5fa',
    target_color: '#94a3b8',
    order: 1,
  },
  {
    key: 'supply_hours',
    label: 'Supply Hours',
    universe: 'official_yango_aligned',
    internal: false,
    supports_history: true,
    supports_city_chart: true,
    default_window_months: 3,
    color: '#34d399',
    target_color: '#94a3b8',
    order: 2,
  },
  {
    key: 'operational_flow',
    label: 'Flujo Operativo YEGO',
    universe: 'yego_operational_internal',
    internal: true,
    supports_history: true,
    supports_city_chart: false,
    lima_only: true,
    default_window_months: 3,
    color: '#f59e0b',
    target_color: '#94a3b8',
    order: 3,
  },
]

export const METRIC_UNIVERSES = {
  official_yango_aligned: {
    label: 'Yango-aligned',
    badge_color: 'bg-blue-500/20 text-blue-400',
  },
  yego_operational_internal: {
    label: 'Indicador interno',
    badge_color: 'bg-amber-500/20 text-amber-400',
  },
}

export const HISTORY_CONFIG = {
  default_months: 3,
  max_months: 12,
  lazy_load: true,
}
