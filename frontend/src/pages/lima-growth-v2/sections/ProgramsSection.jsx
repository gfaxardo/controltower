import { SectionCard, LoadingState, ErrorState, StatusBadge, formatNum } from '../components/SharedComponents.jsx'
import FreshnessBadge from '../components/FreshnessBadge.jsx'
import ExplainabilityTooltip from '../components/ExplainabilityTooltip.jsx'

const STATUS_COLORS = {
  HEALTHY: { border: '#059669', bg: 'bg-emerald-50', text: 'text-emerald-700', label: 'HEALTHY' },
  WARNING: { border: '#d97706', bg: 'bg-amber-50', text: 'text-amber-700', label: 'WARNING' },
  CRITICAL: { border: '#dc2626', bg: 'bg-red-50', text: 'text-red-700', label: 'CRITICAL' },
  NOT_GENERATED: { border: '#d97706', bg: 'bg-amber-50', text: 'text-amber-700', label: 'NOT_GENERATED' },
  NO_QUEUE: { border: '#d97706', bg: 'bg-amber-50', text: 'text-amber-700', label: 'NO_QUEUE' },
  EXPORTED: { border: '#7c3aed', bg: 'bg-purple-50', text: 'text-purple-700', label: 'EXPORTED' },
}

export default function ProgramsSection({ data, loading, errors, onRetry, sectionFilter }) {
  const programs = data.programs
  const driverState = data.driverState
  const programStatus = data.programStatus

  if (loading.programs && !programs) return <LoadingState />
  if (errors.programs && !programs) return <ErrorState message={errors.programs} onRetry={onRetry} />

  // Use program status data if available for operational state
  const getProgStatus = (progCode) => {
    if (!programStatus?.programs) return null
    return programStatus.programs.find(p => p.program_code === progCode)
  }

  return (
    <div className="space-y-5">
      {/* Program Status Summary */}
      {programStatus && (
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 text-center">
            <p className="text-2xl font-bold text-emerald-700">{programStatus.healthy}</p>
            <p className="text-xs text-emerald-600">Healthy</p>
          </div>
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 text-center">
            <p className="text-2xl font-bold text-amber-700">{programStatus.warning}</p>
            <p className="text-xs text-amber-600">Warning</p>
          </div>
          <div className="bg-red-50 border border-red-200 rounded-xl p-3 text-center">
            <p className="text-2xl font-bold text-red-700">{programStatus.critical}</p>
            <p className="text-xs text-red-600">Critical</p>
          </div>
        </div>
      )}

      {/* Program Operations */}
      <SectionCard title="Program Operations" color="#059669" freshness={programs?.freshness?.program_eligibility}>
        {programs?.programs ? (
          <div className="space-y-3">
            {(programs.programs || []).map((prog) => {
              const status = getProgStatus(prog.program_code)
              const opStatus = status?.operational_status || prog.status || 'UNKNOWN'
              const cfg = STATUS_COLORS[opStatus] || STATUS_COLORS.WARNING

              return (
                <div key={prog.program_code} className="bg-gray-50 rounded-xl border border-gray-100 overflow-hidden">
                  {/* Header with operational status */}
                  <div className="px-4 py-3 flex items-center justify-between" style={{ borderLeftWidth: 4, borderLeftColor: cfg.border }}>
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-semibold text-gray-700">{prog.program_name || prog.program_code?.replace('PROGRAM_', '')}</span>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ${cfg.bg} ${cfg.text}`}>
                        {cfg.label}
                      </span>
                      <FreshnessBadge freshness={prog.freshness} compact />
                      <ExplainabilityTooltip explainability={prog.explainability} />
                    </div>
                    {status?.explanation && (
                      <span className="text-xs text-gray-500 max-w-xs truncate">{status.explanation}</span>
                    )}
                  </div>

                  {/* Operational Metrics */}
                  <div className="px-4 py-3 grid grid-cols-6 gap-3">
                    {[
                      { v: status?.eligible_total ?? prog.eligible_total, l: 'Elegibles', c: 'text-gray-800' },
                      { v: status?.prioritized_total ?? prog.prioritized_total, l: 'Priorizados', c: 'text-purple-700' },
                      { v: status?.actionable_today ?? prog.actionable_today, l: 'Accionables', c: 'text-green-600' },
                      { v: status?.queue_total ?? prog.queued_total, l: 'En Cola', c: 'text-amber-700' },
                      { v: status?.exported_total ?? prog.exported_total, l: 'Exportados', c: 'text-purple-700' },
                      { v: prog.exported_campaigns_count, l: 'Campanas', c: 'text-gray-500' },
                    ].map((m, i) => (
                      <div key={i} className="text-center">
                        <span className={`text-lg font-bold ${m.c}`}>{formatNum(m.v)}</span>
                        <p className="text-[10px] text-gray-400">{m.l}</p>
                      </div>
                    ))}
                  </div>

                  {/* Pipeline bar */}
                  <div className="px-4 pb-3">
                    <div className="flex items-center gap-1.5 text-[10px] text-gray-400">
                      <span>Pipeline:</span>
                      <span className="bg-gray-200 px-1.5 py-0.5 rounded">{formatNum(status?.eligible_total ?? prog.eligible_total)} elig</span>
                      <span>-></span>
                      <span className="bg-gray-200 px-1.5 py-0.5 rounded">{formatNum(status?.prioritized_total ?? prog.prioritized_total)} pri</span>
                      <span>-></span>
                      <span className="bg-gray-200 px-1.5 py-0.5 rounded">{formatNum(status?.actionable_today ?? prog.actionable_today)} act</span>
                      <span>-></span>
                      <span className="bg-gray-200 px-1.5 py-0.5 rounded">{formatNum(status?.queue_total ?? prog.queued_total)} queue</span>
                      <span>-></span>
                      <span className="bg-gray-200 px-1.5 py-0.5 rounded">{formatNum(status?.exported_total ?? prog.exported_total)} exp</span>
                    </div>
                  </div>

                  {/* Recommended action */}
                  {status?.recommended_action && (
                    <div className="px-4 pb-3">
                      <p className="text-[10px] text-amber-600 font-medium">
                        Accion: {status.recommended_action}
                      </p>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-400 text-sm">No programs data available</div>
        )}

        {/* Operational Ranking */}
        {programStatus?.programs && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <p className="text-xs font-semibold text-gray-500 mb-2">Operational Ranking</p>
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="text-gray-400 border-b border-gray-100">
                    <th className="text-left py-1">Programa</th>
                    <th className="text-right py-1">Eligible</th>
                    <th className="text-right py-1">Queue</th>
                    <th className="text-right py-1">Exportados</th>
                    <th className="text-right py-1">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {programStatus.programs.map(p => {
                    const cfg = STATUS_COLORS[p.operational_status] || STATUS_COLORS.WARNING
                    return (
                      <tr key={p.program_code} className="border-b border-gray-50">
                        <td className="py-1 font-medium">{p.program_name}</td>
                        <td className="py-1 text-right">{formatNum(p.eligible_total)}</td>
                        <td className="py-1 text-right">{formatNum(p.queue_total)}</td>
                        <td className="py-1 text-right">{formatNum(p.exported_total)}</td>
                        <td className="py-1 text-right">
                          <span className={`inline-flex px-1.5 py-0.5 rounded text-[9px] font-medium ${cfg.bg} ${cfg.text}`}>{cfg.label}</span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </SectionCard>
    </div>
  )
}
