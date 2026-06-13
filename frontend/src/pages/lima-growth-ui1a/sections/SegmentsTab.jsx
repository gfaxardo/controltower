import { LoadingSpinner, ErrorBlock, SectionHeader, formatNum, formatPct } from '../components/SharedComponents.jsx'

const LIFECYCLE_LABELS = {
  ACTIVE: 'Active',
  NEW_ACTIVE: 'New Active',
  AT_RISK: 'At Risk',
  DECLINING: 'Declining',
  CHURNED: 'Churned',
  INACTIVE: 'Inactive',
  STABLE: 'Stable',
  GROWING: 'Growing',
}

const LIFECYCLE_COLORS = {
  ACTIVE: 'bg-green-500',
  NEW_ACTIVE: 'bg-blue-500',
  AT_RISK: 'bg-yellow-500',
  DECLINING: 'bg-orange-500',
  CHURNED: 'bg-red-500',
  INACTIVE: 'bg-gray-400',
  STABLE: 'bg-teal-500',
  GROWING: 'bg-emerald-500',
}

export default function SegmentsTab({ data, loading, errors, onRetry, onDrilldown }) {
  const taxonomyLoading = loading.taxonomy
  const taxonomyError = errors.taxonomy
  const taxonomy = data.taxonomy

  if (taxonomyError && !taxonomy) {
    return <ErrorBlock message={taxonomyError} onRetry={onRetry} />
  }

  if (taxonomyLoading && !taxonomy) {
    return <LoadingSpinner text="Cargando segmentos..." />
  }

  const dist = taxonomy?.distributions
  const lifecycleDistribution = (dist?.operational_status || []).map(item => ({
    lifecycle: item.operational_status,
    status: item.operational_status,
    count: item.cnt || item.count || 0,
  }))
  const segments = (dist?.operational_segment || []).map(item => ({
    segment: item.operational_segment,
    label: item.operational_segment,
    count: item.cnt || item.count || 0,
  }))
  const valueTiers = (dist?.value_overlay || []).map(item => ({
    tier: item.value_overlay,
    label: item.value_overlay,
    count: item.cnt || item.count || 0,
  }))
  const momentum = (dist?.momentum || []).map(item => ({
    direction: item.momentum_state,
    label: item.momentum_state,
    count: item.cnt || item.count || 0,
  }))
  const total = lifecycleDistribution.reduce((acc, s) => acc + (s.count || s.drivers || 0), 0)

  return (
    <div>
      <SectionHeader title="Segments" subtitle="Distribución de drivers por ciclo de vida, actividad, valor y momentum" />

      {/* Lifecycle Distribution */}
      <div className="bg-white border rounded-lg p-4 mb-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Lifecycle Distribution</h3>
        {lifecycleDistribution.length > 0 ? (
          <div className="space-y-2">
            {lifecycleDistribution.map((item) => {
              const count = item.count || item.drivers || 0
              const pct = total > 0 ? (count / total) * 100 : 0
              const label = LIFECYCLE_LABELS[item.lifecycle || item.status] || item.lifecycle || item.status || 'Unknown'
              const color = LIFECYCLE_COLORS[item.lifecycle || item.status] || 'bg-gray-400'
              return (
                <div key={label}>
                  <div className="flex justify-between text-xs text-gray-600 mb-0.5">
                    <span>{label}</span>
                    <span>{formatNum(count)} ({pct.toFixed(1)}%)</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2.5">
                    <div className={`${color} h-2.5 rounded-full`} style={{ width: `${Math.min(pct, 100)}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <p className="text-xs text-gray-400">No hay datos de distribución de lifecycle.</p>
        )}
      </div>

      {/* Value Tiers */}
      {valueTiers.length > 0 && (
        <div className="bg-white border rounded-lg p-4 mb-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Value Tiers</h3>
          <div className="grid grid-cols-3 gap-3">
            {valueTiers.map((tier) => (
              <div key={tier.tier || tier.label} className="text-center border rounded p-3">
                <p className="text-xs text-gray-400">{tier.tier || tier.label || 'Unknown'}</p>
                <p className="text-lg font-bold text-gray-800">{formatNum(tier.count || tier.drivers || 0)}</p>
                {tier.pct != null && <p className="text-xs text-gray-400">{formatPct(tier.pct)}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Segments Table */}
      {segments.length > 0 && (
        <div className="bg-white border rounded-lg p-4 mb-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Segment Details</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-gray-500">
                  <th className="text-left py-2 px-2">Segment</th>
                  <th className="text-right py-2 px-2">Drivers</th>
                  <th className="text-right py-2 px-2">%</th>
                  <th className="text-center py-2 px-2"></th>
                </tr>
              </thead>
              <tbody>
                {segments.map((s) => {
                  const count = s.count || s.drivers || 0
                  const pct = total > 0 ? ((count / total) * 100).toFixed(1) : '—'
                  const segmentName = s.segment || s.label || s.name || 'Unknown'
                  return (
                    <tr key={segmentName} className="border-b last:border-0">
                      <td className="py-2 px-2 font-medium text-gray-700">{segmentName}</td>
                      <td className="py-2 px-2 text-right text-gray-600">{formatNum(count)}</td>
                      <td className="py-2 px-2 text-right text-gray-400">{pct}%</td>
                      <td className="py-2 px-2 text-center">
                        <button
                          onClick={() => onDrilldown && onDrilldown({ segment: segmentName })}
                          className="text-blue-500 hover:text-blue-700 text-xs underline"
                        >
                          Drivers →
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Momentum */}
      {momentum.length > 0 && (
        <div className="bg-white border rounded-lg p-4 mb-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Momentum</h3>
          <div className="grid grid-cols-3 gap-3">
            {momentum.map((m) => (
              <div key={m.direction || m.label} className="text-center border rounded p-3">
                <p className="text-xs text-gray-400">{m.direction || m.label || 'Unknown'}</p>
                <p className="text-lg font-bold text-gray-800">{formatNum(m.count || m.drivers || 0)}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {!taxonomy && (
        <div className="bg-gray-50 border rounded-lg p-6 text-center text-sm text-gray-500">
          No hay datos de segmentos disponibles.
        </div>
      )}

      <details className="bg-purple-50 border border-purple-200 rounded-lg p-4 mt-4">
        <summary className="text-sm font-medium text-purple-700 cursor-pointer">Why these segments?</summary>
        <div className="mt-3 space-y-2 text-xs text-purple-600">
          <p><strong>Lifecycle:</strong> Based on trip recency and frequency patterns. ACTIVE = trips in last 7d, NEW_ACTIVE = first trip in 30d, AT_RISK = declining trip pattern, DECLINING = no trips 14d+, CHURNED = no trips 30d+.</p>
          <p><strong>Value Tiers:</strong> Percentile-based ranking of driver earnings. Top 20% are highest-value drivers by revenue.</p>
          <p><strong>Momentum:</strong> 4-week trip trend: rising (+20% trips), stable (±20%), falling (-20%).</p>
          <p><strong>Source:</strong> growth.yego_lima_driver_taxonomy_v2_daily (matched_rules + failed_rules per layer).</p>
        </div>
      </details>
    </div>
  )
}
