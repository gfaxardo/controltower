/**
 * DriverOperatorView — FASE H3.5
 * Role: Operator — "¿Qué debo hacer hoy?"
 *
 * Reutiliza Action Queues + Pilot Workboard.
 * Muestra casos asignados, prioridades y quick actions.
 */
import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'
import DriverActionableLists from './DriverActionableLists'

function formatNum (n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('es-ES')
}

export default function DriverOperatorView () {
  const [workflows, setWorkflows] = useState([])
  const [metrics, setMetrics] = useState(null)
  const [ownerFilter, setOwnerFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadMyWork = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [wfRes, mRes] = await Promise.all([
        api.get('/drivers/workflow', { params: { limit: 50, offset: 0 }, timeout: 15000 }),
        api.get('/drivers/workflow-metrics', { timeout: 15000 }),
      ])
      setWorkflows(wfRes.data?.workflows || [])
      setMetrics(mRes.data)
    } catch (err) {
      setError(err.code === 'ECONNABORTED' ? 'Timeout al cargar workflows' : (err.message || 'Error al cargar vista operador'))
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { loadMyWork() }, [loadMyWork])

  const filtered = ownerFilter
    ? workflows.filter(w => (w.assigned_owner || '').toLowerCase().includes(ownerFilter.toLowerCase()))
    : workflows

  const statusPriority = { UNASSIGNED: 1, ASSIGNED: 2, IN_PROGRESS: 3, CONTACTED: 4, NO_RESPONSE: 5, RECOVERED: 6, CLOSED: 7, BLOCKED: 8 }
  filtered.sort((a, b) => (statusPriority[a.workflow_status] || 99) - (statusPriority[b.workflow_status] || 99))

  return (
    <div className='space-y-4'>
      {/* My Work header */}
      <div className='bg-ct-card border border-ct-border rounded-xl px-5 py-4'>
        <div className='flex items-baseline gap-2'>
          <h2 className='text-lg font-bold text-ct-text'>My Work Today</h2>
          <span className='text-xs text-ct-text3'>Operator View</span>
        </div>
        <p className='text-xs text-ct-text3 mt-1'>Revisa tus casos asignados y contacta drivers en orden de prioridad.</p>
      </div>

      {error && (
        <div className='border border-red-200 rounded-lg p-3 bg-red-50/50'>
          <div className='flex items-start justify-between gap-2'>
            <div>
              <span className='text-[11px] text-red-700 font-medium'>Error t\u00e9cnico</span>
              <div className='text-[10px] text-red-600 mt-0.5'>{error}</div>
              <div className='text-[10px] text-gray-500 mt-1'>Remediaci\u00f3n: Verificar conectividad con el backend y que las tablas de workflow existan.</div>
            </div>
            <button type='button' onClick={loadMyWork} className='flex-shrink-0 px-2.5 py-1 text-[10px] font-medium rounded border border-gray-300 bg-white text-gray-600 hover:bg-gray-50'>Reintentar</button>
          </div>
        </div>
      )}

      {/* Quick stats */}
      {metrics && (
        <div className='grid grid-cols-2 sm:grid-cols-4 gap-2'>
          {[
            { label: 'Pending', value: metrics.pending_count || (filtered.filter(w => ['UNASSIGNED', 'ASSIGNED', 'IN_PROGRESS'].includes(w.workflow_status)).length), color: 'text-amber-700' },
            { label: 'Contacted', value: metrics.contacted_count || filtered.filter(w => w.workflow_status === 'CONTACTED').length, color: 'text-emerald-700' },
            { label: 'No Response', value: metrics.no_response_count || filtered.filter(w => w.workflow_status === 'NO_RESPONSE').length, color: 'text-orange-700' },
            { label: 'Recovered', value: metrics.recovered_count || filtered.filter(w => w.workflow_status === 'RECOVERED').length, color: 'text-green-700' },
          ].map(kpi => (
            <div key={kpi.label} className='border border-ct-border rounded-lg px-3 py-2 bg-white/40'>
              <div className='text-[10px] text-ct-text3 uppercase'>{kpi.label}</div>
              <div className={`text-sm font-bold ${kpi.color}`}>{kpi.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* Workflows list */}
      <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
        <div className='flex items-center justify-between mb-3'>
          <h3 className='text-sm font-semibold text-ct-text'>Assigned Cases ({filtered.length})</h3>
          <input type='text' value={ownerFilter} onChange={e => setOwnerFilter(e.target.value)}
            placeholder='Filter by owner...'
            className='px-2 py-1 border border-ct-border rounded text-[11px] w-40' />
        </div>

        {loading ? (
          <div className='animate-pulse'><div className='h-4 bg-gray-100 rounded w-48' /></div>
        ) : filtered.length === 0 ? (
          <div className='text-center py-6 text-xs text-ct-text3'>No assigned cases. Check Action Queues below.</div>
        ) : (
          <div className='overflow-x-auto max-h-96 overflow-y-auto'>
            <table className='w-full text-[11px]'>
              <thead className='sticky top-0 bg-white'>
                <tr className='text-left text-gray-400 border-b'>
                  <th className='py-1 pr-2'>Driver</th>
                  <th className='py-1 pr-2'>Queue</th>
                  <th className='py-1 pr-2'>Status</th>
                  <th className='py-1 pr-2'>Owner</th>
                  <th className='py-1 pr-2'>Last Action</th>
                  <th className='py-1 pr-2'>Priority</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((w, i) => (
                  <tr key={i} className='border-b border-gray-50'>
                    <td className='py-1 pr-2 font-medium text-ct-text truncate max-w-[100px]'>{w.driver_id?.slice(0, 12)}</td>
                    <td className='py-1 pr-2 text-ct-text2'>{w.queue_type}</td>
                    <td className='py-1 pr-2'><span className={`px-1 py-0.5 rounded text-[9px] font-medium ${
                      w.workflow_status === 'RECOVERED' ? 'bg-green-100 text-green-700' :
                      w.workflow_status === 'CONTACTED' ? 'bg-emerald-100 text-emerald-700' :
                      w.workflow_status === 'NO_RESPONSE' ? 'bg-orange-100 text-orange-700' :
                      w.workflow_status === 'BLOCKED' ? 'bg-red-100 text-red-700' :
                      'bg-gray-100 text-gray-600'
                    }`}>{w.workflow_status}</span></td>
                    <td className='py-1 pr-2 text-ct-text2'>{w.assigned_owner || '—'}</td>
                    <td className='py-1 pr-2 text-ct-text3'>{w.latest_action_type || '—'}</td>
                    <td className='py-1 pr-2'>{w.priority_snapshot || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Action Queues quick access */}
      <div>
        <h3 className='text-sm font-semibold text-ct-text mb-2'>Action Queues</h3>
        <DriverActionableLists />
      </div>
    </div>
  )
}
