import { MetricCard, SectionCard, LoadingState, ErrorState, formatNum, StatusBadge, HealthDot } from '../components/SharedComponents.jsx'

const STATUS_COLORS = {
  REACTIVATED: { bg: 'bg-emerald-100', text: 'text-emerald-800', icon: '✓' },
  TRIP_DETECTED: { bg: 'bg-green-100', text: 'text-green-800', icon: '▶' },
  SUPPLY_DETECTED: { bg: 'bg-blue-100', text: 'text-blue-800', icon: '◷' },
  OBSERVED: { bg: 'bg-gray-100', text: 'text-gray-700', icon: '○' },
  ACTIONED_NO_ACTIVITY: { bg: 'bg-amber-100', text: 'text-amber-800', icon: '⏳' },
  STALE: { bg: 'bg-red-100', text: 'text-red-800', icon: '✗' },
}

export default function IntradaySignalsSection({ data, loading, errors, onRetry, navigateTo }) {
  const summary = data.intradaySignals
  const byCampaign = data.intradaySignalsByCampaign
  const byProgram = data.intradaySignalsByProgram

  if (loading.intradaySignals && !summary) return <LoadingState text="Cargando señales intradía..." />
  if (errors.intradaySignals && !summary) return <ErrorState message={errors.intradaySignals} onRetry={onRetry} />

  if (!summary) {
    return (
      <div className="space-y-4">
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 text-center">
          <p className="text-amber-800 font-semibold">No hay señales intradía disponibles</p>
          <p className="text-amber-600 text-sm mt-1">Las señales se construyen durante el monitoreo live cada 5 minutos.</p>
        </div>
      </div>
    )
  }

  const statuses = summary.signals_by_status || {}
  const totalMonitored = summary.monitored_actions || 0
  const withTrips = summary.drivers_with_trips_after_action || 0
  const withActivity = summary.drivers_with_activity_detected || 0
  const reactivated = summary.drivers_reactivated_observed || 0
  const lastUpdate = summary.last_updated_at

  return (
    <div className="space-y-5">
      {/* HEADER */}
      <div className="bg-gradient-to-r from-[#1a0a4a] to-[#2d1b7a] rounded-2xl p-5 text-white shadow-md">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-white/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
            </svg>
            <span className="text-sm font-bold text-white uppercase tracking-wide">Intraday Signals</span>
            <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-white/15 text-white/90">
              LIVE MONITORING
            </span>
          </div>
          <div className="flex items-center gap-2 text-xs text-white/60">
            <span>{summary.signal_date}</span>
            {lastUpdate && (
              <span className="text-white/40">| Updated: {new Date(lastUpdate).toLocaleTimeString()}</span>
            )}
          </div>
        </div>

        {/* MAIN KPI CARDS */}
        <div className="grid grid-cols-5 gap-3">
          <StatusKpi label="Monitoreados" value={formatNum(totalMonitored)} sub="drivers accionados" />
          <StatusKpi label="Con Viaje" value={formatNum(withTrips)} sub="post-acción observado" accent="green" />
          <StatusKpi label="Con Actividad" value={formatNum(withActivity)} sub="hoy detectado" accent="blue" />
          <StatusKpi label="Reactivados" value={formatNum(reactivated)} sub="observado post-acción" accent="emerald" />
          <StatusKpi label="Sin Actividad" value={formatNum(totalMonitored - withActivity)} sub="aún sin señal" accent="amber" />
        </div>

        {/* Pipeline summary row */}
        <div className="mt-3 pt-3 border-t border-white/10 text-xs text-white/50 flex items-center gap-2 flex-wrap">
          <span>Fuente:</span>
          <span className="text-white/80 font-mono">YANGO_API_LIVE</span>
          <span className="text-white/20">|</span>
          <span className="text-white/40 italic">observado después de acción, no atribución causal</span>
        </div>
      </div>

      {/* STATUS BREAKDOWN */}
      {Object.keys(statuses).length > 0 && (
        <SectionCard title="Desglose por Estado" color="#6d28d9">
          <div className="grid grid-cols-3 gap-3">
            {Object.entries(statuses).map(([status, count]) => {
              const cfg = STATUS_COLORS[status] || STATUS_COLORS.OBSERVED
              return (
                <div key={status} className="bg-gray-50 rounded-xl p-3 border border-gray-100">
                  <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.bg} ${cfg.text} mb-2`}>
                    <span>{cfg.icon}</span>
                    <span>{status}</span>
                  </div>
                  <p className="text-2xl font-bold text-gray-800">{formatNum(count)}</p>
                  <p className="text-[10px] text-gray-400">drivers</p>
                </div>
              )
            })}
          </div>
        </SectionCard>
      )}

      {/* BY CAMPAIGN */}
      {byCampaign?.campaigns?.length > 0 && (
        <SectionCard title="Por Campaña" color="#7c3aed">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100 text-gray-500">
                  <th className="text-left py-2 px-2">Campaña</th>
                  <th className="text-right py-2 px-2">Total</th>
                  <th className="text-right py-2 px-2">Con Viaje</th>
                  <th className="text-right py-2 px-2">Reactivados</th>
                </tr>
              </thead>
              <tbody>
                {byCampaign.campaigns.map((c) => (
                  <tr key={c.campaign_id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 px-2 font-mono text-gray-700">{c.campaign_id === 'UNKNOWN' ? '—' : c.campaign_id}</td>
                    <td className="py-2 px-2 text-right font-semibold">{formatNum(c.total_signals)}</td>
                    <td className="py-2 px-2 text-right">{formatNum(c.drivers_with_trips)}</td>
                    <td className="py-2 px-2 text-right">{formatNum(c.drivers_reactivated)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      {/* BY PROGRAM */}
      {byProgram?.programs?.length > 0 && (
        <SectionCard title="Por Programa" color="#8b5cf6">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100 text-gray-500">
                  <th className="text-left py-2 px-2">Programa</th>
                  <th className="text-right py-2 px-2">Total</th>
                  <th className="text-right py-2 px-2">Con Viaje</th>
                  <th className="text-right py-2 px-2">Reactivados</th>
                </tr>
              </thead>
              <tbody>
                {byProgram.programs.map((p) => (
                  <tr key={p.program_code} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 px-2 text-gray-700">
                      <span className="font-medium">{p.program_name || p.program_code}</span>
                      <span className="text-gray-400 ml-1">({p.program_code})</span>
                    </td>
                    <td className="py-2 px-2 text-right font-semibold">{formatNum(p.total_signals)}</td>
                    <td className="py-2 px-2 text-right">{formatNum(p.drivers_with_trips)}</td>
                    <td className="py-2 px-2 text-right">{formatNum(p.drivers_reactivated)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      {/* DISCLAIMER */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-xs text-amber-700">
        <span className="font-semibold">Disclaimer:</span> Las señales intradía reflejan actividad{" "}
        <span className="italic">observada después de la acción</span>. No constituyen atribución causal,
        cálculo de impacto, ni ROI. Fuente: YANGO_API_LIVE. Uso exclusivamente observacional.
      </div>
    </div>
  )
}

function StatusKpi({ label, value, sub, accent = 'default' }) {
  const colorMap = {
    green: 'text-green-400',
    blue: 'text-blue-400',
    emerald: 'text-emerald-400',
    amber: 'text-amber-400',
    purple: 'text-purple-400',
    red: 'text-red-400',
    default: 'text-white',
  }
  return (
    <div className="text-center">
      <p className={`text-xl font-bold ${colorMap[accent] || colorMap.default}`}>{value}</p>
      <p className="text-[10px] text-white/50">{label}</p>
      <p className="text-[9px] text-white/30">{sub}</p>
    </div>
  )
}
