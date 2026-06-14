import { useState, useEffect } from 'react'
import { getExclusiveWorklistSummary, getExclusiveWorklistControlLoopPreview } from '../../../services/api.js'

const UNIVERSE_LABELS = {
  'RECOVERY_RECENT_INACTIVE_HIGH_VALUE': { short: 'Recovery High', desc: 'Alta prioridad — recuperar conductores valiosos', actionable: true, priority: 1 },
  'NEW_REACTIVATED_0_14_TO_50': { short: 'New / Reactivated', desc: 'Nuevos o reactivados — llevar a 50 viajes', actionable: true, priority: 2 },
  'RAMP_UP_15_45_TO_100W': { short: 'Ramp Up', desc: '15-45 días — llevar a 100 viajes/semana', actionable: true, priority: 3 },
  'CONSOLIDATION_46_90_TO_100W': { short: 'Consolidation', desc: '46-90 días — sostener 100 viajes/semana', actionable: true, priority: 4 },
  'ACTIVE_GROWTH_90_PLUS_BAND_UP': { short: 'Active Growth', desc: 'Activos 90+ — subir de banda', actionable: true, priority: 5 },
  'RECOVERY_RECENT_INACTIVE_LOW_VALUE': { short: 'Recovery Low', desc: 'Baja prioridad — recuperación masiva', actionable: true, priority: 6 },
  'PROTECTED_ALREADY_MEETING_GOAL': { short: 'Protected', desc: 'No trabajar — ya cumple meta', actionable: false, priority: 7 },
  'CEMETERY_LONG_CHURNED': { short: 'Cemetery', desc: 'No trabajar — churn largo', actionable: false, priority: 8 },
  'NO_DATA_OR_NO_ACTION': { short: 'No Data', desc: 'Sin datos suficientes', actionable: false, priority: 9 },
}

const PRIORITY_ORDER = [
  'RECOVERY_RECENT_INACTIVE_HIGH_VALUE',
  'NEW_REACTIVATED_0_14_TO_50',
  'RAMP_UP_15_45_TO_100W',
  'CONSOLIDATION_46_90_TO_100W',
  'ACTIVE_GROWTH_90_PLUS_BAND_UP',
  'RECOVERY_RECENT_INACTIVE_LOW_VALUE',
  'PROTECTED_ALREADY_MEETING_GOAL',
  'CEMETERY_LONG_CHURNED',
  'NO_DATA_OR_NO_ACTION',
]

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
      if (!s && !c) setError('Both endpoints unreachable.')
    })
    return () => { cancelled = true }
  }, [])

  if (loading) return <div className="p-6 text-sm text-gray-400">Loading daily command...</div>
  if (error && !summary && !clPreview) return <div className="p-6 bg-red-50 text-red-700 text-sm rounded">{error}</div>

  const date = summary?.resolved_generated_date || '—'
  const total = summary?.total_drivers || 0
  const exportable = summary?.exportable_drivers || 0
  const nonExportable = summary?.non_exportable_drivers || Math.max(0, total - exportable)
  const rawByUniverse = Array.isArray(summary?.by_universe) ? summary.by_universe : []

  // Map backend key "assigned_universe_v1" to frontend
  const byUniverse = rawByUniverse.map(u => ({
    key: u?.assigned_universe_v1 || u?.universe || '',
    count: u?.drivers || u?.count || 0,
  })).filter(u => u.key)

  const actionableCount = byUniverse
    .filter(u => UNIVERSE_LABELS[u.key]?.actionable)
    .reduce((s, u) => s + u.count, 0)
  const nonActionableCount = byUniverse
    .filter(u => !UNIVERSE_LABELS[u.key]?.actionable)
    .reduce((s, u) => s + u.count, 0)

  // Sort by priority
  const sorted = [...byUniverse].sort((a, b) => {
    const pa = UNIVERSE_LABELS[a.key]?.priority || 99
    const pb = UNIVERSE_LABELS[b.key]?.priority || 99
    return pa - pb
  })

  const clTotal = clPreview?.total_exportable || 0
  const today = new Date().toISOString().substring(0, 10)
  const isToday = date === today

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-bold text-gray-800">Comando Diario</h2>

      {/* Top cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card label="Lista generada" value={date} subtitle={isToday ? 'Actualizada hoy' : `Fecha de la worklist`} />
        <Card label="Total clasificados" value={total.toLocaleString()} subtitle="Conductores en algún universo" />
        <Card label="Para trabajar hoy" value={exportable.toLocaleString()} subtitle="Enviados a Control Loop" color="text-green-700" bg="bg-green-50" />
        <Card label="No trabajar" value={nonExportable.toLocaleString()} subtitle="Cemetery + Protected" color="text-gray-500" bg="bg-gray-50" />
      </div>

      {/* Actionable / Non-actionable summary */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <p className="text-xs text-green-600 font-semibold uppercase tracking-wide">Accionables</p>
          <p className="text-2xl font-bold text-green-800">{actionableCount.toLocaleString()}</p>
          <p className="text-xs text-green-500 mt-1">6 universes ready for agents</p>
        </div>
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <p className="text-xs text-gray-500 font-semibold uppercase tracking-wide">No Accionables</p>
          <p className="text-2xl font-bold text-gray-600">{nonActionableCount.toLocaleString()}</p>
          <p className="text-xs text-gray-400 mt-1">Cemetery, Protected</p>
        </div>
      </div>

      {/* Priority work order hint */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-xs text-blue-700 font-semibold mb-2">Orden sugerido de trabajo:</p>
        <div className="flex flex-wrap gap-1 text-xs text-blue-600">
          {[1,2,3,4,5,6].map(p => {
            const u = PRIORITY_ORDER.find(k => UNIVERSE_LABELS[k]?.priority === p)
            return u ? <span key={p} className="after:content-['→'] after:ml-1 after:text-blue-300 last:after:content-none">{UNIVERSE_LABELS[u].short}</span> : null
          })}
        </div>
        <p className="text-xs text-blue-400 mt-1">Prioriza valor recuperable, ventanas tempranas y conductores cerca de meta.</p>
      </div>

      {/* Universe breakdown */}
      {sorted.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold text-gray-700 mb-2">Por Universo</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {sorted.map((u, i) => {
              const meta = UNIVERSE_LABELS[u.key] || {}
              return (
                <div key={u.key || i} className={`rounded-lg p-3 border ${meta.actionable ? 'bg-white border-blue-200' : 'bg-gray-50 border-gray-200'}`}>
                  <p className={`text-xs font-semibold ${meta.actionable ? 'text-blue-800' : 'text-gray-500'}`}>
                    {meta.short || u.key.replace(/_/g, ' ').substring(0, 28)}
                  </p>
                  <p className={`text-lg font-bold ${meta.actionable ? 'text-blue-900' : 'text-gray-400'}`}>{u.count.toLocaleString()}</p>
                  <p className="text-[11px] text-gray-400 mt-0.5">{meta.desc || ''}</p>
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
            <p className="text-xs text-indigo-500 mt-1">{clTotal.toLocaleString()} drivers READY for agent assignment</p>
          </>
        ) : (
          <p className="text-xs text-orange-600">Control Loop preview endpoint not available. Worklist data is current.</p>
        )}
      </div>

      {error && (summary || clPreview) && <p className="text-xs text-orange-600 bg-orange-50 p-2 rounded">Partial data available.</p>}
    </div>
  )
}

function Card({ label, value, subtitle, color = 'text-gray-700', bg = 'bg-white' }) {
  return (
    <div className={`rounded-lg border border-gray-200 p-3 ${bg}`}>
      <p className="text-[11px] text-gray-400 uppercase tracking-wide">{label}</p>
      <p className={`text-xl font-bold ${color}`}>{value}</p>
      <p className="text-[10px] text-gray-400">{subtitle}</p>
    </div>
  )
}
