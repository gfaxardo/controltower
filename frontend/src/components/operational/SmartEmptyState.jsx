/**
 * SmartEmptyState — FASE 1H.3
 * Estado vacío inteligente: muestra qué falta, por qué falta, y remediation.
 * NO muestra loaders infinitos.
 */
import { useMemo } from 'react'

const EMPTY_KINDS = {
  no_data: {
    icon: 'M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4',
    border: 'border-gray-300',
    bg: 'bg-gray-50/70',
    title: 'Sin datos disponibles',
    defaultMsg: 'No hay datos con los filtros actuales.',
    defaultAction: 'Ajusta los filtros o cambia el grano temporal.',
  },
  needs_filter: {
    icon: 'M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z',
    border: 'border-amber-300',
    bg: 'bg-amber-50/70',
    title: 'Filtro requerido',
    defaultMsg: 'Selecciona los filtros necesarios para ver los datos.',
    defaultAction: 'Completa los filtros marcados con *.',
  },
  loading_failed: {
    icon: 'M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z',
    border: 'border-red-300',
    bg: 'bg-red-50/70',
    title: 'Error al cargar',
    defaultMsg: 'No se pudieron cargar los datos.',
    defaultAction: 'Reintenta o verifica la conexión con el servidor.',
  },
  empty_result: {
    icon: 'M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z',
    border: 'border-blue-300',
    bg: 'bg-blue-50/70',
    title: 'Sin resultados',
    defaultMsg: 'La búsqueda no encontró resultados para estos filtros.',
    defaultAction: 'Prueba con filtros más amplios o cambia el grano.',
  },
  not_configured: {
    icon: 'M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 010 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 010-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28z',
    border: 'border-purple-300',
    bg: 'bg-purple-50/70',
    title: 'No configurado',
    defaultMsg: 'Esta funcionalidad requiere configuración adicional.',
    defaultAction: 'Contacta al administrador del sistema.',
  },
}

export default function SmartEmptyState ({
  kind = 'no_data',
  title,
  message,
  actionLabel,
  actionHint,
  onAction,
  children,
  className = '',
}) {
  const kindDef = EMPTY_KINDS[kind] || EMPTY_KINDS.no_data
  const displayTitle = title || kindDef.title
  const displayMsg = message || kindDef.defaultMsg
  const displayHint = actionHint || kindDef.defaultAction

  return (
    <div className={`rounded-lg border border-dashed ${kindDef.border} ${kindDef.bg} px-6 py-8 text-center flex flex-col items-center gap-3 ${className}`}>
      <div className="w-12 h-12 rounded-full bg-white/80 flex items-center justify-center shadow-sm">
        <svg className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d={kindDef.icon} />
        </svg>
      </div>
      <div>
        <p className="text-sm font-semibold text-gray-700">{displayTitle}</p>
        <p className="mt-1 text-xs text-gray-500 max-w-sm mx-auto">{displayMsg}</p>
        {displayHint && <p className="mt-1.5 text-xs text-gray-400 max-w-sm mx-auto">{displayHint}</p>}
      </div>
      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="px-4 py-1.5 rounded-md text-xs font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-colors shadow-sm"
        >
          {actionLabel}
        </button>
      )}
      {children}
    </div>
  )
}
