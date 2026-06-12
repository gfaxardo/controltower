import { useEffect, useState } from 'react'
import { LoadingSpinner, ErrorBlock, SectionHeader, formatNum, StatusBadge } from '../components/SharedComponents.jsx'
import api from '../../../services/api.js'

const MOVEMENT_TYPE_LABELS = {
  ENTERED_PROGRAM: 'Entered Program', EXITED_PROGRAM: 'Exited Program',
  STATE_CHANGE: 'State Change', LIFECYCLE_TRANSITION: 'Lifecycle Transition',
  PROGRAM_ASSIGNED: 'Program Assigned', PROGRAM_REMOVED: 'Program Removed',
}

export default function MovementTab({ data, loading, errors, onRetry, onDrilldown }) {
  const summaryLoading = loading.movementSummary
  const recordsLoading = loading.movementRecords
  const movementError = errors.movementSummary || errors.movementRecords
  const summary = data.movementSummary
  const records = data.movementRecords

  const [analytics, setAnalytics] = useState(null)
  const [stats, setStats] = useState(null)
  const [winners, setWinners] = useState(null)
  const [losers, setLosers] = useState(null)

  useEffect(() => {
    api.get('/yego-lima-growth/movement-analytics/matrix', { timeout: 30000 }).then(r => setAnalytics(r.data)).catch(() => {})
    api.get('/yego-lima-growth/movement-analytics/stats', { timeout: 30000 }).then(r => setStats(r.data)).catch(() => {})
    api.get('/yego-lima-growth/movement-analytics/winners?limit=10', { timeout: 30000 }).then(r => setWinners(r.data)).catch(() => {})
    api.get('/yego-lima-growth/movement-analytics/losers?limit=10', { timeout: 30000 }).then(r => setLosers(r.data)).catch(() => {})
  }, [])

  if (movementError && !summary && !records) {
    return <ErrorBlock message={movementError} onRetry={onRetry} />
  }

  if ((summaryLoading || recordsLoading) && !summary && !records) {
    return <LoadingSpinner text="Cargando datos de movimiento..." />
  }

  const entries = stats?.positive_transitions ?? summary?.entries ?? summary?.total_entries ?? 0
  const exits = stats?.negative_transitions ?? summary?.exits ?? summary?.total_exits ?? 0
  const totalTransitions = stats?.total_transitions ?? 0
  const netMovement = stats?.net_movement ?? summary?.movement_score ?? 0
  const movementClasses = stats?.movement_classes || []
  const transitionTypes = summary?.transition_types || summary?.types || []
  const topMovers = records?.records || records?.data || records || []
  const isStale = summary?.stale || false

  const segmentTransitions = analytics?.segment_transitions || []
  const lifecycleTransitions = analytics?.lifecycle_transitions || []
  const topWinners = winners?.top_winners || []
  const topLosers = losers?.top_losers || []

  return (
    <div>
      <SectionHeader title="Movement Dashboard" subtitle="Como se mueve el universo de drivers" />

      {isStale && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-4 text-xs text-yellow-700">
          Datos desactualizados. Ultimo registro: {summary?.last_updated || 'desconocido'}.
        </div>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="bg-white border rounded-lg p-4 text-center">
          <p className="text-xs text-gray-400 uppercase">Total Transitions</p>
          <p className="text-2xl font-bold text-gray-800">{formatNum(totalTransitions)}</p>
        </div>
        <div className="bg-white border rounded-lg p-4 text-center">
          <p className="text-xs text-gray-400 uppercase">Positive</p>
          <p className="text-2xl font-bold text-green-600">{formatNum(entries)}</p>
        </div>
        <div className="bg-white border rounded-lg p-4 text-center">
          <p className="text-xs text-gray-400 uppercase">Negative</p>
          <p className="text-2xl font-bold text-red-600">{formatNum(exits)}</p>
        </div>
        <div className="bg-white border rounded-lg p-4 text-center">
          <p className="text-xs text-gray-400 uppercase">Net Movement</p>
          <p className={`text-2xl font-bold ${netMovement >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {netMovement != null ? netMovement.toFixed(1) : '—'}
          </p>
        </div>
      </div>

      {/* Movement Classes */}
      {movementClasses.length > 0 && (
        <div className="bg-white border rounded-lg p-4 mb-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Movement Classes</h3>
          <div className="flex flex-wrap gap-2">
            {movementClasses.map((mc) => (
              <span key={mc.class} className="px-3 py-1.5 bg-gray-100 rounded-full text-xs text-gray-700">
                {mc.class}: <strong>{formatNum(mc.count)}</strong>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Transition Matrix */}
      {segmentTransitions.length > 0 && (
        <div className="bg-white border rounded-lg p-4 mb-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Transition Matrix</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b bg-gray-50 text-gray-500">
                  <th className="text-left py-2 px-2">From</th>
                  <th className="text-left py-2 px-2">→</th>
                  <th className="text-left py-2 px-2">To</th>
                  <th className="text-right py-2 px-2">Drivers</th>
                  <th className="text-right py-2 px-2">%</th>
                </tr>
              </thead>
              <tbody>
                {segmentTransitions.slice(0, 20).map((t, i) => {
                  const pct = totalTransitions > 0 ? ((t.count / totalTransitions) * 100).toFixed(1) : '—'
                  return (
                    <tr key={i} className="border-b last:border-0 hover:bg-gray-50">
                      <td className="py-2 px-2 text-gray-600">{t.from || '—'}</td>
                      <td className="py-2 px-2 text-gray-400">→</td>
                      <td className="py-2 px-2 font-medium text-gray-700">{t.to || '—'}</td>
                      <td className="py-2 px-2 text-right text-gray-800">{formatNum(t.count)}</td>
                      <td className="py-2 px-2 text-right text-gray-400">{pct}%</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Top Winners */}
      {topWinners.length > 0 && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 mb-4">
          <h3 className="text-sm font-semibold text-green-700 mb-3">Top Winners</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-green-200 text-green-600">
                  <th className="text-left py-2 px-2">Driver</th>
                  <th className="text-left py-2 px-2">From → To</th>
                  <th className="text-left py-2 px-2">Program</th>
                  <th className="text-right py-2 px-2">Score</th>
                </tr>
              </thead>
              <tbody>
                {topWinners.map((w, i) => (
                  <tr key={i} className="border-b border-green-100 last:border-0">
                    <td className="py-2 px-2 font-mono text-green-800">{w.driver_id?.slice(0, 12)}...</td>
                    <td className="py-2 px-2 text-green-700">{w.from_segment} → {w.to_segment}</td>
                    <td className="py-2 px-2 text-green-600">{w.program || '—'}</td>
                    <td className="py-2 px-2 text-right font-bold text-green-700">+{w.score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Top Losers */}
      {topLosers.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
          <h3 className="text-sm font-semibold text-red-700 mb-3">Top Losers</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-red-200 text-red-600">
                  <th className="text-left py-2 px-2">Driver</th>
                  <th className="text-left py-2 px-2">From → To</th>
                  <th className="text-left py-2 px-2">Program</th>
                  <th className="text-right py-2 px-2">Score</th>
                </tr>
              </thead>
              <tbody>
                {topLosers.map((w, i) => (
                  <tr key={i} className="border-b border-red-100 last:border-0">
                    <td className="py-2 px-2 font-mono text-red-800">{w.driver_id?.slice(0, 12)}...</td>
                    <td className="py-2 px-2 text-red-700">{w.from_segment} → {w.to_segment}</td>
                    <td className="py-2 px-2 text-red-600">{w.program || '—'}</td>
                    <td className="py-2 px-2 text-right font-bold text-red-700">{w.score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Transition Types */}
      {transitionTypes.length > 0 && (
        <div className="bg-white border rounded-lg p-4 mb-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Transition Types</h3>
          <div className="space-y-2">
            {transitionTypes.map((t) => {
              const label = MOVEMENT_TYPE_LABELS[t.type] || t.type || 'Unknown'
              const count = t.count || t.total || 0
              const max = Math.max(...transitionTypes.map((x) => x.count || x.total || 0), 1)
              return (
                <div key={t.type || label}>
                  <div className="flex justify-between text-xs text-gray-600 mb-0.5">
                    <span>{label}</span>
                    <span>{formatNum(count)}</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${(count / max) * 100}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Top Movers */}
      <div className="bg-white border rounded-lg p-4 mb-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Movement History</h3>
        {Array.isArray(topMovers) && topMovers.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-gray-500">
                  <th className="text-left py-2 px-2">Driver</th>
                  <th className="text-left py-2 px-2">From → To</th>
                  <th className="text-left py-2 px-2">Type</th>
                  <th className="text-center py-2 px-2"></th>
                </tr>
              </thead>
              <tbody>
                {topMovers.slice(0, 20).map((m, i) => {
                  const driverId = m.driver_id || m.driver_profile_id || m.driver || '—'
                  const from = m.from_state || m.from || '—'
                  const to = m.to_state || m.to || '—'
                  const type = MOVEMENT_TYPE_LABELS[m.transition_type || m.type] || m.transition_type || m.type || '—'
                  return (
                    <tr key={i} className="border-b last:border-0">
                      <td className="py-2 px-2 font-mono text-gray-700">{driverId}</td>
                      <td className="py-2 px-2 text-gray-600">{from} → {to}</td>
                      <td className="py-2 px-2"><StatusBadge status="FRESH" label={type} /></td>
                      <td className="py-2 px-2 text-center">
                        <button onClick={() => onDrilldown && onDrilldown({ driverId })}
                          className="text-blue-500 hover:text-blue-700 text-xs underline">Why?</button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-gray-400">No hay movimientos recientes.</p>
        )}
      </div>

      <details className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <summary className="text-sm font-medium text-blue-700 cursor-pointer">Why this movement?</summary>
        <div className="mt-3 space-y-2 text-xs text-blue-600">
          <p><strong>Movement Score:</strong> −15 to +15 based on segment/lifecycle change severity.</p>
          <p><strong>Segment transitions:</strong> Real operational segment changes (e.g. ACTIVE_GROWTH → TOP_PERFORMER).</p>
          <p><strong>Program changes:</strong> Program assignment transitions between days.</p>
          <p><strong>Source:</strong> growth.driver_movement_fact (built from taxonomy + lifecycle + program snapshots).</p>
        </div>
      </details>
    </div>
  )
}
