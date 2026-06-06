import { SectionCard, LoadingState, ErrorState, formatNum } from '../components/SharedComponents.jsx'
import FreshnessBadge from '../components/FreshnessBadge.jsx'
import ExplainabilityTooltip from '../components/ExplainabilityTooltip.jsx'

const STATUS_CONFIG = {
  READY:    { bg: 'bg-green-100', text: 'text-green-700', label: 'READY' },
  ACTIVE:   { bg: 'bg-blue-100', text: 'text-blue-700', label: 'ACTIVE' },
  EMPTY:    { bg: 'bg-gray-100', text: 'text-gray-500', label: 'EMPTY' },
  STALE:    { bg: 'bg-red-100', text: 'text-red-700', label: 'STALE' },
  UNKNOWN:  { bg: 'bg-gray-100', text: 'text-gray-400', label: 'UNKNOWN' },
  BLOCKED:  { bg: 'bg-red-100', text: 'text-red-700', label: 'BLOCKED' },
}

export default function ProgramsSection({ data, loading, errors, onRetry }) {
  const programs = data.programs
  const driverState = data.driverState

  if (loading.programs && !programs) return <LoadingState />
  if (errors.programs && !programs) return <ErrorState message={errors.programs} onRetry={onRetry} />

  return (
    <div className="space-y-5">
      {/* Program Operations */}
      <SectionCard title="Program Operations" color="#059669" freshness={programs?.freshness?.program_eligibility}>
        <div className="text-xs text-gray-400 mb-4">
          Programas definidos en STATIC_REGISTRY. Cada programa muestra su pipeline operativo completo.
        </div>

        {programs?.programs ? (
          <div className="space-y-3">
            {(programs.programs || []).map((prog) => {
              const statusCfg = STATUS_CONFIG[prog.status] || STATUS_CONFIG.UNKNOWN
              const hasBlockers = (prog.blockers || []).length > 0

              return (
                <div key={prog.program_code} className="bg-gray-50 rounded-xl border border-gray-100 overflow-hidden">
                  {/* Header */}
                  <div className="px-4 py-3 flex items-center justify-between" style={{ borderLeftWidth: 4, borderLeftColor: prog.color || '#059669' }}>
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-semibold text-gray-700">{prog.program_name || prog.program_code?.replace('PROGRAM_', '')}</span>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusCfg.bg} ${statusCfg.text}`}>
                        {statusCfg.label}
                      </span>
                      <FreshnessBadge freshness={prog.freshness} compact />
                      <ExplainabilityTooltip explainability={prog.explainability} />
                    </div>
                    <span className="text-xs text-gray-400">last run: {prog.last_run_at}</span>
                  </div>

                  {/* Metrics Grid */}
                  <div className="px-4 py-3 grid grid-cols-6 gap-3">
                    {[
                      { v: prog.eligible_total, l: 'Elegibles', c: 'text-gray-800' },
                      { v: prog.prioritized_total, l: 'Priorizados', c: 'text-[#7c3aed]' },
                      { v: prog.actionable_today, l: 'Accionables', c: 'text-green-600' },
                      { v: prog.queued_total, l: 'En Cola', c: 'text-[#d97706]' },
                      { v: prog.exported_total, l: 'Exportados', c: 'text-[#7c3aed]' },
                      { v: prog.exported_campaigns_count, l: 'Campanas', c: 'text-gray-500' },
                    ].map((m, i) => (
                      <div key={i} className="text-center">
                        <span className={`text-lg font-bold ${m.c}`}>{formatNum(m.v)}</span>
                        <p className="text-[10px] text-gray-400">{m.l}</p>
                      </div>
                    ))}
                  </div>

                  {/* Blockers + Remediation */}
                  {hasBlockers && (
                    <div className="px-4 py-2 bg-red-50 border-t border-red-100">
                      <div className="flex items-start gap-2 text-xs">
                        <svg className="w-3.5 h-3.5 text-red-400 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                        </svg>
                        <div>
                          {prog.blockers.map((b, j) => (
                            <div key={j} className="text-red-700">{b.message}</div>
                          ))}
                          {(prog.remediation || []).map((r, j) => (
                            <div key={j} className="text-red-500 mt-0.5">{r}</div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        ) : (
          <LoadingState text="Cargando programas..." />
        )}
      </SectionCard>

      {/* Driver State */}
      <SectionCard title="Estado del Conductor" color="#1a56db" freshness={driverState?.freshness?.driver_snapshot}>
        <div className="text-xs text-gray-400 mb-3 bg-blue-50 border border-blue-100 rounded-lg p-2">
          Driver State es un snapshot de segmentacion. No es una lista accionable. Los estados de lifecycle, performance y retention describen al conductor pero no permiten gestion directa todavia.
        </div>
        {loading.driverState && !driverState ? (
          <LoadingState />
        ) : errors.driverState && !driverState ? (
          <ErrorState message={errors.driverState} />
        ) : driverState ? (
          <>
            <div className="grid grid-cols-2 gap-3 mb-4">
              <MetricCardMini label="Total Drivers" value={formatNum(driverState.total_drivers)} />
              <MetricCardMini label="Snapshot" value={driverState.latest_date} />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <StateBreakdown title="Lifecycle" color="#1a56db" items={driverState.by_lifecycle_state} total={driverState.total_drivers} />
              <StateBreakdown title="Performance" color="#059669" items={driverState.by_performance_state} total={driverState.total_drivers} />
              <StateBreakdown title="Retention" color="#dc2626" items={driverState.by_retention_state} total={driverState.total_drivers} />
            </div>
          </>
        ) : null}
      </SectionCard>
    </div>
  )
}

function MetricCardMini({ label, value }) {
  return (
    <div className="bg-gray-50 rounded-xl p-3 text-center">
      <span className="text-xl font-bold text-gray-800">{value}</span>
      <p className="text-xs text-gray-400 mt-0.5">{label}</p>
    </div>
  )
}

function StateBreakdown({ title, color, items = [], total }) {
  return (
    <div className="bg-gray-50 rounded-xl p-3">
      <span className="text-xs font-semibold text-gray-500">{title}</span>
      <div className="mt-2 space-y-1.5">
        {(items || []).map((s) => {
          const pct = total > 0 ? Math.round((s.count / total) * 100) : 0
          return (
            <div key={s.state}>
              <div className="flex justify-between text-xs mb-0.5">
                <span className="text-gray-600">{s.state}</span>
                <span className="font-medium text-gray-700">{formatNum(s.count)} ({pct}%)</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-1.5">
                <div className="h-1.5 rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
