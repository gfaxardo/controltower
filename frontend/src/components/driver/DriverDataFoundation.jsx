/**
 * DriverDataFoundation — FASE D2
 * Data Foundation card for the Driver Operating Hub.
 *
 * Muestra:
 *  - Identity coverage (drivers con nombre)
 *  - Phone coverage (drivers con telefono)
 *  - Sources freshness (desde /drivers/raw-freshness)
 *  - Blocking gaps
 *
 * Consume endpoints backend. NO calculos en frontend.
 * Compacto, enterprise, no consume mucho espacio.
 */
import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'
import { DriverRefreshHint } from './DriverLoadState'

function FreshnessDot ({ status }) {
  const map = {
    fresh: 'bg-emerald-500',
    stale: 'bg-amber-500',
    unknown: 'bg-gray-400',
    blocked: 'bg-red-500',
  }
  return <span className={`w-2 h-2 rounded-full inline-block ${map[status] || 'bg-gray-300'}`} />
}

function GapItem ({ gap }) {
  return (
    <div className='flex items-start gap-2 text-[11px] py-0.5'>
      <span className='text-red-400 mt-0.5'>&#x25CF;</span>
      <div>
        <span className='font-medium text-gray-600'>{gap.source_name}</span>
        <span className='text-gray-400 ml-1'>({gap.role})</span>
        <span className='text-gray-400 ml-1'>— {gap.remediation}</span>
      </div>
    </div>
  )
}

export default function DriverDataFoundation () {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [loadKey, setLoadKey] = useState(0)

  const reload = useCallback(() => { setLoadKey(k => k + 1) }, [])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    api.get('/drivers/serving-freshness', { timeout: 10000 })
      .then((res) => {
        if (!cancelled) {
          const d = res.data
          const facts = d.facts || []
          const freshCount = facts.filter(f => f.freshness_status === 'fresh').length
          const staleCount = facts.filter(f => f.freshness_status === 'stale').length
          const blockedCount = facts.filter(f => f.freshness_status === 'blocked').length
          const freshMap = {}
          facts.forEach(f => { freshMap[f.fact_name] = f })
          setData({
            status: d.status || 'ok',
            sources: facts.map(f => ({
              source_name: f.fact_name,
              role: 'serving_fact',
              freshness_status: f.freshness_status,
              refreshed_at: f.refreshed_at,
              max_period: f.max_operational_period,
              row_count: f.row_count,
            })),
            blocking_gaps: d.blocked_facts?.length ? d.blocked_facts.map(n => ({ source_name: n, role: 'serving_fact', remediation: d.remediation })) : [],
            _freshCount: freshCount,
            _staleCount: staleCount,
            _blockedCount: blockedCount,
            _freshMap: freshMap,
            _remediation: d.remediation,
          })
          setError(null)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          const msg = err.code === 'ECONNABORTED' ? 'Timeout al conectar con el servicio' : (err.message || 'Error al cargar freshness')
          setError(msg)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [loadKey])

  if (loading) {
    return (
      <div className='border border-ct-border rounded-lg p-3 bg-white/40'>
        <div className='animate-pulse flex flex-col gap-2'>
          <div className='h-3 bg-gray-100 rounded w-32' />
          <div className='h-2 bg-gray-50 rounded w-48' />
          <div className='h-2 bg-gray-50 rounded w-36' />
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className='border border-red-200 rounded-lg p-3 bg-red-50/50'>
        <div className='flex items-start justify-between gap-2'>
          <div>
            <span className='text-[11px] text-red-700 font-medium'>Data Foundation: error t\u00e9cnico</span>
            <div className='text-[10px] text-red-600 mt-0.5'>{error}</div>
            <div className='text-[10px] text-gray-500 mt-1'>Remediaci\u00f3n: Run refresh_driver_supply_facts.py o verificar conectividad DB.</div>
          </div>
          <button type='button' onClick={reload} className='flex-shrink-0 px-2.5 py-1 text-[10px] font-medium rounded border border-gray-300 bg-white text-gray-600 hover:bg-gray-50'>Reintentar</button>
        </div>
      </div>
    )
  }

  if (!data) return null

  const freshCount = data._freshCount ?? 0
  const staleCount = data._staleCount ?? 0
  const blockedCount = data._blockedCount ?? 0
  const sources = data.sources || []
  const blocking = data.blocking_gaps || []

  return (
    <div className='border border-ct-border rounded-lg p-3 bg-white/40 mb-4'>
      <div className='flex items-baseline gap-2 mb-2'>
        <h3 className='text-xs font-semibold text-ct-text'>Serving Foundation</h3>
        <span className={`text-[10px] font-medium px-1.5 py-px rounded-full border ${
          data.status === 'ok' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
          data.status === 'warning' ? 'bg-amber-50 text-amber-700 border-amber-200' :
          'bg-red-50 text-red-700 border-red-200'
        }`}>
          {data.status === 'ok' ? 'Healthy' : data.status === 'warning' ? 'Warning' : 'Blocked'}
        </span>
      </div>

      <div className='flex items-center gap-4 flex-wrap text-[11px] text-gray-500'>
        <span className='inline-flex items-center gap-1'>
          <FreshnessDot status='fresh' /> {freshCount} fresh
        </span>
        <span className='inline-flex items-center gap-1'>
          <FreshnessDot status='stale' /> {staleCount} stale
        </span>
        <span className='inline-flex items-center gap-1'>
          <FreshnessDot status='blocked' /> {blockedCount} blocked
        </span>
        <span className='text-gray-300'>|</span>
        <span className='inline-flex items-center gap-1 text-emerald-600'>
          Facts: serving
        </span>
      </div>

      {sources.length > 0 && (
        <div className='border-t border-gray-100 pt-2 mt-2'>
          <div className='grid grid-cols-1 sm:grid-cols-2 gap-1'>
            {sources.map(s => (
              <div key={s.source_name} className='flex items-center gap-1.5 text-[10px]'>
                <FreshnessDot status={s.freshness_status} />
                <span className='text-gray-600 truncate'>{s.source_name}</span>
                {s.refreshed_at && <span className='text-gray-300 ml-auto'>{s.refreshed_at.slice(0, 16).replace('T', ' ')}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {blocking.length > 0 && (
        <div className='border-t border-gray-100 pt-2 mt-1'>
          <span className='text-[10px] font-medium text-red-600 uppercase tracking-wide'>
            Blocking ({blocking.length})
          </span>
          <div className='mt-1 text-[10px] text-red-500'>
            {data._remediation || 'Run refresh_driver_supply_facts.py'}
          </div>
        </div>
      )}

      <div className='border-t border-gray-100 pt-2 mt-2'>
        <DriverRefreshHint />
      </div>
    </div>
  )
}
