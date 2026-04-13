import { useState } from 'react'
import { MATRIX_KPIS } from './omniviewMatrixUtils.js'

/**
 * Texto de ayuda: origen de datos y KPIs (Omniview Matrix / Reportes).
 */
export default function OmniviewDataHelp ({ className = '' }) {
  const [open, setOpen] = useState(false)
  return (
    <div className={`rounded-lg border border-slate-200 bg-slate-50/80 text-slate-700 ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-600 hover:bg-slate-100/80 rounded-lg"
      >
        <span>¿Qué significan estos números?</span>
        <span className="text-slate-400" aria-hidden>{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 pt-0 space-y-2 text-xs leading-relaxed border-t border-slate-200/80">
          <p>
            <strong>Origen:</strong> los valores vienen de la capa operativa <strong>Business Slice</strong> (viajes reales
            clasificados por reglas de negocio), agregados en tablas fact en Postgres y expuestos por la API{' '}
            <code className="text-[10px] bg-white px-1 rounded border">/ops/business-slice/monthly|weekly|daily</code>.
            No mezclan datos de Plan.
          </p>
          <p>
            <strong>KPIs:</strong> el backend devuelve sumas y medias ponderadas por período y dimensión (país, ciudad,
            tajada, flota/subflota). En la tabla, la matriz solo <em>organiza</em> esas cifras; no recalcula totales.
          </p>
          <ul className="list-disc pl-4 space-y-0.5">
            {MATRIX_KPIS.map((k) => (
              <li key={k.key}>
                <strong>{k.label}</strong> ({k.key}): {k.unit === 'ratio' && k.showAsPct ? 'ratio 0–1 mostrado como % donde aplica' : `unidad: ${k.unit}`}
              </li>
            ))}
          </ul>
          <p>
            <strong>Comparativos:</strong> dependen del <strong>grano</strong> — mensual (vs mes anterior o equivalente
            parcial), semanal (vs semana ISO anterior), diario (vs mismo día de la semana previa). El motor de estados y
            el contexto de comparación vienen en <code className="text-[10px] bg-white px-1 rounded border">meta</code> y en cada fila cuando aplica.
          </p>
        </div>
      )}
    </div>
  )
}
