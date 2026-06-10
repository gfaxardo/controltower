import { useState } from 'react'
import { SectionCard, LoadingState, ErrorState, StatusBadge, SemanticBanner, formatNum } from '../components/SharedComponents.jsx'
import FreshnessBadge from '../components/FreshnessBadge.jsx'
import { getChannelSemantic } from '../design/semanticRegistry.js'

const PROGRAMS = ['PROGRAM_HIGH_VALUE_RECOVERY', 'PROGRAM_CHURN_PREVENTION', 'PROGRAM_14_90', 'PROGRAM_ACTIVE_GROWTH']
const CHANNELS = ['CALL_CENTER', 'SAC', 'BOT', 'FIELD', 'WHATSAPP']
const MODES = [
  { value: 'CAPACITY_LIMITED', label: 'Respetar Capacidad', desc: 'Respeta la capacidad diaria configurada.' },
  { value: 'TAKE_ALL', label: 'Tomar Todo', desc: 'Toma todo el universo filtrado. Requiere justificacion.' },
  { value: 'PROGRAM_LIMITED', label: 'Limitar por Programa', desc: 'Define cantidad maxima por programa.' },
  { value: 'CHANNEL_LIMITED', label: 'Limitar por Canal', desc: 'Define cantidad maxima por canal.' },
]

export default function ExecutionQueueSection({ data, loading, errors, onBuildQueue, onExport, onRefresh, sectionFilter, navigateTo }) {
  const [queueFilters, setQueueFilters] = useState(() => ({
    status: sectionFilter?.status || '',
    program: sectionFilter?.program || '',
    channel: sectionFilter?.channel || '',
  }))
  const [building, setBuilding] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportLimit, setExportLimit] = useState(5)
  const [exportResult, setExportResult] = useState(null)
  const [buildResult, setBuildResult] = useState(null)

  // Queue Control Panel state
  const [buildMode, setBuildMode] = useState('CAPACITY_LIMITED')
  const [overrideReason, setOverrideReason] = useState('')
  const [programLimits, setProgramLimits] = useState({})
  const [channelLimits, setChannelLimits] = useState({})
  const [showPreview, setShowPreview] = useState(false)

  const queue = data.queue
  const qSummary = data.queueSummary
  const summary = data.summary
  const isQueueLoading = loading.queue && !queue

  const updateProgramLimit = (program, val) => {
    setProgramLimits(prev => ({ ...prev, [program]: Math.max(0, parseInt(val) || 0) }))
  }
  const updateChannelLimit = (channel, val) => {
    setChannelLimits(prev => ({ ...prev, [channel]: Math.max(0, parseInt(val) || 0) }))
  }

  const canBuild = () => {
    if (buildMode === 'TAKE_ALL' && !overrideReason.trim()) return false
    return true
  }

  // Build preview calculation
  const eligibleTotal = summary?.eligible_total || 0
  const capacity = summary?.daily_action_capacity || 500
  let expectedQueue = 0
  if (buildMode === 'CAPACITY_LIMITED') expectedQueue = Math.min(eligibleTotal, capacity)
  else if (buildMode === 'TAKE_ALL') expectedQueue = eligibleTotal
  else if (buildMode === 'PROGRAM_LIMITED') expectedQueue = Object.values(programLimits).reduce((s, v) => s + v, 0)
  else if (buildMode === 'CHANNEL_LIMITED') expectedQueue = Object.values(channelLimits).reduce((s, v) => s + v, 0)
  const exceedsCapacity = expectedQueue > capacity && buildMode !== 'CAPACITY_LIMITED'

  const handleBuild = async () => {
    setBuilding(true)
    setBuildResult(null)
    try {
      const result = await onBuildQueue()
      if (result) {
        setBuildResult(result)
      } else {
        setBuildResult({ error: 'Build completed but returned no data' })
      }
      if (onRefresh) await onRefresh()
    } catch (e) {
      setBuildResult({ error: e.message || 'Build failed' })
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
      {/* ===== QUEUE CONTROL PANEL ===== */}
      <div className="bg-gradient-to-r from-[#1a0a4a] to-[#2d1b7a] rounded-2xl p-5 text-white shadow-md">
        <div className="flex items-center gap-2 mb-3">
          <svg className="w-5 h-5 text-white/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 4h4v4H4V4zm6 0h4v4h-4V4zm6 0h4v4h-4V4zM4 10h4v4H4v-4zm6 0h4v4h-4v-4zm6 0h4v4h-4v-4zM4 16h4v4H4v-4zm6 0h4v4h-4v-4zm6 0h4v4h-4v-4z" />
          </svg>
          <span className="text-sm font-bold uppercase tracking-wide">Queue Control Panel</span>
        </div>

        {/* Mode Selector */}
        <div className="grid grid-cols-4 gap-2 mb-3">
          {MODES.map(m => (
            <button key={m.value} onClick={() => { setBuildMode(m.value); setShowPreview(false) }}
              className={`p-2 rounded-lg text-xs text-left transition-all ${buildMode === m.value ? 'bg-white/20 ring-1 ring-white/30' : 'bg-white/5 hover:bg-white/10'}`}>
              <p className="font-semibold">{m.label}</p>
              <p className="text-white/50 mt-0.5 leading-tight">{m.desc}</p>
            </button>
          ))}
        </div>

        {/* PROGRAM_LIMITED inputs */}
        {buildMode === 'PROGRAM_LIMITED' && (
          <div className="bg-white/10 rounded-lg p-3 mb-3">
            <p className="text-xs text-white/60 mb-2">Limites por Programa</p>
            <div className="grid grid-cols-4 gap-2">
              {PROGRAMS.map(p => (
                <div key={p}>
                  <p className="text-[10px] text-white/50">{p.replace('PROGRAM_', '').replace(/_/g, ' ')}</p>
                  <input type="number" min={0} value={programLimits[p] || ''} onChange={e => updateProgramLimit(p, e.target.value)}
                    className="w-full px-2 py-1 rounded text-xs text-gray-800 bg-white" placeholder="0" />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* CHANNEL_LIMITED inputs */}
        {buildMode === 'CHANNEL_LIMITED' && (
          <div className="bg-white/10 rounded-lg p-3 mb-3">
            <p className="text-xs text-white/60 mb-2">Limites por Canal</p>
            <div className="grid grid-cols-5 gap-2">
              {CHANNELS.map(c => (
                <div key={c}>
                  <p className="text-[10px] text-white/50">{c}</p>
                  <input type="number" min={0} value={channelLimits[c] || ''} onChange={e => updateChannelLimit(c, e.target.value)}
                    className="w-full px-2 py-1 rounded text-xs text-gray-800 bg-white" placeholder="0" />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAKE_ALL override_reason */}
        {buildMode === 'TAKE_ALL' && (
          <div className="bg-white/10 rounded-lg p-3 mb-3">
            <p className="text-xs text-amber-300 font-medium mb-1">ATENCION: Tomar todo excede la capacidad configurada ({capacity}).</p>
            <p className="text-[10px] text-white/50 mb-2">Justificacion obligatoria:</p>
            <textarea value={overrideReason} onChange={e => setOverrideReason(e.target.value)}
              className="w-full px-2 py-1.5 rounded text-xs text-gray-800 bg-white" rows={2}
              placeholder="Motivo del override operativo..." />
          </div>
        )}

        {/* Build Preview */}
        <button onClick={() => setShowPreview(!showPreview)} className="text-xs text-white/60 hover:text-white mb-2 underline">
          {showPreview ? 'Ocultar preview' : 'Ver preview'}
        </button>
        {showPreview && (
          <div className="bg-white/10 rounded-lg p-3 mb-3 grid grid-cols-5 gap-2 text-center text-xs">
            <div><p className="text-white/40">Universo</p><p className="font-bold">{formatNum(summary?.universe_total)}</p></div>
            <div><p className="text-white/40">Elegibles</p><p className="font-bold">{formatNum(eligibleTotal)}</p></div>
            <div><p className="text-white/40">Capacidad</p><p className="font-bold">{formatNum(capacity)}</p></div>
            <div><p className="text-white/40">Cola Esperada</p><p className="font-bold text-amber-300">{formatNum(expectedQueue)}</p></div>
            <div><p className="text-white/40">Restante</p><p className="font-bold">{formatNum(Math.max(0, eligibleTotal - expectedQueue))}</p></div>
          </div>
        )}

        {exceedsCapacity && (
          <div className="bg-amber-500/20 border border-amber-400/30 rounded-lg p-2 mb-3 text-xs text-amber-300">
            CAPACITY_EXCEEDED_BY_OPERATOR_OVERRIDE: {expectedQueue} excede capacidad de {capacity}.
          </div>
        )}

        {/* Action buttons */}
        <div className="flex items-center gap-3">
          <button onClick={handleBuild} disabled={building || !canBuild()}
            className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-gray-900 rounded-lg text-xs font-bold disabled:opacity-40 transition-colors">
            {building ? 'Construyendo...' : 'Construir Cola'}
          </button>
          <span className="text-white/30 text-xs">|</span>
          <span className="text-xs text-white/50">Export limit:</span>
          <input type="number" min={1} max={50} value={exportLimit} onChange={e => setExportLimit(Math.min(50, Math.max(1, parseInt(e.target.value) || 1)))}
            className="w-14 px-2 py-1 rounded text-xs text-gray-800" />
          <button onClick={handleExport} disabled={exporting || !(totals.ready > 0)}
            className="px-3 py-2 bg-purple-500 hover:bg-purple-400 text-white rounded-lg text-xs font-medium disabled:opacity-40">
            {exporting ? 'Exportando...' : 'Exportar READY'}
          </button>
        </div>

        {buildResult && !buildResult.error && (
          <div className="mt-2 bg-emerald-500/20 rounded-lg p-2 text-xs text-emerald-200">
            +{buildResult.created_count || buildResult.ready_count} en cola ({buildResult.ready_count || 0} READY, {buildResult.held_count || 0} HELD)
          </div>
        )}
        {buildResult?.error && <div className="mt-2 bg-red-500/20 rounded-lg p-2 text-xs text-red-200">Error: {buildResult.error}</div>}
        {exportResult && (
          <div className="mt-2 bg-purple-500/20 rounded-lg p-2 text-xs text-purple-200">
            {exportResult.error ? `Error: ${exportResult.error}` : `Campana #${exportResult.campaign_id_external} — ${exportResult.contacts_inserted} insertados`}
          </div>
        )}
      </div>

      {/* ===== COVERAGE CARD ===== */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Coverage</span>
        <div className="grid grid-cols-3 gap-3 mt-2">
          <CoverageBlock label="Elegibles" value={formatNum(eligibleTotal)} />
          <CoverageBlock label="En Cola" value={formatNum(totals.ready + totals.held || 0)} />
          <CoverageBlock label="Coverage %" value={`${eligibleTotal > 0 ? ((totals.ready + totals.held || 0) / eligibleTotal * 100).toFixed(1) : 0}%`} color="text-purple-600" />
        </div>
      </div>

      {/* ===== WARNINGS ===== */}
      {(totals.held > 0 || exceedsCapacity) && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3">
          <p className="text-xs font-semibold text-amber-700 mb-1">Warnings</p>
          {totals.held > 0 && <p className="text-xs text-amber-600">{totals.held} drivers HELD (sin telefono o canal)</p>}
          {exceedsCapacity && <p className="text-xs text-amber-600">Capacidad excedida por override operativo</p>}
          {(eligibleTotal - (totals.ready + totals.held || 0)) > 0 && (
            <p className="text-xs text-amber-600">{formatNum(eligibleTotal - (totals.ready + totals.held || 0))} drivers pendientes sin asignar</p>
          )}
        </div>
      )}

      {/* ===== QUEUE TABLE (existing) ===== */}
      <SectionCard title="Registros en Cola" color="#d97706">
        <div className="flex items-center gap-3 flex-wrap mb-3">
          <select value={queueFilters.status} onChange={e => handleFilter('status', e.target.value)} className="text-xs border border-gray-200 rounded-lg px-2 py-1.5">
            <option value="">Todos</option>
            <option value="READY">READY</option>
            <option value="HELD">HELD</option>
            <option value="EXPORTED">EXPORTED</option>
          </select>
          <select value={queueFilters.program} onChange={e => handleFilter('program', e.target.value)} className="text-xs border border-gray-200 rounded-lg px-2 py-1.5">
            <option value="">Todos los programas</option>
            {PROGRAMS.map(p => <option key={p} value={p}>{p.replace('PROGRAM_', '')}</option>)}
          </select>
          <select value={queueFilters.channel} onChange={e => handleFilter('channel', e.target.value)} className="text-xs border border-gray-200 rounded-lg px-2 py-1.5">
            <option value="">Todos los canales</option>
            {CHANNELS.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <span className="text-xs text-gray-400 ml-auto">{queue ? formatNum(queue.total_records) : '...'} registros</span>
        </div>

        {isQueueLoading && <LoadingState text="Cargando cola..." />}
        {!isQueueLoading && !queue && <div className="text-center py-8 text-sm text-gray-400">Construye la cola para ver registros.</div>}
        {!isQueueLoading && queue && !(queue.records || []).length && <div className="text-center py-8 text-sm text-gray-400">Sin registros.</div>}
        {!isQueueLoading && queue && (queue.records || []).length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="border-b border-gray-100 text-gray-400 bg-gray-50">
                <th className="text-left py-2 px-3">Nombre</th><th className="text-left py-2 px-3">Telefono</th>
                <th className="text-left py-2 px-3">Programa</th><th className="text-left py-2 px-3">Canal</th>
                <th className="text-left py-2 px-3">Estado</th><th className="text-left py-2 px-3">Campana</th>
                <th className="text-center py-2 px-1 w-10"></th>
              </tr></thead>
              <tbody>
                {(queue.records || []).slice(0, 50).map((r, i) => (
                  <tr key={r.id || i} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 px-3 font-medium text-gray-700">{r.driver_name || '—'}</td>
                    <td className="py-2 px-3 text-gray-500 font-mono">{r.phone || '—'}</td>
                    <td className="py-2 px-3"><span className="px-1.5 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700">{r.program_code?.replace('PROGRAM_', '')}</span></td>
                    <td className="py-2 px-3"><ChannelBadge channel={r.assigned_channel} /></td>
                    <td className="py-2 px-3"><StatusBadge status={r.queue_status} /></td>
                    <td className="py-2 px-3 text-gray-400 font-mono">{r.campaign_id_external?.slice(0, 12) || '—'}</td>
                    <td className="py-2 px-1 text-center">
                      <WhyButton driverId={r.driver_id} driverName={r.driver_name} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      {/* ===== BUILD HISTORY ===== */}
      <BuildHistoryPanel date={qSummary?.date} />

      {/* ===== EXPORT HISTORY ===== */}
      <SectionCard title="Historial de Exportaciones" color="#7c3aed">
        {!data.exports?.length ? <div className="text-center py-8 text-sm text-gray-400">Sin exports.</div> : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="border-b border-gray-100 text-gray-400 bg-gray-50">
                <th className="text-left py-2 px-3">Fecha</th><th className="text-left py-2 px-3">Campana</th>
                <th className="text-left py-2 px-3">Enviados</th><th className="text-left py-2 px-3">Insertados</th>
                <th className="text-left py-2 px-3">Estado</th>
              </tr></thead>
              <tbody>
                {data.exports.map(e => (
                  <tr key={e.export_id} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-2 px-3 text-gray-500">{e.exported_at ? new Date(e.exported_at).toLocaleDateString('es-PE') : '—'}</td>
                    <td className="py-2 px-3 font-medium text-gray-700">{e.campaign_name}</td>
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
      <ResultSyncPanel exports={data.exports} />
    </div>
  )
}

function ResultSyncPanel({ exports }) {
  const [selectedCampaign, setSelectedCampaign] = useState(null)
  const [summary, setSummary] = useState(null)
  const [records, setRecords] = useState(null)
  const [loading, setLoading] = useState(false)

  const campaigns = (exports || []).filter(e => e.campaign_id_external).slice(0, 10)

  const loadResults = async (cid) => {
    setSelectedCampaign(cid)
    setLoading(true)
    try {
      const { default: api } = await import('../../../services/api.js')
      const [s, r] = await Promise.all([
        api.get('/yego-lima-growth/loopcontrol/results/summary?campaign_id_external=' + cid),
        api.get('/yego-lima-growth/loopcontrol/results?campaign_id_external=' + cid)
      ])
      setSummary(s.data)
      setRecords(r.data)
    } catch { setSummary(null); setRecords(null) }
    finally { setLoading(false) }
  }

  return (
    <SectionCard title="Resultados LoopControl" color="#7c3aed">
      {!campaigns.length ? <p className="text-xs text-gray-400 py-4 text-center">No hay campanas exportadas con resultados.</p> :
        <div className="mb-3">
          <select value={selectedCampaign || ''} onChange={e => loadResults(e.target.value)} className="text-xs border border-gray-200 rounded-lg px-2 py-1.5">
            <option value="">Seleccionar campana...</option>
            {campaigns.map(c => <option key={c.campaign_id_external} value={c.campaign_id_external}>{c.campaign_name || c.campaign_id_external} ({new Date(c.exported_at).toLocaleDateString('es-PE')})</option>)}
          </select>
        </div>}
      {loading && <LoadingState text="Cargando resultados..." />}
      {summary && (
        <div className="grid grid-cols-4 gap-2 mb-3 text-center text-xs">
          <div className="bg-gray-50 rounded-lg p-2"><p className="font-bold">{formatNum(summary.total_results)}</p><p className="text-gray-400">Total</p></div>
          <div className="bg-emerald-50 rounded-lg p-2"><p className="font-bold text-emerald-700">{formatNum(summary.matched_queue_count)}</p><p className="text-gray-400">Matched</p></div>
          <div className="bg-amber-50 rounded-lg p-2"><p className="font-bold text-amber-700">{formatNum(summary.unmatched_count)}</p><p className="text-gray-400">Unmatched</p></div>
          <div className="bg-purple-50 rounded-lg p-2"><p className="font-bold text-purple-700">{formatNum(summary.contacted_count)}</p><p className="text-gray-400">Contacted</p></div>
        </div>)}
      {records?.records?.length > 0 && (
        <div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr className="border-b border-gray-100 text-gray-400"><th className="text-left py-1">Driver</th><th className="text-left py-1">Status</th><th className="text-left py-1">Disposition</th><th className="text-left py-1">Agent</th></tr></thead><tbody>{records.records.map((r,i) => (<tr key={i} className="border-b border-gray-50"><td className="py-1">{r.driver_name || r.phone || '�'}</td><td className="py-1"><span className={'px-1.5 py-0.5 rounded text-xs font-medium ' + (r.status==='CONTACTED'?'bg-emerald-100 text-emerald-700':'bg-gray-100 text-gray-600')}>{r.status||'UNKNOWN'}</span></td><td className="py-1">{r.disposition||'�'}</td><td className="py-1 text-gray-500">{r.agent||'�'}</td></tr>))}</tbody></table></div>)}
    </SectionCard>
  )
}


function BuildHistoryPanel({ date }) {
  const [entries, setEntries] = useState(null)
  const [loading, setLoading] = useState(false)

  const fetch = async () => {
    if (entries) return
    setLoading(true)
    try {
      const { default: api } = await import('../../../services/api.js')
      const resp = await api.get('/yego-lima-growth/assignment-queue/build-audit', { params: { limit: 20 }, timeout: 15000 })
      setEntries(resp.data?.entries || [])
    } catch { setEntries([]) }
    finally { setLoading(false) }
  }

  return (
    <SectionCard title="Build History" color="#7c3aed">
      {!entries && <button onClick={fetch} className="text-xs text-purple-600 hover:underline" disabled={loading}>{loading ? 'Cargando...' : 'Cargar historial'}</button>}
      {entries?.length === 0 && <p className="text-xs text-gray-400 py-4 text-center">Sin registros de build.</p>}
      {entries?.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="border-b border-gray-100 text-gray-400">
              <th className="text-left py-2">Fecha</th><th className="text-left py-2">Modo</th>
              <th className="text-right py-2">Creados</th><th className="text-right py-2">READY</th>
              <th className="text-right py-2">HELD</th><th className="text-left py-2">Override</th>
            </tr></thead>
            <tbody>
              {entries.map((e, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-2 text-gray-500">{e.created_at ? new Date(e.created_at).toLocaleDateString('es-PE') : '—'}</td>
                  <td className="py-2"><span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-gray-100 text-gray-700">{e.allocation_mode || e.mode || '—'}</span></td>
                  <td className="py-2 text-right font-medium">{formatNum(e.total_assigned || e.created_count)}</td>
                  <td className="py-2 text-right text-green-600">{formatNum(e.ready_count)}</td>
                  <td className="py-2 text-right text-amber-600">{formatNum(e.held_count)}</td>
                  <td className="py-2 text-gray-400 max-w-[150px] truncate">{e.override_reason || '—'}</td>
                </tr>
              ))}
            </tbody>
            </table>
          </div>
        )}
      </SectionCard>
  )
}

function CoverageBlock({ label, value, color = 'text-gray-800' }) {
  return (
    <div className="bg-gray-50 rounded-xl p-3 text-center">
      <span className={`text-lg font-bold ${color}`}>{value}</span>
      <p className="text-[10px] text-gray-400">{label}</p>
    </div>
  )
}

function WhyButton({ driverId, driverName }) {
  const [showModal, setShowModal] = useState(false)
  const [trace, setTrace] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchTrace = async () => {
    if (trace) { setShowModal(true); return }
    setLoading(true); setError(null)
    try {
      const { default: api } = await import('../../../services/api.js')
      const resp = await api.get('/yego-lima-growth/diagnostic-trace/' + driverId, { timeout: 15000 })
      setTrace(resp.data)
      setShowModal(true)
    } catch (e) {
      setError('Unable to load diagnostic trace')
    } finally { setLoading(false) }
  }

  return (
    <>
      <button onClick={fetchTrace} disabled={loading}
        className="text-[10px] px-1.5 py-0.5 rounded bg-purple-50 text-purple-600 hover:bg-purple-100 font-medium"
        title="Why is this driver here?">
        {loading ? '...' : 'Why?'}
      </button>
      {showModal && trace && (
        <WhyModal trace={trace} driverName={driverName} onClose={() => setShowModal(false)} />
      )}
      {error && !showModal && (
        <span className="text-[9px] text-red-500 ml-1">{error}</span>
      )}
    </>
  )
}

function WhyModal({ trace, driverName, onClose }) {
  const pt = trace.program_trace
  const tt = trace.transition_trace

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full max-h-[80vh] overflow-y-auto p-5" onClick={e => e.stopPropagation()}>
        <div className="flex justify-between items-center mb-4">
          <div>
            <span className="text-sm font-bold text-gray-800">Diagnostic Trace</span>
            <p className="text-[10px] text-gray-400">{driverName || trace.driver_id?.slice(0, 16)}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg">&times;</button>
        </div>

        {pt && (
          <div className="mb-4">
            <p className="text-xs font-semibold text-purple-600 mb-2">WHY THIS PROGRAM?</p>
            <div className="bg-purple-50 rounded-lg p-3 text-xs space-y-1">
              <p><span className="text-gray-400">Selected:</span> <span className="font-medium">{pt.selected_program}</span></p>
              <p><span className="text-gray-400">Reason:</span> {pt.selection_reason}</p>
              {pt.eligible_programs?.length > 0 && (
                <p><span className="text-gray-400">Also eligible:</span> {pt.eligible_programs.filter(p => p !== pt.selected_program).join(', ') || 'none'}</p>
              )}
              <p><span className="text-gray-400">Score:</span> {pt.opportunity_score?.toFixed(2)} | <span className="text-gray-400">Rank:</span> #{pt.final_rank}</p>
            </div>
          </div>
        )}

        {tt && (
          <div className="mb-4">
            <p className="text-xs font-semibold text-blue-600 mb-2">WHY DID I MOVE?</p>
            <div className="bg-blue-50 rounded-lg p-3 text-xs space-y-1">
              <p><span className="text-gray-400">Type:</span> <span className="font-medium">{tt.transition_type}</span></p>
              <p><span className="text-gray-400">Trigger:</span> {tt.trigger_reason}</p>
              {tt.state_before && <p><span className="text-gray-400">Before:</span> {tt.state_before.retention || '?'} / {tt.state_before.performance || '?'}</p>}
              {tt.state_after && <p><span className="text-gray-400">After:</span> {tt.state_after.retention || '?'} / {tt.state_after.performance || '?'}</p>}
            </div>
          </div>
        )}

        {tt?.rule_deltas?.length > 0 && (
          <div className="mb-4">
            <p className="text-xs font-semibold text-amber-600 mb-2">WHAT RULE CHANGED?</p>
            <div className="bg-amber-50 rounded-lg p-3 text-xs">
              {tt.rule_deltas.map((rd, i) => (
                <div key={i} className="flex items-center gap-2 py-0.5">
                  <span className="font-mono text-[10px]">{rd.rule}</span>
                  <span className={rd.before === 'MATCH' ? 'text-green-600' : 'text-red-400'}>{rd.before}</span>
                  <span className="text-gray-300">→</span>
                  <span className={rd.after === 'MATCH' ? 'text-green-600' : 'text-red-400'}>{rd.after}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {(pt?.policy_version || tt?.policy_version) && (
          <p className="text-[10px] text-gray-400">
            Policy: {pt?.policy_version || tt?.policy_version} | Run: {(pt?.run_id || tt?.run_id || '').slice(0, 12)}
          </p>
        )}
      </div>
    </div>
  )
}

function ChannelBadge({ channel }) {
  const ch = getChannelSemantic(channel)
  return <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${ch.bg} ${ch.color}`}>{ch.label}</span>
}
