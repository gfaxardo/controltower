/**
 * ActionContext — FASE 1H.3
 * Muestra contexto operacional y acciones relacionadas cuando se selecciona
 * una ciudad, KPI, slice o alert, sin obligar a navegación manual.
 */
import { useMemo } from 'react'

export default function ActionContext ({
  selection,
  grain,
  onDrill,
  onFilter,
  onNavigate,
  relatedMetrics = [],
}) {
  const context = useMemo(() => {
    if (!selection) return null
    const { cityKey, lineKey, period, kpiKey, lineData, raw } = selection
    const cityParts = cityKey?.split('::') || []
    const city = raw?.city || cityParts[1] || '—'
    const country = cityParts[0] || '—'
    const slice = lineData?.business_slice_name || '—'

    return { city, country, slice, period, kpiKey }
  }, [selection])

  if (!context) return null

  return (
    <div className="rounded-lg border border-blue-100 bg-gradient-to-r from-blue-50 to-white px-3 py-2.5 shadow-sm">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-blue-400">Contexto</span>

        <div className="flex flex-wrap items-center gap-1.5">
          <ContextPill label="País" value={context.country} onClick={() => onFilter?.('country', context.country)} />
          <ContextPill label="Ciudad" value={context.city} onClick={() => onFilter?.('city', context.city)} />
          <ContextPill label="Tajada" value={context.slice} onClick={() => onFilter?.('slice', context.slice)} />
          <ContextPill label="Período" value={context.period} plain />
          {context.kpiKey && (
            <ContextPill label="KPI" value={context.kpiKey?.replace(/_/g, ' ')} plain />
          )}
        </div>

        {selection && onDrill && (
          <button
            type="button"
            onClick={() => onDrill(selection)}
            className="ml-auto px-2.5 py-1 rounded text-[10px] font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-colors"
          >
            Drill
          </button>
        )}

        {relatedMetrics.length > 0 && (
          <div className="w-full flex flex-wrap gap-1 mt-1 pt-1.5 border-t border-blue-100">
            <span className="text-[9px] font-medium text-blue-400 uppercase tracking-wider">Relacionado</span>
            {relatedMetrics.map((m, i) => (
              <span key={i} className="text-[9px] text-gray-600 bg-white border border-gray-200 rounded px-1.5 py-0.5">
                {m.label}: <strong>{m.value}</strong>
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function ContextPill ({ label, value, onClick, plain }) {
  const cls = plain
    ? 'inline-flex items-center gap-0.5 text-[9px] text-gray-500 bg-white border border-gray-150 rounded px-1.5 py-0.5'
    : 'inline-flex items-center gap-0.5 text-[9px] text-blue-700 bg-white border border-blue-200 rounded px-1.5 py-0.5 hover:bg-blue-100 cursor-pointer transition-colors'

  return (
    <span
      className={cls}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {label}: <strong>{value}</strong>
    </span>
  )
}
