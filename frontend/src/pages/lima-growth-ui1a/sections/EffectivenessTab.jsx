import { useEffect, useState } from 'react'
import { getEffectivenessSummary } from '../../../services/api.js'
import { LoadingSpinner, ErrorBlock, SectionHeader, formatNum, formatPct, StatusBadge } from '../components/SharedComponents.jsx'

const PROGRAM_LABELS = {
  RNA_ONBOARDING: 'RNA Onboarding',
  ACTIVE_GROWTH: 'Active Growth',
  TOP_RETENTION: 'Top Retention',
  CHURN_RECOVERY: 'Churn Recovery',
  CHURN_PREVENTION: 'Churn Prevention',
  PROGRAM_14_90: '14/90',
  PROGRAM_ACTIVE_GROWTH: 'Active Growth',
  PROGRAM_CHURN_PREVENTION: 'Churn Prevention',
  PROGRAM_HIGH_VALUE_RECOVERY: 'High Value Recovery',
}

export default function EffectivenessTab() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    getEffectivenessSummary()
      .then(setData)
      .catch((e) => setError(e?.response?.data?.detail || e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner text="Calculando efectividad de programas..." />
  if (error) return <ErrorBlock message={error} onRetry={() => window.location.reload()} />

  const programs = data?.programs || []
  const totalTracked = data?.total_drivers_tracked || 0
  const withOutcome = data?.drivers_with_outcome || 0
  const coveragePct = data?.coverage_pct || 0

  const topPerformers = [...programs]
    .filter((p) => p.net_effect > 0)
    .sort((a, b) => b.net_effect - a.net_effect)
  const worstPerformers = [...programs]
    .filter((p) => p.net_effect < 0)
    .sort((a, b) => a.net_effect - b.net_effect)

  return (
    <div>
      <SectionHeader title="Program Effectiveness" subtitle="Medicion real de impacto de programas" />

      {data?.message ? (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4 text-sm text-yellow-700">
          {data.message}
        </div>
      ) : null}

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div className="bg-white border rounded-lg p-4 text-center">
          <p className="text-xs text-gray-400 uppercase">Programs Measured</p>
          <p className="text-2xl font-bold text-blue-600">{programs.length}</p>
        </div>
        <div className="bg-white border rounded-lg p-4 text-center">
          <p className="text-xs text-gray-400 uppercase">Drivers Tracked</p>
          <p className="text-2xl font-bold text-gray-800">{formatNum(totalTracked)}</p>
        </div>
        <div className="bg-white border rounded-lg p-4 text-center">
          <p className="text-xs text-gray-400 uppercase">With Outcome</p>
          <p className="text-2xl font-bold text-green-600">{formatNum(withOutcome)}</p>
        </div>
        <div className="bg-white border rounded-lg p-4 text-center">
          <p className="text-xs text-gray-400 uppercase">Coverage</p>
          <p className="text-2xl font-bold text-purple-600">{coveragePct}%</p>
        </div>
      </div>

      {/* Data freshness note */}
      <div className="text-xs text-gray-400 mb-4">
        Latest data: {data?.latest_date || 'unknown'} | Data builds daily as pipeline accumulates snapshots.
      </div>

      {/* Top Performers */}
      {topPerformers.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Top Performers</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {topPerformers.map((p) => (
              <div key={p.program_code} className="bg-green-50 border border-green-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-bold text-gray-800">
                    {PROGRAM_LABELS[p.program_code] || p.program_code}
                  </span>
                  <StatusBadge status="HEALTHY" label={`Net: ${p.net_effect.toFixed(1)}`} />
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <span className="text-gray-400">Assigned</span>
                    <p className="font-bold text-gray-700">{formatNum(p.assigned_drivers)}</p>
                  </div>
                  <div>
                    <span className="text-gray-400">Improved</span>
                    <p className="font-bold text-green-600">{formatNum(p.positive_moves)}</p>
                  </div>
                  <div>
                    <span className="text-gray-400">Declined</span>
                    <p className="font-bold text-red-500">{formatNum(p.negative_moves)}</p>
                  </div>
                </div>
                <div className="mt-2 flex gap-3 text-xs">
                  <span className="text-green-600">+{formatPct(p.improvement_rate)} improvement</span>
                  {p.decline_rate > 0 && <span className="text-red-500">{formatPct(p.decline_rate)} decline</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Worst Performers */}
      {worstPerformers.length > 0 && (
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Needs Attention</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {worstPerformers.map((p) => (
              <div key={p.program_code} className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-bold text-gray-800">
                    {PROGRAM_LABELS[p.program_code] || p.program_code}
                  </span>
                  <StatusBadge status="DEGRADED" label={`Net: ${p.net_effect.toFixed(1)}`} />
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs">
                  <div>
                    <span className="text-gray-400">Assigned</span>
                    <p className="font-bold text-gray-700">{formatNum(p.assigned_drivers)}</p>
                  </div>
                  <div>
                    <span className="text-gray-400">Improved</span>
                    <p className="font-bold text-green-600">{formatNum(p.positive_moves)}</p>
                  </div>
                  <div>
                    <span className="text-gray-400">Declined</span>
                    <p className="font-bold text-red-500">{formatNum(p.negative_moves)}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* All Programs Scorecard */}
      {programs.length > 0 && (
        <div className="bg-white border rounded-lg p-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Full Scorecard</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b bg-gray-50 text-gray-500">
                  <th className="text-left py-2 px-2">Program</th>
                  <th className="text-right py-2 px-2">Assigned</th>
                  <th className="text-right py-2 px-2">+Moves</th>
                  <th className="text-right py-2 px-2">-Moves</th>
                  <th className="text-right py-2 px-2">Improv%</th>
                  <th className="text-right py-2 px-2">Decline%</th>
                  <th className="text-right py-2 px-2">Net Effect</th>
                  <th className="text-right py-2 px-2">Score Δ</th>
                </tr>
              </thead>
              <tbody>
                {programs.map((p) => (
                  <tr key={p.program_code} className="border-b last:border-0 hover:bg-gray-50">
                    <td className="py-2 px-2 font-medium text-gray-700">
                      {PROGRAM_LABELS[p.program_code] || p.program_code}
                    </td>
                    <td className="py-2 px-2 text-right text-gray-600">{formatNum(p.assigned_drivers)}</td>
                    <td className="py-2 px-2 text-right text-green-600">{formatNum(p.positive_moves)}</td>
                    <td className="py-2 px-2 text-right text-red-500">{formatNum(p.negative_moves)}</td>
                    <td className="py-2 px-2 text-right text-green-600">{formatPct(p.improvement_rate)}</td>
                    <td className="py-2 px-2 text-right text-red-500">{formatPct(p.decline_rate)}</td>
                    <td className="py-2 px-2 text-right font-bold">
                      <span className={p.net_effect >= 0 ? 'text-green-600' : 'text-red-500'}>
                        {p.net_effect.toFixed(1)}
                      </span>
                    </td>
                    <td className="py-2 px-2 text-right text-gray-600">{formatPct(p.movement_score_delta)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Movement Types */}
      {data?.movement_types?.length > 0 && (
        <div className="bg-white border rounded-lg p-4 mt-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Movement Types Detected</h3>
          <div className="space-y-1.5">
            {data.movement_types.map((m) => (
              <div key={m.type} className="flex justify-between items-center">
                <span className="text-xs text-gray-600">{m.type}</span>
                <span className="text-xs font-medium text-gray-800">{formatNum(m.count)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
