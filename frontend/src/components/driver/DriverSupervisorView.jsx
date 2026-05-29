/**
 * DriverSupervisorView — FASE H3.5
 * Role: Supervisor — "¿Cómo va mi equipo y qué está trabado?"
 *
 * Execution overview, owners performance, open queues, stuck cases,
 * campaign progress, CRM sync warnings.
 */
import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'
import PilotWorkboard from '../driver/PilotWorkboard.jsx'

function formatNum (n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('es-ES')
}

function formatPct (n) {
  if (n == null) return '—'
  return (Number(n) * 100).toFixed(1) + '%'
}

export default function DriverSupervisorView () {
  const [metrics, setMetrics] = useState(null)
  const [campaigns, setCampaigns] = useState([])
  const [syncHealth, setSyncHealth] = useState(null)
  const [stuckCases, setStuckCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    const [mRes, cRes, sRes, wRes] = await Promise.allSettled([
      api.get('/drivers/workflow-metrics', { timeout: 15000 }),
      api.get('/drivers/campaigns', { params: { limit: 10 }, timeout: 15000 }),
      api.get('/drivers/campaigns/sync-health', { timeout: 15000 }),
      api.get('/drivers/workflow', { params: { limit: 100, offset: 0 }, timeout: 15000 }),
    ])
    if (mRes.status === 'fulfilled') setMetrics(mRes.value.data)
    if (cRes.status === 'fulfilled') setCampaigns(cRes.value.data?.campaigns || [])
    if (sRes.status === 'fulfilled') setSyncHealth(sRes.value.data)
    if (wRes.status === 'fulfilled') {
      const allWf = wRes.value.data?.workflows || []
      const stuck = allWf.filter(w => ['ASSIGNED', 'IN_PROGRESS'].includes(w.workflow_status))
      setStuckCases(stuck.slice(0, 20))
    }
    const _failures = [mRes, cRes, sRes, wRes].filter(r => r.status === 'rejected')
    if (_failures.length === 4) {
      const err = _failures[0].reason
      setError(err?.code === 'ECONNABORTED' ? 'Timeout al cargar datos de supervisión' : (err?.message || 'Error al cargar vista supervisor'))
    } else if (_failures.length > 0) {
      setError(`${_failures.length} de 4 módulos con error parcial. Datos disponibles mostrados.`)
    }
    setLoading(false)
  }, [])

  useEffect(() => { loadAll() }, [loadAll])

  return (
    <div className='space-y-4'>
      <div className='bg-ct-card border border-ct-border rounded-xl px-5 py-4'>
        <div className='flex items-baseline gap-2'>
          <h2 className='text-lg font-bold text-ct-text'>Execution Overview</h2>
          <span className='text-xs text-ct-text3'>Supervisor View</span>
        </div>
        <p className='text-xs text-ct-text3 mt-1'>Monitorea avance del equipo, identifica bloqueos y verifica sync CRM.</p>
      </div>

      {error && (
        <div className='border border-red-200 rounded-lg p-3 bg-red-50/50'>
          <div className='flex items-start justify-between gap-2'>
            <div>
              <span className='text-[11px] text-red-700 font-medium'>Error t\u00e9cnico</span>
              <div className='text-[10px] text-red-600 mt-0.5'>{error}</div>
              <div className='text-[10px] text-gray-500 mt-1'>Remediaci\u00f3n: Verificar conectividad con backend y tablas de workflow/campaigns.</div>
            </div>
            <button type='button' onClick={loadAll} className='flex-shrink-0 px-2.5 py-1 text-[10px] font-medium rounded border border-gray-300 bg-white text-gray-600 hover:bg-gray-50'>Reintentar</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className='animate-pulse space-y-2'><div className='h-4 bg-gray-100 rounded w-48' /></div>
      ) : (
        <>
          {/* KPI strip */}
          {metrics && (
            <div className='grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2'>
              {[
                { label: 'Total WFs', value: metrics.total_workflows || formatNum(metrics.total_count), color: '' },
                { label: 'Open', value: metrics.open_count || formatNum(metrics.pending_count), color: 'text-amber-700' },
                { label: 'Contacted', value: metrics.contacted_count || 0, color: 'text-emerald-700' },
                { label: 'Recovered', value: metrics.recovered_count || 0, color: 'text-green-700' },
                { label: 'No Response', value: metrics.no_response_count || 0, color: 'text-orange-700' },
                { label: 'Active Owners', value: metrics.active_owners || metrics.owners_count || '—', color: 'text-blue-700' },
              ].map(kpi => (
                <div key={kpi.label} className='border border-ct-border rounded-lg px-3 py-2 bg-white/40'>
                  <div className='text-[10px] text-ct-text3 uppercase'>{kpi.label}</div>
                  <div className={`text-sm font-bold ${kpi.color || 'text-ct-text'}`}>{kpi.value}</div>
                </div>
              ))}
            </div>
          )}

          {/* Stuck cases */}
          <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
            <h3 className='text-sm font-semibold text-ct-text mb-2'>
              Stuck Cases <span className='text-amber-600'>({stuckCases.length} assigned with no action)</span>
            </h3>
            {stuckCases.length === 0 ? (
              <div className='text-xs text-ct-text3'>No stuck cases detected.</div>
            ) : (
              <div className='overflow-x-auto max-h-60 overflow-y-auto'>
                <table className='w-full text-[11px]'>
                  <thead className='sticky top-0 bg-white'><tr className='text-left text-gray-400 border-b'><th className='py-1 pr-2'>Driver</th><th className='py-1 pr-2'>Owner</th><th className='py-1 pr-2'>Queue</th><th className='py-1 pr-2'>Status</th><th className='py-1 pr-2'>Priority</th></tr></thead>
                  <tbody>
                    {stuckCases.map((w, i) => (
                      <tr key={i} className='border-b border-gray-50'>
                        <td className='py-1 pr-2 font-medium text-ct-text'>{w.driver_id?.slice(0, 12)}</td>
                        <td className='py-1 pr-2 text-ct-text2'>{w.assigned_owner || '—'}</td>
                        <td className='py-1 pr-2 text-ct-text2'>{w.queue_type}</td>
                        <td className='py-1 pr-2'><span className='px-1 py-0.5 rounded text-[9px] bg-amber-100 text-amber-700'>{w.workflow_status}</span></td>
                        <td className='py-1 pr-2'>{w.priority_snapshot || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Campaign progress */}
          <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
            <h3 className='text-sm font-semibold text-ct-text mb-2'>Campaign Progress ({campaigns.length})</h3>
            {campaigns.length === 0 ? (
              <div className='text-xs text-ct-text3'>No campaigns yet.</div>
            ) : (
              <div className='grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2'>
                {campaigns.map(c => (
                  <div key={c.campaign_id} className='border border-ct-border rounded-lg px-3 py-2'>
                    <div className='text-[11px] font-medium text-ct-text truncate'>{c.campaign_name || '(Sin nombre)'}</div>
                    <div className='text-[10px] text-ct-text2 mt-0.5'>
                      {c.campaign_type} · {formatNum(c.target_count)} members · {formatNum(c.with_phone_count)} phone
                    </div>
                    <div className='flex gap-1.5 mt-1'>
                      <span className={`px-1 py-0.5 rounded text-[9px] font-medium ${
                        c.crm_sync_status === 'SYNCED' ? 'bg-emerald-100 text-emerald-700' :
                        c.crm_sync_status === 'PARTIAL' ? 'bg-amber-100 text-amber-700' :
                        'bg-gray-100 text-gray-600'
                      }`}>{c.crm_sync_status}</span>
                      <span className='px-1 py-0.5 rounded text-[9px] bg-gray-100 text-gray-600'>{c.campaign_status}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* CRM Sync Health */}
          {syncHealth && (
            <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
              <h3 className='text-sm font-semibold text-ct-text mb-2'>CRM Sync Health</h3>
              <div className='grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]'>
                <div><span className='text-ct-text3'>Total Syncs:</span> <strong>{syncHealth.total_syncs}</strong></div>
                <div><span className='text-ct-text3'>Completed:</span> <strong className='text-emerald-600'>{syncHealth.completed}</strong></div>
                <div><span className='text-ct-text3'>Partial:</span> <strong className='text-amber-600'>{syncHealth.partial}</strong></div>
                <div><span className='text-ct-text3'>Failed:</span> <strong className='text-red-600'>{syncHealth.failed}</strong></div>
              </div>
            </div>
          )}

          {/* Pilot Workboard */}
          <div>
            <h3 className='text-sm font-semibold text-ct-text mb-2'>Operational Pilot</h3>
            <PilotWorkboard />
          </div>
        </>
      )}
    </div>
  )
}
