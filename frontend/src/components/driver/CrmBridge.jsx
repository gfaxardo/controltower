/**
 * CrmBridge — FASE H3.3
 * Execution & Campaign Layer: CRM Bridge & Sync
 *
 * Muestra:
 *  - Campaigns ready for CRM sync
 *  - Export payload status
 *  - Import outcomes status
 *  - Sync history
 *  - Bridge health
 *  - Graceful degradation: CRM failure does NOT block Drivers
 *
 * NO CRM UI. NO messaging center. NO complex orchestration.
 */
import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'

const SYNC_STATUS_COLORS = {
  PENDING: 'bg-gray-100 text-gray-500',
  READY: 'bg-blue-100 text-blue-700',
  EXPORTING: 'bg-purple-100 text-purple-700',
  EXPORTED: 'bg-emerald-100 text-emerald-700',
  PARTIAL: 'bg-amber-100 text-amber-700',
  FAILED: 'bg-red-100 text-red-700',
  IMPORTING_OUTCOMES: 'bg-cyan-100 text-cyan-700',
  COMPLETED: 'bg-green-100 text-green-700',
}

export default function CrmBridge () {
  const [health, setHealth] = useState(null)
  const [syncHistory, setSyncHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [hRes, sRes] = await Promise.all([
        api.get('/drivers/crm-bridge/health', { timeout: 15000 }),
        api.get('/drivers/campaigns/sync-history', { params: { limit: 50 }, timeout: 15000 }),
      ])
      setHealth(hRes.data)
      setSyncHistory(sRes.data?.syncs || [])
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load bridge data')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { loadData() }, [loadData])

  const handleExport = async (campaignId) => {
    try {
      await api.get(`/drivers/campaigns/${campaignId}/crm-export`, {
        params: { crm_system_name: 'generic', actor: 'operator' },
        timeout: 30000,
      })
      loadData()
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Export failed')
    }
  }

  return (
    <div className='space-y-4'>
      {/* Header */}
      <div className='bg-ct-card border border-ct-border rounded-xl px-5 py-4'>
        <h2 className='text-lg font-bold text-ct-text'>CRM Bridge</h2>
        <p className='text-xs text-ct-text3 mt-1'>
          Exporta listas de conductores al CRM y recibe resultados del contacto. Mantiene trazabilidad completa.
        </p>
      </div>

      {/* Degradation banner */}
      <div className='bg-orange-50 border border-orange-200 rounded-lg p-3 flex items-center gap-2'>
        <span className='text-orange-500 text-lg'>&#x26A0;</span>
        <div className='text-xs text-orange-800'>
          <strong>Importante:</strong> Si el CRM no responde, Drivers sigue funcionando normalmente. Las campañas, colas y workflows no se bloquean.
        </div>
      </div>

      {/* Tabs */}
      <div className='flex gap-1.5 flex-wrap'>
        {[
          { key: 'overview', label: 'Resumen' },
          { key: 'syncs', label: 'Historial de sincronización' },
        ].map(t => (
          <button key={t.key} type='button' onClick={() => setActiveTab(t.key)}
            className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${activeTab === t.key ? 'bg-ct-accent text-white shadow-sm' : 'text-ct-text2 hover:text-ct-text hover:bg-ct-border'}`}>
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

      {loading ? (
        <div className='animate-pulse space-y-2'><div className='h-4 bg-gray-100 rounded w-48' /><div className='h-3 bg-gray-50 rounded w-3/4' /></div>
      ) : (
        <>
          {/* Overview */}
          {activeTab === 'overview' && health && (
            <div className='space-y-4'>
              {/* Health */}
              <div className='flex items-center gap-3 flex-wrap'>
                <span className={`text-sm font-semibold px-3 py-1 rounded-full border ${
                  health.status === 'ok' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                  'bg-red-50 text-red-700 border-red-200'
                }`}>
                  {health.status === 'ok' ? 'Healthy' : 'Issues Detected'}
                </span>
                <span className='text-xs text-ct-text2'>{health.message}</span>
              </div>

              {/* Stats */}
              <div className='grid grid-cols-2 sm:grid-cols-5 gap-2'>
                {[
                  { label: 'Total envíos', value: health.total_syncs },
                  { label: 'Completados', value: health.completed, color: 'text-emerald-700' },
                  { label: 'Exportados', value: health.exported, color: 'text-blue-700' },
                  { label: 'Parciales', value: health.partial, color: 'text-amber-700' },
                  { label: 'Fallidos', value: health.failed, color: 'text-red-700' },
                ].map(kpi => (
                  <div key={kpi.label} className='border border-ct-border rounded-lg px-3 py-2'>
                    <div className='text-[10px] text-ct-text3 uppercase'>{kpi.label}</div>
                    <div className={`text-sm font-bold ${kpi.color || 'text-ct-text'}`}>{kpi.value}</div>
                  </div>
                ))}
              </div>

              {/* Pending sync campaigns */}
              {health.pending_sync_campaigns?.length > 0 && (
                <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
                  <h3 className='text-sm font-semibold text-ct-text mb-2'>Pending CRM Sync ({health.pending_sync_campaigns.length})</h3>
                  <div className='overflow-x-auto'>
                    <table className='w-full text-xs'>
                      <thead><tr className='text-left text-gray-400 border-b'><th className='py-1.5 pr-2'>Campaign</th><th className='py-1.5 pr-2'>Status</th><th className='py-1.5 pr-2'>CRM Status</th><th className='py-1.5 pr-2'>Created</th><th className='py-1.5'>Action</th></tr></thead>
                      <tbody>
                        {health.pending_sync_campaigns.map(c => (
                          <tr key={c.campaign_id} className='border-b border-gray-50'>
                            <td className='py-1.5 pr-2 font-medium text-ct-text truncate max-w-[200px]'>{c.campaign_name || '(Sin nombre)'}</td>
                            <td className='py-1.5 pr-2'>{c.campaign_status}</td>
                            <td className='py-1.5 pr-2'>{c.crm_sync_status}</td>
                            <td className='py-1.5 pr-2 text-ct-text3'>{c.created_at?.slice(0, 10) || '—'}</td>
                            <td className='py-1.5'>
                              <button type='button' onClick={() => handleExport(c.campaign_id)}
                                className='px-2 py-0.5 rounded bg-blue-500 text-white text-[10px] font-medium hover:bg-blue-600'>
                                Export to CRM
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Checks */}
              {health.checks?.length > 0 && (
                <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
                  <h3 className='text-sm font-semibold text-ct-text mb-2'>Bridge Health Checks</h3>
                  {health.checks.map((c, i) => (
                    <div key={i} className='flex items-center gap-2 text-[11px] py-0.5'>
                      <span className={`w-1.5 h-1.5 rounded-full ${
                        c.status === 'ok' ? 'bg-emerald-500' : c.status === 'warning' ? 'bg-amber-500' : 'bg-red-500'
                      }`} />
                      <span className='font-medium text-ct-text'>{c.name}</span>
                      <span className='text-ct-text2'>{c.message}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Sync History */}
          {activeTab === 'syncs' && (
            <div className='bg-ct-card border border-ct-border rounded-lg overflow-hidden'>
              <div className='px-4 py-2 border-b border-ct-border flex items-center justify-between'>
                <h3 className='text-sm font-semibold text-ct-text'>Sync History ({syncHistory.length})</h3>
                <button type='button' onClick={loadData} className='text-xs text-ct-accent hover:underline'>Refresh</button>
              </div>
              {syncHistory.length === 0 ? (
                <div className='px-4 py-6 text-center text-xs text-ct-text3'>No sync records yet. Export a campaign to create one.</div>
              ) : (
                <div className='overflow-x-auto'>
                  <table className='w-full text-xs'>
                    <thead>
                      <tr className='text-left text-gray-400 border-b border-gray-100'>
                        <th className='py-1.5 px-2'>Direction</th>
                        <th className='py-1.5 px-2'>Status</th>
                        <th className='py-1.5 px-2 text-right'>Members</th>
                        <th className='py-1.5 px-2 text-right'>Failed</th>
                        <th className='py-1.5 px-2'>CRM</th>
                        <th className='py-1.5 px-2'>Error</th>
                        <th className='py-1.5 px-2'>Last Sync</th>
                      </tr>
                    </thead>
                    <tbody>
                      {syncHistory.map((s, i) => (
                        <tr key={i} className='border-b border-gray-50'>
                          <td className='py-1.5 px-2'>{s.sync_direction}</td>
                          <td className='py-1.5 px-2'>
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${SYNC_STATUS_COLORS[s.sync_status] || 'bg-gray-100'}`}>{s.sync_status}</span>
                          </td>
                          <td className='py-1.5 px-2 text-right'>{s.exported_members_count}</td>
                          <td className='py-1.5 px-2 text-right text-red-500'>{s.failed_members_count || 0}</td>
                          <td className='py-1.5 px-2 text-ct-text2'>{s.crm_system_name}</td>
                          <td className='py-1.5 px-2 text-ct-text2 truncate max-w-[150px]'>{s.sync_error_summary || '—'}</td>
                          <td className='py-1.5 px-2 text-ct-text3'>{s.last_sync_at?.slice(0, 16) || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
