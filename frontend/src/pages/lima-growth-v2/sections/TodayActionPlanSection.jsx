import { MetricCard, SectionCard, LoadingState, ErrorState, formatNum, StatusBadge, HealthDot, SemanticBanner } from '../components/SharedComponents.jsx'
import FreshnessBadge from '../components/FreshnessBadge.jsx'
import { getStatusSemantic } from '../design/semanticRegistry.js'

const ACTION_ICONS = {
  BUILD: '🔨',
  EXPORT: '📤',
  RESOLVE: '🔧',
  ASSIGN_CHANNEL: '📡',
  PRIORITIZE: '⭐',
  SCALE: '📊',
  NOTICE: 'ℹ',
  ADJUST: '⚙',
}

export default function TodayActionPlanSection({ data, loading, errors, onRetry, navigateTo }) {
  const plan = data.todayActionPlan
  const summary = data.summary

  if (loading.todayActionPlan && !plan) return <LoadingState text="Generando Today's Action Plan..." />
  if (errors.todayActionPlan && !plan) return <ErrorState message={errors.todayActionPlan} onRetry={onRetry} />

  const statusCfg = getStatusSemantic(plan?.operational_status)

  return (
    <div className="space-y-5">
      {/* BLOQUE 1: TODAY STATUS */}
      <div className="bg-gradient-to-r from-[#06244a] to-[#0d3b7a] rounded-2xl p-5 text-white shadow-md">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-white/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h2m6-14h2a2 2 0 012 2v10a2 2 0 01-2 2h-2M12 3v18M9 9h6M9 13h6M9 17h6" />
            </svg>
            <span className="text-sm font-bold text-white uppercase tracking-wide">Today's Action Plan</span>
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusCfg.bg} ${statusCfg.color}`}>{statusCfg.icon} {statusCfg.label}</span>
          </div>
          <span className="text-xs text-white/60">{plan?.date}</span>
        </div>
        <div className="grid grid-cols-5 gap-3">
          <StatusKpi label="Capacidad" value={formatNum(plan?.capacity?.available)} sub={`${plan?.capacity?.configured || 0} canales`} />
          <StatusKpi label="READY" value={formatNum(plan?.workload?.ready)} sub="listos para exportar" accent="green" />
          <StatusKpi label="HELD" value={formatNum(plan?.workload?.held)} sub="retenidos" accent="yellow" />
          <StatusKpi label="Exportados" value={formatNum(plan?.workload?.exported)} sub="hoy" accent="purple" />
          <StatusKpi label="Gap" value={formatNum(plan?.gap?.missing_capacity)} sub={`${plan?.gap?.missing_capacity > 0 ? 'faltante' : 'excedente'}`} accent={plan?.gap?.missing_capacity > 0 ? 'red' : 'green'} />
        </div>
        {/* Pipeline bar */}
        {plan?.pipeline_summary && (
          <div className="mt-3 flex items-center gap-2 text-xs text-white/70 flex-wrap pt-3 border-t border-white/10">
            <span className="text-white/50">Pipeline:</span>
            <span>{formatNum(plan.pipeline_summary.universe_total)} universo</span>
            <span className="text-white/30">→</span>
            <span>{formatNum(plan.pipeline_summary.eligible_total)} elegibles</span>
            <span className="text-white/30">→</span>
            <span>{formatNum(plan.pipeline_summary.prioritized_total)} priorizados</span>
            <span className="text-white/30">→</span>
            <span className="text-white font-semibold">{formatNum(plan.pipeline_summary.actionable_today)} accionables</span>
          </div>
        )}
      </div>

      {/* If queue not built, show primary CTA */}
      {plan?.operational_status === 'QUEUE_NOT_BUILT' && (
        <SemanticBanner severity="HIGH" className="rounded-2xl p-6 text-center">
          <p className="font-semibold text-lg mb-2">La cola no ha sido construida para hoy</p>
          <p className="text-sm">Sin cola no hay trabajo asignable. Ve a Execution Queue para construirla.</p>
        </SemanticBanner>
      )}

      {/* BLOQUE 2: TOP PRIORITIES */}
      {plan?.priorities?.length > 0 && (
        <SectionCard title="Top Prioridades" color="#7c3aed">
          <div className="grid grid-cols-3 gap-3">
            {plan.priorities.map((p) => (
              <div key={p.program_code} className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg font-bold text-gray-800">#{p.priority_position}</span>
                  <span className="text-sm font-semibold text-gray-700">{p.program_name}</span>
                </div>
                <p className="text-xs text-gray-500 mb-3">{p.reason}</p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="text-center bg-white rounded-lg p-2">
                    <span className="block font-bold text-green-600">{formatNum(p.actionable_today)}</span>
                    <span className="text-gray-400">accionables</span>
                  </div>
                  <div className="text-center bg-white rounded-lg p-2">
                    <span className="block font-bold text-[#d97706]">{formatNum(p.queued_total)}</span>
                    <span className="text-gray-400">en cola</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {/* BLOQUE 3: BLOCKERS */}
      {plan?.blockers?.filter(b => b.action_required)?.length > 0 && (
        <SectionCard title="Bloqueadores" color="#dc2626">
          <div className="space-y-2">
            {plan.blockers.filter(b => b.action_required).map((b, i) => (
              <div key={i} className="flex items-start gap-3 bg-red-50 rounded-xl p-3 border border-red-100">
                <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${b.severity === 'HIGH' ? 'bg-red-500' : 'bg-yellow-500'}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-sm font-semibold text-red-800">{b.description}</span>
                    <span className="text-xs font-bold text-red-500 bg-red-100 px-1.5 py-0.5 rounded">{b.count}</span>
                  </div>
                  {b.remediation && <p className="text-xs text-red-600">{b.remediation}</p>}
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {/* For non-blocking blockers (info) */}
      {plan?.blockers?.filter(b => !b.action_required)?.length > 0 && (
        <SectionCard title="Observaciones" color="#0891b2">
          <div className="space-y-2">
            {plan.blockers.filter(b => !b.action_required).map((b, i) => (
              <div key={i} className="text-xs text-gray-600 bg-blue-50 rounded-lg p-2 border border-blue-100">
                {b.description} — <span className="text-blue-600">{b.remediation}</span>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {/* BLOQUE 4: TODAY ACTIONS */}
      {plan?.recommended_actions?.length > 0 && (
        <SectionCard title="Acciones Recomendadas" color="#059669">
          <div className="space-y-2">
            {plan.recommended_actions.map((a, i) => (
              <div key={i} className="flex items-start gap-3 bg-white rounded-xl p-4 border border-gray-100 hover:border-gray-200 transition-colors">
                <span className="text-xl mt-0.5 flex-shrink-0">{ACTION_ICONS[a.action_type] || '▸'}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="px-1.5 py-0.5 rounded text-xs font-bold bg-gray-100 text-gray-500">{a.priority}</span>
                    <span className="text-sm font-semibold text-gray-800">{a.action}</span>
                  </div>
                  <p className="text-xs text-gray-500 mb-1"><span className="font-medium text-gray-600">Porque:</span> {a.reason}</p>
                  <p className="text-xs text-green-700 bg-green-50 rounded-lg px-2 py-1 inline-block">
                    <span className="font-medium">Efecto esperado:</span> {a.expected_effect}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {/* Cross-section CTAs */}
      {plan?.operational_status !== 'QUEUE_NOT_BUILT' && plan?.recommended_actions?.length > 0 && navigateTo && (
        <div className="grid grid-cols-4 gap-3">
          {(plan.workload?.ready > 0 || plan.recommended_actions.some(a => a.action_type === 'EXPORT')) && (
            <button
              data-testid="cta-go-to-ready-queue"
              onClick={() => navigateTo('queue', { label: 'Exportar READY', status: 'READY' })}
              className="text-xs bg-[#7c3aed] text-white px-3 py-2 rounded-lg hover:bg-[#6d28d9] font-medium text-center"
            >
              Ir a Queue READY
            </button>
          )}
          {plan.blockers?.some(b => b.blocker === 'CAPACITY_GAP' || b.blocker?.includes('CHANNEL_FULL')) && (
            <button
              data-testid="cta-view-allocation-trace"
              onClick={() => navigateTo('config', { label: 'Allocation Trace', scrollTo: 'allocation-trace-panel' })}
              className="text-xs bg-[#0891b2] text-white px-3 py-2 rounded-lg hover:bg-[#067a96] font-medium text-center"
            >
              Ver Allocation Trace
            </button>
          )}
          {plan.blockers?.some(b => b.blocker === 'SIN_CANAL_ASIGNADO') && (
            <button
              data-testid="cta-view-channel-capacity"
              onClick={() => navigateTo('config', { label: 'Capacidad por canal' })}
              className="text-xs bg-[#d97706] text-white px-3 py-2 rounded-lg hover:bg-[#b65c00] font-medium text-center"
            >
              Ver capacidad por canal
            </button>
          )}
          {plan.priorities?.length > 0 && (
            <button
              data-testid="cta-view-programs"
              onClick={() => navigateTo('programs', { label: 'Programas prioritarios' })}
              className="text-xs bg-[#059669] text-white px-3 py-2 rounded-lg hover:bg-[#047857] font-medium text-center"
            >
              Ver Programas
            </button>
          )}
        </div>
      )}

      {/* Empty state when no actions */}
      {(!plan?.recommended_actions || plan.recommended_actions.length === 0) && plan?.operational_status === 'ALL_EXPORTED' && (
        <SemanticBanner severity="INFO" className="rounded-2xl p-6 text-center">
          <p className="font-semibold text-lg mb-2">Todo el trabajo del dia esta completo</p>
          <p className="text-sm">Todas las exportaciones han sido procesadas. No hay acciones pendientes para hoy.</p>
        </SemanticBanner>
      )}

      {/* BLOQUE 5: OPERATIONAL HEALTH */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <div className="flex items-center gap-6 flex-wrap">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Operational Health</span>
          <HealthBadge label="Queue" status={plan?.operational_status === 'QUEUE_NOT_BUILT' ? 'red' : plan?.workload?.total > 0 ? 'green' : 'yellow'} />
          <HealthBadge label="Capacity" status={plan?.capacity?.available > 0 ? 'green' : 'red'} />
          <HealthBadge label="Export" status={plan?.workload?.exported > 0 ? 'green' : 'yellow'} />
          <HealthBadge label="Programs" status={plan?.priorities?.length > 0 ? 'green' : 'yellow'} />
          <div className="flex-1" />
          {plan?.freshness && (
            <div className="flex items-center gap-2">
              <FreshnessBadge freshness={plan.freshness.driver_snapshot} compact />
              <FreshnessBadge freshness={plan.freshness.opportunity_engine} compact />
              <FreshnessBadge freshness={plan.freshness.exports} compact />
              <FreshnessBadge freshness={plan.freshness.assignment_queue} compact />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function StatusKpi({ label, value, sub, accent = 'default' }) {
  const colors = {
    green: 'text-green-300',
    yellow: 'text-yellow-300',
    red: 'text-red-300',
    purple: 'text-purple-300',
    default: 'text-white',
  }
  return (
    <div className="text-center">
      <span className={`text-xl font-bold ${colors[accent] || colors.default}`}>{value}</span>
      <p className="text-xs text-white/60 mt-0.5">{label}</p>
      {sub && <p className="text-[10px] text-white/40">{sub}</p>}
    </div>
  )
}

function HealthBadge({ label, status }) {
  const color = { green: 'bg-green-400', yellow: 'bg-yellow-400', red: 'bg-red-400' }
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50">
      <span className={`w-2 h-2 rounded-full ${color[status] || 'bg-gray-300'}`} />
      <span className="text-xs text-gray-500">{label}</span>
    </div>
  )
}
