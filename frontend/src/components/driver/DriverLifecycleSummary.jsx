/**
 * DriverLifecycleSummary — FASE D3
 * Lifecycle distribution card for Driver Operating Hub.
 *
 * Consume /drivers/lifecycle-summary.
 * Muestra distribución de lifecycle_stage con counts y phone coverage.
 * Compacto, enterprise.
 */
import { useState, useEffect } from 'react'
import api from '../../services/api'

const STAGE_COLORS = {
  ACTIVE: { dot: 'bg-emerald-500', bar: 'bg-emerald-100', text: 'text-emerald-700' },
  ACTIVE_LOW: { dot: 'bg-teal-500', bar: 'bg-teal-100', text: 'text-teal-700' },
  DECLINING: { dot: 'bg-amber-500', bar: 'bg-amber-100', text: 'text-amber-700' },
  AT_RISK: { dot: 'bg-red-500', bar: 'bg-red-100', text: 'text-red-700' },
  REGISTERED_NO_TRIPS: { dot: 'bg-blue-400', bar: 'bg-blue-50', text: 'text-blue-600' },
  REACTIVATED: { dot: 'bg-green-500', bar: 'bg-green-100', text: 'text-green-700' },
  CHURNED_RECENT: { dot: 'bg-orange-500', bar: 'bg-orange-100', text: 'text-orange-700' },
  CHURNED_LONG: { dot: 'bg-gray-400', bar: 'bg-gray-100', text: 'text-gray-600' },
  NO_ACTIVITY_DATA: { dot: 'bg-gray-300', bar: 'bg-gray-50', text: 'text-gray-500' },
}

function StageBar ({ stage, count, total, avgTrips }) {
  const colors = STAGE_COLORS[stage] || STAGE_COLORS.NO_ACTIVITY_DATA
  const pct = total > 0 ? Math.round((count / total) * 100) : 0

  return (
    <div className='flex items-center gap-2 text-[11px]'>
      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${colors.dot}`} />
      <span className={`w-20 font-medium ${colors.text} truncate`}>{stage.replace(/_/g, ' ')}</span>
      <span className='w-10 text-right font-mono text-gray-600'>{count}</span>
      <div className='flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden'>
        <div className={`h-full rounded-full ${colors.dot.replace('bg-', 'bg-').replace('500', '300')}`} style={{ width: `${pct}%` }} />
      </div>
      <span className='w-8 text-right text-gray-400'>{pct}%</span>
      {avgTrips > 0 && (
        <span className='text-gray-400 w-16 text-right'>avg {avgTrips}</span>
      )}
    </div>
  )
}

export default function DriverLifecycleSummary () {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api.get('/drivers/lifecycle-summary', { timeout: 25000 })
      .then((res) => {
        if (!cancelled) setData(res.data)
      })
      .catch(() => {
        if (!cancelled) setData(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return (
      <div className='border border-ct-border rounded-lg p-3 bg-white/40'>
        <div className='animate-pulse space-y-2'>
          <div className='h-3 bg-gray-100 rounded w-28' />
          <div className='h-2 bg-gray-50 rounded w-full' />
          <div className='h-2 bg-gray-50 rounded w-3/4' />
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className='border border-amber-200 rounded-lg p-3 bg-amber-50/50'>
        <span className='text-[11px] text-amber-700 font-medium'>Lifecycle: unavailable</span>
      </div>
    )
  }

  const summary = data.summary || []
  const total = summary.reduce((s, item) => s + item.drivers_count, 0)
  const quality = data.quality || {}
  const warnings = data.warnings || []

  return (
    <div className='border border-ct-border rounded-lg p-3 bg-white/40 mb-4'>
      <div className='flex items-baseline gap-2 mb-2'>
        <h3 className='text-xs font-semibold text-ct-text'>Lifecycle Distribution</h3>
        <span className='text-[10px] text-gray-400'>{total} drivers</span>
      </div>

      <div className='space-y-1.5'>
        {summary.map((item) => (
          <StageBar
            key={item.lifecycle_stage}
            stage={item.lifecycle_stage}
            count={item.drivers_count}
            total={total}
            avgTrips={item.avg_trips_30d}
          />
        ))}
      </div>

      <div className='flex items-center gap-3 mt-2 pt-2 border-t border-gray-100 text-[10px] text-gray-400'>
        <span>Identity: {quality.identity_coverage != null ? `${quality.identity_coverage}%` : '—'}</span>
        <span>Phone: {quality.phone_coverage != null ? `${quality.phone_coverage}%` : '—'}</span>
        <span>Activity: {quality.activity_coverage != null ? `${quality.activity_coverage}%` : '—'}</span>
      </div>

      {warnings.length > 0 && (
        <div className='mt-2 text-[10px] text-amber-600'>
          {warnings[0].message}
        </div>
      )}

      {data.blocking_gaps && data.blocking_gaps.length > 0 && (
        <div className='mt-1 text-[10px] text-red-500'>
          Blocking: {data.blocking_gaps[0].message}
        </div>
      )}
    </div>
  )
}
