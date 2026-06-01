/**
 * OperationalPriorityLayer.jsx
 *
 * RC-1: Capa de prioridad operacional encima de Omniview Matrix.
 *
 * OBJETIVO: Responder en 2 segundos "¿Dónde debe mirar primero el operador?"
 *
 * Muestra:
 *   - Top 3 deterioros (▼ críticas)
 *   - Top 3 mejoras     (▲ oportunidades)
 *
 * Derivado de: displayProjMatrix (datos ya cargados en memoria)
 * Sin nuevas llamadas API. Sin AI. Sin recomendaciones.
 *
 * Motor: Control Foundation — Priority Layer
 */

import { useMemo } from 'react'
import { computeOperationalPriorities } from '../../../utils/operationalPriorityEngine.js'
import { fmtValue } from '../omniviewMatrixUtils.js'
import { getMomentumSeverityColor } from '../../../utils/operationalMomentumEmphasis.js'

const KPI_LABEL = {
  trips_completed: 'Viajes',
  revenue_yego_net: 'Revenue',
  active_drivers: 'Conductores',
  avg_ticket: 'Ticket',
  trips_per_driver: 'TPD',
}

export default function OperationalPriorityLayer({
  projMatrix,
  focusedKpi,
  grain,
  compact = false,
  onCellNavigate,
}) {
  const priorities = useMemo(() => {
    if (!projMatrix) return { deteriorations: [], improvements: [] }
    return computeOperationalPriorities(projMatrix, focusedKpi, grain)
  }, [projMatrix, focusedKpi, grain])

  const { deteriorations, improvements } = priorities
  const hasAny = deteriorations.length > 0 || improvements.length > 0

  const handleClick = (priority) => {
    if (onCellNavigate && priority.navigation) {
      const nav = priority.navigation
      const cellId = `${nav.cityKey}::${nav.lineKey}::${nav.period}::${nav.kpiKey}`
      onCellNavigate(cellId, nav)
    }
  }

  if (!hasAny) {
    return (
      <div className="bg-ct-surface px-4 py-2">
        <span className="text-[10px] font-bold text-ct-text2 uppercase tracking-wider">Prioridad</span>
        <span className="ml-3 text-[11px] text-ct-text3">
          Sin prioridades operacionales detectadas
        </span>
      </div>
    )
  }

  const py = compact ? 'py-1' : 'py-1.5'

  return (
    <div className={`bg-ct-surface px-4 ${py} space-y-1.5`}>
      <span className="text-[10px] font-bold text-ct-text2 uppercase tracking-wider">Prioridad</span>

      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {/* ── CRÍTICAS ── */}
        <div className="flex-1 min-w-[200px]">
          <span className="text-[9px] font-semibold uppercase text-red-700 tracking-wide">
            Críticas
          </span>
          <div className="mt-0.5 space-y-0.5">
            {deteriorations.length === 0 && (
              <span className="text-[10px] text-ct-text3">—</span>
            )}
            {deteriorations.map((p) => (
              <PriorityRow
                key={p.id}
                priority={p}
                compact={compact}
                onClick={() => handleClick(p)}
              />
            ))}
          </div>
        </div>

        {/* ── OPORTUNIDADES ── */}
        <div className="flex-1 min-w-[200px]">
          <span className="text-[9px] font-semibold uppercase text-emerald-700 tracking-wide">
            Oportunidades
          </span>
          <div className="mt-0.5 space-y-0.5">
            {improvements.length === 0 && (
              <span className="text-[10px] text-ct-text3">—</span>
            )}
            {improvements.map((p) => (
              <PriorityRow
                key={p.id}
                priority={p}
                compact={compact}
                onClick={() => handleClick(p)}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function PriorityRow({ priority, compact, onClick }) {
  const p = priority
  const color = getMomentumSeverityColor(p.deltaPct)
  const arrow = p.type === 'deterioration' ? '▼' : '▲'
  const absPct = Math.abs(p.deltaPct || 0)
  const pctStr = Number.isFinite(absPct) ? `${absPct.toFixed(0)}%` : '—'
  const label = p.comparisonType || ''
  const kpiLabel = KPI_LABEL[p.metric] || p.metric
  const valStr = fmtValue(p.actualValue, p.metric)

  const borderL = p.type === 'deterioration'
    ? 'border-l-2 border-red-300/40'
    : 'border-l-2 border-emerald-300/40'

  return (
    <button
      type="button"
      onClick={onClick}
      className={`block w-full text-left px-2 py-1 rounded-r text-[10px] leading-tight transition-colors
        ${borderL}
        hover:bg-blue-50/60 active:bg-blue-100/40
        ${p.type === 'deterioration' ? 'bg-red-50/20' : 'bg-emerald-50/15'}`}
      title={`${p.city} · ${p.slice} · ${p.periodLabel} · ${kpiLabel}\n${arrow} ${pctStr} ${label} | Score: ${p.priorityScore}`}
    >
      <div className="flex items-center gap-1">
        <span
          className="flex-shrink-0 font-bold text-[11px] leading-none"
          style={{ color }}
        >
          {arrow}{pctStr}
        </span>
        <span className="text-[9px] font-medium text-ct-text3 flex-shrink-0">
          {label}
        </span>
        <span className="truncate text-ct-text font-medium">
          {p.city}
          {p.slice !== '—' && (
            <span className="text-ct-text2"> · {p.slice}</span>
          )}
        </span>
        <span className="ml-auto flex-shrink-0 text-ct-text3 text-[9px]">
          {kpiLabel} {valStr}
        </span>
      </div>
    </button>
  )
}
