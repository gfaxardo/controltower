/**
 * FASE 2D — Claves dimensionales estables para evitar state-leaks y cache collisions.
 * Dimensión (dim) = screenId, country, periodType, drillBy/groupBy, segment, period/dateRange, etc.
 * Regla: si cambia cualquier dim-field => reset drillState + cancelar requests en vuelo.
 */

const DIM_KEYS_ORDER = [
  'screenId',
  'country',
  'periodType',
  'drillBy',
  'groupBy',
  'segment',
  'periodStart',
  'dateFrom',
  'dateTo',
  'city',
  'parkId',
  'alertFilter'
]

/**
 * Serializa un objeto de dimensión con keys en orden determinista.
 * @param {Record<string, unknown>} dimObj - Objeto con campos dimensionales (solo primitivos/string).
 * @returns {string} Clave estable para cache/abort.
 */
export function buildDimKey (dimObj) {
  if (dimObj == null || typeof dimObj !== 'object') return ''
  const ordered = {}
  for (const k of DIM_KEYS_ORDER) {
    if (Object.prototype.hasOwnProperty.call(dimObj, k)) {
      const v = dimObj[k]
      if (v !== undefined && v !== null) ordered[k] = String(v).trim()
    }
  }
  return JSON.stringify(ordered)
}

/**
 * Clave completa para un drill row: dimKey + rowKey (ej. country|period_start).
 * Garantiza que no se reutilice cache de otra dimensión o fila.
 * @param {Record<string, unknown>} dimObj - Objeto dimensional (drillBy, periodType, country, segment, ...).
 * @param {string} rowKey - Identificador de fila (ej. "pe|2026-01-01").
 * @returns {string}
 */
export function buildDrillKey (dimObj, rowKey) {
  const dim = buildDimKey(dimObj)
  const row = (rowKey != null && rowKey !== undefined) ? String(rowKey).trim() : ''
  return row ? `${dim}|${row}` : dim
}
