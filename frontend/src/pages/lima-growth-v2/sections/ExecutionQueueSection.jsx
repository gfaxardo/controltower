import { useState } from 'react'
import { SectionCard, LoadingState, ErrorState, StatusBadge, formatNum } from '../components/SharedComponents.jsx'

const PROGRAMS = ['PROGRAM_HIGH_VALUE_RECOVERY', 'PROGRAM_CHURN_PREVENTION', 'PROGRAM_14_90', 'PROGRAM_ACTIVE_GROWTH']
const CHANNELS = ['CALL_CENTER', 'SAC', 'BOT']

export default function ExecutionQueueSection({ data, loading, errors, onBuildQueue, onExport, onRefresh }) {
  const [queueFilters, setQueueFilters] = useState({ status: '', program: '', channel: '' })
  const [building, setBuilding] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportLimit, setExportLimit] = useState(5)
  const [exportResult, setExportResult] = useState(null)
  const [buildResult, setBuildResult] = useState(null)

  const queue = data.queue
  const summary = data.summary
  const isLoading = loading.queue && !queue

  const handleBuild = async () => {
    setBuilding(true)
    try {
      const result = await onBuildQueue()
      setBuildResult(result)
      if (onRefresh) await onRefresh()
    } catch (e) {
      setBuildResult({ error: e.message })
    } finally {
      setBuilding(false)
    }
  }

  const handleExport = async () => {
    setExporting(true)
    setExportResult(null)
    try {
      const result = await onExport(exportLimit)
      setExportResult(result)
    } catch (e) {
      setExportResult({ error: e.message })
    } finally {
      setExporting(false)
    }
  }

  const handleFilter = (field, value) => {
    const f = { ...queueFilters, [field]: value }
    setQueueFilters(f)
    if (onRefresh) onRefresh(f)
  }

  return (
    <div className="space-y-5">
      {/* Queue KPIs + Actions */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
          <div className="flex items-center gap-4">
            <KpiInline label="En Cola" value={formatNum(queue?.total_records)} />
            <KpiInline label="READY" value={formatNum(queue?.ready_count)} color="text-green-600" />
            <KpiInline label="HELD" value={formatNum(queue?.held_count)} color="text-yellow-600" />
            <KpiInline label="Exportados" value={formatNum(summary?.loopcontrol_contacts_inserted)} color="text-[#7c3aed]" />
            {buildResult && !buildResult.error && (
              <span className="text-xs text-green-600">+{buildResult.created_count} creados</span>
            )}
            {exportResult && !exportResult.error && exportResult.campaign_id_external && (
              <span className="text-xs text-green-600">Campana #{exportResult.campaign_id_external} exportada</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1">
              <span className="text-xs text-gray-400">Limit:</span>
              <input type="number" min={1} max={50} value={exportLimit} onChange={(e) => setExportLimit(Math.min(50, Math.max(1, parseInt(e.target.value) || 1)))} className="w-14 px-2 py-1 border border-gray-200 rounded text-xs text-gray-700" />
            </div>
            <button onClick={handleExport} disabled={exporting || !(queue?.ready_count > 0)} className="text-xs bg-[#7c3aed] text-white px-4 py-2 rounded-lg hover:bg-[#6d28d9] disabled:opacity-50 font-medium">
              {exporting ? 'Exportando...' : 'Exportar READY'}
            </button>
            <button onClick={handleBuild} disabled={building} className="text-xs bg-[#d97706] text-white px-4 py-2 rounded-lg hover:bg-[#b65c00] disabled:opacity-50 font-medium">
              {building ? 'Construyendo...' : 'Construir Cola'}
            </button>
          </div>
        </div>

        {/* Export Result */}
        {exportResult && (
          <div className={`p-3 rounded-lg text-xs ${exportResult.error ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
            {exportResult.error ? (
              <span>Error: {exportResult.error}</span>
            ) : (
              <div className="flex items-center gap-4">
                <span>Campana: <strong>#{exportResult.campaign_id_external}</strong></span>
                <span>Insertados: <strong>{exportResult.contacts_inserted}</strong></span>
                <span>Saltados: <strong>{exportResult.contacts_skipped}</strong></span>
                <span>Status: <strong>{exportResult.export_status}</strong></span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-3">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Filtros</span>
          <select value={queueFilters.status} onChange={(e) => handleFilter('status', e.target.value)} className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 text-gray-600">
            <option value="">Todos</option>
            <option value="READY">READY</option>
            <option value="HELD">HELD</option>
          </select>
          <select value={queueFilters.program} onChange={(e) => handleFilter('program', e.target.value)} className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 text-gray-600">
            <option value="">Todos los programas</option>
            {PROGRAMS.map((p) => <option key={p} value={p}>{p.replace('PROGRAM_', '')}</option>)}
          </select>
          <select value={queueFilters.channel} onChange={(e) => handleFilter('channel', e.target.value)} className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 text-gray-600">
            <option value="">Todos los canales</option>
            {CHANNELS.map((c) => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}
          </select>
          <div className="flex-1" />
          <span className="text-xs text-gray-400">{queue ? formatNum(queue.total_records) : '...'} registros</span>
        </div>
      </div>

      {/* Queue Table */}
      {isLoading ? (
        <LoadingState text="Cargando cola..." />
      ) : errors.queue ? (
        <ErrorState message={errors.queue} />
      ) : !queue ? (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 text-center">
          <p className="text-sm text-gray-400">Usa "Construir Cola" para generar la cola del dia.</p>
        </div>
      ) : !(queue.records || []).length ? (
        <SectionCard title="Cola de Asignacion" color="#d97706">
          <div className="text-center py-8 text-sm text-gray-400">Sin registros con los filtros actuales.</div>
        </SectionCard>
      ) : (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100 text-gray-400 bg-gray-50">
                  <th className="text-left py-2.5 px-3 font-medium">Nombre</th>
                  <th className="text-left py-2.5 px-3 font-medium">Telefono</th>
                  <th className="text-left py-2.5 px-3 font-medium">Programa</th>
                  <th className="text-left py-2.5 px-3 font-medium">Canal</th>
                  <th className="text-left py-2.5 px-3 font-medium">Estado</th>
                  <th className="text-left py-2.5 px-3 font-medium">Motivo</th>
                </tr>
              </thead>
              <tbody>
                {(queue.records || []).map((r, i) => (
                  <tr key={r.id || i} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 px-3 font-medium text-gray-700">{r.driver_name || '—'}</td>
                    <td className="py-2 px-3 text-gray-500 font-mono">{r.phone || '—'}</td>
                    <td className="py-2 px-3"><span className="px-1.5 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700">{r.program_code?.replace('PROGRAM_', '')}</span></td>
                    <td className="py-2 px-3"><ChannelBadge channel={r.assigned_channel} /></td>
                    <td className="py-2 px-3"><StatusBadge status={r.queue_status} /></td>
                    <td className="py-2 px-3 text-gray-500 max-w-[200px] truncate" title={r.opportunity_reason}>{r.opportunity_reason || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Export History */}
      <SectionCard title="Historial de Exportaciones" color="#7c3aed">
        {!data.exports?.length ? (
          <div className="text-center py-8 text-sm text-gray-400">Sin exports registrados.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100 text-gray-400 bg-gray-50">
                  <th className="text-left py-2 px-3 font-medium">Fecha</th>
                  <th className="text-left py-2 px-3 font-medium">Campana</th>
                  <th className="text-left py-2 px-3 font-medium">LC ID</th>
                  <th className="text-left py-2 px-3 font-medium">Programa</th>
                  <th className="text-left py-2 px-3 font-medium">Enviados</th>
                  <th className="text-left py-2 px-3 font-medium">Insertados</th>
                  <th className="text-left py-2 px-3 font-medium">Estado</th>
                </tr>
              </thead>
              <tbody>
                {data.exports.map((e) => (
                  <tr key={e.export_id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 px-3 text-gray-500">{e.exported_at ? new Date(e.exported_at).toLocaleDateString('es-PE') : '—'}</td>
                    <td className="py-2 px-3 font-medium text-gray-700">{e.campaign_name}</td>
                    <td className="py-2 px-3 text-gray-500 font-mono">{e.campaign_id_external || '—'}</td>
                    <td className="py-2 px-3"><span className="px-1.5 py-0.5 rounded text-xs bg-purple-50 text-purple-700">{e.program_code?.replace('PROGRAM_', '')}</span></td>
                    <td className="py-2 px-3 text-gray-600">{e.contacts_sent}</td>
                    <td className="py-2 px-3 font-medium text-green-600">{e.contacts_inserted}</td>
                    <td className="py-2 px-3"><StatusBadge status={e.export_status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  )
}

function KpiInline({ label, value, color = 'text-gray-800' }) {
  return (
    <div className="text-center px-3">
      <span className={`text-xl font-bold ${color}`}>{value}</span>
      <p className="text-xs text-gray-400">{label}</p>
    </div>
  )
}

function ChannelBadge({ channel }) {
  const map = {
    CALL_CENTER: 'bg-blue-50 text-blue-700',
    SAC: 'bg-purple-50 text-purple-700',
    BOT: 'bg-cyan-50 text-cyan-700',
  }
  const label = { CALL_CENTER: 'Call Center', SAC: 'SAC', BOT: 'Bot' }
  return <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${map[channel] || 'bg-red-50 text-red-700'}`}>{label[channel] || 'Sin canal'}</span>
}
