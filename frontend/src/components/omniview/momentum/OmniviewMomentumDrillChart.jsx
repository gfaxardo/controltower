/**
 * OmniviewMomentumDrillChart — Chart de momentum operacional para drill de Omniview.
 * 
 * Muestra series comparables:
 * - Daily: same-weekday (DoD DOM→DOM, LUN→LUN, etc.)
 * - Weekly: week-over-week (WoW)
 * - Monthly: month-over-month (MoM)
 * 
 * Usa el endpoint /ops/business-slice/omniview-momentum-drill.
 * Motor: Control Foundation + Diagnostic Engine Temprano
 */
import { useEffect, useState, useMemo } from 'react'
import { getOmniviewMomentumDrill } from '../../../services/api'
import { MATRIX_KPIS } from '../omniviewMatrixUtils'

const SEVERITY_COLORS = {
  critical: '#dc2626',
  elevated: '#f59e0b',
  warning:  '#fbbf24',
  normal:   '#22c55e',
  unknown:  '#d6d3d0',
}

const SEVERITY_BG = {
  critical: '#fee2e2',
  elevated: '#fef3c7',
  warning:  '#fffbeb',
  normal:   '#f0fdf4',
  unknown:  '#f5f3f0',
}

const COMPARISON_LABELS = {
  same_weekday: 'DoD Same-Weekday',
  week_over_week: 'WoW',
  month_over_month: 'MoM',
  sequential: 'Period-over-Period',
}

export default function OmniviewMomentumDrillChart({
  selection,
  grain = 'daily',
  year,
  weekday = null,
  compact = false,
}) {
  const { lineData, kpiKey: initialKpi, cityKey, lineKey } = selection || {}
  const resolvedCity = cityKey?.split('::')?.[1] || ''
  const resolvedCountry = cityKey?.split('::')?.[0] || ''
  const sliceName = lineData?.business_slice_name

  const [chartKpi, setChartKpi] = useState(initialKpi || 'trips_completed')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    setChartKpi(initialKpi || 'trips_completed')
  }, [initialKpi])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)

    const params = {
      grain,
      metric_code: chartKpi,
      limit: 8,
    }
    if (resolvedCountry) params.country = resolvedCountry
    if (resolvedCity) params.city = resolvedCity
    if (sliceName) params.business_slice = sliceName
    if (year) params.year = year
    if (grain === 'daily' && weekday != null) params.weekday = weekday

    getOmniviewMomentumDrill(params)
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch((err) => {
        if (!cancelled) setError(err?.message || 'Error loading momentum data')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [grain, chartKpi, resolvedCountry, resolvedCity, sliceName, year, weekday])

  const series = data?.series || []
  const comparisonType = data?.comparison_type || ''
  const comparisonLabel = COMPARISON_LABELS[comparisonType] || 'Momentum'

  const W = compact ? 240 : 280
  const H = compact ? 80 : 100
  const padX = 36
  const padY = 12
  const padB = 18

  if (loading) {
    return (
      <div className="px-3 py-2 border-b border-gray-100">
        <ChartHeader chartKpi={chartKpi} setChartKpi={setChartKpi} label={comparisonLabel} />
        <div className="flex items-center justify-center" style={{height: H + padY + padB}}>
          <span className="text-xs text-ct-text3">Loading momentum data...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-3 py-2 border-b border-gray-100">
        <ChartHeader chartKpi={chartKpi} setChartKpi={setChartKpi} label={comparisonLabel} />
        <div className="flex items-center justify-center py-3">
          <span className="text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded border border-amber-200">
            Momentum not available — showing Evolution
          </span>
        </div>
      </div>
    )
  }

  if (series.length < 2) {
    return (
      <div className="px-3 py-2 border-b border-gray-100">
        <ChartHeader chartKpi={chartKpi} setChartKpi={setChartKpi} label={comparisonLabel} />
        <div className="flex items-center justify-center py-3">
          <span className="text-xs text-ct-text3">Insufficient momentum data</span>
        </div>
      </div>
    )
  }

  // Compute chart bounds
  const allValues = series.flatMap(s => [s.value, s.previous_value || s.value])
  const minV = Math.min(...allValues) * 0.9
  const maxV = Math.max(...allValues) * 1.1
  const range = maxV - minV || 1

  const toX = (i) => padX + (i / (series.length - 1)) * (W - padX - 8)
  const toY = (v) => padY + H - ((v - minV) / range) * H

  const fmtShort = (v) => {
    if (v >= 1000000) return `${(v / 1000000).toFixed(1)}M`
    if (v >= 1000) return `${(v / 1000).toFixed(0)}K`
    return v.toFixed(0)
  }

  return (
    <div className={`px-3 py-2 border-b border-gray-100`}>
      <ChartHeader chartKpi={chartKpi} setChartKpi={setChartKpi} label={comparisonLabel} />

      {/* Delta severity strip */}
      <div className="flex flex-wrap gap-1 mb-1.5">
        {series.map((s, i) => {
          const sevColor = SEVERITY_COLORS[s.severity] || SEVERITY_COLORS.unknown
          const sevBg = SEVERITY_BG[s.severity] || SEVERITY_BG.unknown
          return (
            <div key={i} className="flex-1 min-w-[30px] flex flex-col items-center gap-0.5" style={{background: sevBg, borderRadius: 3, padding: '2px 0'}}>
              <span className="text-[9px] font-bold leading-none" style={{color: sevColor}}>
                {s.delta_pct != null ? `${s.delta_pct > 0 ? '+' : ''}${s.delta_pct.toFixed(0)}%` : '—'}
              </span>
              <span className="text-[8px] text-ct-text3 leading-none truncate max-w-full">{s.label}</span>
            </div>
          )
        })}
      </div>

      {/* SVG Chart */}
      <svg width={W} height={H + padY + padB} style={{display: 'block'}}>
        {/* Grid */}
        {[0, 0.25, 0.5, 0.75, 1].map((frac, i) => (
          <line key={i} x1={padX} y1={toY(minV + frac * range)} x2={W - 4} y2={toY(minV + frac * range)}
            stroke="#e5e7eb" strokeWidth={i === 0 ? 0.5 : 0.3} />
        ))}

        {/* Value polyline */}
        <polyline
          points={series.map((s, i) => `${toX(i)},${toY(s.value)}`).join(' ')}
          fill="none" stroke="#3b82f6" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
        />

        {/* Data dots with severity */}
        {series.map((s, i) => {
          const isCritical = s.severity === 'critical' || s.severity === 'elevated'
          const dotColor = isCritical ? '#dc2626' : '#3b82f6'
          const dotR = isCritical ? 3.5 : 2.5
          return (
            <g key={i}>
              <circle cx={toX(i)} cy={toY(s.value)} r={dotR} fill={dotColor} stroke="white" strokeWidth={1} />
              <title>{s.label}: {fmtShort(s.value)} · {s.delta_pct != null ? `${s.delta_pct > 0 ? '+' : ''}${s.delta_pct.toFixed(1)}%` : '—'}</title>
            </g>
          )
        })}

        {/* X-axis labels */}
        {series.map((s, i) => {
          const step = Math.max(1, Math.floor(series.length / 5))
          if (i % step !== 0 && i !== series.length - 1) return null
          return (
            <text key={i} x={toX(i)} y={H + padY + 14} textAnchor="middle"
              fill="#9ca3af" fontSize={compact ? 8 : 9} fontFamily="monospace">
              {s.label.split(' ')[0]}
            </text>
          )
        })}

        {/* Legend */}
        <text x={W - 4} y={padY + 6} textAnchor="end" fill="#3b82f6" fontSize={9} fontWeight={600}>
          ● Value
        </text>
        <text x={W - 4} y={padY + 14} textAnchor="end" fill="#9ca3af" fontSize={8}>
          ● Critical/↑elevated
        </text>
      </svg>
    </div>
  )
}

/** Compact chart header with KPI selector */
function ChartHeader({ chartKpi, setChartKpi, label }) {
  return (
    <div className="flex items-center gap-2 mb-1">
      <span className="text-xs font-semibold text-ct-text">{label}</span>
      <select value={chartKpi} onChange={(e) => setChartKpi(e.target.value)}
        className="text-[11px] border border-gray-200 rounded px-1.5 py-0.5 bg-white text-ct-text outline-none">
        {MATRIX_KPIS.map(k => (
          <option key={k.key} value={k.key}>{k.short || k.label}</option>
        ))}
      </select>
    </div>
  )
}
