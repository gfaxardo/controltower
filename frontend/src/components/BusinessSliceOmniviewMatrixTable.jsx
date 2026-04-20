import { useMemo, useState, memo } from 'react'
import BusinessSliceOmniviewMatrixHeader, { COL1_W, COL2_W, HEADER_H_COMFORTABLE, HEADER_H_COMPACT } from './BusinessSliceOmniviewMatrixHeader.jsx'
import BusinessSliceOmniviewMatrixCell from './BusinessSliceOmniviewMatrixCell.jsx'
import { MATRIX_KPIS, computeDeltas, computeTotalsDeltas, fmtValue, fmtDelta, signalColorForKpi, signalArrow, sortLineEntries, periodLabel as periodLabelFn, trustIssueSummaryForTooltip, trustPeriodCellOverlayClass, resolveCellTrustVisual, resolveTotalsTrustVisual } from './omniview/omniviewMatrixUtils.js'
import {
  computeProjectionDeltas,
  computeProjectionTotalsDeltas,
  fmtAttainment,
  fmtGap,
  fmtGapPct,
  basisSuffix,
  projectionSignalColor,
  SIGNAL_DOT,
  PROJECTION_KPIS,
  countryRank,
} from './omniview/projectionMatrixUtils.js'

export default function BusinessSliceOmniviewMatrixTable ({
  matrix,
  grain,
  compact,
  sortKey,
  onCellClick,
  selectedCell,
  insightCellMap,
  insightMode,
  lineImpactMap,
  periodStates,
  matrixTrust = null,
  focusedKpi = 'trips_completed',
  mode = 'evolution',
}) {
  const isProjection = mode === 'projection'
  const { cities, allPeriods, totals, comparisonTotals, comparisonMeta, cityVolumeMap, lineVolumeMap } = matrix
  const [collapsed, setCollapsed] = useState(new Set())
  const headerH = compact ? HEADER_H_COMPACT : HEADER_H_COMFORTABLE
  const trustLine = useMemo(() => isProjection ? null : trustIssueSummaryForTooltip(matrixTrust), [matrixTrust, isProjection])
  const activeKpi = useMemo(
    () => MATRIX_KPIS.find((kpi) => kpi.key === focusedKpi) || MATRIX_KPIS.find((kpi) => kpi.key === 'trips_completed') || MATRIX_KPIS[0],
    [focusedKpi]
  )

  const cityEntries = useMemo(() => {
    return [...cities.entries()].sort((a, b) => {
      const [aKey, aData] = a
      const [bKey, bData] = b

      if (!isProjection) {
        // Evolución: UNMAPPED al final, luego alfabético
        const aUn = aData.city === 'UNMAPPED' ? 1 : 0
        const bUn = bData.city === 'UNMAPPED' ? 1 : 0
        if (aUn !== bUn) return aUn - bUn
        return aKey.localeCompare(bKey)
      }

      // Proyección: Perú arriba, Colombia abajo; dentro de país por mayor volumen proyectado
      const rankA = countryRank(aData.country)
      const rankB = countryRank(bData.country)
      if (rankA !== rankB) return rankA - rankB
      const volA = cityVolumeMap?.get(aKey) ?? 0
      const volB = cityVolumeMap?.get(bKey) ?? 0
      if (volB !== volA) return volB - volA
      return aKey.localeCompare(bKey)
    })
  }, [cities, isProjection, cityVolumeMap])

  const totalsDeltas = useMemo(
    () => isProjection
      ? computeProjectionTotalsDeltas(totals, allPeriods)
      : computeTotalsDeltas(totals, allPeriods, periodStates, comparisonTotals, comparisonMeta),
    [totals, allPeriods, periodStates, comparisonTotals, comparisonMeta, isProjection]
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
        <p className="text-xs text-gray-500">
          {isProjection
            ? 'Sin datos de proyección para la combinación de filtros seleccionados.'
            : 'Sin datos para la combinación de filtros y grano seleccionados.'}
        </p>
      </div>
    )
  }

  // Proyección usa columnas más anchas para acomodar el formato Proy/Real/Av/Gap
  const colW = isProjection
    ? (compact ? 72 : 90)
    : (compact ? 58 : 66)

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden" data-omniview-matrix-table>
      <div className="overflow-x-auto overflow-y-auto" style={{ maxHeight: 'calc(100vh - 240px)' }}>
        <table className="border-collapse min-w-full" style={{ tableLayout: 'fixed', width: 'auto' }}>
          <colgroup>
            <col style={{ width: COL1_W, minWidth: COL1_W }} />
            <col style={{ width: COL2_W, minWidth: COL2_W }} />
            {allPeriods.map((pk) => (
              <col key={`${pk}-${activeKpi.key}`} style={{ width: colW, minWidth: colW }} />
            ))}
          </colgroup>

          <BusinessSliceOmniviewMatrixHeader allPeriods={allPeriods} grain={grain} compact={compact} periodStates={periodStates} matrixTrust={isProjection ? null : matrixTrust} focusedKpi={activeKpi} />

          <tbody>
            {isProjection
              ? <ProjectionTotalsRow allPeriods={allPeriods} totalsDeltas={totalsDeltas} compact={compact} headerH={headerH} focusedKpi={activeKpi} />
              : <TotalsRow allPeriods={allPeriods} totalsDeltas={totalsDeltas} compact={compact} headerH={headerH} grain={grain} matrixTrust={matrixTrust} trustLine={trustLine} focusedKpi={activeKpi} />
            }

            {cityEntries.map(([cityKey, cityData]) => {
              const isCollapsed = collapsed.has(cityKey)

              // En proyección: ordenar líneas por mayor volumen proyectado (trips)
              let lineEntries
              if (isProjection) {
                lineEntries = [...cityData.lines.entries()].sort((a, b) => {
                  const va = lineVolumeMap?.get(`${cityKey}::${a[0]}`) ?? 0
                  const vb = lineVolumeMap?.get(`${cityKey}::${b[0]}`) ?? 0
                  if (vb !== va) return vb - va
                  return a[1].business_slice_name.localeCompare(b[1].business_slice_name)
                })
              } else {
                lineEntries = sortLineEntries([...cityData.lines.entries()], sortKey, {
                  lineImpactMap,
                  cityKey,
                })
              }

              return (
                <CityBlock
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
                  insightCellMap={isProjection ? null : insightCellMap}
                  insightMode={isProjection ? false : insightMode}
                  periodStates={periodStates}
                  matrixTrust={isProjection ? null : matrixTrust}
                  trustLine={isProjection ? null : trustLine}
                  focusedKpi={activeKpi}
                  mode={mode}
                />
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const TotalsRow = memo(function TotalsRow ({ allPeriods, totalsDeltas, compact, headerH, grain, matrixTrust, trustLine, focusedKpi }) {
  const py = compact ? 'py-px' : 'py-0.5'
  const valSize = compact ? 'text-[10px]' : 'text-[11px]'
  const deltaSize = compact ? 'text-[8px]' : 'text-[9px]'

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
        const periodTrust = resolveTotalsTrustVisual(matrixTrust, grain, pk, focusedKpi.key)
        const trustOv = trustPeriodCellOverlayClass(periodTrust)
        const d = pDeltas?.[focusedKpi.key]
        const bgStyle = zebra ? { backgroundColor: 'rgb(238,240,245)' } : { backgroundColor: 'rgb(243,244,248)' }
        const trustTitle = periodTrust && trustLine ? trustLine : undefined
        if (!d) return <td key={`t-${pk}-${focusedKpi.key}`} className={`px-1 ${py} text-center ${valSize} text-gray-300 border-r border-gray-200/60 ${trustOv}`} style={bgStyle} title={trustTitle}>—</td>
        const val = fmtValue(d.value, focusedKpi.key)
        const dt = fmtDelta(d)
        const color = signalColorForKpi(d.signal, focusedKpi.key)
        const isPC = d.isPartialComparison
        const title = [isPC ? 'Comparativo parcial vs cerrado' : null, trustTitle].filter(Boolean).join(' — ') || undefined
        return (
          <td key={`t-${pk}-${focusedKpi.key}`} className={`px-1 ${py} text-center whitespace-nowrap border-r border-gray-200/60 ${trustOv}`} style={bgStyle}
            title={title}>
            <div className={`${valSize} font-bold text-slate-700 leading-none`}>{val}</div>
            {dt && (
              <div className={`${deltaSize} leading-none font-semibold mt-px`} style={{ color, opacity: isPC ? 0.55 : 1 }}>
                {signalArrow(d.signal)}{dt}{isPC ? '~' : ''}
              </div>
            )}
          </td>
        )
      })}
    </tr>
  )
})

const ProjectionTotalsRow = memo(function ProjectionTotalsRow ({ allPeriods, totalsDeltas, compact, headerH, focusedKpi }) {
  const py = compact ? 'py-0.5' : 'py-1'
  const valSize = compact ? 'text-[9px]' : 'text-[9px]'
  const lblSize = compact ? 'text-[7px]' : 'text-[8px]'
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

        if (!d) return (
          <td key={`t-${pk}-${focusedKpi.key}`} className={`px-1 ${py} text-center ${lblSize} text-gray-300 border-r border-gray-200/60`} style={bgStyle}>—</td>
        )

        if (!isProjectable || !d.isProjection) {
          const val = fmtValue(d.value, focusedKpi.key)
          return (
            <td key={`t-${pk}-${focusedKpi.key}`} className={`px-1 ${py} text-center whitespace-nowrap border-r border-gray-200/60`} style={bgStyle}>
              <div className={`${valSize} font-bold text-slate-700 leading-none`}>{val}</div>
              <div className={`${lblSize} leading-none text-gray-300 mt-px`}>sin plan</div>
            </td>
          )
        }

        const projected    = d.projected_total
        const actual       = d.value
        const att          = d.attainment_pct
        const gap          = d.gap_to_expected
        const gapPct       = d.gap_pct
        const basis        = d.comparison_basis
        const sfx          = basisSuffix(basis)            // '(E)', '(F)', ''
        const hasPlan      = (projected ?? 0) > 0
        const hasReal      = actual != null && actual > 0
        const hasNegActual = actual != null && actual < 0

        const projStr = hasPlan ? fmtValue(projected, focusedKpi.key) : '—'
        const realStr = hasReal
          ? fmtValue(actual, focusedKpi.key)
          : hasNegActual ? fmtValue(actual, focusedKpi.key) : (actual === 0 ? '0' : '—')

        // avance con sufijo base
        const rawAv   = hasPlan ? fmtAttainment(hasReal && !hasNegActual ? att : 0) : '—'
        const avStr   = (rawAv !== '—' && sfx) ? `${rawAv} ${sfx}` : rawAv
        const gapStr  = gap != null ? fmtGap(gap, focusedKpi.key) : null
        const gapPctStr = fmtGapPct(gapPct)

        const signal   = hasNegActual ? 'danger' : (d.signal || 'no_data')
        const dotClass = SIGNAL_DOT[signal] || SIGNAL_DOT.no_data
        const attColor = projectionSignalColor(signal)

        const tooltipParts = [
          `TOTAL · ${focusedKpi.label}`,
          basis ? `Base: ${basis === 'expected_to_date_month' || basis === 'expected_to_date_week' ? 'Expected al corte' : 'Plan período completo'}` : null,
          ``,
          `Plan (mes):    ${projStr}`,
          `Expected${sfx || ''}:  ${hasPlan ? fmtValue(d.projected_expected, focusedKpi.key) : '—'}`,
          `Real:          ${realStr}`,
          ``,
          `Avance ${sfx}:  ${avStr}`,
          gapStr ? `Gap absoluto:  ${gapStr}` : null,
          gapPctStr ? `Gap %:         ${gapPctStr}` : null,
          ``,
          `Nota: Total usa suma(real) / suma(expected), no promedio de %`,
        ].filter(v => v !== null).join('\n')

        return (
          <td key={`t-${pk}-${focusedKpi.key}`}
            className={`px-1 ${py} text-center whitespace-nowrap border-r border-gray-200/60`}
            style={bgStyle}
            title={tooltipParts}
          >
            {/* Proy (expected) */}
            <div className={`${lblSize} text-gray-400 leading-none`}>
              <span className="text-gray-300">↑</span> {projStr}
            </div>
            {/* Real */}
            <div className={`${valSize} font-bold leading-none mt-px ${hasReal ? 'text-slate-700' : hasNegActual ? 'text-red-700' : 'text-gray-400'}`}>
              {realStr}
            </div>
            {/* Avance con sufijo */}
            <div className={`${lblSize} leading-none font-semibold mt-px flex items-center justify-center gap-0.5`}>
              <span className={`inline-block w-1.5 h-1.5 rounded-full ${dotClass} flex-shrink-0`} />
              <span style={{ color: attColor }}>{avStr}</span>
            </div>
            {/* Gap absoluto */}
            {gapStr && (
              <div className={`${lblSize} leading-none mt-px text-gray-400`}>{gapStr}</div>
            )}
          </td>
        )
      })}
    </tr>
  )
})

function CityBlock ({ cityKey, cityData, lineEntries, allPeriods, isCollapsed, onToggle, onCellClick, selectedCell, grain, compact, insightCellMap, insightMode, periodStates, matrixTrust, trustLine, focusedKpi, mode }) {
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
        <LineRow key={lineKey} cityKey={cityKey} cityName={cityData.city} lineKey={lineKey} lineData={lineData}
          allPeriods={allPeriods} onCellClick={onCellClick} selectedCell={selectedCell} grain={grain} compact={compact}
          insightCellMap={insightCellMap} insightMode={insightMode} periodStates={periodStates}
          matrixTrust={matrixTrust} trustLine={trustLine} focusedKpi={focusedKpi} mode={mode} />
      ))}
    </>
  )
}

function LineRow ({ cityKey, cityName, lineKey, lineData, allPeriods, onCellClick, selectedCell, grain, compact, insightCellMap, insightMode, periodStates, matrixTrust, trustLine, focusedKpi, mode }) {
  const isProjection = mode === 'projection'
  const deltas = useMemo(
    () => isProjection
      ? computeProjectionDeltas(lineData.periods, allPeriods)
      : computeDeltas(lineData.periods, allPeriods, periodStates),
    [lineData.periods, allPeriods, periodStates, isProjection]
  )
  const isSubfleet = lineData.is_subfleet
  const py = compact ? 'py-px' : 'py-1'
  const fontSize = compact ? 'text-[11px]' : 'text-xs'

  return (
    <tr className={`border-b border-gray-100/80 ${isSubfleet ? 'bg-gray-50/40' : 'bg-white'} hover:bg-blue-50/40 transition-colors`}>
      <td className={`sticky left-0 z-10 bg-inherit border-r border-gray-100 ${py}`} style={{ width: COL1_W, minWidth: COL1_W }} />
      <td className={`sticky z-10 bg-inherit px-2 ${py} ${fontSize} text-gray-700 font-medium border-r border-gray-200 whitespace-nowrap overflow-hidden text-ellipsis`}
        style={{ left: COL1_W, width: COL2_W, minWidth: COL2_W }}
        title={`${lineData.business_slice_name}${lineData.fleet_display_name && lineData.fleet_display_name !== '—' && lineData.fleet_display_name !== lineData.business_slice_name ? ` · ${lineData.fleet_display_name}` : ''}${isSubfleet ? ` (sub: ${lineData.subfleet_name})` : ''}`}>
        {isSubfleet && <span className="text-gray-400 mr-0.5 text-[10px]">└</span>}
        <span className={isSubfleet ? 'text-gray-500' : 'text-gray-800'}>{lineData.business_slice_name}</span>
        {lineData.fleet_display_name && lineData.fleet_display_name !== '—' && lineData.fleet_display_name !== lineData.business_slice_name && (
          <span className="text-[9px] text-gray-400 ml-1">{lineData.fleet_display_name}</span>
        )}
      </td>

      {allPeriods.map((pk, periodIdx) => {
        const periodDeltas = deltas.get(pk)
        const pLabel = periodLabelFn(pk, grain)
        const pState = isProjection ? null : periodStates?.get(pk)
        const cellId = `${cityKey}::${lineKey}::${pk}::${focusedKpi.key}`
        const delta = periodDeltas ? periodDeltas[focusedKpi.key] : null
        const insightSev = isProjection ? null : (insightCellMap?.get(cellId) || null)
        const ptv = isProjection ? null : resolveCellTrustVisual(matrixTrust, grain, cityName, lineData.business_slice_name, pk, focusedKpi.key)
        return (
          <BusinessSliceOmniviewMatrixCell
            key={cellId} kpiKey={focusedKpi.key} kpi={focusedKpi} delta={delta}
            isSelected={selectedCell === cellId} compact={compact} periodIdx={periodIdx}
            cityName={cityName} lineName={lineData.business_slice_name} periodLbl={pLabel}
            insightSeverity={insightSev} insightMode={isProjection ? false : insightMode} periodState={pState} grain={grain}
            periodTrustVisual={ptv} trustLine={trustLine}
            matrixTrust={matrixTrust}
            periodKey={pk}
            matrixCellId={cellId}
            mode={mode}
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
