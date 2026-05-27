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
import { useState, useEffect } from 'react'
import api from '../../services/api'

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

  useEffect(() => {
    let cancelled = false
    setLoading(true)
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
          setError(err.message || 'Failed to load serving freshness')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

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
      <div className='border border-amber-200 rounded-lg p-3 bg-amber-50/50'>
        <span className='text-[11px] text-amber-700 font-medium'>Data Foundation: unavailable</span>
        <span className='text-[10px] text-amber-600 ml-2'>{error}</span>
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
    </div>
  )
}
