/**
 * Estados de fuente REAL para señales en UI (canonicalización).
 * Evitar confundir: cero real vs dato no poblado vs feature no migrada.
 */
export const SOURCE_STATUS = {
  canonical: 'canonical',
  legacy: 'legacy',
  migrating: 'migrating',
  data_in_progress: 'data_in_progress',
  data_missing: 'data_missing',
  source_incomplete: 'source_incomplete',
  under_review: 'under_review'
}

export const SOURCE_STATUS_LABELS = {
  [SOURCE_STATUS.canonical]: 'Fuente canónica',
  [SOURCE_STATUS.legacy]: 'Fuente legacy',
  [SOURCE_STATUS.migrating]: 'Migrando a fuente canónica',
  [SOURCE_STATUS.data_in_progress]: 'Datos en proceso de poblado',
  [SOURCE_STATUS.data_missing]: 'Sin datos para este periodo',
  [SOURCE_STATUS.source_incomplete]: 'Vista temporalmente limitada',
  [SOURCE_STATUS.under_review]: 'En revisión'
}

/** Colores: canonical=verde, migrating/legacy=ámbar, data_*=gris, source_incomplete/under_review=rojo */
export const SOURCE_STATUS_CLASSES = {
  [SOURCE_STATUS.canonical]: 'bg-green-100 text-green-800 border-green-200',
  [SOURCE_STATUS.legacy]: 'bg-amber-50 text-amber-800 border-amber-200',
  [SOURCE_STATUS.migrating]: 'bg-amber-50 text-amber-800 border-amber-200',
  [SOURCE_STATUS.data_in_progress]: 'bg-gray-100 text-gray-600 border-gray-200',
  [SOURCE_STATUS.data_missing]: 'bg-gray-100 text-gray-600 border-gray-200',
  [SOURCE_STATUS.source_incomplete]: 'bg-red-50 text-red-800 border-red-200',
  [SOURCE_STATUS.under_review]: 'bg-red-50 text-red-800 border-red-200'
}

export function getSourceLabel (status) {
  return SOURCE_STATUS_LABELS[status] || status || 'Fuente'
}

export function getSourceClass (status) {
  return SOURCE_STATUS_CLASSES[status] || 'bg-gray-100 text-gray-700 border-gray-200'
}
