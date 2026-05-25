/**
 * BehavioralDiagnosisMvpPanel — Panel de diagnostico conductual MVP.
 * Fase 2A.3 — Diagnostic Engine.
 *
 * Muestra diagnostico individual de conductores usando solo senales disponibles:
 * trips, active_days, days_since_last, weekend_share.
 *
 * NO usa: revenue, online_hours, cancellations, acceptance, zones.
 * NO recomienda acciones.
 * NO usa IA.
 */
import { useEffect, useState, useMemo } from 'react'
import { getBehavioralDiagnosisMvp } from '../../services/api'

const STATUS_COLORS = {
  critical:  { bg: '#fee2e2', text: '#dc2626', border: '#fecaca', label: 'Critico' },
  elevated:  { bg: '#fef3c7', text: '#d97706', border: '#fde68a', label: 'Elevado' },
  warning:   { bg: '#fffbeb', text: '#92400e', border: '#fde68a', label: 'Advertencia' },
  normal:    { bg: '#f0fdf4', text: '#065f46', border: '#bbf7d0', label: 'Normal' },
}

const STATUS_LABELS = {
  churned:       'Inactivo (churn)',
  inactive_risk: 'Riesgo inactividad',
  at_risk:       'En riesgo',
  declining:     'Deteriorandose',
  growing:       'Creciendo',
  top:           'Alto rendimiento',
  stable:        'Estable',
}

export default function BehavioralDiagnosisMvpPanel({
  country = null,
  city = null,
  parkId = null,
  windowDays = 28,
  compact = false,
  className = '',
}) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    const params = { window_days: windowDays, limit: 100 }
    if (country) params.country = country
    if (city) params.city = city
    if (parkId) params.park_id = parkId

    getBehavioralDiagnosisMvp(params)
      .then((res) => { if (!cancelled) setData(res) })
      .catch((err) => { if (!cancelled) setError(err.message || 'Error cargando diagnostico') })
      .finally(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [country, city, parkId, windowDays])

  const summary = data?.summary
  const drivers = data?.drivers || []
  const visibleDrivers = expanded ? drivers : drivers.slice(0, 8)

  const fontSize = compact ? 'text-[10px]' : 'text-xs'

  if (!country) {
    return (
      <div className={`rounded-lg border border-dashed border-gray-200 bg-gray-50/50 p-4 text-center ${className}`}>
        <p className="text-xs text-gray-400">Selecciona un pais para ver diagnostico conductual.</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div className={`rounded-lg border border-gray-200 bg-white p-4 ${className}`}>
        <div className="flex items-center gap-2">
          <span className="inline-block w-3 h-3 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
          <span className="text-xs text-gray-400">Cargando diagnostico conductual...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className={`rounded-lg border border-red-200 bg-red-50 p-4 ${className}`}>
        <p className="text-xs text-red-700 font-medium">Error cargando diagnostico</p>
        <p className="text-[10px] text-red-500 mt-0.5">{error}</p>
      </div>
    )
  }

  if (!data || drivers.length === 0) {
    return (
      <div className={`rounded-lg border border-dashed border-gray-200 bg-gray-50/50 p-4 text-center ${className}`}>
        <p className="text-xs text-gray-400">Sin datos de diagnostico para los filtros actuales.</p>
      </div>
    )
  }

  return (
    <div className={`rounded-lg border border-gray-200 bg-white overflow-hidden ${className}`} data-behavioral-mvp>
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-gray-100 bg-slate-50/60 flex items-center justify-between">
        <div>
          <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide">
            Diagnostico Conductual
          </h3>
          <p className="text-[9px] text-gray-400 mt-0.5">
            {summary.total} conductores · {data.period_days}d · MVP
          </p>
        </div>
        <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-amber-100 text-amber-800 border border-amber-200">
          senales limitadas
        </span>
      </div>

      {/* Summary badges */}
      <div className="px-4 py-2 flex flex-wrap gap-1.5 border-b border-gray-100 bg-white">
        <SummaryChip label="Criticos" count={summary.at_risk_count} color="critical" />
        <SummaryChip label="Deterioro" count={summary.declining_count} color="elevated" />
        <SummaryChip label="Creciendo" count={summary.growing_count} color="normal" />
        <SummaryChip label="Top" count={summary.top_count} color="normal" />
        <SummaryChip label="Estables" count={summary.stable_count} color="normal" />
        <SummaryChip label="Inactivos" count={summary.churned_count} color="normal" />
      </div>

      {/* Driver list */}
      <div className="divide-y divide-gray-50 max-h-[400px] overflow-y-auto">
        {visibleDrivers.map((driver) => {
          const colors = STATUS_COLORS[driver.severity] || STATUS_COLORS.normal
          const statusLabel = STATUS_LABELS[driver.status] || driver.status
          return (
            <div
              key={driver.driver_id}
              className="px-4 py-2 hover:bg-blue-50/30 transition-colors cursor-default"
              title={driver.explanation}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className={`${fontSize} font-semibold text-gray-800 truncate`}>
                      {driver.driver_id}
                    </span>
                    <span
                      className="inline-block px-1.5 py-px rounded text-[9px] font-semibold border"
                      style={{ background: colors.bg, color: colors.text, borderColor: colors.border }}
                    >
                      {statusLabel}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[9px] text-gray-400">
                      {driver.city || '—'} · {driver.avg_trips} viajes · {driver.active_days}d act.
                    </span>
                    {driver.delta_pct != null && (
                      <span className={`text-[9px] font-semibold ${driver.delta_pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {driver.delta_pct >= 0 ? '+' : ''}{driver.delta_pct}%
                      </span>
                    )}
                  </div>
                </div>
                <div className="text-right flex-shrink-0">
                  <div className={`${fontSize} font-bold text-gray-700`}>
                    {driver.trips_per_day.toFixed(1)} <span className="text-[9px] text-gray-400 font-normal">v/d</span>
                  </div>
                  {driver.days_since_last > 0 && (
                    <div className="text-[9px] text-gray-400">
                      ult: {driver.days_since_last}d
                    </div>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>

      {/* Expand/Collapse */}
      {drivers.length > 8 && (
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="w-full px-4 py-2 text-[10px] font-medium text-blue-600 hover:bg-blue-50 transition-colors border-t border-gray-100"
        >
          {expanded ? `Mostrar solo 8 de ${drivers.length}` : `Ver todos (${drivers.length})`}
        </button>
      )}

      {/* Signal gaps note */}
      <div className="px-4 py-2 bg-amber-50/50 border-t border-amber-100">
        <p className="text-[9px] text-amber-800 leading-relaxed">
          <span className="font-semibold">Senales no disponibles:</span>{' '}
          {data.signals_unavailable?.join(', ') || '—'}.{' '}
          El diagnostico solo usa trips, dias activos, dias desde ultimo viaje y patron fin de semana.
          No genera recomendaciones.
        </p>
      </div>
    </div>
  )
}

function SummaryChip({ label, count, color }) {
  const colors = STATUS_COLORS[color] || STATUS_COLORS.normal
  return (
    <span
      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-semibold border"
      style={{ background: colors.bg, color: colors.text, borderColor: colors.border }}
    >
      {count} {label}
    </span>
  )
}
