import { useMemo, useState } from 'react'
import { MATRIX_KPIS } from './omniview/omniviewMatrixUtils.js'
import {
  computeProjectionDeltas,
  PROJECTION_KPIS,
  fmtAttainment,
  fmtGap,
  projectionSignalColor,
  SIGNAL_DOT,
} from './omniview/projectionMatrixUtils.js'

/** @deprecated FASE 3.3 — Usar OmniviewPriorityPanel; montaje actualizado en BusinessSliceOmniviewMatrix. */
export default function OmniviewTopDeviations ({ projMatrix, focusedKpi, compact, onCellNavigate }) {
  const [collapsed, setCollapsed] = useState(false)

  const kpiObj = useMemo(
    () => MATRIX_KPIS.find(k => k.key === focusedKpi) || MATRIX_KPIS[0],
    [focusedKpi]
  )

  const { worst, best } = useMemo(() => {
    if (!projMatrix || !PROJECTION_KPIS.includes(focusedKpi)) return { worst: [], best: [] }

    const { cities, allPeriods } = projMatrix
    const lastPk = allPeriods.length > 0 ? allPeriods[allPeriods.length - 1] : null
    if (!lastPk) return { worst: [], best: [] }

    const entries = []

    for (const [cityKey, cityData] of cities) {
      for (const [lineKey, lineData] of cityData.lines) {
        const deltas = computeProjectionDeltas(lineData.periods, allPeriods)
        const periodDeltas = deltas.get(lastPk)
        if (!periodDeltas) continue
        const d = periodDeltas[focusedKpi]
        if (!d || !d.isProjection || d.attainment_pct == null) continue

        entries.push({
          cityKey,
          lineKey,
          city: cityData.city,
          country: cityData.country,
          slice: lineData.business_slice_name,
          attainment: d.attainment_pct,
          gap: d.gap_to_expected,
          signal: d.signal,
          period: lastPk,
          lineData,
          periodDeltas,
          raw: lineData.periods.get(lastPk)?.raw,
        })
      }
    }

    const sorted = [...entries].sort((a, b) => a.attainment - b.attainment)
    return {
      worst: sorted.slice(0, 5),
      best: sorted.slice(-5).reverse(),
    }
  }, [projMatrix, focusedKpi])

  if (worst.length === 0 && best.length === 0) return null

  const py = compact ? 'py-1.5' : 'py-2'
  const fontSize = compact ? 'text-[10px]' : 'text-[11px]'

  const handleClick = (entry) => {
    if (!onCellNavigate) return
    const cellId = `${entry.cityKey}::${entry.lineKey}::${entry.period}::${focusedKpi}`
    onCellNavigate({
      id: cellId,
      cityKey: entry.cityKey,
      lineKey: entry.lineKey,
      period: entry.period,
      kpiKey: focusedKpi,
      lineData: entry.lineData,
      periodDeltas: entry.periodDeltas,
      raw: entry.raw,
    })
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      <button
        type="button"
        onClick={() => setCollapsed(p => !p)}
        className={`w-full px-4 ${py} flex items-center justify-between bg-gray-50/60 hover:bg-gray-100/60 transition-colors`}
      >
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">Top desviaciones</span>
          <span className="text-[10px] text-slate-400">{kpiObj.label}</span>
        </div>
        <span className="text-slate-400 text-[10px]">{collapsed ? '▶' : '▼'}</span>
      </button>

      {!collapsed && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-0 divide-x divide-gray-100">
          <DeviationColumn
            title="Peor desempeño"
            entries={worst}
            focusedKpi={focusedKpi}
            kpiObj={kpiObj}
            compact={compact}
            fontSize={fontSize}
            accent="red"
            onClick={handleClick}
          />
          <DeviationColumn
            title="Mejor desempeño"
            entries={best}
            focusedKpi={focusedKpi}
            kpiObj={kpiObj}
            compact={compact}
            fontSize={fontSize}
            accent="green"
            onClick={handleClick}
          />
        </div>
      )}
    </div>
  )
}

function DeviationColumn ({ title, entries, focusedKpi, kpiObj, compact, fontSize, accent, onClick }) {
  const headerBg = accent === 'red' ? 'bg-red-50/60' : 'bg-emerald-50/60'
  const headerText = accent === 'red' ? 'text-red-700' : 'text-emerald-700'
  const py = compact ? 'py-0.5' : 'py-1'

  return (
    <div>
      <div className={`px-3 py-1.5 ${headerBg}`}>
        <span className={`${fontSize} font-semibold ${headerText} uppercase tracking-wide`}>{title}</span>
      </div>
      {entries.length === 0 ? (
        <div className="px-3 py-3 text-center">
          <span className={`${fontSize} text-gray-400`}>Sin datos</span>
        </div>
      ) : (
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100">
              <th className={`px-2 ${py} text-left ${fontSize} font-medium text-gray-400 uppercase`}>Ciudad</th>
              <th className={`px-2 ${py} text-left ${fontSize} font-medium text-gray-400 uppercase`}>Tajada</th>
              <th className={`px-2 ${py} text-right ${fontSize} font-medium text-gray-400 uppercase`}>Cumpl.</th>
              <th className={`px-2 ${py} text-right ${fontSize} font-medium text-gray-400 uppercase`}>Gap</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry, idx) => {
              const dotClass = SIGNAL_DOT[entry.signal] || SIGNAL_DOT.no_data
              const attColor = projectionSignalColor(entry.signal)
              return (
                <tr
                  key={`${entry.cityKey}-${entry.lineKey}-${idx}`}
                  className="border-b border-gray-50 hover:bg-blue-50/40 cursor-pointer transition-colors"
                  onClick={() => onClick(entry)}
                >
                  <td className={`px-2 ${py} ${fontSize} text-gray-600 whitespace-nowrap`}>{entry.city}</td>
                  <td className={`px-2 ${py} ${fontSize} text-gray-700 font-medium whitespace-nowrap max-w-[120px] overflow-hidden text-ellipsis`} title={entry.slice}>{entry.slice}</td>
                  <td className={`px-2 ${py} ${fontSize} text-right whitespace-nowrap`}>
                    <span className="inline-flex items-center gap-0.5">
                      <span className={`inline-block w-1.5 h-1.5 rounded-full ${dotClass}`} />
                      <span style={{ color: attColor }} className="font-semibold">{fmtAttainment(entry.attainment)}</span>
                    </span>
                  </td>
                  <td className={`px-2 ${py} ${fontSize} text-right text-gray-500 font-medium whitespace-nowrap`}>{fmtGap(entry.gap, focusedKpi)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
