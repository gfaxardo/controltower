/**
 * DriverOperationalHealth — H1 Hardening
 * Minimal component surfacing /drivers/health endpoint.
 * Replaces placeholder on /drivers/operational-health route.
 *
 * NO features. NO new functionality. Just exposes existing health checks.
 */
import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'
import { DriverRefreshHint } from './DriverLoadState'

export default function DriverOperationalHealth () {
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [loadKey, setLoadKey] = useState(0)

  const reload = useCallback(() => { setLoadKey(k => k + 1) }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    api.get('/drivers/health', { timeout: 30000 })
      .then((res) => {
        if (!cancelled) { setHealth(res.data); setError(null) }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.code === 'ECONNABORTED' ? 'Timeout al verificar health del sistema' : (err.message || 'Error al cargar health'))
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [loadKey])

  if (loading) {
    return (
      <div className='space-y-4'>
        <div className='bg-ct-card border border-ct-border rounded-xl px-5 py-4'>
          <h2 className='text-lg font-bold text-ct-text'>Operational Health</h2>
          <p className='text-xs text-ct-text3 mt-1'>Verificando salud de todos los servicios de Drivers...</p>
        </div>
        <div className='animate-pulse space-y-2'>
          <div className='h-4 bg-gray-100 rounded w-48' />
          <div className='h-3 bg-gray-50 rounded w-3/4' />
          <div className='h-3 bg-gray-50 rounded w-2/3' />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className='space-y-4'>
        <div className='bg-ct-card border border-ct-border rounded-xl px-5 py-4'>
          <h2 className='text-lg font-bold text-ct-text'>Operational Health</h2>
          <p className='text-xs text-ct-text3 mt-1'>Monitoreo de salud de servicios de Drivers.</p>
        </div>
        <div className='border border-red-200 rounded-lg p-3 bg-red-50/50'>
          <div className='flex items-start justify-between gap-2'>
            <div>
              <span className='text-[11px] text-red-700 font-medium'>Error al verificar health</span>
              <div className='text-[10px] text-red-600 mt-0.5'>{error}</div>
            </div>
            <button type='button' onClick={reload} className='flex-shrink-0 px-2.5 py-1 text-[10px] font-medium rounded border border-gray-300 bg-white text-gray-600 hover:bg-gray-50'>Reintentar</button>
          </div>
        </div>
      </div>
    )
  }

  if (!health) return null

  const checks = health.checks || []
  const blockingGaps = health.blocking_gaps || []
  const warnings = health.warnings || []

  return (
    <div className='space-y-4'>
      <div className='bg-ct-card border border-ct-border rounded-xl px-5 py-4'>
        <h2 className='text-lg font-bold text-ct-text'>Operational Health</h2>
        <p className='text-xs text-ct-text3 mt-1'>
          Monitoreo de salud de todos los servicios de Drivers. Cada check verifica una fuente de datos o servicio.
        </p>
      </div>

      <div className='flex items-center gap-3'>
        <span className={`text-xs px-2.5 py-1 rounded-full font-medium border ${
          health.status === 'ok' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
          health.status === 'warning' ? 'bg-amber-50 text-amber-700 border-amber-200' :
          'bg-red-50 text-red-700 border-red-200'
        }`}>
          Overall: {health.status}
        </span>
        <span className='text-[11px] text-ct-text2'>{checks.length} checks</span>
        {blockingGaps.length > 0 && (
          <span className='text-[11px] text-red-600'>{blockingGaps.length} blocking</span>
        )}
        {warnings.length > 0 && (
          <span className='text-[11px] text-amber-600'>{warnings.length} warnings</span>
        )}
        <button type='button' onClick={reload} disabled={loading}
          className='ml-auto px-3 py-1 rounded bg-ct-accent text-white text-xs font-medium hover:bg-blue-600 disabled:opacity-50'>
          {loading ? 'Checking...' : 'Refresh'}
        </button>
      </div>

      {blockingGaps.length > 0 && (
        <div className='bg-red-50 border border-red-200 rounded-lg px-4 py-3'>
          <div className='text-xs font-semibold text-red-800 mb-1'>Blocking Gaps</div>
          {blockingGaps.map((g, i) => (
            <div key={i} className='text-[11px] text-red-700'>
              {g.name || g} — {g.remediation || g.message || ''}
            </div>
          ))}
        </div>
      )}

      {health.remediation && (
        <div className='bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-[11px] text-amber-800'>
          <strong>Remediation:</strong> {health.remediation}
        </div>
      )}

      <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
        <h3 className='text-sm font-semibold text-ct-text mb-3'>Health Checks</h3>
        <div className='overflow-x-auto'>
          <table className='w-full text-[11px]'>
            <thead>
              <tr className='text-left text-gray-400 border-b'>
                <th className='py-1.5 pr-2'>Source</th>
                <th className='py-1.5 pr-2'>Status</th>
                <th className='py-1.5 pr-2'>Message</th>
                <th className='py-1.5'>Remediation</th>
              </tr>
            </thead>
            <tbody>
              {checks.map((c, i) => (
                <tr key={i} className='border-b border-gray-50 hover:bg-gray-50/50'>
                  <td className='py-1.5 pr-2 font-medium text-ct-text'>{c.name}</td>
                  <td className='py-1.5 pr-2'>
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium border ${
                      c.status === 'ok' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                      c.status === 'warning' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                      'bg-red-50 text-red-700 border-red-200'
                    }`}>{c.status}</span>
                  </td>
                  <td className='py-1.5 pr-2 text-ct-text2 truncate max-w-[300px]' title={c.message}>{c.message}</td>
                  <td className='py-1.5 text-ct-text3 text-[10px] truncate max-w-[200px]' title={c.remediation}>{c.remediation || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {checks.length === 0 && (
          <div className='py-6 text-center text-xs text-ct-text3'>No health checks available.</div>
        )}
      </div>

      <DriverRefreshHint />
    </div>
  )
}
