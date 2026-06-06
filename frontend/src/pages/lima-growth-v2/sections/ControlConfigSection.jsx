import { useState } from 'react'
import { SectionCard, StatusBadge, formatNum } from '../components/SharedComponents.jsx'

const DEFAULT_CHANNELS = [
  { channel: 'Call Center', agents: 2, capacity_per_agent: 40 },
  { channel: 'SAC', agents: 1, capacity_per_agent: 30 },
  { channel: 'Bot / WhatsApp', agents: 1, capacity_per_agent: 200 },
]

export default function ControlConfigSection({ data, loading, errors, onSaveCapacity }) {
  const summary = data.summary
  const config = data.config
  const capacityData = data.capacity

  const channels = capacityData?.channels?.length ? capacityData.channels : DEFAULT_CHANNELS
  const [editChannels, setEditChannels] = useState(null)
  const [saving, setSaving] = useState(false)

  const currentChannels = editChannels || channels

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
                <th className="text-left py-2 font-medium">Capacidad / Agente</th>
                <th className="text-left py-2 font-medium">Capacidad Total</th>
              </tr>
            </thead>
            <tbody>
              {currentChannels.map((ch, idx) => {
                const total = (ch.agents || 0) * (ch.capacity_per_agent || 0)
                const editing = !!editChannels
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
                  </tr>
                )
              })}
              <tr className="bg-gray-50">
                <td className="py-2 font-semibold text-gray-700">TOTAL</td>
                <td className="py-2 text-gray-500">{currentChannels.reduce((s, c) => s + (c.agents || 0), 0)}</td>
                <td />
                <td className="py-2 font-bold text-gray-800">{formatNum(totalCap)}</td>
              </tr>
            </tbody>
          </table>
        </div>
        {!editChannels && (
          <button onClick={() => setEditChannels(currentChannels)} className="mt-3 text-xs text-[#0891b2] hover:underline">Editar capacidad</button>
        )}
      </SectionCard>

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
