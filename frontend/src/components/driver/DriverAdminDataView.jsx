/**
 * DriverAdminDataView — FASE H3.5
 * Role: Admin / Data — "¿La data está confiable y el sistema está sano?"
 *
 * Data Foundation, Health, Governance, Sync Health.
 */
import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'
import DriverDataFoundation from './DriverDataFoundation.jsx'
import { DriverRefreshHint } from './DriverLoadState'

function formatNum (n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('es-ES')
}

export default function DriverAdminDataView () {
  const [health, setHealth] = useState(null)
  const [syncHealth, setSyncHealth] = useState(null)
  const [freshness, setFreshness] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const loadAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [hRes, sRes, fRes] = await Promise.all([
        api.get('/drivers/health', { timeout: 30000 }),
        api.get('/drivers/campaigns/sync-health', { timeout: 15000 }),
        api.get('/drivers/raw-freshness', { timeout: 15000 }),
      ])
      setHealth(hRes.data)
      setSyncHealth(sRes.data)
      setFreshness(fRes.data)
    } catch (err) {
      setError(err.code === 'ECONNABORTED' ? 'Timeout al cargar health del sistema' : (err.message || 'Error al cargar vista admin'))
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { loadAll() }, [loadAll])

  return (
    <div className='space-y-4'>
      <div className='bg-ct-card border border-ct-border rounded-xl px-5 py-4'>
        <div className='flex items-baseline gap-2'>
          <h2 className='text-lg font-bold text-ct-text'>System Health & Governance</h2>
          <span className='text-xs text-ct-text3'>Admin / Data View</span>
        </div>
        <p className='text-xs text-ct-text3 mt-1'>Verifica que los datos estén frescos, las fuentes operativas y el sistema sin bloqueos.</p>
      </div>

      {error && (
        <div className='border border-red-200 rounded-lg p-3 bg-red-50/50'>
          <div className='flex items-start justify-between gap-2'>
            <div>
              <span className='text-[11px] text-red-700 font-medium'>Error t\u00e9cnico</span>
              <div className='text-[10px] text-red-600 mt-0.5'>{error}</div>
              <div className='text-[10px] text-gray-500 mt-1'>Remediaci\u00f3n: Verificar conectividad con el backend y que el health check responda.</div>
            </div>
            <button type='button' onClick={loadAll} className='flex-shrink-0 px-2.5 py-1 text-[10px] font-medium rounded border border-gray-300 bg-white text-gray-600 hover:bg-gray-50'>Reintentar</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className='animate-pulse space-y-2'><div className='h-4 bg-gray-100 rounded w-48' /><div className='h-3 bg-gray-50 rounded w-3/4' /></div>
      ) : (
        <>
          {/* Data Foundation */}
          <DriverDataFoundation />

          {/* System Health */}
          {health && (
            <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
              <div className='flex items-baseline gap-2 mb-3'>
                <h3 className='text-sm font-semibold text-ct-text'>System Health</h3>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium border ${
                  health.status === 'ok' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                  health.status === 'warning' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                  'bg-red-50 text-red-700 border-red-200'
                }`}>{health.status}</span>
              </div>
              <div className='overflow-x-auto'>
                <table className='w-full text-[11px]'>
                  <thead><tr className='text-left text-gray-400 border-b'><th className='py-1 pr-2'>Check</th><th className='py-1 pr-2'>Status</th><th className='py-1 pr-2'>Message</th><th className='py-1'>Remediaci\u00f3n</th></tr></thead>
                  <tbody>
                    {(health.checks || []).map((c, i) => (
                      <tr key={i} className='border-b border-gray-50'>
                        <td className='py-1 pr-2 font-medium text-ct-text'>{c.name}</td>
                        <td className='py-1 pr-2'>
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium ${
                            c.status === 'ok' ? 'bg-emerald-100 text-emerald-700' :
                            c.status === 'warning' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'
                          }`}>{c.status}</span>
                        </td>
                        <td className='py-1 pr-2 text-ct-text2'>{c.message}</td>
                        <td className='py-1 text-ct-text3 text-[10px]'>{c.remediation || ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {health.blocking_gaps?.length > 0 && (
                <div className='mt-2 bg-red-50 rounded p-2 text-[10px] text-red-700'>
                  Blocking gaps: {health.blocking_gaps.map(g => g.name).join(', ')}
                </div>
              )}
            </div>
          )}

          {/* Freshness detail */}
          {freshness && (
            <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
              <h3 className='text-sm font-semibold text-ct-text mb-2'>Raw Freshness ({freshness.sources?.length || 0} sources)</h3>
              <div className='grid grid-cols-2 sm:grid-cols-3 gap-1.5'>
                {(freshness.sources || []).slice(0, 12).map((s, i) => (
                  <div key={i} className='flex items-center gap-1.5 text-[10px]'>
                    <span className={`w-1.5 h-1.5 rounded-full ${
                      s.freshness_status === 'fresh' ? 'bg-emerald-500' :
                      s.freshness_status === 'stale' ? 'bg-amber-500' : 'bg-red-500'
                    }`} />
                    <span className='text-ct-text truncate'>{s.source_name}</span>
                    <span className='text-ct-text3'>{s.freshness_status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* CRM Sync Health */}
          {syncHealth && (
            <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
              <h3 className='text-sm font-semibold text-ct-text mb-2'>CRM Sync Health</h3>
              <div className='grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]'>
                <div><span className='text-ct-text3'>Total:</span> <strong>{syncHealth.total_syncs}</strong></div>
                <div><span className='text-ct-text3'>Completed:</span> <strong className='text-emerald-600'>{syncHealth.completed}</strong></div>
                <div><span className='text-ct-text3'>Failed:</span> <strong className='text-red-600'>{syncHealth.failed}</strong></div>
                <div><span className='text-ct-text3'>Health:</span> <strong className={syncHealth.health === 'ok' ? 'text-emerald-600' : 'text-amber-600'}>{syncHealth.health}</strong></div>
              </div>
            </div>
          )}

          <DriverRefreshHint />

          <div className='bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-xs text-blue-800'>
            <strong>Governance:</strong> Esta vista muestra datos de salud del sistema. Para ver el mapa completo de capabilities, usar "Full Capability Map".
          </div>
        </>
      )}
    </div>
  )
}
