import { useMemo, useState } from 'react'
import { MATRIX_KPIS } from './omniview/omniviewMatrixUtils.js'
import {
  PROJECTION_KPIS,
  fmtAttainment,
  fmtGap,
  projectionSignalColor,
  SIGNAL_DOT,
} from './omniview/projectionMatrixUtils.js'
import { computeAlertsForMatrix } from './omniview/alertingEngine.js'

const BAND_BADGE = {
  CRITICAL: 'bg-red-100 text-red-800 border-red-200',
  HIGH: 'bg-orange-100 text-orange-900 border-orange-200',
  MEDIUM: 'bg-amber-100 text-amber-900 border-amber-200',
  LOW: 'bg-slate-100 text-slate-700 border-slate-200',
  WATCH: 'bg-emerald-100 text-emerald-800 border-emerald-200',
}

export default function OmniviewPriorityPanel ({ projMatrix, focusedKpi, grain, compact, onCellNavigate }) {
  const [collapsed, setCollapsed] = useState(false)

  const kpiObj = useMemo(
    () => MATRIX_KPIS.find(k => k.key === focusedKpi) || MATRIX_KPIS[0],
    [focusedKpi]
  )

  const { underperforming, watch } = useMemo(
    () => computeAlertsForMatrix(projMatrix, focusedKpi, grain || 'monthly'),
    [projMatrix, focusedKpi, grain]
  )

  if (!PROJECTION_KPIS.includes(focusedKpi)) return null
  if (underperforming.length === 0 && watch.length === 0) return null

  const py = compact ? 'py-1.5' : 'py-2'
  const fontSize = compact ? 'text-[10px]' : 'text-[11px]'

  const handleClick = (alert) => {
    if (!onCellNavigate || !alert.navigation) return
    const nav = alert.navigation
    const cellId = `${nav.cityKey}::${nav.lineKey}::${nav.period}::${focusedKpi}`
    onCellNavigate({
      id: cellId,
      cityKey: nav.cityKey,
      lineKey: nav.lineKey,
      period: nav.period,
      kpiKey: focusedKpi,
      lineData: nav.lineData,
      periodDeltas: nav.periodDeltas,
      raw: nav.raw,
    })
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      <button
        type="button"
        onClick={() => setCollapsed(p => !p)}
        className={`w-full px-4 ${py} flex items-center justify-between bg-slate-50/60 hover:bg-slate-100/60 transition-colors`}
      >
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-slate-600 uppercase tracking-wider">Prioridades del periodo</span>
          <span className="text-[10px] text-slate-400">{kpiObj.label}</span>
        </div>
        <span className="text-slate-400 text-[10px]">{collapsed ? '▶' : '▼'}</span>
      </button>

      {!collapsed && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-0 divide-x divide-gray-100">
          <PriorityColumn
            title="Top prioridad (atender)"
            subtitle="Orden por score · no solo %"
            alerts={underperforming}
            focusedKpi={focusedKpi}
            fontSize={fontSize}
            accent="red"
            onClick={handleClick}
            compact={!!compact}
          />
          <PriorityColumn
            title="Watch (sobrecumplimiento)"
            subtitle="Seguimiento"
            alerts={watch}
            focusedKpi={focusedKpi}
            fontSize={fontSize}
            accent="green"
            onClick={handleClick}
            compact={!!compact}
            watchMode
          />
        </div>
      )}
    </div>
  )
}

function PriorityColumn ({
  title,
  subtitle,
  alerts,
  focusedKpi,
  fontSize,
  accent,
  onClick,
  watchMode = false,
  compact = false,
}) {
  const headerBg = accent === 'red' ? 'bg-red-50/50' : 'bg-emerald-50/50'
  const headerText = accent === 'red' ? 'text-red-800' : 'text-emerald-800'
  const py = compact ? 'py-0.5' : 'py-1'

  return (
    <div>
      <div className={`px-3 py-1.5 ${headerBg}`}>
        <span className={`${fontSize} font-semibold ${headerText} uppercase tracking-wide`}>{title}</span>
        <div className="text-[9px] text-gray-400 font-normal normal-case">{subtitle}</div>
      </div>
      {alerts.length === 0 ? (
        <div className="px-3 py-3 text-center">
          <span className={`${fontSize} text-gray-400`}>Sin entradas</span>
        </div>
      ) : (
        <table className="w-full table-fixed">
          <thead>
            <tr className="border-b border-gray-100">
              <th className={`px-1 ${py} text-left ${fontSize} font-medium text-gray-400 uppercase`}>Ciudad</th>
              <th className={`px-1 ${py} text-left ${fontSize} font-medium text-gray-400 uppercase truncate`}>Tajada</th>
              <th className={`px-1 ${py} text-center ${fontSize} font-medium text-gray-400 uppercase`}>Band</th>
              {!watchMode && (
                <th className={`px-1 ${py} text-right ${fontSize} font-medium text-gray-400 uppercase`}>Score</th>
              )}
              <th className={`px-1 ${py} text-right ${fontSize} font-medium text-gray-400 uppercase`}>Cumpl.</th>
              <th className={`px-1 ${py} text-right ${fontSize} font-medium text-gray-400 uppercase`}>Gap</th>
              <th className={`px-1 ${py} text-left ${fontSize} font-medium text-gray-400 uppercase`}>Driver</th>
              <th className={`px-1 ${py} text-left ${fontSize} font-medium text-gray-400 uppercase truncate`}>Acción</th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((a, idx) => {
              const sig = a.signal || 'no_data'
              const dotClass = SIGNAL_DOT[sig] || SIGNAL_DOT.no_data
              const attColor = projectionSignalColor(
                a.priority_band === 'WATCH' ? 'green' : sig
              )
              const bandCls = BAND_BADGE[a.priority_band] || BAND_BADGE.LOW
              const mainLbl = a.main_driver?.label || '—'
              const actionShort = (a.suggested_action_text || '').length > 42
                ? `${(a.suggested_action_text || '').slice(0, 40)}…`
                : (a.suggested_action_text || '—')

              return (
                <tr
                  key={`${a.city_key}-${a.line_key}-${idx}`}
                  className="border-b border-gray-50 hover:bg-blue-50/40 cursor-pointer transition-colors"
                  onClick={() => onClick(a)}
                  title={a.suggested_action_text || undefined}
                >
                  <td className={`px-1 ${py} ${fontSize} text-gray-600 whitespace-nowrap`}>{a.city}</td>
                  <td className={`px-1 ${py} ${fontSize} text-gray-700 font-medium truncate max-w-[100px]`} title={a.slice}>
                    {a.slice}
                  </td>
                  <td className={`px-1 ${py} text-center`}>
                    <span className={`inline-block px-1 py-px rounded text-[8px] font-bold border ${bandCls}`}>
                      {a.priority_band}
                    </span>
                  </td>
                  {!watchMode && (
                    <td className={`px-1 ${py} ${fontSize} text-right text-gray-700 font-mono tabular-nums`}>
                      <span className="inline-flex items-center justify-end gap-0.5">
                        {a.priority_score != null ? a.priority_score.toFixed(0) : '—'}
                        {a.projection_confidence === 'low' && (
                          <span className="text-[7px] font-bold text-amber-700 border border-amber-300 rounded px-0.5" title="Baja confianza de proyección">
                            Baja conf.
                          </span>
                        )}
                      </span>
                    </td>
                  )}
                  <td className={`px-1 ${py} ${fontSize} text-right whitespace-nowrap`}>
                    <span className="inline-flex items-center gap-0.5 justify-end">
                      <span className={`inline-block w-1 h-1 rounded-full ${dotClass}`} />
                      <span style={{ color: attColor }} className="font-semibold">{fmtAttainment(a.attainment_pct)}</span>
                    </span>
                  </td>
                  <td className={`px-1 ${py} ${fontSize} text-right text-gray-500 whitespace-nowrap`}>
                    {fmtGap(a.gap_total, focusedKpi)}
                  </td>
                  <td className={`px-1 ${py} ${fontSize} text-gray-600 truncate max-w-[90px]`} title={mainLbl}>
                    {mainLbl}
                  </td>
                  <td className={`px-1 ${py} ${fontSize} text-gray-600 truncate`} title={a.suggested_action_text}>
                    {actionShort}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
