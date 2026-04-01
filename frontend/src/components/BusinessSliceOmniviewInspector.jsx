import { useMemo } from 'react'
import { MATRIX_KPIS, fmtValue, fmtRaw, fmtDelta, signalColor, signalArrow, periodLabel } from './omniview/omniviewMatrixUtils.js'

export default function BusinessSliceOmniviewInspector ({ selection, grain, compact, onClose, insightForSelection, insightTransparency }) {
  const w = compact ? 'w-72' : 'w-80'

  if (!selection) {
    return (
      <aside className={`${w} shrink-0 rounded-lg border border-gray-200 bg-white shadow-sm self-start sticky top-2`}>
        <div className="px-4 py-3 border-b border-gray-100">
          <h3 className="text-xs font-bold text-gray-600 uppercase tracking-wide">Inspector</h3>
        </div>
        <div className="p-4">
          <p className="text-[11px] text-gray-400 leading-relaxed">
            Click en una celda de la matriz para inspeccionar KPIs, comparativos y trazabilidad.
          </p>
          <div className="mt-4 flex items-center justify-center">
            <div className="w-12 h-12 rounded-full bg-gray-50 flex items-center justify-center">
              <svg className="w-5 h-5 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
            </div>
          </div>
        </div>
      </aside>
    )
  }

  const { lineData, periodDeltas, period, raw, kpiKey: selectedKpiKey } = selection
  const label = periodLabel(period, grain)
  const padCard = compact ? 'px-2 py-1.5' : 'px-2.5 py-2'
  const ins = insightForSelection

  return (
    <aside className={`${w} shrink-0 rounded-lg border ${ins ? 'border-red-200' : 'border-blue-200'} bg-white shadow-md self-start sticky top-2 overflow-hidden`}>
      <div className="bg-slate-800 text-white px-3 py-2 flex items-center justify-between">
        <div className="min-w-0">
          <div className="text-[11px] font-bold uppercase tracking-wide truncate">{lineData.business_slice_name}</div>
          <div className="text-[10px] text-slate-400 truncate">
            {lineData.fleet_display_name !== '—' && lineData.fleet_display_name}
            {lineData.is_subfleet && ` · Sub: ${lineData.subfleet_name}`}
          </div>
        </div>
        <button type="button" onClick={onClose} className="text-slate-400 hover:text-white text-sm leading-none ml-2 shrink-0" title="Cerrar">×</button>
      </div>

      <div className="px-3 py-1.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-semibold text-slate-400 uppercase tracking-wider">Periodo</span>
          <span className="text-xs font-bold text-slate-800">{label}</span>
        </div>
        {raw?.country && <span className="text-[9px] text-slate-400">{raw.country} · {raw.city}</span>}
      </div>

      {/* ── Insight detected section (additive, only if insight exists) ── */}
      {ins && <InsightBanner insight={ins} transparency={insightTransparency} />}

      <SparklineBar lineData={lineData} kpiKey={selectedKpiKey} />

      <div className={`${compact ? 'p-2 space-y-1' : 'p-3 space-y-1.5'} max-h-[50vh] overflow-y-auto`}>
        {MATRIX_KPIS.map((kpi) => {
          const d = periodDeltas?.[kpi.key]
          const currentVal = d?.value
          const color = d ? signalColor(d.signal) : '#9ca3af'
          const arrow = d ? signalArrow(d.signal) : '—'
          const deltaText = d ? fmtDelta(d) : null
          const isHighlighted = selectedKpiKey === kpi.key

          return (
            <div key={kpi.key} className={`rounded-md border ${padCard} transition-colors ${
              isHighlighted ? 'border-blue-300 bg-blue-50/60 shadow-sm' : 'border-gray-100 bg-gray-50/20 hover:bg-gray-50/50'
            }`}>
              <div className="flex items-center justify-between mb-0.5">
                <span className={`text-[9px] font-semibold uppercase tracking-wide ${isHighlighted ? 'text-blue-600' : 'text-gray-500'}`}>{kpi.label}</span>
                {deltaText && <span className="text-[10px] font-bold" style={{ color }}>{arrow} {deltaText}</span>}
              </div>
              <div className="flex items-baseline justify-between">
                <span className={`${compact ? 'text-base' : 'text-lg'} font-bold text-gray-900 leading-tight`}>{fmtValue(currentVal, kpi.key)}</span>
                {d?.previous != null && <span className="text-[9px] text-gray-400">ant: {fmtRaw(d.previous)}</span>}
              </div>
              {(d?.delta_abs_pp != null || d?.delta_pct != null) && (
                <div className="mt-0.5 flex gap-3 text-[9px] text-gray-400">
                  {d?.delta_abs_pp != null && <span>Δ pp: {d.delta_abs_pp.toFixed(2)}</span>}
                  {d?.delta_pct != null && <span>Δ: {(d.delta_pct * 100).toFixed(1)}%</span>}
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className="px-3 py-2 bg-gray-50 border-t border-gray-200 space-y-0.5">
        <p className="text-[9px] font-bold text-gray-400 uppercase tracking-wide">Trazabilidad</p>
        <MetaRow label="Fuente" value="real_business_slice_month_fact" />
        {raw?.country && <MetaRow label="País" value={raw.country} />}
        {raw?.city && <MetaRow label="Ciudad" value={raw.city} />}
        {raw?.is_subfleet != null && <MetaRow label="Subflota" value={raw.is_subfleet ? 'Sí' : 'No'} />}
        <MetaRow label="Grano" value={grain} />
      </div>
    </aside>
  )
}

// ─── Insight banner in inspector ────────────────────────────────────────────
function InsightBanner ({ insight, transparency }) {
  const isCritical = insight.severity === 'critical'
  const bg = isCritical ? 'bg-red-50' : 'bg-amber-50'
  const border = isCritical ? 'border-red-200' : 'border-amber-200'
  const badgeBg = isCritical ? 'bg-red-600' : 'bg-amber-500'
  const textColor = isCritical ? 'text-red-800' : 'text-amber-800'

  const fmtPct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : null
  const fmtDelta = (s) => {
    if (s.metric === 'cancel_rate_pct' && s.delta_abs_pp != null) return `${(s.delta_abs_pp / 100).toFixed(1)} pp`
    return fmtPct(s.delta_pct) || '—'
  }

  return (
    <div className={`${bg} border-b ${border} px-3 py-2 space-y-1`}>
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className={`${badgeBg} text-white px-1.5 py-px rounded text-[8px] font-bold uppercase`}>
          {insight.severity}
        </span>
        <span className={`text-[10px] font-bold ${textColor}`}>Insight detectado</span>
        {insight.groupedCount > 1 && (
          <span className="text-[8px] text-gray-500 bg-white/70 px-1 rounded border border-gray-200">
            {insight.groupedCount} señales agrupadas
          </span>
        )}
      </div>

      <div className={`text-[11px] font-semibold ${textColor} leading-tight`}>
        {insight.metricLabel}: {fmtPct(insight.delta_pct) || (insight.delta_abs_pp != null ? `${(insight.delta_abs_pp / 100).toFixed(1)} pp` : '—')}
      </div>

      {(insight.secondarySignals || []).length > 0 && (
        <ul className="text-[9px] text-gray-600 space-y-0.5 pl-2 list-disc">
          {(insight.secondarySignals || []).map((s) => (
            <li key={s.metric}>
              <span className="font-medium">{s.metricLabel}</span> ({s.severity}): {fmtDelta(s)}
            </li>
          ))}
        </ul>
      )}

      <div className="text-[10px] text-gray-600 leading-tight">
        <span className="font-medium">Causa (heurística):</span> {insight.explanation.cause}
      </div>

      <div className="text-[10px] text-gray-600 leading-tight">
        <span className="font-medium">Acción sugerida:</span> {insight.action.action}
      </div>

      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[9px] text-gray-400 mt-0.5">
        {insight.explanation.drivers_delta_pct != null && (
          <span>Conductores: {fmtPct(insight.explanation.drivers_delta_pct)}</span>
        )}
        {insight.explanation.trips_delta_pct != null && (
          <span>Viajes: {fmtPct(insight.explanation.trips_delta_pct)}</span>
        )}
        {insight.explanation.ticket_delta_pct != null && (
          <span>Ticket: {fmtPct(insight.explanation.ticket_delta_pct)}</span>
        )}
      </div>

      {transparency?.disclaimer && (
        <p className="text-[8px] text-gray-400 leading-snug border-t border-gray-200/60 pt-1 mt-1 italic">
          {transparency.disclaimer}
        </p>
      )}
    </div>
  )
}

function SparklineBar ({ lineData, kpiKey }) {
  const values = useMemo(() => {
    if (!lineData?.periods) return []
    const vals = []
    for (const pk of [...lineData.periods.keys()].sort()) {
      const v = lineData.periods.get(pk)?.metrics?.[kpiKey]
      vals.push(v != null ? Number(v) : null)
    }
    return vals
  }, [lineData, kpiKey])

  const valid = values.filter((v) => v != null)
  if (valid.length < 2) return null
  const max = Math.max(...valid), min = Math.min(...valid), range = max - min || 1
  const w = 200, h = 28, padY = 3
  const points = values.map((v, i) => {
    if (v == null) return null
    const x = values.length === 1 ? w / 2 : (i / (values.length - 1)) * w
    const y = padY + (h - 2 * padY) - ((v - min) / range) * (h - 2 * padY)
    return [x, y]
  }).filter(Boolean)
  const polyline = points.map((p) => p.join(',')).join(' ')
  const last = points[points.length - 1]

  return (
    <div className="px-3 py-1.5 border-b border-gray-100 flex items-center gap-2">
      <span className="text-[9px] text-gray-400 uppercase tracking-wider shrink-0">Tendencia</span>
      <svg width={w} height={h} className="flex-1" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
        <polyline points={polyline} fill="none" stroke="#3b82f6" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
        {last && <circle cx={last[0]} cy={last[1]} r={2.5} fill="#3b82f6" />}
      </svg>
    </div>
  )
}

function MetaRow ({ label, value }) {
  return (
    <div className="flex justify-between text-[9px]">
      <span className="text-gray-400">{label}</span>
      <span className="text-gray-600 font-mono truncate max-w-[140px]" title={String(value)}>{String(value)}</span>
    </div>
  )
}
