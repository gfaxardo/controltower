/**
 * Franja KPI desde totals del backend (signals y deltas sin recalcular negocio).
 */
import { formatDeltaLine, formatMetricValue, signalArrow, signalColor } from './omniview/omniviewUtils.js'

const KPI_DEFS = [
  { key: 'trips_completed', short: 'Viajes' },
  { key: 'revenue_yego_net', short: 'Revenue' },
  { key: 'commission_pct', short: 'Comm %' },
  { key: 'active_drivers', short: 'Conductores' },
  { key: 'cancel_rate_pct', short: 'Cancel %' }
]

export default function BusinessSliceOmniviewKpis ({ totals, unitsMeta }) {
  const cur = totals?.current || {}
  const delta = totals?.delta || {}
  const signals = totals?.signals || {}

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-4">
      {KPI_DEFS.map(({ key, short }) => {
        const sig = signals[key]?.signal || 'no_data'
        const dir = signals[key]?.direction || 'neutral'
        const dline = formatDeltaLine(key, delta[key], unitsMeta)
        const color = signalColor(sig)
        const arr = signalArrow(sig, dir)
        return (
          <div
            key={key}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 shadow-sm"
          >
            <div className="text-xs font-medium text-slate-500 uppercase tracking-wide">{short}</div>
            <div className="text-lg font-semibold text-slate-900 tabular-nums">
              {formatMetricValue(key, cur[key], unitsMeta)}
            </div>
            {dline
              ? (
                <div
                  className="text-sm font-medium tabular-nums mt-0.5 flex items-center gap-1"
                  style={{ color }}
                >
                  <span aria-hidden>{arr}</span>
                  <span>{dline}</span>
                </div>
                )
              : (
                <div className="text-xs text-slate-400 mt-0.5">Sin variación</div>
                )}
          </div>
        )
      })}
    </div>
  )
}
