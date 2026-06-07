import { useState } from 'react'
import { SectionCard, StatusBadge, SemanticBanner, formatNum } from '../components/SharedComponents.jsx'
import { getAllocationModeSemantic } from '../design/semanticRegistry.js'

const DEFAULT_CHANNELS = [
  { channel: 'Call Center', agents: 2, capacity_per_agent: 40 },
  { channel: 'SAC', agents: 1, capacity_per_agent: 30 },
  { channel: 'Bot / WhatsApp', agents: 1, capacity_per_agent: 200 },
]

export default function ControlConfigSection({ data, loading, errors, onSaveCapacity, navigateTo }) {
  const summary = data.summary
  const config = data.config
  const capacityData = data.capacity
  const qSummary = data.queueSummary

  const channels = capacityData?.channels?.length ? capacityData.channels : DEFAULT_CHANNELS
  const [editChannels, setEditChannels] = useState(null)
  const [saving, setSaving] = useState(false)

  const currentChannels = editChannels || channels

  const channelUtilMap = {}
  if (qSummary?.channel_utilization) {
    for (const cu of qSummary.channel_utilization) {
      if (cu.channel !== 'UNASSIGNED') {
        channelUtilMap[cu.channel] = cu
      }
    }
  }

  const handleEdit = (idx, field, value) => {
    const next = [...currentChannels]
    next[idx] = { ...next[idx], [field]: field === 'agents' || field === 'capacity_per_agent' ? parseInt(value) || 0 : value }
    setEditChannels(next)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSaveCapacity(currentChannels)
      setEditChannels(null)
    } catch (e) {
      alert('Error: ' + (e.message || 'Error desconocido'))
    } finally {
      setSaving(false)
    }
  }

  const totalCap = currentChannels.reduce((s, c) => s + ((c.agents || 0) * (c.capacity_per_agent || 0)), 0)

  return (
    <div className="space-y-5">
      {/* Policy */}
      {summary && (
        <SectionCard title="Politica de Oportunidades" color="#1a56db" freshness={summary?.freshness?.policy_config}>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <ConfigItem label="Daily Action Capacity" value={formatNum(summary.daily_action_capacity)} highlight />
            <ConfigItem label="Accionables Hoy" value={formatNum(summary.actionable_today)} />
            <ConfigItem label="Priorizados Totales" value={formatNum(summary.prioritized_total)} />
            <ConfigItem label="Universo" value={formatNum(summary.universe_total)} />
            <ConfigItem label="Elegibles" value={formatNum(summary.eligible_total)} />
            <ConfigItem label="Capacidad" value={formatNum(summary.capacity_total || totalCap)} />
          </div>
        </SectionCard>
      )}

      {/* LoopControl Config */}
      <SectionCard title="LoopControl Integration" color="#7c3aed">
        {config ? (
          <div className="grid grid-cols-3 gap-4 text-sm">
            <ConfigItem label="Estado" value={config.enabled ? 'LIVE' : 'DRY_RUN'} badge={config.enabled ? 'LIVE' : 'DRY_RUN'} />
            <ConfigItem label="Base URL" value={config.base_url_configured ? 'Configurada' : 'Falta'} />
            <ConfigItem label="Integration Key" value={config.integration_key_configured ? 'Configurada' : 'Falta'} />
            <ConfigItem label="Mode" value={config.mode} />
            <ConfigItem label="Campanas Exportadas" value={formatNum(summary?.loopcontrol_campaigns_exported)} />
            <ConfigItem label="Contactos Insertados" value={formatNum(summary?.loopcontrol_contacts_inserted)} />
          </div>
        ) : (
          <div className="text-center py-8 text-sm text-gray-400">Cargando configuracion...</div>
        )}
      </SectionCard>

      {/* Capacity Config */}
      <SectionCard title="Capacidad Operativa" color="#0891b2">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs text-gray-400">Configuracion de capacidad diaria por canal</span>
          <div className="flex items-center gap-2">
            {editChannels && (
              <button onClick={() => setEditChannels(null)} className="text-xs text-gray-400 hover:text-gray-600 px-2 py-1 rounded">Cancelar</button>
            )}
            {editChannels && (
              <button onClick={handleSave} disabled={saving} className="text-xs bg-[#0891b2] text-white px-3 py-1.5 rounded-lg hover:bg-[#067a96] disabled:opacity-50">
                {saving ? 'Guardando...' : 'Guardar'}
              </button>
            )}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-100 text-gray-400">
                <th className="text-left py-2 font-medium">Canal</th>
                <th className="text-left py-2 font-medium">Agentes</th>
                <th className="text-left py-2 font-medium">Cap / Agente</th>
                <th className="text-left py-2 font-medium">Cap Total</th>
                <th className="text-left py-2 font-medium">En Cola</th>
                <th className="text-left py-2 font-medium">Disp</th>
              </tr>
            </thead>
            <tbody>
              {currentChannels.map((ch, idx) => {
                const total = (ch.agents || 0) * (ch.capacity_per_agent || 0)
                const editing = !!editChannels
                const util = channelUtilMap[ch.channel]
                const assigned = util?.assigned_in_queue || 0
                const available = util?.available_capacity ?? total
                const utilPct = util?.utilization_pct || 0
                return (
                  <tr key={ch.channel} className="border-b border-gray-50">
                    <td className="py-2 font-medium text-gray-700">{ch.channel}</td>
                    <td className="py-2">
                      {editing ? (
                        <input type="number" min={0} value={ch.agents} onChange={(e) => handleEdit(idx, 'agents', e.target.value)} className="w-16 px-2 py-1 border border-gray-200 rounded text-gray-700 text-xs" />
                      ) : (
                        <span className="text-gray-600">{ch.agents}</span>
                      )}
                    </td>
                    <td className="py-2">
                      {editing ? (
                        <input type="number" min={0} value={ch.capacity_per_agent} onChange={(e) => handleEdit(idx, 'capacity_per_agent', e.target.value)} className="w-20 px-2 py-1 border border-gray-200 rounded text-gray-700 text-xs" />
                      ) : (
                        <span className="text-gray-600">{ch.capacity_per_agent}</span>
                      )}
                    </td>
                    <td className="py-2 font-bold text-gray-800">{formatNum(total)}</td>
                    <td className="py-2">
                      {util ? (
                        <div>
                          <span className="text-gray-700 font-medium">{formatNum(assigned)}</span>
                          {utilPct >= 100 && <span className="ml-1 text-[10px] text-red-500">lleno</span>}
                          <div className="w-16 h-1 bg-gray-100 rounded-full mt-0.5">
                            <div className={`h-1 rounded-full ${utilPct >= 100 ? 'bg-red-400' : utilPct >= 80 ? 'bg-yellow-400' : 'bg-green-400'}`} style={{ width: `${Math.min(100, utilPct)}%` }} />
                          </div>
                        </div>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="py-2 font-medium text-green-600">{util ? formatNum(available) : '—'}</td>
                  </tr>
                )
              })}
              <tr className="bg-gray-50">
                <td className="py-2 font-semibold text-gray-700">TOTAL</td>
                <td className="py-2 text-gray-500">{currentChannels.reduce((s, c) => s + (c.agents || 0), 0)}</td>
                <td />
                <td className="py-2 font-bold text-gray-800">{formatNum(totalCap)}</td>
                <td className="py-2 text-gray-500">{formatNum(Object.values(channelUtilMap).reduce((s, u) => s + (u.assigned_in_queue || 0), 0))}</td>
                <td className="py-2 font-medium text-green-600">{formatNum(Object.values(channelUtilMap).reduce((s, u) => s + (u.available_capacity || 0), 0))}</td>
              </tr>
            </tbody>
          </table>
        </div>
        {!editChannels && (
          <button onClick={() => setEditChannels(currentChannels)} className="mt-3 text-xs text-[#0891b2] hover:underline">Editar capacidad</button>
        )}
      </SectionCard>

      {/* Capacity Allocation Trace */}
      <div id="allocation-trace-panel" data-testid="allocation-trace-panel">
        <AllocationTracePanel trace={data.allocationTrace} />
      </div>

      {/* Program Capacity Policy */}
      <div id="program-policy-panel" data-testid="program-policy-panel">
        <ProgramPolicyPanel policy={data.programPolicy} summary={data.summary} navigateTo={navigateTo} />
      </div>

      {/* Backlog */}
      <SectionCard title="Backlog No Certificado" color="#9ca3af">
        <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
          {['Result Sync', 'Impact Attribution', 'Driver Movement', 'Agent Attribution', 'ROI Engine', 'Program Builder'].map((item) => (
            <div key={item} className="flex items-center gap-2 px-3 py-2 bg-gray-50 rounded-lg">
              <span className="w-1.5 h-1.5 rounded-full bg-gray-300" />
              {item} — Pendiente certificacion
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-400 mt-3">Estas funcionalidades no estan visibles operacionalmente hasta completar su certificacion.</p>
      </SectionCard>
    </div>
  )
}

function ConfigItem({ label, value, highlight, badge }) {
  return (
    <div className="bg-gray-50 rounded-xl p-3">
      <span className="text-xs text-gray-400">{label}</span>
      <p className={`mt-0.5 ${highlight ? 'text-lg font-bold text-gray-800' : 'font-medium text-gray-700'}`}>
        {value}
        {badge && <StatusBadge status={badge} />}
      </p>
    </div>
  )
}

function AllocationTracePanel({ trace }) {
  if (!trace) return null

  return (
    <SectionCard title="Capacity Allocation Trace" color="#d97706">
      {/* Summary */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        <AllocKpi label="Accionables" value={formatNum(trace.total_actionable)} color="text-gray-800" />
        <AllocKpi label="Capacidad" value={formatNum(trace.total_capacity)} color="text-[#0891b2]" />
        <AllocKpi label="Asignados" value={formatNum(trace.assigned_total)} color="text-green-600" />
        <AllocKpi label="Sin Canal" value={formatNum(trace.unassigned_total)} color="text-red-600" />
      </div>

      {trace.explanation && (
        <SemanticBanner severity="WARNING" className="mb-4">
          <span className="font-medium">Por que quedaron UNASSIGNED:</span> {trace.explanation}
        </SemanticBanner>
      )}

      {/* By Program */}
      {trace.by_program?.length > 0 && (
        <div className="mb-4">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Consumo por Programa</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100 text-gray-400 bg-gray-50">
                  <th className="text-left py-2 px-2 font-medium">Programa</th>
                  <th className="text-right py-2 px-2 font-medium">Prioridad</th>
                  <th className="text-right py-2 px-2 font-medium">Accionables</th>
                  <th className="text-right py-2 px-2 font-medium">Asignados</th>
                  <th className="text-right py-2 px-2 font-medium">Sin Canal</th>
                  <th className="text-right py-2 px-2 font-medium">% Cap</th>
                </tr>
              </thead>
              <tbody>
                {trace.by_program.map((p) => (
                  <tr key={p.program_code} className="border-b border-gray-50">
                    <td className="py-2 px-2 font-medium text-gray-700">{p.program_name}</td>
                    <td className="py-2 px-2 text-center text-gray-500">#{p.priority_rank}</td>
                    <td className="py-2 px-2 text-right text-gray-700">{formatNum(p.actionable)}</td>
                    <td className="py-2 px-2 text-right text-green-600 font-medium">{formatNum(p.assigned)}</td>
                    <td className="py-2 px-2 text-right">
                      {p.unassigned > 0 ? (
                        <span className="text-red-600 font-medium">{formatNum(p.unassigned)}</span>
                      ) : (
                        <span className="text-gray-300">0</span>
                      )}
                    </td>
                    <td className="py-2 px-2 text-right text-gray-500">{p.capacity_share_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {trace.by_program.map((p) => (
            p.reason && <p key={p.program_code} className="text-xs text-gray-500 mt-1">{p.program_name}: {p.reason}</p>
          ))}
        </div>
      )}

      {/* By Channel */}
      {trace.by_channel?.length > 0 && (
        <div className="mb-3">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Consumo por Canal</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100 text-gray-400 bg-gray-50">
                  <th className="text-left py-2 px-2 font-medium">Canal</th>
                  <th className="text-right py-2 px-2 font-medium">Capacidad</th>
                  <th className="text-right py-2 px-2 font-medium">Asignado</th>
                  <th className="text-right py-2 px-2 font-medium">Utilizacion</th>
                  <th className="text-left py-2 px-2 font-medium">Llenado por</th>
                </tr>
              </thead>
              <tbody>
                {trace.by_channel.map((ch) => (
                  <tr key={ch.channel} className="border-b border-gray-50">
                    <td className="py-2 px-2 font-medium text-gray-700">{ch.channel}</td>
                    <td className="py-2 px-2 text-right text-gray-600">{formatNum(ch.configured_capacity)}</td>
                    <td className="py-2 px-2 text-right text-gray-700 font-medium">{formatNum(ch.macro_assigned)}</td>
                    <td className="py-2 px-2 text-right">
                      <span className={ch.utilization_pct >= 100 ? 'text-red-600 font-bold' : 'text-gray-500'}>
                        {ch.utilization_pct}%
                      </span>
                    </td>
                    <td className="py-2 px-2 text-xs text-gray-500">
                      {(ch.filled_by_programs || []).map((fp, i) => (
                        <span key={i}>{i > 0 ? ', ' : ''}{fp.program_name} (+{fp.assigned})</span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Allocation order - compact */}
      {trace.allocation_order?.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Orden de Asignacion</h4>
          <div className="space-y-1">
            {trace.allocation_order.filter(a => a.rejected > 0 || a.assigned > 0).map((a, i) => (
              <div key={i} className={`text-xs rounded-lg p-2 flex items-center gap-2 ${a.rejected > 0 ? 'bg-red-50 border border-red-100' : 'bg-gray-50'}`}>
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${a.rejected > 0 ? 'bg-red-200 text-red-700' : 'bg-green-200 text-green-700'}`}>
                  {a.step}
                </span>
                <span className="text-gray-700">
                  <span className="font-medium">{a.program_name}</span>
                  {a.rejected > 0 ? (
                    <span className="text-red-600"> — {a.rejected} RECHAZADOS (sin capacidad)</span>
                  ) : (
                    <span className="text-green-600"> — {a.assigned} asignados a {a.channel}</span>
                  )}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {trace.remediation && (
        <SemanticBanner severity="INFO" className="mt-3">
          <span className="font-medium">Que se tendria que cambiar:</span> {trace.remediation}
        </SemanticBanner>
      )}
    </SectionCard>
  )
}

function AllocKpi({ label, value, color = 'text-gray-800' }) {
  return (
    <div className="bg-gray-50 rounded-xl p-3 text-center">
      <span className={`text-xl font-bold ${color}`}>{value}</span>
      <p className="text-xs text-gray-400 mt-0.5">{label}</p>
    </div>
  )
}

function ProgramPolicyPanel({ policy, summary, navigateTo }) {
  if (!policy?.active || !policy?.programs?.length) return null

  return (
    <SectionCard title="Program Capacity Policy" color="#059669">
      <div className="text-xs text-gray-400 mb-3">
        Politica que gobierna como se distribuye la capacidad entre programas.
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-100 text-gray-400 bg-gray-50">
              <th className="text-left py-2 px-2 font-medium">Programa</th>
              <th className="text-center py-2 px-2 font-medium">Rank</th>
              <th className="text-center py-2 px-2 font-medium">Mode</th>
              <th className="text-right py-2 px-2 font-medium">Min</th>
              <th className="text-right py-2 px-2 font-medium">Max</th>
              <th className="text-right py-2 px-2 font-medium">Share%</th>
              <th className="text-center py-2 px-2 font-medium">Status</th>
              <th className="text-left py-2 px-2 font-medium">Reason</th>
            </tr>
          </thead>
          <tbody>
            {policy.programs.map((p) => (
              <tr key={p.program_code} className="border-b border-gray-50">
                <td className="py-2 px-2 font-medium text-gray-700">{p.program_code?.replace('PROGRAM_', '')}</td>
                <td className="py-2 px-2 text-center text-gray-500">#{p.priority_rank}</td>
                <td className="py-2 px-2 text-center">
                  {(() => {
                    const am = getAllocationModeSemantic(p.allocation_mode)
                    return <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${am.bg} ${am.color}`}>{am.label}</span>
                  })()}
                </td>
                <td className="py-2 px-2 text-right text-gray-500">{p.min_daily_capacity ?? '—'}</td>
                <td className="py-2 px-2 text-right text-gray-500">{p.max_daily_capacity ?? '—'}</td>
                <td className="py-2 px-2 text-right text-gray-500">{p.target_share_pct != null ? p.target_share_pct + '%' : '—'}</td>
                <td className="py-2 px-2 text-center">
                  <StatusBadge status={p.policy_status} />
                </td>
                <td className="py-2 px-2 text-gray-400 text-[11px] max-w-[200px] truncate">{p.policy_reason || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="mt-3 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
        <p className="text-xs text-yellow-800">
          <span className="font-medium">Guardrails:</span> Activation requires validation + simulation. No auto-rebuild. Changes affect future queue builds only.
        </p>
        {navigateTo && (
          <button
            data-testid="cta-view-build-audit"
            onClick={() => navigateTo('queue', { label: 'Build Audit' })}
            className="mt-2 text-xs text-yellow-700 hover:text-yellow-900 underline"
          >
            Ver Build Audit en Queue
          </button>
        )}
      </div>
    </SectionCard>
  )
}
