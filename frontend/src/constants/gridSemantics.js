/**
 * Semántica visual unificada para grillas — YEGO Control Tower.
 * Usar en todas las vistas que muestren tablas: Real LOB, Driver Lifecycle, Supply, Core, Plan Tabs.
 * Ref: docs/grid_system_audit_and_standards.md, docs/comparative_semantics_audit.md
 */

// —— Nomenclatura comparativa oficial (siempre MoM, WoW, DoD — nunca MOM, WOW, DOD)
export const COMPARATIVE_LABELS = {
  MoM: 'MoM',
  WoW: 'WoW',
  DoD: 'DoD',
  /** periodType: 'weekly' | 'monthly' */
  deltaPctLabel (periodType) {
    return periodType === 'weekly' ? 'WoW Δ%' : 'MoM Δ%'
  },
  ppLabel (periodType) {
    return periodType === 'weekly' ? 'WoW pp' : 'MoM pp'
  },
  comparativeTitle (periodType) {
    return periodType === 'weekly'
      ? 'Comparativo WoW (última semana cerrada vs anterior)'
      : 'Comparativo MoM (último mes cerrado vs anterior)'
  },
  /** Para vista diaria: label de columna según baseline (DoD genérico o D-1, WoW, etc.) */
  dailyDeltaPctLabel (baseline) {
    if (!baseline || baseline === 'D-1') return 'DoD Δ%'
    if (baseline === 'same_weekday_previous_week') return 'WoW Δ%'
    if (baseline === 'same_weekday_avg_4w') return 'Avg 4d Δ%'
    return 'Δ%'
  },
  dailyPpLabel () {
    return 'DoD pp'
  }
}

// —— Estados de periodo / dato (Cerrado, Abierto, Parcial, Falta data, Vacío)
export const GRID_ESTADO = {
  CERRADO: { className: 'bg-green-100 text-green-800', label: 'Cerrado', title: 'Periodo cerrado' },
  ABIERTO: { className: 'bg-blue-100 text-blue-800', label: 'Abierto', title: 'Mes/semana en curso (datos parciales)' },
  FALTA_DATA: { className: 'bg-red-100 text-red-800', label: 'Falta data', title: 'Falta data hasta cierre de ayer' },
  VACIO: { className: 'bg-gray-200 text-gray-600', label: 'Vacío', title: 'Sin datos' },
  PARCIAL: { className: 'bg-amber-100 text-amber-800', label: 'Parcial', title: 'Comparativo parcial (periodo abierto)' }
}

export function getEstadoConfig (estado, options = {}) {
  const fallback = options.openAsAbierto ? GRID_ESTADO.ABIERTO : GRID_ESTADO.VACIO
  const config = GRID_ESTADO[estado] || fallback
  const title = options.faltaDataTitle || config.title
  return { ...config, title }
}

// —— Comparativos (WoW / MoM / DoD): positivo, negativo, neutro
export const GRID_COMPARATIVE = {
  positive: { bg: 'bg-green-50', text: 'text-green-700 font-medium', arrow: '↑' },
  negative: { bg: 'bg-red-50', text: 'text-red-700 font-medium', arrow: '↓' },
  neutral: { bg: 'bg-gray-50', text: 'text-gray-600', arrow: '→' }
}

export function getComparativeClass (trend) {
  if (trend === 'up') return GRID_COMPARATIVE.positive
  if (trend === 'down') return GRID_COMPARATIVE.negative
  return GRID_COMPARATIVE.neutral
}

// —— Badges B2B / Segmento
export const GRID_BADGE = {
  segment: 'inline-flex px-2 py-0.5 rounded text-xs font-medium bg-slate-100 text-slate-800',
  b2b: 'inline-flex px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800'
}

// —— Clases base de tabla (estándar)
export const GRID_TABLE = {
  wrapper: 'overflow-x-auto border border-gray-200 rounded-lg',
  table: 'min-w-full divide-y divide-gray-200',
  thead: 'bg-gray-50',
  th: 'px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase',
  thRight: 'px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase',
  tbody: 'bg-white divide-y divide-gray-200',
  td: 'px-3 py-2 text-sm',
  tdRight: 'px-3 py-2 text-sm text-right',
  tdCenter: 'px-3 py-2 text-sm text-center',
  rowHover: 'hover:bg-slate-50',
  drillRowBg: 'bg-slate-50'
}
