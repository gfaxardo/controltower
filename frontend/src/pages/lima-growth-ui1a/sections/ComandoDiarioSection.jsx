import { useState, useEffect } from 'react'
import { getExclusiveWorklistSummary, getExclusiveWorklistControlLoopPreview } from '../../../services/api.js'

const ACTIONABLE = ['NEW_REACTIVATED_0_14_TO_50','RAMP_UP_15_45_TO_100W','CONSOLIDATION_46_90_TO_100W','ACTIVE_GROWTH_90_PLUS_BAND_UP','RECOVERY_RECENT_INACTIVE_HIGH_VALUE','RECOVERY_RECENT_INACTIVE_LOW_VALUE']
const NON_ACTIONABLE = ['CEMETERY_LONG_CHURNED','PROTECTED_ALREADY_MEETING_GOAL','NO_DATA_OR_NO_ACTION']

export default function ComandoDiarioSection() {
  const [summary, setSummary] = useState(null)
  const [clPreview, setClPreview] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([
      getExclusiveWorklistSummary().catch(e => { console.warn('summary failed', e); return null }),
      getExclusiveWorklistControlLoopPreview({ limit: 10 }).catch(e => { console.warn('CL preview failed', e); return null }),
    ]).then(([s, c]) => {
      if (cancelled) return
      setSummary(s || null)
      setClPreview(c || null)
      setLoading(false)
      if (!s && !c) setError('Both endpoints unreachable. Check backend Growth.')
    })
    return () => { cancelled = true }
  }, [])

  if (loading) return <div className="p-6 text-sm text-gray-400">Loading daily command...</div>
  if (error && !summary && !clPreview) return <div className="p-6 bg-red-50 text-red-700 text-sm rounded">{error}</div>

  const date = summary?.resolved_generated_date || '—'
  const total = summary?.total_drivers || 0
  const exportable = summary?.exportable_drivers || 0
  const nonExportable = summary?.non_exportable_drivers || Math.max(0, total - exportable)
  const byUniverse = Array.isArray(summary?.by_universe) ? summary.by_universe : []

  const actionableCount = byUniverse.filter(u => ACTIONABLE.includes(u?.universe)).reduce((s,u) => s + (u?.drivers || u?.count || 0), 0)
  const nonActionableCount = byUniverse.filter(u => NON_ACTIONABLE.includes(u?.universe)).reduce((s,u) => s + (u?.drivers || u?.count || 0), 0)

  const clTotal = clPreview?.total_exportable || 0

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-bold text-gray-800">Comando Diario</h2>

      {/* Top metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card label="Generated Date" value={date} />
        <Card label="Total Classified" value={total} />
        <Card label="Exportable" value={exportable} color="text-green-700" bg="bg-green-50" />
        <Card label="Non-Exportable" value={nonExportable} color="text-gray-500" bg="bg-gray-50" />
      </div>

      {/* Actionable vs Non-actionable */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <p className="text-xs text-green-600 font-semibold uppercase tracking-wide">Accionables</p>
          <p className="text-2xl font-bold text-green-800">{actionableCount}</p>
          <p className="text-xs text-green-500 mt-1">6 universes ready for agent assignment</p>
        </div>
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wide">No Accionables</p>
          <p className="text-2xl font-bold text-gray-600">{nonActionableCount}</p>
          <p className="text-xs text-gray-400 mt-1">Cemetery + Protected</p>
        </div>
      </div>

      {/* Universe breakdown */}
      {byUniverse.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-2">Por Universo</h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {byUniverse.map((u, i) => {
              const count = u?.drivers || u?.count || 0
              const uni = u?.universe || ''
              const isActionable = uni && ACTIONABLE.includes(uni)
              return (
                <div key={uni || i} className={`rounded-lg p-3 border ${isActionable ? 'bg-white border-blue-200' : 'bg-gray-50 border-gray-200'}`}>
                  <p className={`text-xs truncate ${isActionable ? 'text-blue-700 font-medium' : 'text-gray-400'}`}>{uni.replace(/_/g,' ').substring(0,35)}</p>
                  <p className={`text-lg font-bold ${isActionable ? 'text-blue-900' : 'text-gray-400'}`}>{count}</p>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Control Loop batch */}
      <div className={`rounded-lg p-4 border ${clPreview ? 'bg-indigo-50 border-indigo-200' : 'bg-orange-50 border-orange-200'}`}>
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-semibold uppercase tracking-wide" style={{color: clPreview ? '#4338ca' : '#c2410c'}}>Control Loop Batch</span>
          {clPreview ? <span className="text-xs bg-green-500 text-white px-1.5 py-0.5 rounded font-bold">SYNCED</span> : <span className="text-xs bg-orange-500 text-white px-1.5 py-0.5 rounded">UNAVAILABLE</span>}
        </div>
        {clPreview ? (
          <>
            <p className="text-sm text-indigo-700">Batch: <span className="font-mono text-xs">prod-{date}</span></p>
            <p className="text-xs text-indigo-500 mt-1">{clTotal} drivers READY for agent assignment</p>
          </>
        ) : (
          <p className="text-xs text-orange-600">Control Loop preview endpoint not available. Worklist data is current.</p>
        )}
      </div>

      {error && (summary || clPreview) && <p className="text-xs text-orange-600 bg-orange-50 p-2 rounded">Partial data: some endpoints unavailable.</p>}
    </div>
  )
}

function Card({ label, value, color = 'text-gray-700', bg = 'bg-white' }) {
  return (
    <div className={`rounded-lg border border-gray-200 p-3 ${bg}`}>
      <p className="text-xs text-gray-400">{label}</p>
      <p className={`text-xl font-bold ${color}`}>{value}</p>
    </div>
  )
}
