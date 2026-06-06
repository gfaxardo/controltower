import { MetricCard, SectionCard, HealthDot, LoadingState, ErrorState, formatNum, StatusBadge } from '../components/SharedComponents.jsx'
import FreshnessBadge from '../components/FreshnessBadge.jsx'

export default function CommandCenterSection({ data, loading, errors, onRetry }) {
  const summary = data.summary
  const config = data.config
  const exports = data.exports

  if (loading.summary && !summary) return <LoadingState text="Cargando Command Center..." />
  if (errors.summary && !summary) return <ErrorState message={errors.summary} onRetry={onRetry} />

  const exportedCampaigns = (exports || []).filter((e) => e.export_status === 'exported')
  const totalExported = exportedCampaigns.reduce((sum, e) => sum + (e.contacts_inserted || 0), 0)

  const engineHealth = {
    opportunity: summary?.prioritized_total > 0 ? 'green' : summary ? 'yellow' : 'red',
    queue: (summary?.queue_total || 0) > 0 ? 'green' : summary ? 'yellow' : 'red',
    export: (summary?.loopcontrol_campaigns_exported || 0) > 0 ? 'green' : summary ? 'yellow' : 'red',
    loopcontrol: config?.enabled ? (summary?.loopcontrol_campaigns_exported > 0 ? 'green' : 'yellow') : 'red',
  }

  const capacityTotal = summary?.capacity_total || data.capacity?.channels?.reduce((s, c) => s + ((c.agents || 0) * (c.capacity_per_agent || 0)), 0) || 0

  return (
    <div className="space-y-5">
      {/* Pipeline Bar */}
      {summary && (
        <div className="bg-gradient-to-r from-[#06244a] to-[#0d3b7a] rounded-2xl p-5 text-white shadow-md">
          <div className="flex items-center gap-2 mb-2">
            <svg className="w-4 h-4 text-white/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            <span className="text-xs font-semibold text-white/70 uppercase tracking-wider">Pipeline Operacional</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-white/80 flex-wrap">
            <span className="bg-white/10 px-2 py-0.5 rounded">Universo: {formatNum(summary.universe_total)}</span>
            <span className="text-white/40">→</span>
            <span className="bg-white/10 px-2 py-0.5 rounded">Elegibles: {formatNum(summary.eligible_total)}</span>
            <span className="text-white/40">→</span>
            <span className="bg-white/10 px-2 py-0.5 rounded">Priorizados: {formatNum(summary.prioritized_total)}</span>
            <span className="text-white/40">→</span>
            <span className="bg-white/20 px-2 py-0.5 rounded font-bold">Accionables: {formatNum(summary.actionable_today)}</span>
          </div>
        </div>
      )}

      {/* Row 1: Core KPIs */}
      <div className="grid grid-cols-4 gap-3">
        <MetricCard label="Universo Total" value={formatNum(summary?.universe_total)} color="#1a56db" tooltip="Total drivers en snapshot mas reciente" explainability={summary?.explainability?.universe_total} />
        <MetricCard label="Priorizados" value={formatNum(summary?.prioritized_total)} color="#7c3aed" tooltip="Drivers con programa y ranking asignado" explainability={summary?.explainability?.prioritized_total} />
        <MetricCard label="Accionables Hoy" value={formatNum(summary?.actionable_today)} color="#059669" tooltip={`Limitado por daily_action_capacity = ${formatNum(summary?.daily_action_capacity)}`} explainability={summary?.explainability?.actionable_today} />
        <MetricCard label="Capacidad Diaria" value={formatNum(capacityTotal)} color="#0891b2" tooltip="Capacidad operativa total" explainability={summary?.explainability?.capacity_total} />
      </div>

      {/* Row 2: Queue + Export */}
      <div className="grid grid-cols-4 gap-3">
        <MetricCard label="En Cola" value={formatNum(summary?.queue_total)} color="#d97706" subtitle={`${formatNum(summary?.queue_ready)} READY / ${formatNum(summary?.queue_held)} HELD`} explainability={summary?.explainability?.queue_total} />
        <MetricCard label="Exportados" value={formatNum(summary?.loopcontrol_contacts_inserted)} color="#7c3aed" subtitle={`${formatNum(summary?.loopcontrol_campaigns_exported)} campanas`} explainability={summary?.explainability?.loopcontrol_contacts_inserted} />
        <MetricCard label="LoopControl" value={config?.mode || '...'} color={config?.enabled ? '#059669' : '#dc2626'} subtitle={config?.enabled ? 'Integrado' : 'DRY RUN'} />
        <MetricCard label="Gap Capacidad" value={summary ? formatNum((summary.actionable_today || 0) - capacityTotal) : '...'} color={(summary?.actionable_today || 0) > capacityTotal ? '#dc2626' : '#059669'} />
      </div>

      {/* Capacity Explanation */}
      {summary && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-3 text-sm text-yellow-800">
          <span className="font-medium">Accionables hoy ({formatNum(summary.actionable_today)})</span> estan limitados por <span className="font-mono bg-yellow-100 px-1 rounded">daily_action_capacity = {formatNum(summary.daily_action_capacity)}</span>.
          Universo: {formatNum(summary.universe_total)}, elegibles: {formatNum(summary.eligible_total)}, priorizados: {formatNum(summary.prioritized_total)}.
        </div>
      )}

      {/* Engine Health */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <div className="flex items-center gap-6 flex-wrap">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Engine Health</span>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50"><span className="text-xs text-gray-500">Opportunity</span><HealthDot status={engineHealth.opportunity} /></div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50"><span className="text-xs text-gray-500">Queue</span><HealthDot status={engineHealth.queue} /></div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50"><span className="text-xs text-gray-500">Export</span><HealthDot status={engineHealth.export} /></div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50"><span className="text-xs text-gray-500">LoopControl</span><HealthDot status={engineHealth.loopcontrol} /></div>
          <div className="flex-1" />
          {summary?.freshness && (
            <div className="flex items-center gap-2">
              <FreshnessBadge freshness={summary.freshness.driver_snapshot} compact />
              <FreshnessBadge freshness={summary.freshness.opportunity_engine} compact />
              <FreshnessBadge freshness={summary.freshness.exports} compact />
            </div>
          )}
        </div>
      </div>

      {/* By Program Distribution */}
      {summary?.by_program && (
        <SectionCard title="Distribucion por Programa" color="#7c3aed">
          <div className="grid grid-cols-4 gap-3">
            {summary.by_program.map((p) => (
              <div key={p.program_code} className="bg-gray-50 rounded-xl p-3 text-center">
                <span className="text-xl font-bold text-gray-800">{formatNum(p.prioritized)}</span>
                <p className="text-xs text-gray-500 mt-1">{p.program_code.replace('PROGRAM_', '')}</p>
              </div>
            ))}
          </div>
        </SectionCard>
      )}
    </div>
  )
}
