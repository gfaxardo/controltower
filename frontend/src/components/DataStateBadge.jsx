/**
 * DataStateBadge — Estados de data y de fuente REAL para confianza en el dato.
 * Data: completo, en proceso, faltante.
 * Fuente (canonicalización): canonical, legacy, migrating, data_in_progress, data_missing, source_incomplete.
 * No toca lógica; solo presentación. Uso en KPIs, tablas, cards.
 */
import { SOURCE_STATUS_LABELS, SOURCE_STATUS_CLASSES } from '../constants/sourceStatus'

const STATE_CONFIG = {
  complete: {
    label: 'Completo',
    className: 'bg-green-100 text-green-800 border-green-200',
    title: 'Dato disponible y confiable'
  },
  pending: {
    label: 'En proceso',
    className: 'bg-gray-100 text-gray-600 border-gray-200',
    title: 'Dato aún en proceso de poblado o actualización'
  },
  missing: {
    label: 'Faltante',
    className: 'bg-amber-50 text-amber-800 border-amber-200',
    title: 'Dato faltante o con issue de fuente; no confundir con 0'
  },
  // Fuente REAL (canonicalización)
  canonical: {
    label: SOURCE_STATUS_LABELS.canonical,
    className: SOURCE_STATUS_CLASSES.canonical,
    title: 'Datos desde la cadena canónica hourly-first'
  },
  legacy: {
    label: SOURCE_STATUS_LABELS.legacy,
    className: SOURCE_STATUS_CLASSES.legacy,
    title: 'Datos desde fuente legacy; migración pendiente'
  },
  migrating: {
    label: SOURCE_STATUS_LABELS.migrating,
    className: SOURCE_STATUS_CLASSES.migrating,
    title: 'Esta pantalla se está migrando a la fuente canónica'
  },
  data_in_progress: {
    label: SOURCE_STATUS_LABELS.data_in_progress,
    className: SOURCE_STATUS_CLASSES.data_in_progress,
    title: 'Datos en proceso de poblado'
  },
  data_missing: {
    label: SOURCE_STATUS_LABELS.data_missing,
    className: SOURCE_STATUS_CLASSES.data_missing,
    title: 'Sin datos para este periodo; no confundir con 0'
  },
  source_incomplete: {
    label: SOURCE_STATUS_LABELS.source_incomplete,
    className: SOURCE_STATUS_CLASSES.source_incomplete,
    title: 'Algunos valores pueden no cargar'
  },
  under_review: {
    label: SOURCE_STATUS_LABELS.under_review,
    className: SOURCE_STATUS_CLASSES.under_review,
    title: 'Pantalla en revisión; no considerar datos como definitivos'
  }
}

function DataStateBadge ({ state = 'complete', label: customLabel, className: extraClass = '', title: customTitle }) {
  const config = STATE_CONFIG[state] || STATE_CONFIG.complete
  const label = customLabel ?? config.label
  const title = customTitle ?? config.title

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${config.className} ${extraClass}`}
      title={title}
    >
      {label}
    </span>
  )
}

export default DataStateBadge
export { STATE_CONFIG }
