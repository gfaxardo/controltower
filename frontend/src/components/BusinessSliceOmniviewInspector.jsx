import { MATRIX_KPIS, fmtValue, fmtDelta, signalColor, signalArrow, periodLabel } from './omniview/omniviewMatrixUtils.js'

export default function BusinessSliceOmniviewInspector ({ selection, grain, compact, onClose }) {
  const w = compact ? 'w-72' : 'w-80'

  if (!selection) {
    return (
      <aside className={`${w} shrink-0 rounded-lg border border-gray-200 bg-white shadow-sm p-4 self-start sticky top-2`}>
        <h3 className="text-xs font-bold text-gray-600 uppercase tracking-wide mb-2">Inspector</h3>
        <p className="text-[11px] text-gray-400 leading-relaxed">
          Click en una celda de la matriz para ver detalle completo con comparativos, señales y trazabilidad.
        </p>
        <div className="mt-4 flex items-center justify-center">
          <div className="w-12 h-12 rounded-full bg-gray-100 flex items-center justify-center">
            <svg className="w-6 h-6 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h12A2.25 2.25 0 0020.25 14.25V3m-16.5 0h16.5m-16.5 0L12 13.5 20.25 3" />
            </svg>
          </div>
        </div>
      </aside>
    )
  }

  const { lineData, periodDeltas, period, raw } = selection
  const label = periodLabel(period, grain)
  const cardPad = compact ? 'p-2' : 'p-2.5'

  return (
    <aside className={`${w} shrink-0 rounded-lg border border-blue-200 bg-white shadow-md self-start sticky top-2 overflow-hidden`}>
      <div className="bg-slate-800 text-white px-3 py-2 flex items-center justify-between">
        <div className="min-w-0">
          <div className="text-[11px] font-bold uppercase tracking-wide truncate">{lineData.business_slice_name}</div>
          <div className="text-[10px] text-slate-400 truncate">
            {lineData.fleet_display_name !== '—' && lineData.fleet_display_name}
            {lineData.is_subfleet && ` · Sub: ${lineData.subfleet_name}`}
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-slate-400 hover:text-white text-sm leading-none ml-2 shrink-0"
          title="Cerrar"
        >
          ×
        </button>
      </div>

      <div className="px-3 py-1.5 bg-slate-50 border-b border-slate-200 flex items-center gap-2">
        <span className="text-[9px] font-semibold text-slate-400 uppercase tracking-wider">Periodo</span>
        <span className="text-xs font-bold text-slate-800">{label}</span>
      </div>

      <div className={`${compact ? 'p-2 space-y-1' : 'p-3 space-y-1.5'} max-h-[55vh] overflow-y-auto`}>
        {MATRIX_KPIS.map((kpi) => {
          const d = periodDeltas?.[kpi.key]
          const currentVal = d?.value
          const color = d ? signalColor(d.signal) : '#9ca3af'
          const arrow = d ? signalArrow(d.signal) : '—'
          const deltaText = d ? fmtDelta(d) : null

          return (
            <div
              key={kpi.key}
              className={`rounded-md border ${cardPad} transition-colors ${
                selection.kpiKey === kpi.key
                  ? 'border-blue-300 bg-blue-50/60'
                  : 'border-gray-100 bg-gray-50/20'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-[9px] font-semibold text-gray-500 uppercase tracking-wide">{kpi.label}</span>
                {deltaText && (
                  <span className="text-[10px] font-bold" style={{ color }}>
                    {arrow} {deltaText}
                  </span>
                )}
              </div>
              <div className={`${compact ? 'text-base' : 'text-lg'} font-bold text-gray-900 leading-tight`}>
                {fmtValue(currentVal, kpi.key)}
              </div>
              {(d?.delta_abs != null || d?.delta_abs_pp != null || d?.delta_pct != null) && (
                <div className="mt-0.5 flex gap-3 text-[9px] text-gray-400">
                  {d?.delta_abs != null && (
                    <span>Δ abs: {d.delta_abs.toFixed(kpi.showAsPct ? 4 : 1)}</span>
                  )}
                  {d?.delta_abs_pp != null && (
                    <span>Δ pp: {d.delta_abs_pp.toFixed(2)}</span>
                  )}
                  {d?.delta_pct != null && (
                    <span>Δ %: {(d.delta_pct * 100).toFixed(1)}%</span>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className="px-3 py-2 bg-gray-50 border-t border-gray-200 space-y-0.5">
        <p className="text-[9px] font-bold text-gray-400 uppercase tracking-wide">Trazabilidad</p>
        <MetaRow label="Fuente" value="ops.real_business_slice_month_fact" />
        {raw?.country && <MetaRow label="País" value={raw.country} />}
        {raw?.city && <MetaRow label="Ciudad" value={raw.city} />}
        {raw?.is_subfleet != null && <MetaRow label="Subflota" value={raw.is_subfleet ? 'Sí' : 'No'} />}
        <MetaRow label="Grain" value={grain} />
      </div>
    </aside>
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
