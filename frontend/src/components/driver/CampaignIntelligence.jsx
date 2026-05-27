/**
 * CampaignIntelligence — FASE H3.2
 * Execution & Campaign Layer
 *
 * Campaign Builder + List + Detail.
 * Drivers define el universo; CRM ejecuta comunicación.
 *
 * NO CRM UI. NO kanban. NO auto-messages.
 */
import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'

const CAMPAIGN_TYPES = ['RECOVERY', 'REACTIVATION', 'LOYALTY', 'ACTIVATION', 'RETENTION', 'CROSS_SELL', 'OTHER']

const QUEUE_LABELS = {
  AT_RISK_DRIVERS: 'At Risk',
  CHURNED_RECENT: 'Recent Churn',
  DECLINING_DRIVERS: 'Declining',
  REGISTERED_NO_FIRST_TRIP: 'No First Trip',
  HIGH_POTENTIAL_UNDERUTILIZED: 'Underutilized',
}

const PRIORITY_LABELS = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']

const STATUS_COLORS = {
  DRAFT: 'bg-gray-100 text-gray-600',
  READY_FOR_CRM: 'bg-blue-100 text-blue-700',
  SENT_TO_CRM: 'bg-purple-100 text-purple-700',
  IN_EXECUTION: 'bg-amber-100 text-amber-700',
  COMPLETED: 'bg-emerald-100 text-emerald-700',
  CANCELLED: 'bg-red-100 text-red-700',
}

const CRM_STATUS_COLORS = {
  NOT_SYNCED: 'bg-gray-100 text-gray-500',
  READY: 'bg-blue-100 text-blue-700',
  SYNCED: 'bg-emerald-100 text-emerald-700',
  PARTIAL: 'bg-amber-100 text-amber-700',
  FAILED: 'bg-red-100 text-red-700',
}

function formatNum (n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('es-ES')
}

export default function CampaignIntelligence () {
  const [activeView, setActiveView] = useState('builder')

  // Builder state
  const [build, setBuild] = useState({
    campaign_name: '',
    campaign_type: 'RECOVERY',
    campaign_objective: '',
    source_queue_types: ['AT_RISK_DRIVERS', 'CHURNED_RECENT'],
    country: '',
    city: '',
    park_id: '',
    priority: ['HIGH', 'MEDIUM'],
    has_phone: true,
    max_drivers: 200,
  })

  const [preview, setPreview] = useState(null)
  const [previewing, setPreviewing] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createResult, setCreateResult] = useState(null)
  const [error, setError] = useState(null)

  // List state
  const [campaigns, setCampaigns] = useState([])
  const [listLoading, setListLoading] = useState(false)
  const [listFilter, setListFilter] = useState({ campaign_status: '', campaign_type: '' })

  // Detail state
  const [detailId, setDetailId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [members, setMembers] = useState(null)
  const [membersLoading, setMembersLoading] = useState(false)
  const [progress, setProgress] = useState(null)
  const [effectiveness, setEffectiveness] = useState(null)
  const [effLoading, setEffLoading] = useState(false)

  // Detail
  const loadDetail = useCallback(async (id) => {
    setDetailId(id)
    setDetailLoading(true)
    try {
      const [dRes, mRes, pRes] = await Promise.all([
        api.get(`/drivers/campaigns/${id}`, { timeout: 15000 }),
        api.get(`/drivers/campaigns/${id}/members`, { params: { limit: 100 }, timeout: 15000 }),
        api.get(`/drivers/campaigns/${id}/progress`, { timeout: 15000 }),
      ])
      setDetail(dRes.data)
      setMembers(mRes.data)
      setProgress(pRes.data)
      loadEffectiveness(id)
    } catch { /* ignore */ } finally { setDetailLoading(false) }
  }, [])

  const handleViewDetail = (id) => {
    setActiveView('detail')
    loadDetail(id)
  }

  const loadEffectiveness = useCallback(async (id) => {
    setEffLoading(true)
    try {
      const res = await api.get(`/drivers/campaigns/${id}/effectiveness`, { params: { window_days: 7 }, timeout: 30000 })
      setEffectiveness(res.data)
    } catch { setEffectiveness(null) } finally { setEffLoading(false) }
  }, [])

  return (
    <div className='space-y-4'>
      {/* Header */}
      <div className='bg-ct-card border border-ct-border rounded-xl px-5 py-4'>
        <h2 className='text-lg font-bold text-ct-text'>Campaign Intelligence</h2>
        <p className='text-xs text-ct-text3 mt-1'>
          Define universos y campañas accionables desde segmentos/queues. El CRM ejecuta la comunicación.
        </p>
      </div>

      {/* Tabs */}
      <div className='flex gap-1.5 flex-wrap'>
        {[
          { key: 'builder', label: 'Campaign Builder' },
          { key: 'list', label: 'Campaigns' },
          { key: 'detail', label: 'Detail' },
        ].map(t => (
          <button key={t.key} type='button' onClick={() => setActiveView(t.key)}
            className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${activeView === t.key ? 'bg-ct-accent text-white shadow-sm' : 'text-ct-text2 hover:text-ct-text hover:bg-ct-border'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {error && (
        <div className='bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-xs text-red-700'>
          {error}
          <button type='button' onClick={() => setError(null)} className='ml-2 text-gray-400 hover:text-gray-600'>&times;</button>
        </div>
      )}

      {/* ── Builder ── */}
      {activeView === 'builder' && (
        <div className='space-y-4'>
          <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
            <h3 className='text-sm font-semibold text-ct-text mb-3'>Campaign Builder</h3>
            <p className='text-[11px] text-ct-text3 mb-3'>Define el universo de drivers para tu campaña. El CRM ejecutará la comunicación.</p>

            <div className='grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 text-xs'>
              <div>
                <label className='block text-ct-text3 mb-1'>Nombre</label>
                <input type='text' value={build.campaign_name} onChange={e => setBuild(b => ({ ...b, campaign_name: e.target.value }))}
                  placeholder='Ej: Reactivación Lima AT_RISK'
                  className='w-full px-2 py-1.5 border border-ct-border rounded text-ct-text' />
              </div>
              <div>
                <label className='block text-ct-text3 mb-1'>Tipo</label>
                <select value={build.campaign_type} onChange={e => setBuild(b => ({ ...b, campaign_type: e.target.value }))}
                  className='w-full px-2 py-1.5 border border-ct-border rounded text-ct-text'>
                  {CAMPAIGN_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className='block text-ct-text3 mb-1'>Objetivo</label>
                <input type='text' value={build.campaign_objective} onChange={e => setBuild(b => ({ ...b, campaign_objective: e.target.value }))}
                  placeholder='Objetivo de la campaña'
                  className='w-full px-2 py-1.5 border border-ct-border rounded text-ct-text' />
              </div>
              <div>
                <label className='block text-ct-text3 mb-1'>País</label>
                <input type='text' value={build.country} onChange={e => setBuild(b => ({ ...b, country: e.target.value }))}
                  placeholder='Todos'
                  className='w-full px-2 py-1.5 border border-ct-border rounded text-ct-text' />
              </div>
              <div>
                <label className='block text-ct-text3 mb-1'>Ciudad</label>
                <input type='text' value={build.city} onChange={e => setBuild(b => ({ ...b, city: e.target.value }))}
                  placeholder='Todas'
                  className='w-full px-2 py-1.5 border border-ct-border rounded text-ct-text' />
              </div>
              <div>
                <label className='block text-ct-text3 mb-1'>Max Drivers</label>
                <input type='number' min={5} max={2000} value={build.max_drivers} onChange={e => setBuild(b => ({ ...b, max_drivers: Number(e.target.value) }))}
                  className='w-full px-2 py-1.5 border border-ct-border rounded text-ct-text' />
              </div>
            </div>

            <div className='mt-3 space-y-2'>
              <label className='block text-xs text-ct-text3'>Queues fuente</label>
              <div className='flex flex-wrap gap-2'>
                {Object.entries(QUEUE_LABELS).map(([k, v]) => (
                  <label key={k} className='inline-flex items-center gap-1 cursor-pointer text-[11px]'>
                    <input type='checkbox' checked={build.source_queue_types.includes(k)} onChange={e => {
                      setBuild(b => ({
                        ...b,
                        source_queue_types: e.target.checked ? [...b.source_queue_types, k] : b.source_queue_types.filter(q => q !== k),
                      }))
                    }} className='rounded' />
                    <span>{v}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className='mt-2 space-y-2'>
              <label className='block text-xs text-ct-text3'>Prioridad</label>
              <div className='flex flex-wrap gap-2'>
                {PRIORITY_LABELS.map(p => (
                  <label key={p} className='inline-flex items-center gap-1 cursor-pointer text-[11px]'>
                    <input type='checkbox' checked={build.priority.includes(p)} onChange={e => {
                      setBuild(b => ({
                        ...b,
                        priority: e.target.checked ? [...b.priority, p] : b.priority.filter(pp => pp !== p),
                      }))
                    }} className='rounded' />
                    <span>{p}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className='mt-2'>
              <label className='inline-flex items-center gap-2 cursor-pointer text-[11px]'>
                <input type='checkbox' checked={build.has_phone} onChange={e => setBuild(b => ({ ...b, has_phone: e.target.checked }))} className='rounded' />
                <span>Only drivers with phone</span>
              </label>
            </div>

            <div className='flex gap-2 mt-4'>
              <button type='button' onClick={handlePreview} disabled={previewing || build.source_queue_types.length === 0}
                className='px-3 py-1.5 rounded bg-blue-500 text-white text-xs font-medium hover:bg-blue-600 disabled:opacity-50'>
                {previewing ? 'Previewing...' : 'Preview'}
              </button>
              <button type='button' onClick={handleCreate} disabled={creating || !preview || preview.recommended_go_no_go === 'NO_GO'}
                className='px-3 py-1.5 rounded bg-green-600 text-white text-xs font-medium hover:bg-green-700 disabled:opacity-50'>
                {creating ? 'Creating...' : 'Create Campaign'}
              </button>
            </div>

            {/* API contract hint */}
            <div className='mt-4 p-3 bg-blue-50 border border-blue-200 rounded text-[11px] text-blue-800'>
              <strong>API Contract CRM:</strong>{' '}
              <code className='text-blue-900'>GET /drivers/campaigns/{'{campaign_id}'}/members?only_with_phone=true</code>
              <br />
              <span className='text-blue-700'>El CRM consumirá este endpoint para obtener los miembros de la campaña.</span>
            </div>
          </div>

          {/* Preview result */}
          {preview && (
            <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
              <h3 className='text-sm font-semibold text-ct-text mb-2'>
                Preview ({preview.estimated_total} drivers)
                <span className={`ml-2 text-xs px-2 py-0.5 rounded-full font-medium ${
                  preview.recommended_go_no_go === 'GO' ? 'bg-emerald-100 text-emerald-700' :
                  preview.recommended_go_no_go === 'WARNING' ? 'bg-amber-100 text-amber-700' :
                  'bg-red-100 text-red-700'
                }`}>
                  {preview.recommended_go_no_go}
                </span>
              </h3>

              <div className='grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px] mb-3'>
                <div><span className='text-ct-text3'>Contactables:</span> <strong className='text-emerald-600'>{preview.with_phone_count}</strong></div>
                <div><span className='text-ct-text3'>No phone:</span> <strong className='text-amber-600'>{preview.without_phone_count}</strong></div>
                {Object.entries(preview.by_queue || {}).map(([k, v]) => (
                  <div key={k}><span className='text-ct-text3'>{QUEUE_LABELS[k] || k}:</span> <strong>{v}</strong></div>
                ))}
              </div>

              {preview.by_priority && (
                <div className='flex flex-wrap gap-2 text-[11px] mb-2'>
                  {Object.entries(preview.by_priority).map(([k, v]) => (
                    <span key={k} className='px-1.5 py-0.5 rounded bg-gray-100 text-gray-600'>{k}: {v}</span>
                  ))}
                </div>
              )}

              {preview.data_quality?.length > 0 && (
                <div className='text-[11px] space-y-0.5'>
                  {preview.data_quality.map((q, i) => (
                    <div key={i} className={q.status === 'blocked' ? 'text-red-600' : q.status === 'warning' ? 'text-amber-600' : 'text-gray-500'}>
                      {q.message}
                    </div>
                  ))}
                </div>
              )}

              {preview.sample_drivers?.length > 0 && (
                <div className='mt-3 overflow-x-auto max-h-60 overflow-y-auto'>
                  <table className='w-full text-[11px]'>
                    <thead><tr className='text-left text-gray-400 border-b'><th className='py-1 pr-2'>Driver</th><th className='py-1 pr-2'>Queue</th><th className='py-1 pr-2'>Priority</th><th className='py-1 pr-2'>Lifecycle</th></tr></thead>
                    <tbody>
                      {preview.sample_drivers.map((d, i) => (
                        <tr key={i} className='border-b border-gray-50'>
                          <td className='py-1 pr-2 font-medium text-ct-text truncate max-w-[120px]'>{d.driver_name || d.driver_id?.slice(0, 12)}</td>
                          <td className='py-1 pr-2 text-ct-text2'>{QUEUE_LABELS[d.queue_type] || d.queue_type}</td>
                          <td className='py-1 pr-2'>{d.queue_priority}</td>
                          <td className='py-1 pr-2 text-ct-text2'>{d.lifecycle_stage}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {createResult && createResult.status === 'ok' && (
            <div className='bg-emerald-50 border border-emerald-200 rounded-lg p-4'>
              <h3 className='text-sm font-semibold text-emerald-800 mb-1'>Campaign Created</h3>
              <div className='text-xs text-emerald-700 space-y-1'>
                <div>ID: <code className='text-emerald-900'>{createResult.campaign_id}</code></div>
                <div>Members: {createResult.members_inserted}</div>
              </div>
              <button type='button' onClick={() => handleViewDetail(createResult.campaign_id)}
                className='mt-2 px-3 py-1 rounded bg-emerald-500 text-white text-xs font-medium hover:bg-emerald-600'>
                View Campaign Detail
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── List ── */}
      {activeView === 'list' && (
        <div className='space-y-4'>
          <div className='flex flex-wrap gap-2 items-end'>
            <div>
              <label className='block text-[10px] text-ct-text3 mb-1'>Status</label>
              <select value={listFilter.campaign_status} onChange={e => setListFilter(f => ({ ...f, campaign_status: e.target.value }))}
                className='px-2 py-1 border border-ct-border rounded text-xs'>
                <option value=''>All</option>
                {Object.keys(STATUS_COLORS).map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className='block text-[10px] text-ct-text3 mb-1'>Type</label>
              <select value={listFilter.campaign_type} onChange={e => setListFilter(f => ({ ...f, campaign_type: e.target.value }))}
                className='px-2 py-1 border border-ct-border rounded text-xs'>
                <option value=''>All</option>
                {CAMPAIGN_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <button type='button' onClick={loadList} className='px-3 py-1 rounded bg-ct-accent text-white text-xs font-medium'>
              Refresh
            </button>
          </div>

          {listLoading ? (
            <div className='animate-pulse'><div className='h-4 bg-gray-100 rounded w-64' /></div>
          ) : (
            <div className='overflow-x-auto'>
              <table className='w-full text-xs'>
                <thead>
                  <tr className='text-left text-gray-400 border-b border-gray-100'>
                    <th className='py-1.5 pr-2'>Name</th>
                    <th className='py-1.5 pr-2'>Type</th>
                    <th className='py-1.5 pr-2 text-right'>Target</th>
                    <th className='py-1.5 pr-2 text-right'>Phone</th>
                    <th className='py-1.5 pr-2'>Status</th>
                    <th className='py-1.5 pr-2'>CRM Sync</th>
                    <th className='py-1.5 pr-2'>Country</th>
                    <th className='py-1.5 pr-2'>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {campaigns.map(c => (
                    <tr key={c.campaign_id} className='border-b border-gray-50 hover:bg-gray-50/50 cursor-pointer' onClick={() => handleViewDetail(c.campaign_id)}>
                      <td className='py-1.5 pr-2 font-medium text-ct-text max-w-[200px] truncate'>{c.campaign_name || '(Sin nombre)'}</td>
                      <td className='py-1.5 pr-2 text-ct-text2'>{c.campaign_type}</td>
                      <td className='py-1.5 pr-2 text-right'>{formatNum(c.target_count)}</td>
                      <td className='py-1.5 pr-2 text-right text-emerald-600'>{formatNum(c.with_phone_count)}</td>
                      <td className='py-1.5 pr-2'><span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${STATUS_COLORS[c.campaign_status] || 'bg-gray-100'}`}>{c.campaign_status}</span></td>
                      <td className='py-1.5 pr-2'><span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${CRM_STATUS_COLORS[c.crm_sync_status] || 'bg-gray-100'}`}>{c.crm_sync_status}</span></td>
                      <td className='py-1.5 pr-2 text-ct-text2'>{c.country || '—'}</td>
                      <td className='py-1.5 pr-2 text-ct-text3'>{c.created_at?.slice(0, 10) || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {campaigns.length === 0 && (
                <div className='py-8 text-center text-xs text-ct-text3'>No campaigns yet. Create one in the Campaign Builder.</div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Detail ── */}
      {activeView === 'detail' && (
        <div className='space-y-4'>
          {!detailId ? (
            <div className='bg-gray-50 border border-gray-200 rounded-lg p-6 text-center text-sm text-gray-500'>
              Create or select a campaign to view details.
            </div>
          ) : detailLoading ? (
            <div className='animate-pulse space-y-2'><div className='h-4 bg-gray-100 rounded w-48' /><div className='h-3 bg-gray-50 rounded w-3/4' /></div>
          ) : detail?.campaign ? (
            <>
              <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
                <h3 className='text-sm font-semibold text-ct-text mb-2'>{detail.campaign.campaign_name || '(Sin nombre)'}</h3>
                <div className='grid grid-cols-2 sm:grid-cols-3 gap-2 text-[11px]'>
                  <div><span className='text-ct-text3'>Type:</span> <strong>{detail.campaign.campaign_type}</strong></div>
                  <div><span className='text-ct-text3'>Status:</span> <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${STATUS_COLORS[detail.campaign.campaign_status] || 'bg-gray-100'}`}>{detail.campaign.campaign_status}</span></div>
                  <div><span className='text-ct-text3'>CRM Sync:</span> <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${CRM_STATUS_COLORS[detail.campaign.crm_sync_status] || 'bg-gray-100'}`}>{detail.campaign.crm_sync_status}</span></div>
                  <div><span className='text-ct-text3'>Target:</span> <strong>{formatNum(detail.campaign.target_count)}</strong></div>
                  <div><span className='text-ct-text3'>With Phone:</span> <strong className='text-emerald-600'>{formatNum(detail.campaign.with_phone_count)}</strong></div>
                  <div><span className='text-ct-text3'>Country:</span> <strong>{detail.campaign.country || 'All'}</strong></div>
                  <div><span className='text-ct-text3'>City:</span> <strong>{detail.campaign.city || 'All'}</strong></div>
                  <div><span className='text-ct-text3'>Created:</span> {detail.campaign.created_at?.slice(0, 16) || '—'}</div>
                  <div><span className='text-ct-text3'>Objective:</span> {detail.campaign.campaign_objective || '—'}</div>
                </div>
              </div>

              {/* Members summary */}
              {detail.members_summary && (
                <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
                  <h3 className='text-sm font-semibold text-ct-text mb-2'>Members ({detail.members_summary.total})</h3>
                  <div className='flex flex-wrap gap-2 text-[11px] mb-3'>
                    {Object.entries(detail.members_summary.by_crm_status || {}).map(([k, v]) => (
                      <span key={k} className='px-1.5 py-0.5 rounded bg-gray-100 text-gray-600'>{k}: {v}</span>
                    ))}
                  </div>

                  {detail.members_sample?.length > 0 && (
                    <div className='overflow-x-auto'>
                      <table className='w-full text-[11px]'>
                        <thead><tr className='text-left text-gray-400 border-b'><th className='py-1 pr-2'>Driver</th><th className='py-1 pr-2'>Phone</th><th className='py-1 pr-2'>Queue</th><th className='py-1 pr-2'>Priority</th><th className='py-1 pr-2'>CRM Status</th></tr></thead>
                        <tbody>
                          {detail.members_sample.map((m, i) => (
                            <tr key={i} className='border-b border-gray-50'>
                              <td className='py-1 pr-2 font-medium text-ct-text truncate max-w-[120px]'>{m.driver_name_snapshot || m.driver_id?.slice(0, 12)}</td>
                              <td className='py-1 pr-2'>{m.phone_snapshot ? <span className='text-emerald-500'>&#x2713;</span> : <span className='text-amber-500'>&#x2717;</span>}</td>
                              <td className='py-1 pr-2 text-ct-text2'>{QUEUE_LABELS[m.queue_type_snapshot] || m.queue_type_snapshot}</td>
                              <td className='py-1 pr-2'>{m.priority_snapshot}</td>
                              <td className='py-1 pr-2 text-ct-text2'>{m.crm_status}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {detail.members_sample.length >= 20 && (
                        <p className='text-[10px] text-gray-400 mt-1'>Showing first 20 of {detail.members_summary.total} members</p>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Execution Progress */}
              {progress && progress.total > 0 && (
                <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
                  <h3 className='text-sm font-semibold text-ct-text mb-2'>Execution Progress</h3>
                  <div className='grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2'>
                    {[
                      { label: 'Contacted', value: progress.contacted, pct: progress.contact_rate, color: 'text-emerald-700' },
                      { label: 'Recovered', value: progress.recovered, pct: progress.recovery_rate, color: 'text-green-700' },
                      { label: 'No Response', value: progress.no_response, color: 'text-orange-700' },
                      { label: 'Bad Phone', value: progress.bad_phone, color: 'text-red-600' },
                      { label: 'Pending', value: progress.pending, color: 'text-gray-600' },
                      { label: 'Coverage', value: progress.execution_coverage + '%', color: 'text-blue-700' },
                      { label: 'Avg Attempts', value: progress.avg_attempts, color: 'text-purple-700' },
                    ].map(kpi => (
                      <div key={kpi.label} className='border border-ct-border rounded-lg px-3 py-2'>
                        <div className='text-[10px] text-ct-text3 uppercase'>{kpi.label}</div>
                        <div className={`text-sm font-bold ${kpi.color}`}>
                          {kpi.value}{kpi.pct != null ? <span className='text-[10px] ml-1'>({kpi.pct}%)</span> : ''}
                        </div>
                      </div>
                    ))}
                  </div>

                  {progress.by_owner && Object.keys(progress.by_owner).length > 0 && (
                    <div className='mt-3'>
                      <div className='text-[11px] font-medium text-ct-text3 mb-1'>By Executor</div>
                      <div className='flex flex-wrap gap-2 text-[10px]'>
                        {Object.entries(progress.by_owner).map(([owner, statuses]) => (
                          <span key={owner} className='px-1.5 py-0.5 rounded bg-gray-100 text-gray-600'>
                            {owner}: {Object.values(statuses).reduce((a, b) => a + b, 0)}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* CRM Sync History */}
              {progress?.sync_history?.length > 0 && (
                <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
                  <h3 className='text-sm font-semibold text-ct-text mb-2'>Sync History</h3>
                  <div className='overflow-x-auto'>
                    <table className='w-full text-[11px]'>
                      <thead><tr className='text-left text-gray-400 border-b'><th className='py-1 pr-2'>Direction</th><th className='py-1 pr-2'>Status</th><th className='py-1 pr-2'>Members</th><th className='py-1 pr-2'>Failed</th><th className='py-1 pr-2'>CRM</th><th className='py-1 pr-2'>Last Sync</th></tr></thead>
                      <tbody>
                        {progress.sync_history.map((s, i) => (
                          <tr key={i} className='border-b border-gray-50'>
                            <td className='py-1 pr-2'>{s.sync_direction}</td>
                            <td className='py-1 pr-2'><span className={`px-1 py-0.5 rounded text-[9px] ${
                              s.sync_status === 'COMPLETED' ? 'bg-emerald-100 text-emerald-700' :
                              s.sync_status === 'EXPORTED' ? 'bg-blue-100 text-blue-700' :
                              s.sync_status === 'PARTIAL' ? 'bg-amber-100 text-amber-700' :
                              'bg-red-100 text-red-700'
                            }`}>{s.sync_status}</span></td>
                            <td className='py-1 pr-2'>{s.exported_members_count}</td>
                            <td className='py-1 pr-2 text-red-500'>{s.failed_members_count || 0}</td>
                            <td className='py-1 pr-2 text-ct-text2'>{s.crm_system_name}</td>
                            <td className='py-1 pr-2 text-ct-text3'>{s.last_sync_at?.slice(0, 16) || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Campaign Effectiveness */}
              <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
                <h3 className='text-sm font-semibold text-ct-text mb-2'>Effectiveness (D+7)</h3>
                {effLoading ? (
                  <div className='text-xs text-ct-text3'>Loading...</div>
                ) : effectiveness?.status === 'error' ? (
                  <div className='text-xs text-red-600'>{effectiveness.error}</div>
                ) : effectiveness?.summary ? (
                  <div className='space-y-2'>
                    <div className='grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]'>
                      <div><span className='text-ct-text3'>Re-activated:</span> <strong className='text-green-700'>{effectiveness.summary.reactivated_count}</strong></div>
                      <div><span className='text-ct-text3'>Rate:</span> <strong className='text-green-700'>{(effectiveness.summary.reactivation_rate * 100).toFixed(1)}%</strong></div>
                      <div><span className='text-ct-text3'>Trips After:</span> <strong>{effectiveness.summary.trips_after_window}</strong></div>
                      <div><span className='text-ct-text3'>Trip Δ:</span> <strong className={effectiveness.summary.observed_trip_delta >= 0 ? 'text-emerald-600' : 'text-red-500'}>{effectiveness.summary.observed_trip_delta >= 0 ? '+' : ''}{effectiveness.summary.observed_trip_delta}</strong></div>
                    </div>
                    {effectiveness.warnings?.length > 0 && (
                      <div className='text-[10px] text-amber-600'>{effectiveness.warnings[0]}</div>
                    )}
                    <p className='text-[10px] text-gray-400 italic mt-1'>Observed lift, not causal. D+{effectiveness.window_days}, {effectiveness.days_since_campaign}d since campaign.</p>
                  </div>
                ) : (
                  <div className='text-xs text-ct-text3'>Effectiveness not yet available.</div>
                )}
              </div>

              {/* CRM Export + API contract */}
              <div className='bg-blue-50 border border-blue-200 rounded-lg p-4'>
                <h3 className='text-sm font-semibold text-blue-900 mb-2'>CRM Bridge</h3>
                <div className='flex flex-wrap gap-2 mb-3'>
                  <a href={`/api/drivers/campaigns/${detailId}/crm-export`} target='_blank' rel='noopener noreferrer'
                    className='px-3 py-1.5 rounded bg-blue-600 text-white text-xs font-medium hover:bg-blue-700 inline-block'>
                    Export CRM Payload
                  </a>
                </div>
                <div className='text-[11px] text-blue-800 space-y-1'>
                  <div><strong>GET Members:</strong> <code className='text-blue-900'>/drivers/campaigns/{detailId}/members?only_with_phone=true&limit=200</code></div>
                  <div><strong>POST Outcomes:</strong> <code className='text-blue-900'>/drivers/campaigns/{detailId}/outcomes</code></div>
                  <div><strong>GET Progress:</strong> <code className='text-blue-900'>/drivers/campaigns/{detailId}/progress</code></div>
                </div>
              </div>
            </>
          ) : (
            <div className='bg-amber-50 border border-amber-200 rounded-lg p-4 text-xs text-amber-700'>
              Campaign not found or failed to load.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
