/**
 * OperationalStatusBar — FASE 1H.3
 * Barra de estado operacional colapsada.
 * Reemplaza múltiples banners individuales por una barra única expandible.
 */
import { useState, useMemo } from 'react'

export default function OperationalStatusBar ({
  grain,
  periodStates,
  allPeriods = [],
  freshnessInfo,
  sliceMaxTripDate,
  coverageSummary,
  matrixMeta,
  matrixTrust,
  execKpis,
  compact = false,
}) {
  const [expanded, setExpanded] = useState(false)

  const items = useMemo(() => {
    const result = []

    // Data freshness
    const maxDate = sliceMaxTripDate || freshnessInfo?.derived_max_date
    if (maxDate) {
      result.push({ type: 'freshness', label: 'Data hasta', value: maxDate })
    }

    // Coverage
    const cp = coverageSummary?.coverage_pct
    const um = coverageSummary?.unmapped_trips
    if (cp != null) {
      result.push({ type: cp >= 92 ? 'ok' : 'warning', label: 'Cobertura', value: `${cp}%` })
    }
    if (um != null && um > 0) {
      result.push({ type: 'warning', label: 'Sin mapear', value: `${um.toLocaleString()} viajes` })
    }

    // Period state
    const lastPeriod = allPeriods.length > 0 ? allPeriods[allPeriods.length - 1] : null
    const lastState = lastPeriod ? periodStates?.get(lastPeriod) : null
    if (lastState) {
      const stateLabels = { open: 'En curso', partial: 'Parcial', stale: 'Desactualizado', closed: 'Cerrado', current_day: 'Hoy', future: 'Futuro' }
      result.push({ type: lastState === 'closed' ? 'ok' : 'warning', label: 'Período actual', value: stateLabels[lastState] || lastState })
    }

    // Trust status
    const ts = matrixTrust?.trust_status
    if (ts && ts !== 'ok') {
      result.push({ type: ts === 'blocked' ? 'error' : 'warning', label: 'Trust', value: matrixTrust?.executive?.status || ts })
    }

    // Fact layer
    const factStatus = matrixMeta?.fact_layer?.status
    if (factStatus === 'empty') {
      result.push({ type: 'error', label: 'Fact layer', value: matrixMeta.fact_layer.message || 'Sin datos' })
    }

    // KPI summary
    if (execKpis?.trips_completed != null) {
      result.push({ type: 'ok', label: 'Trips', value: Number(execKpis.trips_completed).toLocaleString() })
    }

    return result
  }, [freshnessInfo, sliceMaxTripDate, coverageSummary, matrixMeta, matrixTrust, periodStates, allPeriods, execKpis])

  if (items.length === 0) return null

  const hasWarnings = items.some(i => i.type === 'warning' || i.type === 'error')
  const borderColor = hasWarnings
    ? items.some(i => i.type === 'error') ? 'border-red-200 bg-red-50/40' : 'border-amber-200 bg-amber-50/40'
    : 'border-emerald-200 bg-emerald-50/40'

  const itemCls = (type) => {
    if (type === 'error') return 'bg-red-100 text-red-800 border-red-200'
    if (type === 'warning') return 'bg-amber-100 text-amber-800 border-amber-200'
    return 'bg-emerald-100 text-emerald-800 border-emerald-200'
  }

  return (
    <div className={`rounded-lg border ${borderColor} overflow-hidden`}>
      <button
        type="button"
        onClick={() => setExpanded(e => !e)}
        className={`w-full px-3 py-1.5 flex items-center gap-2 text-xs font-medium transition-colors hover:bg-white/50 ${compact ? 'py-1' : 'py-1.5'}`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${hasWarnings ? 'bg-amber-500' : 'bg-emerald-500'}`} />
        <span className="text-gray-600">Estado operacional</span>
        <span className="text-gray-400 flex-1 text-left truncate">
          {items.slice(0, 3).map((i, idx) => (
            <span key={idx}>{i.value}{idx < Math.min(items.length, 3) - 1 ? ' · ' : ''}</span>
          ))}
        </span>
        <svg className={`w-3 h-3 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {expanded && (
        <div className={`px-3 pb-2 flex flex-wrap gap-1.5 ${compact ? 'text-[10px]' : 'text-xs'}`}>
          {items.map((item, idx) => (
            <span key={idx} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border ${itemCls(item.type)} font-medium`}>
              {item.label}: <strong>{item.value}</strong>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
