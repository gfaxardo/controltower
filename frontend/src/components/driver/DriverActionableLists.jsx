/**
 * DriverActionableLists — FASE D4 + D5
 * Actionable Supply Engine + Workflow Execution.
 *
 * Tabla operacional con quick actions y workflow tracking.
 * NO kanban, NO BPM, NO CRM pesado.
 */
import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'

const PRIORITY_COLORS = {
  CRITICAL: { dot: 'bg-red-500', badge: 'bg-red-100 text-red-800 border-red-200' },
  HIGH: { dot: 'bg-amber-500', badge: 'bg-amber-100 text-amber-800 border-amber-200' },
  MEDIUM: { dot: 'bg-blue-500', badge: 'bg-blue-100 text-blue-800 border-blue-200' },
  LOW: { dot: 'bg-gray-400', badge: 'bg-gray-100 text-gray-600 border-gray-200' },
}

const WF_STATUS_COLORS = {
  UNASSIGNED: 'bg-gray-100 text-gray-500',
  ASSIGNED: 'bg-blue-100 text-blue-700',
  IN_PROGRESS: 'bg-amber-100 text-amber-700',
  CONTACTED: 'bg-emerald-100 text-emerald-700',
  NO_RESPONSE: 'bg-orange-100 text-orange-700',
  RECOVERED: 'bg-green-100 text-green-700',
  CLOSED: 'bg-gray-200 text-gray-500',
  BLOCKED: 'bg-red-100 text-red-700',
}

const QUEUE_LABELS = {
  REGISTERED_NO_FIRST_TRIP: 'No First Trip',
  DECLINING_DRIVERS: 'Declining',
  AT_RISK_DRIVERS: 'At Risk',
  CHURNED_RECENT: 'Recent Churn',
  HIGH_POTENTIAL_UNDERUTILIZED: 'Underutilized',
}
const QUEUE_TYPES = Object.keys(QUEUE_LABELS)

function PriorityBadge ({ priority }) {
  const c = PRIORITY_COLORS[priority] || PRIORITY_COLORS.LOW
  return <span className={`inline-flex items-center gap-1 px-1.5 py-px rounded-full text-[10px] font-medium border ${c.badge}`}><span className={`w-1 h-1 rounded-full ${c.dot}`} />{priority}</span>
}

function WfBadge ({ status }) {
  if (!status) return null
  const c = WF_STATUS_COLORS[status] || WF_STATUS_COLORS.UNASSIGNED
  return <span className={`inline-flex px-1.5 py-px rounded text-[10px] font-medium ${c}`}>{status.replace(/_/g, ' ')}</span>
}

function SummaryCards ({ data }) {
  if (!data?.summary) return null
  const s = data.summary
  return (
    <div className='flex gap-3 flex-wrap mb-3'>
      <div className='border border-ct-border rounded-lg px-3 py-2 bg-white/40 min-w-[80px]'>
        <div className='text-[10px] text-gray-400 uppercase'>Total</div><div className='text-sm font-semibold text-gray-700'>{s.total_in_all_queues}</div>
      </div>
      {['CRITICAL', 'HIGH'].map(p => {
        const count = p === 'CRITICAL' ? s.critical : s.high
        if (!count) return null
        return <div key={p} className='border border-ct-border rounded-lg px-3 py-2 bg-white/40 min-w-[80px]'><div className={`text-[10px] uppercase font-medium ${PRIORITY_COLORS[p]?.badge?.match(/text-\w+-\d+/)?.[0] || ''}`}>{p}</div><div className='text-sm font-semibold text-gray-700'>{count}</div></div>
      })}
    </div>
  )
}

function QueuePill ({ qt, active, onClick, count }) {
  return (
    <button type='button' onClick={() => onClick(qt)}
      className={`px-2.5 py-1 rounded text-[11px] font-medium inline-flex items-center gap-1.5 transition-all ${active ? 'bg-ct-accent text-white shadow-sm' : 'text-ct-text2 hover:text-ct-text hover:bg-ct-border'}`}>
      {QUEUE_LABELS[qt] || qt}
      {count > 0 && <span className={`text-[10px] px-1 py-px rounded-full ${active ? 'bg-white/20' : 'bg-gray-100 text-gray-500'}`}>{count}</span>}
    </button>
  )
}

export default function DriverActionableLists () {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeQueue, setActiveQueue] = useState(null)
  const [workflows, setWorkflows] = useState({})
  const [assignOwner, setAssignOwner] = useState('')

  const fetchData = useCallback(async (queueFilter) => {
    setLoading(true)
    try {
      const res = await api.get('/drivers/actionable-list', {
        params: { queue_type: queueFilter || undefined, limit: 200, offset: 0 }, timeout: 30000,
      })
      setData(res.data)
    } catch { setData(null) } finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchData(activeQueue) }, [activeQueue, fetchData])

  const quickAction = async (q, action) => {
    const owner = assignOwner || 'operator'
    let wfRes
    try {
      if (action === 'assign') {
        wfRes = await api.post('/drivers/workflow/assign', {
          driver_id: q.driver_id, queue_type: q.queue_type, assigned_owner: owner,
        })
      } else if (action === 'contact') {
        wfRes = await api.post('/drivers/workflow/status', {
          workflow_id: q._wf_id, workflow_status: 'CONTACTED',
        })
        await api.post('/drivers/workflow/action', {
          workflow_id: q._wf_id, action_type: 'DRIVER_CONTACTED', action_channel: 'call',
        })
      } else if (action === 'no_response') {
        wfRes = await api.post('/drivers/workflow/status', {
          workflow_id: q._wf_id, workflow_status: 'NO_RESPONSE',
        })
        await api.post('/drivers/workflow/action', {
          workflow_id: q._wf_id, action_type: 'NO_RESPONSE', action_channel: 'call',
        })
      } else if (action === 'recover') {
        wfRes = await api.post('/drivers/workflow/status', {
          workflow_id: q._wf_id, workflow_status: 'RECOVERED',
        })
        await api.post('/drivers/workflow/action', {
          workflow_id: q._wf_id, action_type: 'DRIVER_RECOVERED',
        })
      } else if (action === 'close') {
        wfRes = await api.post('/drivers/workflow/status', {
          workflow_id: q._wf_id, workflow_status: 'CLOSED',
        })
        await api.post('/drivers/workflow/action', {
          workflow_id: q._wf_id, action_type: 'CLOSED_CASE',
        })
      }
      if (wfRes?.data && !wfRes.data.error) {
        setWorkflows(prev => ({ ...prev, [q.driver_id + q.queue_type]: wfRes.data }))
      }
    } catch { /* ignore */ }
  }

  // Enrich queues with workflow status
  const queues = (data?.queues || []).map(q => {
    const wf = workflows[q.driver_id + q.queue_type]
    return {
      ...q,
      _wf_id: wf?.workflow_id,
      _wf_status: wf?.workflow_status || 'UNASSIGNED',
      _wf_owner: wf?.assigned_owner,
    }
  })

  const summary = data?.summary || {}
  const queueCounts = summary?.by_queue || {}

  if (loading && !data) {
    return <div className='animate-pulse space-y-2'><div className='h-3 bg-gray-100 rounded w-full' /><div className='h-3 bg-gray-50 rounded w-3/4' /></div>
  }

  return (
    <div>
      {/* Queue pills */}
      <div className='flex items-center gap-1.5 mb-3 overflow-x-auto pb-1'>
        <button type='button' onClick={() => { setActiveQueue(null) }}
          className={`px-2.5 py-1 rounded text-[11px] font-medium transition-all ${!activeQueue ? 'bg-ct-accent text-white shadow-sm' : 'text-ct-text2 hover:text-ct-text hover:bg-ct-border'}`}>All</button>
        {QUEUE_TYPES.map(qt => <QueuePill key={qt} qt={qt} active={activeQueue === qt} onClick={() => setActiveQueue(qt)} count={queueCounts?.[qt] || 0} />)}
      </div>

      <SummaryCards data={data} />

      {/* Owner filter */}
      <div className='flex items-center gap-2 mb-2'>
        <input
          type='text' value={assignOwner} onChange={e => setAssignOwner(e.target.value)}
          placeholder='Assigned owner...'
          className='px-2 py-1 text-[11px] border border-ct-border rounded bg-white text-gray-600 w-36 focus:outline-none focus:border-ct-accent'
        />
      </div>

      {queues.length > 0 ? (
        <div className='overflow-x-auto'>
          <table className='w-full text-[11px]'>
            <thead>
              <tr className='text-left text-gray-400 border-b border-gray-100'>
                <th className='py-1.5 pr-1 w-6'></th>
                <th className='py-1.5 pr-2 font-medium'>Driver</th>
                <th className='py-1.5 pr-2 w-16 font-medium'>Priority</th>
                <th className='py-1.5 pr-2 w-16 font-medium'>Status</th>
                <th className='py-1.5 pr-2 w-16 text-right font-medium'>7d</th>
                <th className='py-1.5 pr-2 w-16 text-right font-medium'>30d</th>
                <th className='py-1.5 pr-2 font-medium'>Queue</th>
                <th className='py-1.5 pr-2 font-medium w-40'>Action</th>
              </tr>
            </thead>
            <tbody>
              {queues.map((q, i) => (
                <tr key={`${q.driver_id}-${q.queue_type}-${i}`} className='border-b border-gray-50 hover:bg-gray-50/50'>
                  <td className='py-1.5 pr-1'>
                    {q.has_phone ? <span className='text-emerald-500 text-xs'>&#x2713;</span> : <span className='text-amber-500 text-xs'>&#x2717;</span>}
                  </td>
                  <td className='py-1.5 pr-2'>
                    <div className='font-medium text-gray-700 truncate max-w-[130px]' title={q.driver_name}>{q.driver_name || q.driver_id?.slice(0, 12)}</div>
                    <div className='text-[10px] text-gray-400 truncate max-w-[130px]'>{q.city}{q.park_name ? ' · ' + q.park_name : ''}</div>
                  </td>
                  <td className='py-1.5 pr-2'><PriorityBadge priority={q.queue_priority} /></td>
                  <td className='py-1.5 pr-2'><WfBadge status={q._wf_status} /></td>
                  <td className='py-1.5 pr-2 text-right font-mono text-gray-600'>{q.trips_7d}</td>
                  <td className='py-1.5 pr-2 text-right font-mono text-gray-600'>{q.trips_30d}</td>
                  <td className='py-1.5 pr-2 text-[10px] text-gray-500'>{QUEUE_LABELS[q.queue_type]}</td>
                  <td className='py-1.5 pr-2'>
                    <div className='flex items-center gap-1'>
                      {q._wf_status === 'UNASSIGNED' && (
                        <button type='button' onClick={() => quickAction(q, 'assign')}
                          className='px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200 transition-colors'>Assign</button>
                      )}
                      {['ASSIGNED', 'IN_PROGRESS'].includes(q._wf_status) && (
                        <>
                          <button type='button' onClick={() => quickAction(q, 'contact')}
                            className='px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200'>Contacted</button>
                          <button type='button' onClick={() => quickAction(q, 'no_response')}
                            className='px-1.5 py-0.5 rounded text-[10px] font-medium bg-orange-50 text-orange-700 hover:bg-orange-100 border border-orange-200'>No Resp</button>
                        </>
                      )}
                      {['CONTACTED', 'NO_RESPONSE'].includes(q._wf_status) && (
                        <button type='button' onClick={() => quickAction(q, 'recover')}
                          className='px-1.5 py-0.5 rounded text-[10px] font-medium bg-green-50 text-green-700 hover:bg-green-100 border border-green-200'>Recover</button>
                      )}
                      {!['CLOSED', 'RECOVERED'].includes(q._wf_status) && (
                        <button type='button' onClick={() => quickAction(q, 'close')}
                          className='px-1.5 py-0.5 rounded text-[10px] font-medium text-gray-400 hover:text-gray-600 hover:bg-gray-100 border border-transparent'>Close</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className='text-center py-6 text-xs text-gray-400'>No actionable drivers in selected queue.</div>
      )}
    </div>
  )
}
