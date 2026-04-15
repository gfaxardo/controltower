/**
 * BusinessSliceOmniviewProjectionTable — tabla de proyección que reutiliza
 * la misma estructura visual de Omniview Matrix (header, ciudades, tajadas).
 */
import { useMemo, useState, memo } from 'react'
import BusinessSliceOmniviewMatrixHeader, { COL1_W, COL2_W, HEADER_H_COMFORTABLE, HEADER_H_COMPACT } from './BusinessSliceOmniviewMatrixHeader.jsx'
import BusinessSliceOmniviewProjectionCell from './BusinessSliceOmniviewProjectionCell.jsx'
import {
  MATRIX_KPIS,
  fmtValue,
  sortLineEntries,
  periodLabel as periodLabelFn,
} from './omniview/omniviewMatrixUtils.js'
import {
  computeProjectionDeltas,
  computeProjectionTotalsDeltas,
  fmtAttainment,
  projectionSignalColor,
  SIGNAL_DOT,
  PROJECTION_KPIS,
} from './omniview/projectionMatrixUtils.js'

export default function BusinessSliceOmniviewProjectionTable ({
  matrix,
  grain,
  compact,
  sortKey,
  onCellClick,
  selectedCell,
  periodStates,
  focusedKpi = 'trips_completed',
}) {
  const { cities, allPeriods, totals } = matrix
  const [collapsed, setCollapsed] = useState(new Set())
  const headerH = compact ? HEADER_H_COMPACT : HEADER_H_COMFORTABLE

  const activeKpi = useMemo(
    () => MATRIX_KPIS.find((kpi) => kpi.key === focusedKpi) || MATRIX_KPIS.find((kpi) => kpi.key === 'trips_completed') || MATRIX_KPIS[0],
    [focusedKpi]
  )

  const cityEntries = useMemo(() => {
    return [...cities.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  }, [cities])

  const totalsDeltas = useMemo(
    () => computeProjectionTotalsDeltas(totals, allPeriods),
    [totals, allPeriods]
  )

  const toggleCity = (ck) => {
    setCollapsed((prev) => {
      const next = new Set(prev)
      if (next.has(ck)) next.delete(ck)
      else next.add(ck)
      return next
    })
  }

  if (!allPeriods.length) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 bg-gray-50/80 p-10 text-center">
        <p className="text-xs text-gray-500">Sin datos de proyección para la combinación de filtros seleccionados.</p>
      </div>
    )
  }

  const colW = compact ? 58 : 66

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden" data-omniview-projection-table>
      <div className="overflow-x-auto overflow-y-auto" style={{ maxHeight: 'calc(100vh - 240px)' }}>
        <table className="border-collapse min-w-full" style={{ tableLayout: 'fixed', width: 'auto' }}>
          <colgroup>
            <col style={{ width: COL1_W, minWidth: COL1_W }} />
            <col style={{ width: COL2_W, minWidth: COL2_W }} />
            {allPeriods.map((pk) => (
              <col key={`${pk}-${activeKpi.key}`} style={{ width: colW, minWidth: colW }} />
            ))}
          </colgroup>

          <BusinessSliceOmniviewMatrixHeader allPeriods={allPeriods} grain={grain} compact={compact} periodStates={periodStates} focusedKpi={activeKpi} />

          <tbody>
            <ProjectionTotalsRow allPeriods={allPeriods} totalsDeltas={totalsDeltas} compact={compact} headerH={headerH} focusedKpi={activeKpi} />

            {cityEntries.map(([cityKey, cityData]) => {
              const isCollapsed = collapsed.has(cityKey)
              const lineEntries = sortLineEntries([...cityData.lines.entries()], sortKey, {})

              return (
                <ProjectionCityBlock
                  key={cityKey}
                  cityKey={cityKey}
                  cityData={cityData}
                  lineEntries={lineEntries}
                  allPeriods={allPeriods}
                  isCollapsed={isCollapsed}
                  onToggle={() => toggleCity(cityKey)}
                  onCellClick={onCellClick}
                  selectedCell={selectedCell}
                  grain={grain}
                  compact={compact}
                  focusedKpi={activeKpi}
                />
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const ProjectionTotalsRow = memo(function ProjectionTotalsRow ({ allPeriods, totalsDeltas, compact, headerH, focusedKpi }) {
  const py = compact ? 'py-px' : 'py-0.5'
  const valSize = compact ? 'text-[10px]' : 'text-[11px]'
  const deltaSize = compact ? 'text-[8px]' : 'text-[9px]'
  const isProjectable = PROJECTION_KPIS.includes(focusedKpi.key)

  return (
    <tr
      className="bg-slate-800/[.06] border-b-2 border-slate-300 font-semibold"
      style={{ position: 'sticky', top: headerH, zIndex: 18 }}
    >
      <td className={`sticky left-0 z-10 px-2 ${py} ${valSize} font-bold text-slate-600 uppercase tracking-wide border-r border-slate-200`}
        style={{ backgroundColor: 'rgb(243,244,248)', minWidth: COL1_W }}>Total</td>
      <td className={`sticky z-10 px-2 ${py} border-r border-slate-200`}
        style={{ left: COL1_W, backgroundColor: 'rgb(243,244,248)', minWidth: COL2_W }} />
      {allPeriods.map((pk, periodIdx) => {
        const pDeltas = totalsDeltas.get(pk)
        const zebra = periodIdx % 2 === 1
        const d = pDeltas?.[focusedKpi.key]
        const bgStyle = zebra ? { backgroundColor: 'rgb(238,240,245)' } : { backgroundColor: 'rgb(243,244,248)' }

        if (!d) return <td key={`t-${pk}-${focusedKpi.key}`} className={`px-1 ${py} text-center ${valSize} text-gray-300 border-r border-gray-200/60`} style={bgStyle}>—</td>

        const val = fmtValue(d.value, focusedKpi.key)

        if (!isProjectable || !d.isProjection) {
          return (
            <td key={`t-${pk}-${focusedKpi.key}`} className={`px-1 ${py} text-center whitespace-nowrap border-r border-gray-200/60`} style={bgStyle}>
              <div className={`${valSize} font-bold text-slate-700 leading-none`}>{val}</div>
            </td>
          )
        }

        const att = fmtAttainment(d.attainment_pct)
        const signal = d.signal || 'no_data'
        const dotClass = SIGNAL_DOT[signal] || SIGNAL_DOT.no_data
        const color = projectionSignalColor(signal)

        return (
          <td key={`t-${pk}-${focusedKpi.key}`} className={`px-1 ${py} text-center whitespace-nowrap border-r border-gray-200/60`} style={bgStyle}>
            <div className={`${valSize} font-bold text-slate-700 leading-none`}>{val}</div>
            <div className={`${deltaSize} leading-none font-semibold mt-px flex items-center justify-center gap-0.5`}>
              <span className={`inline-block w-1.5 h-1.5 rounded-full ${dotClass} flex-shrink-0`} />
              <span style={{ color }}>{att}</span>
            </div>
          </td>
        )
      })}
    </tr>
  )
})

function ProjectionCityBlock ({ cityKey, cityData, lineEntries, allPeriods, isCollapsed, onToggle, onCellClick, selectedCell, grain, compact, focusedKpi }) {
  const totalCols = allPeriods.length
  const py = compact ? 'py-1' : 'py-1.5'
  const fontSize = compact ? 'text-[11px]' : 'text-xs'

  return (
    <>
      <tr className="bg-slate-100 hover:bg-slate-200/80 cursor-pointer transition-colors border-t-2 border-slate-300" onClick={onToggle}>
        <td colSpan={2} className={`sticky left-0 z-10 bg-slate-100 px-2 ${py} ${fontSize} font-bold text-slate-700 uppercase tracking-wide select-none`}
          style={{ minWidth: COL1_W + COL2_W }}>
          <span className="inline-block w-3.5 text-center mr-1 text-slate-400 text-[10px]">{isCollapsed ? '▶' : '▼'}</span>
          {cityData.city}
          <span className="ml-1.5 font-normal text-slate-400 normal-case text-[10px]">
            {cityData.country} · {lineEntries.length} línea{lineEntries.length !== 1 ? 's' : ''}
          </span>
        </td>
        <td colSpan={totalCols} className="bg-slate-100" />
      </tr>
      {!isCollapsed && lineEntries.map(([lineKey, lineData]) => (
        <ProjectionLineRow key={lineKey} cityKey={cityKey} cityName={cityData.city} lineKey={lineKey} lineData={lineData}
          allPeriods={allPeriods} onCellClick={onCellClick} selectedCell={selectedCell} grain={grain} compact={compact}
          focusedKpi={focusedKpi} />
      ))}
    </>
  )
}

function ProjectionLineRow ({ cityKey, cityName, lineKey, lineData, allPeriods, onCellClick, selectedCell, grain, compact, focusedKpi }) {
  const deltas = useMemo(() => computeProjectionDeltas(lineData.periods, allPeriods), [lineData.periods, allPeriods])
  const isSubfleet = lineData.is_subfleet
  const py = compact ? 'py-px' : 'py-1'
  const fontSize = compact ? 'text-[11px]' : 'text-xs'

  return (
    <tr className={`border-b border-gray-100/80 ${isSubfleet ? 'bg-gray-50/40' : 'bg-white'} hover:bg-blue-50/40 transition-colors`}>
      <td className={`sticky left-0 z-10 bg-inherit border-r border-gray-100 ${py}`} style={{ width: COL1_W, minWidth: COL1_W }} />
      <td className={`sticky z-10 bg-inherit px-2 ${py} ${fontSize} text-gray-700 font-medium border-r border-gray-200 whitespace-nowrap overflow-hidden text-ellipsis`}
        style={{ left: COL1_W, width: COL2_W, minWidth: COL2_W }}
        title={`${lineData.business_slice_name} · ${lineData.fleet_display_name}${isSubfleet ? ` (sub: ${lineData.subfleet_name})` : ''}`}>
        {isSubfleet && <span className="text-gray-400 mr-0.5 text-[10px]">└</span>}
        <span className={isSubfleet ? 'text-gray-500' : 'text-gray-800'}>{lineData.business_slice_name}</span>
        {lineData.fleet_display_name && lineData.fleet_display_name !== '—' && lineData.fleet_display_name !== lineData.business_slice_name && (
          <span className="text-[9px] text-gray-400 ml-1">{lineData.fleet_display_name}</span>
        )}
      </td>

      {allPeriods.map((pk, periodIdx) => {
        const periodDeltas = deltas.get(pk)
        const pLabel = periodLabelFn(pk, grain)
        const cellId = `${cityKey}::${lineKey}::${pk}::${focusedKpi.key}`
        const delta = periodDeltas ? periodDeltas[focusedKpi.key] : null
        return (
          <BusinessSliceOmniviewProjectionCell
            key={cellId}
            kpiKey={focusedKpi.key}
            kpi={focusedKpi}
            delta={delta}
            isSelected={selectedCell === cellId}
            compact={compact}
            periodIdx={periodIdx}
            cityName={cityName}
            lineName={lineData.business_slice_name}
            periodLbl={pLabel}
            matrixCellId={cellId}
            onClick={() => onCellClick?.({
              id: cellId, cityKey, lineKey, period: pk, kpiKey: focusedKpi.key,
              lineData, periodDeltas, raw: lineData.periods.get(pk)?.raw,
            })}
          />
        )
      })}
    </tr>
  )
}
