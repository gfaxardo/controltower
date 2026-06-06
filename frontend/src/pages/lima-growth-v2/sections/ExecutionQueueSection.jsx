import { useState } from 'react'
import { SectionCard, LoadingState, ErrorState, StatusBadge, formatNum } from '../components/SharedComponents.jsx'
import FreshnessBadge from '../components/FreshnessBadge.jsx'

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
  const qSummary = data.queueSummary
  const summary = data.summary
  const isQueueLoading = loading.queue && !queue

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

  const status = qSummary?.status || 'NOT_BUILT'
  const totals = qSummary?.totals || {}

  return (
    <div className="space-y-5">
      {/* 1. Queue Status Header */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold text-gray-700">Execution Queue</span>
            <StatusBadge status={status} />
            {qSummary?.freshness && <FreshnessBadge freshness={qSummary.freshness} compact />}
          </div>
          <div className="flex items-center gap-4 text-xs text-gray-400">
            <span>Fecha: {qSummary?.date || '—'}</span>
            {qSummary?.explanation && <span className="text-gray-500 max-w-md truncate">{qSummary.explanation}</span>}
          </div>
        </div>

        {/* KPI Row */}
        <div className="grid grid-cols-5 gap-3 mb-4">
          <KpiBlock label="READY" value={formatNum(totals.ready)} color="text-green-600" />
          <KpiBlock label="HELD" value={formatNum(totals.held)} color="text-yellow-600" />
          <KpiBlock label="EXPORTED" value={formatNum(totals.exported)} color="text-[#7c3aed]" />
          <KpiBlock label="TOTAL" value={formatNum(totals.total)} color="text-gray-800" />
          <KpiBlock label="STATUS" value={status} color={status === 'READY' ? 'text-green-600' : status === 'NOT_BUILT' ? 'text-gray-400' : 'text-gray-600'} />
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 flex-wrap">
          <button onClick={handleBuild} disabled={building} className="text-xs bg-[#d97706] text-white px-4 py-2 rounded-lg hover:bg-[#b65c00] disabled:opacity-50 font-medium">
            {building ? 'Construyendo...' : 'Construir Cola'}
          </button>
          <div className="flex items-center gap-1">
            <span className="text-xs text-gray-400">Limit:</span>
            <input type="number" min={1} max={50} value={exportLimit} onChange={(e) => setExportLimit(Math.min(50, Math.max(1, parseInt(e.target.value) || 1)))} className="w-14 px-2 py-1 border border-gray-200 rounded text-xs text-gray-700" />
          </div>
          <button onClick={handleExport} disabled={exporting || !(totals.ready > 0)} className="text-xs bg-[#7c3aed] text-white px-4 py-2 rounded-lg hover:bg-[#6d28d9] disabled:opacity-50 font-medium">
            {exporting ? 'Exportando...' : 'Exportar READY'}
          </button>
          {buildResult && !buildResult.error && (
            <span className="text-xs text-green-600">+{buildResult.created_count} en cola</span>
          )}
          {exportResult && !exportResult.error && exportResult.campaign_id_external && (
            <span className="text-xs text-green-600">Campana #{exportResult.campaign_id_external}</span>
          )}
          {qSummary?.remediation && (
            <span className="text-xs text-yellow-600">{qSummary.remediation}</span>
          )}
        </div>

        {/* Build/Export result feedback */}
        {buildResult && buildResult.error && <div className="mt-2 text-xs text-red-600 bg-red-50 rounded p-2">Error: {buildResult.error}</div>}
        {exportResult && (
          <div className={`mt-2 text-xs rounded p-2 ${exportResult.error ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
            {exportResult.error ? `Error: ${exportResult.error}` : (
              <span>Campana #{exportResult.campaign_id_external} — {exportResult.contacts_inserted} insertados, {exportResult.contacts_skipped} saltados, status: {exportResult.export_status}</span>
            )}
          </div>
        )}
      </div>

      {/* 2. Operational Breakdown */}
      {qSummary && status !== 'NOT_BUILT' && (
        <div className="grid grid-cols-3 gap-4">
          {qSummary.by_program?.length > 0 && (
            <SectionCard title="Por Programa" color="#7c3aed">
              <div className="space-y-2">
                {qSummary.by_program.map((p) => (
                  <div key={p.program_code} className="flex items-center justify-between text-xs border-b border-gray-50 pb-1.5">
                    <span className="text-gray-600">{p.program_code?.replace('PROGRAM_', '')}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-green-600 font-medium">R:{p.ready}</span>
                      <span className="text-yellow-600 font-medium">H:{p.held}</span>
                      <span className="text-gray-500">T:{p.total}</span>
                    </div>
                  </div>
                ))}
              </div>
            </SectionCard>
          )}
          {qSummary.by_channel?.length > 0 && (
            <SectionCard title="Por Canal" color="#0891b2">
              <div className="space-y-2">
                {qSummary.by_channel.map((c) => (
                  <div key={c.channel} className="flex items-center justify-between text-xs border-b border-gray-50 pb-1.5">
                    <span className="text-gray-600">{c.channel || 'UNASSIGNED'}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-green-600 font-medium">R:{c.ready}</span>
                      <span className="text-yellow-600 font-medium">H:{c.held}</span>
                      <span className="text-gray-500">T:{c.total}</span>
                    </div>
                  </div>
                ))}
              </div>
            </SectionCard>
          )}
          {qSummary.hold_reasons?.length > 0 && (
            <SectionCard title="Razones de Retencion" color="#dc2626">
              <div className="space-y-2">
                {qSummary.hold_reasons.map((h, i) => (
                  <div key={i} className="text-xs">
                    <div className="flex justify-between mb-0.5">
                      <span className="text-gray-600">{h.reason}</span>
                      <span className="font-medium text-red-600">{h.count}</span>
                    </div>
                    {h.remediation && <p className="text-gray-400">{h.remediation}</p>}
                  </div>
                ))}
              </div>
            </SectionCard>
          )}
        </div>
      )}

      {/* 3. Queue Records Preview */}
      <SectionCard title="Registros en Cola" color="#d97706">
        {/* Filters */}
        <div className="flex items-center gap-3 flex-wrap mb-3">
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

        {isQueueLoading ? (
          <LoadingState text="Cargando cola..." />
        ) : errors.queue ? (
          <ErrorState message={errors.queue} />
        ) : !queue ? (
          <div className="text-center py-8 text-sm text-gray-400">
            {status === 'NOT_BUILT' ? 'Usa "Construir Cola" para generar la cola del dia.' : 'Cargando datos de la cola...'}
          </div>
        ) : !(queue.records || []).length ? (
          <div className="text-center py-8 text-sm text-gray-400">Sin registros con los filtros actuales.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100 text-gray-400 bg-gray-50">
                  <th className="text-left py-2 px-3 font-medium">Nombre</th>
                  <th className="text-left py-2 px-3 font-medium">Telefono</th>
                  <th className="text-left py-2 px-3 font-medium">Programa</th>
                  <th className="text-left py-2 px-3 font-medium">Canal</th>
                  <th className="text-left py-2 px-3 font-medium">Estado</th>
                </tr>
              </thead>
              <tbody>
                {(queue.records || []).slice(0, 50).map((r, i) => (
                  <tr key={r.id || i} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 px-3 font-medium text-gray-700">{r.driver_name || '—'}</td>
                    <td className="py-2 px-3 text-gray-500 font-mono">{r.phone || '—'}</td>
                    <td className="py-2 px-3"><span className="px-1.5 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700">{r.program_code?.replace('PROGRAM_', '')}</span></td>
                    <td className="py-2 px-3"><ChannelBadge channel={r.assigned_channel} /></td>
                    <td className="py-2 px-3"><StatusBadge status={r.queue_status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      {/* 4. Export History */}
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

function KpiBlock({ label, value, color = 'text-gray-800' }) {
  return (
    <div className="bg-gray-50 rounded-xl p-3 text-center">
      <span className={`text-xl font-bold ${color}`}>{value}</span>
      <p className="text-xs text-gray-400 mt-0.5">{label}</p>
    </div>
  )
}

function ChannelBadge({ channel }) {
  const map = { CALL_CENTER: 'bg-blue-50 text-blue-700', SAC: 'bg-purple-50 text-purple-700', BOT: 'bg-cyan-50 text-cyan-700' }
  const label = { CALL_CENTER: 'Call Center', SAC: 'SAC', BOT: 'Bot' }
  return <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${map[channel] || 'bg-red-50 text-red-700'}`}>{label[channel] || 'Sin canal'}</span>
}
