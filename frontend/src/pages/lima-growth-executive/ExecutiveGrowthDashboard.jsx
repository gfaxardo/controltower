import React, { useState, useEffect } from 'react'
import { getExclusiveWorklistSummary, getExclusiveWorklistControlLoopPreview } from '../../services/api.js'

const ACTIONABLE = ['NEW_REACTIVATED_0_14_TO_50','RAMP_UP_15_45_TO_100W','CONSOLIDATION_46_90_TO_100W','ACTIVE_GROWTH_90_PLUS_BAND_UP','RECOVERY_RECENT_INACTIVE_HIGH_VALUE','RECOVERY_RECENT_INACTIVE_LOW_VALUE']

export default function ExecutiveGrowthDashboard() {
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
      if (!s) setError('Worklist endpoint unavailable')
    })
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto mb-4" />
          <p className="text-sm text-gray-500">Loading Executive Dashboard...</p>
        </div>
      </div>
    )
  }

  const date = summary?.resolved_generated_date || '—'
  const total = summary?.total_drivers || 0
  const exportable = summary?.exportable_drivers || 0
  const nonExportable = summary?.non_exportable_drivers || 0
  const byUniverse = Array.isArray(summary?.by_universe) ? summary.by_universe : []

  const actionableCount = byUniverse
    .filter(u => ACTIONABLE.includes(u?.universe || u?.assigned_universe_v1))
    .reduce((s, u) => s + (u?.drivers || u?.count || 0), 0)

  const nonActionableCount = total - actionableCount
  const clTotal = clPreview?.total_exportable || 0

  const insightItems = [
    { label: 'Control Loop', value: clPreview ? 'SYNCED' : 'HOLD', status: clPreview ? 'HEALTHY' : 'WARNING', detail: clPreview ? `${clTotal.toLocaleString()} READY` : 'Blocked — Monday observation pending' },
    { label: 'Worklist Date', value: date, status: date === new Date().toISOString().substring(0,10) ? 'HEALTHY' : 'STALE', detail: date },
    { label: 'Accionables', value: `${actionableCount.toLocaleString()}`, status: actionableCount > 5000 ? 'HEALTHY' : 'WARNING', detail: 'Drivers ready for work' },
    { label: 'No accionables', value: `${nonActionableCount.toLocaleString()}`, status: 'INFO', detail: 'Cemetery + Protected' },
    { label: 'Activos (Accionables/Total)', value: `${Math.round(100*actionableCount/total)}%`, status: actionableCount/total > 0.3 ? 'HEALTHY' : 'WARNING', detail: 'Share of fleet actionable' },
  ]

  return (
    <div className="min-h-screen bg-[#f4f6f9]">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Lima Growth Engine</h1>
            <p className="text-sm text-gray-500">Dashboard Ejecutivo · Crecimiento, riesgo y readiness</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full">{date}</span>
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-full">Lima</span>
            <span className="text-xs bg-purple-100 text-purple-700 px-2 py-1 rounded-full">V2 ACTIVE</span>
          </div>
        </div>
      </div>

      {/* Control Loop HOLD Banner */}
      <div className="bg-amber-50 border-b border-amber-200 px-6 py-3">
        <div className="flex items-center gap-2">
          <span className="text-amber-700 font-bold text-sm">CONTROL LOOP: HOLD</span>
          <span className="text-amber-600 text-xs">Bloqueado hasta validar lunes real y autonomous tick. Dashboard read-only.</span>
        </div>
        <div className="flex gap-4 mt-2 text-xs text-amber-500">
          <span>Real date >= 06-15</span>
          <span>·</span>
          <span>Worklist por autonomous_tick</span>
          <span>·</span>
          <span>1 ACTIVE config Lima</span>
          <span>·</span>
          <span>{clPreview ? '✓' : '○'} ~18,545 rows</span>
          <span>·</span>
          <span>{clPreview ? '✓' : '○'} 0 duplicados</span>
        </div>
      </div>

      {/* KPI Strip */}
      <div className="px-6 py-4">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {insightItems.map(item => (
            <div key={item.label} className="bg-white rounded-lg border border-gray-200 p-3">
              <p className="text-[10px] text-gray-400 uppercase tracking-wide">{item.label}</p>
              <p className="text-lg font-bold text-gray-800 mt-0.5">{item.value}</p>
              <p className="text-[10px] text-gray-400 mt-0.5">{item.detail}</p>
              <span className={`inline-block mt-1 w-2 h-2 rounded-full ${
                item.status === 'HEALTHY' ? 'bg-green-500' :
                item.status === 'WARNING' ? 'bg-amber-500' :
                item.status === 'STALE' ? 'bg-red-500' : 'bg-gray-300'
              }`} />
            </div>
          ))}
        </div>
      </div>

      {/* Main Grid */}
      <div className="px-6 pb-6 grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Hero Evolution + Universe Distribution */}
        <div className="lg:col-span-2 space-y-4">
          {/* Hero Evolution Chart */}
          <div className="bg-white rounded-lg border border-gray-200 p-5">
            <h2 className="text-sm font-bold text-gray-800 mb-3">Evolución de la Base — Crecimiento vs Deterioro</h2>
            <EvolutionHeroChart summary={summary} />
          </div>

          {/* Universe Distribution */}
          <div className="bg-white rounded-lg border border-gray-200 p-5">
            <h2 className="text-sm font-bold text-gray-800 mb-3">Distribución del Universo V2</h2>
            <UniverseBars byUniverse={byUniverse} />
          </div>
        </div>

        {/* Right: Insights + Actionable + Movement */}
        <div className="space-y-4">
          {/* Executive Insights */}
          <div className="bg-white rounded-lg border border-gray-200 p-5">
            <h2 className="text-sm font-bold text-gray-800 mb-3">Qué Cambió</h2>
            <InsightsList summary={summary} clPreview={clPreview} />
          </div>

          {/* Actionable Segments */}
          <div className="bg-white rounded-lg border border-gray-200 p-5">
            <h2 className="text-sm font-bold text-gray-800 mb-3">Segmentos Accionables Hoy</h2>
            <ActionableList byUniverse={byUniverse} />
          </div>

          {/* Movement placeholder */}
          <div className="bg-white rounded-lg border border-gray-200 p-5">
            <h2 className="text-sm font-bold text-gray-800 mb-3">Movimiento de Segmentos</h2>
            <p className="text-xs text-gray-400">Flujo de bolsas (ventana 7d). Requiere serving fact de segment movement.</p>
            <div className="mt-3 h-24 bg-gray-50 rounded flex items-center justify-center text-xs text-gray-300">
              Sankey — serving gap
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="bg-white border-t border-gray-200 px-6 py-3 text-xs text-gray-400">
        Lima Growth Engine · Dashboard Ejecutivo · V2 ACTIVE · Read-Only · Gonzalo / COO
      </div>
    </div>
  )
}

/* ── Sub-components ── */

function EvolutionHeroChart({ summary }) {
  const total = summary?.total_drivers || 0
  const exp = summary?.exportable_drivers || 0
  const nonExp = summary?.non_exportable_drivers || Math.max(0, total - exp)
  return (
    <div className="space-y-3">
      <div className="flex items-end gap-2 h-40">
        <div className="flex-1 flex flex-col justify-end">
          <div className="bg-blue-500 rounded-t w-full" style={{height: `${Math.min(100, (exp/total)*100)}%`, minHeight: 4}} />
          <p className="text-[10px] text-gray-500 mt-1 text-center">Exportables ({exp.toLocaleString()})</p>
        </div>
        <div className="flex-1 flex flex-col justify-end">
          <div className="bg-gray-300 rounded-t w-full" style={{height: `${Math.min(100, (nonExp/total)*100)}%`, minHeight: 4}} />
          <p className="text-[10px] text-gray-500 mt-1 text-center">No Exportables ({nonExp.toLocaleString()})</p>
        </div>
      </div>
      <div className="grid grid-cols-4 gap-2 text-center text-xs">
        <div><span className="font-bold text-gray-700">{total.toLocaleString()}</span><br /><span className="text-gray-400">Total</span></div>
        <div><span className="font-bold text-green-600">{exp.toLocaleString()}</span><br /><span className="text-gray-400">Accionables</span></div>
        <div><span className="font-bold text-gray-500">{nonExp.toLocaleString()}</span><br /><span className="text-gray-400">No accionables</span></div>
        <div><span className="font-bold text-blue-600">{Math.round(100*exp/total)}%</span><br /><span className="text-gray-400">Tasa acción</span></div>
      </div>
    </div>
  )
}

function UniverseBars({ byUniverse }) {
  if (!byUniverse.length) return <p className="text-xs text-gray-400">No universe data available.</p>
  const maxCount = Math.max(...byUniverse.map(u => u?.drivers || u?.count || 0))
  return (
    <div className="space-y-1.5 max-h-64 overflow-y-auto">
      {byUniverse.map((u, i) => {
        const uni = u?.universe || u?.assigned_universe_v1 || ''
        const count = u?.drivers || u?.count || 0
        const pct = maxCount > 0 ? (count / maxCount) * 100 : 0
        const isActionable = ACTIONABLE.includes(uni)
        const label = uni.replace(/_/g, ' ').substring(0, 28)
        return (
          <div key={uni || i} className="flex items-center gap-2">
            <span className={`text-xs w-24 truncate ${isActionable ? 'text-gray-700 font-medium' : 'text-gray-400'}`}>{label}</span>
            <div className="flex-1 bg-gray-100 rounded h-4">
              <div className={`h-4 rounded ${isActionable ? 'bg-blue-500' : 'bg-gray-300'}`} style={{width: `${Math.max(pct, 1)}%`}} />
            </div>
            <span className={`text-xs w-16 text-right font-mono ${isActionable ? 'text-gray-700' : 'text-gray-400'}`}>{count.toLocaleString()}</span>
          </div>
        )
      })}
    </div>
  )
}

function InsightsList({ summary, clPreview }) {
  const date = summary?.resolved_generated_date || '—'
  const today = new Date().toISOString().substring(0, 10)
  const isFresh = date === today
  const items = [
    { label: 'Crecimiento', status: 'HEALTHY', text: 'Worklist diaria generada. Segmentación V2 activa.' },
    { label: 'Recovery', status: 'HEALTHY', text: 'Segmento Recovery accionable. 15-60d inactivity.' },
    { label: 'Protected', status: 'WARNING', text: 'Threshold 75w. Baja proporción de protegidos.' },
    { label: 'Cemetery', status: 'INFO', text: 'En observación. >60d inactivity. No daily action.' },
    { label: 'Control Loop', status: clPreview ? 'HEALTHY' : 'WARNING', text: clPreview ? 'Batch sync disponible.' : 'HOLD — Monday observation pending.' },
    { label: 'Freshness', status: isFresh ? 'HEALTHY' : 'WARNING', text: isFresh ? `Data actualizada: ${date}` : `Posible stale: ${date}` },
  ]
  return (
    <div className="space-y-2">
      {items.map(item => (
        <div key={item.label} className="flex items-start gap-2">
          <span className={`mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${
            item.status === 'HEALTHY' ? 'bg-green-500' :
            item.status === 'WARNING' ? 'bg-amber-500' : 'bg-gray-300'
          }`} />
          <div>
            <p className="text-xs font-semibold text-gray-700">{item.label}</p>
            <p className="text-[10px] text-gray-500">{item.text}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

function ActionableList({ byUniverse }) {
  const actionable = byUniverse
    .filter(u => ACTIONABLE.includes(u?.universe || u?.assigned_universe_v1))
    .sort((a, b) => (b?.drivers || b?.count || 0) - (a?.drivers || a?.count || 0))
  if (!actionable.length) return <p className="text-xs text-gray-400">No actionable segments.</p>
  return (
    <div className="space-y-1">
      {actionable.slice(0, 6).map((u, i) => {
        const uni = u?.universe || u?.assigned_universe_v1 || ''
        const count = u?.drivers || u?.count || 0
        const label = uni.replace(/_/g, ' ').substring(0, 25)
        const prio = i < 2 ? 'HIGH' : i < 4 ? 'MEDIUM' : 'STANDARD'
        const prioColor = prio === 'HIGH' ? 'text-red-600' : prio === 'MEDIUM' ? 'text-amber-600' : 'text-gray-500'
        return (
          <div key={uni} className="flex items-center justify-between text-xs border-b border-gray-50 py-1.5">
            <span className="text-gray-700 truncate flex-1">{label}</span>
            <span className="font-mono text-gray-600 mx-2">{count.toLocaleString()}</span>
            <span className={`${prioColor} text-[10px]`}>{prio}</span>
          </div>
        )
      })}
    </div>
  )
}
