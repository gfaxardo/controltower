/**
 * Segmentación semanal de conductores — orden operativo y labels.
 * Orden fijo: dormant, casual, pt, ft, elite, legend (nunca alfabético).
 * Reutilizar en Driver Lifecycle, Supply Dynamics, Migration, filtros, leyendas.
 */

/** Orden operativo de segmentos (claves en minúsculas para comparación). */
export const SEGMENT_ORDER = ['dormant', 'occasional', 'casual', 'pt', 'ft', 'elite', 'legend']

/** Códigos que puede devolver el backend (mayúsculas o mixto). */
export const SEGMENT_ORDER_BACKEND = ['DORMANT', 'OCCASIONAL', 'CASUAL', 'PT', 'FT', 'ELITE', 'LEGEND']

/** Labels y descripciones para UI (fallback si el backend no devuelve config). */
export const SEGMENT_LABELS = {
  DORMANT: { label: 'Dormant', desc: '0 viajes en la semana', order: 1 },
  OCCASIONAL: { label: 'Occasional', desc: '1–4 viajes/semana', order: 2 },
  CASUAL: { label: 'Casual', desc: '1–29 viajes/semana', order: 2 },
  PT: { label: 'PT', desc: '30–59 viajes/semana', order: 3 },
  FT: { label: 'FT', desc: '60–119 viajes/semana', order: 4 },
  ELITE: { label: 'Elite', desc: '120–179 viajes/semana', order: 5 },
  LEGEND: { label: 'Legend', desc: '180+ viajes/semana', order: 6 }
}

/** Descripción corta para tooltip/leyenda (Legend con alias opcional). */
export function getSegmentDescription (segmentCode, options = {}) {
  const key = String(segmentCode || '').toUpperCase()
  const entry = SEGMENT_LABELS[key]
  if (!entry) return segmentCode || '—'
  if (options.legendAlias && key === 'LEGEND') {
    return `${entry.desc}${options.legendAlias ? ` (${options.legendAlias})` : ''}`
  }
  return entry.desc
}

/** Ordenar lista de segmentos por orden operativo (usar priority de API o SEGMENT_LABELS). */
export function sortSegmentsByOrder (segments, getPriority = (s) => SEGMENT_LABELS[s?.segment || s]?.order ?? 99) {
  return [...(segments || [])].sort((a, b) => (getPriority(a) ?? 99) - (getPriority(b) ?? 99))
}

/** Leyenda mínima para mostrar en vistas: array { segment, label, desc }. Orden operativo 7 segmentos (alineado con BD). */
export const SEGMENT_LEGEND_MINIMAL = [
  { segment: 'DORMANT', label: 'Dormant', desc: '0 viajes/semana' },
  { segment: 'OCCASIONAL', label: 'Occasional', desc: '1–4 viajes/semana' },
  { segment: 'CASUAL', label: 'Casual', desc: '5–29 viajes/semana' },
  { segment: 'PT', label: 'PT', desc: '30–59 viajes/semana' },
  { segment: 'FT', label: 'FT', desc: '60–119 viajes/semana' },
  { segment: 'ELITE', label: 'Elite', desc: '120–179 viajes/semana' },
  { segment: 'LEGEND', label: 'Legend', desc: '180+ viajes/semana (Nivel Dios)' }
]
