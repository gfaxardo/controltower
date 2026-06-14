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
    Promise.all([
      getExclusiveWorklistSummary().catch(() => null),
      getExclusiveWorklistControlLoopPreview({ limit: 10 }).catch(() => null),
    ]).then(([s, c]) => {
      if (cancelled) return
      setSummary(s)
      setClPreview(c)
      setLoading(false)
      if (!s && !c) setError('Endpoints unreachable.')
    })
    return () => { cancelled = true }
  }, [])

  if (loading) return <div className="p-6 text-sm text-gray-400">Loading daily command...</div>
  if (error && !summary) return <div className="p-6 bg-red-50 text-red-700 text-sm rounded">Command Center: {error} Check backend Growth.</div>

  const date = summary?.resolved_generated_date || '—'
  const total = summary?.total_drivers || 0
  const exportable = summary?.exportable_drivers || 0
  const nonExportable = summary?.non_exportable_drivers || (total - exportable)
  const byUniverse = summary?.by_universe || []

  const actionableCount = byUniverse.filter(u => ACTIONABLE.includes(u.universe)).reduce((s,u) => s + (u.drivers||u.count||0), 0)
  const nonActionableCount = byUniverse.filter(u => NON_ACTIONABLE.includes(u.universe)).reduce((s,u) => s + (u.drivers||u.count||0), 0)

  const clTotal = clPreview?.total_exportable || (clPreview?.rows?.length || 0)

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-bold text-gray-800">Comando Diario</h2>

      {/* Top metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card label="Generated Date" value={date} icon="📅" />
        <Card label="Total Classified" value={total} icon="👥" />
        <Card label="Exportable" value={exportable} icon="✅" color="text-green-700" bg="bg-green-50" />
        <Card label="Non-Exportable" value={nonExportable} icon="⛔" color="text-gray-500" bg="bg-gray-50" />
      </div>

      {/* Actionable vs Non-actionable split */}
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
      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-2">Por Universo</h3>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
          {byUniverse.map(u => {
            const count = u.drivers || u.count || 0
            const isActionable = ACTIONABLE.includes(u.universe)
            return (
              <div key={u.universe} className={`rounded-lg p-3 border ${isActionable ? 'bg-white border-blue-200' : 'bg-gray-50 border-gray-200'}`}>
                <p className={`text-xs truncate ${isActionable ? 'text-blue-700 font-medium' : 'text-gray-400'}`}>{u.universe.replace(/_/g,' ').substring(0,35)}</p>
                <p className={`text-lg font-bold ${isActionable ? 'text-blue-900' : 'text-gray-400'}`}>{count}</p>
              </div>
            )
          })}
        </div>
      </div>

      {/* Control Loop batch indicator */}
      {clPreview && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs text-indigo-600 font-semibold uppercase tracking-wide">Control Loop Batch</span>
            {clTotal > 0 ? <span className="text-xs bg-green-500 text-white px-1.5 py-0.5 rounded font-bold">SYNCED</span> : <span className="text-xs bg-red-500 text-white px-1.5 py-0.5 rounded">MISSING</span>}
          </div>
          <p className="text-sm text-indigo-700">Batch: <span className="font-mono text-xs">{clPreview?.resolved_generated_date ? `prod-${clPreview.resolved_generated_date}` : '—'}</span></p>
          <p className="text-xs text-indigo-500 mt-1">{clTotal} drivers READY for agent assignment</p>
        </div>
      )}

      {error && summary && <p className="text-xs text-orange-600 bg-orange-50 p-2 rounded">Control Loop batch unavailable — worklist data is current.</p>}
    </div>
  )
}

function Card({ label, value, icon, color = 'text-gray-700', bg = 'bg-white' }) {
  return (
    <div className={`rounded-lg border border-gray-200 p-3 ${bg}`}>
      <p className="text-xs text-gray-400">{icon} {label}</p>
      <p className={`text-xl font-bold ${color}`}>{value}</p>
    </div>
  )
}
