/**
 * Matriz jerárquica expandible: país → ciudad → tajada → flota.
 * Hojas usan señales backend; país usa subtotales API; ciudad/tajada solo sumas aditivas (trips/revenue).
 */
import { Fragment, useMemo } from 'react'
import {
  buildOmniviewTree,
  findSubtotalForCountry,
  formatDeltaLine,
  formatMetricValue,
  signalArrow,
  signalColor,
  sumAdditiveFromLeaves
} from './omniview/omniviewUtils.js'

const CORE_KEYS = ['trips_completed', 'revenue_yego_net', 'active_drivers', 'trips_per_driver', 'cancel_rate_pct', 'commission_pct']
const EXTRA_KEYS = ['avg_ticket', 'trips_cancelled']

function pathCountry (country) {
  return `c|${String(country)}`
}
function pathCity (country, city) {
  return `${pathCountry(country)}|ci|${String(city)}`
}
function pathSlice (country, city, slice) {
  return `${pathCity(country, city)}|sl|${String(slice)}`
}

function LeafMetricCell ({ row, metricKey, unitsMeta }) {
  const cur = row.current?.[metricKey]
  const d = row.delta?.[metricKey]
  const sig = row.signals?.[metricKey]?.signal || 'no_data'
  const dir = row.signals?.[metricKey]?.direction || 'neutral'
  const line = formatDeltaLine(metricKey, d, unitsMeta)
  const color = signalColor(sig)
  return (
    <td className="px-2 py-2 text-right align-top border-b border-slate-100">
      <div className="font-medium text-slate-900 tabular-nums">{formatMetricValue(metricKey, cur, unitsMeta)}</div>
      {line
        ? (
          <div className="text-xs flex justify-end items-center gap-1 mt-0.5 tabular-nums" style={{ color }}>
            <span aria-hidden>{signalArrow(sig, dir)}</span>
            <span>{line}</span>
          </div>
          )
        : (
          <div className="text-xs text-slate-400 mt-0.5">—</div>
          )}
    </td>
  )
}

function SubtotalMetricCell ({ st, metricKey, unitsMeta }) {
  if (!st?.current) {
    return <td className="px-2 py-2 text-right text-slate-400 border-b border-slate-100">—</td>
  }
  const cur = st.current[metricKey]
  const d = st.delta?.[metricKey]
  const sig = st.signals?.[metricKey]?.signal || 'no_data'
  const dir = st.signals?.[metricKey]?.direction || 'neutral'
  const line = formatDeltaLine(metricKey, d, unitsMeta)
  const color = signalColor(sig)
  return (
    <td className="px-2 py-2 text-right align-top border-b border-slate-100 bg-slate-50/80">
      <div className="font-semibold text-slate-900 tabular-nums">{formatMetricValue(metricKey, cur, unitsMeta)}</div>
      {line
        ? (
          <div className="text-xs flex justify-end gap-1 mt-0.5 tabular-nums" style={{ color }}>
            <span aria-hidden>{signalArrow(sig, dir)}</span>
            <span>{line}</span>
          </div>
          )
        : <div className="text-xs text-slate-400 mt-0.5">—</div>}
    </td>
  )
}

/** Solo suma directa de hojas; sin señal fuerte (texto neutro). */
function AggregateMetricCell ({ leaves, metricKey, unitsMeta, additive }) {
  if (!additive) {
    return <td className="px-2 py-2 text-right text-slate-400 border-b border-slate-100">—</td>
  }
  const c = sumAdditiveFromLeaves(leaves, metricKey)
  let p = 0
  for (const { row } of leaves) {
    const v = row?.previous?.[metricKey]
    if (v != null && !Number.isNaN(Number(v))) p += Number(v)
  }
  const line = p !== 0
    ? `${((c - p) / p) * 100 > 0 ? '+' : ''}${(((c - p) / p) * 100).toFixed(1)}%`
    : c !== 0
      ? 'nuevo'
      : null
  return (
    <td className="px-2 py-2 text-right align-top border-b border-slate-100">
      <div className="font-medium text-slate-800 tabular-nums">{formatMetricValue(metricKey, c, unitsMeta)}</div>
      {line && <div className="text-xs text-slate-500 mt-0.5 tabular-nums">{line}</div>}
    </td>
  )
}

export default function BusinessSliceOmniviewTable ({
  rows,
  subtotals,
  expanded,
  toggle,
  unitsMeta,
  expandedView,
  onLeafClick
}) {
  const tree = useMemo(() => buildOmniviewTree(rows || []), [rows])
  const colKeys = expandedView ? [...CORE_KEYS, ...EXTRA_KEYS] : CORE_KEYS

  const colLabels = {
    trips_completed: 'Trips',
    revenue_yego_net: 'Revenue',
    active_drivers: 'Drivers',
    trips_per_driver: 'Trips/Driver',
    cancel_rate_pct: 'Cancel %',
    commission_pct: 'Comm %',
    avg_ticket: 'Ticket',
    trips_cancelled: 'Canc.'
  }

  if (!tree.length) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 bg-slate-50/50 p-8 text-center text-slate-500">
        No hay filas para los filtros seleccionados.
      </div>
    )
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="bg-slate-100 text-left text-xs font-semibold text-slate-600 uppercase tracking-wide">
            <th className="px-3 py-2 sticky left-0 bg-slate-100 z-10 min-w-[220px]">Jerarquía</th>
            {colKeys.map((k) => (
              <th key={k} className="px-2 py-2 text-right whitespace-nowrap">{colLabels[k] || k}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tree.map((country) => {
            const pc = pathCountry(country.key)
            const openC = expanded[pc]
            const st = findSubtotalForCountry(subtotals, country.key)
            return (
              <Fragment key={pc}>
                <tr className="hover:bg-slate-50/80 cursor-pointer" onClick={() => toggle(pc)}>
                  <td className="px-3 py-2 font-semibold text-slate-800 sticky left-0 bg-white border-b border-slate-100">
                    <span className="inline-block w-5 text-slate-500">{openC ? '▼' : '▶'}</span>
                    <span className="text-amber-800">País · {country.key}</span>
                  </td>
                  {colKeys.map((k) => (
                    <SubtotalMetricCell key={k} st={st} metricKey={k} unitsMeta={unitsMeta} />
                  ))}
                </tr>
                {openC && country.cities.map((city) => {
                  const pci = pathCity(country.key, city.key)
                  const openCi = expanded[pci]
                  const cityLeaves = city.slices.flatMap((sl) => sl.leaves)
                  return (
                    <Fragment key={pci}>
                      <tr className="hover:bg-slate-50/50 cursor-pointer" onClick={() => toggle(pci)}>
                        <td className="px-3 py-2 pl-8 text-slate-700 sticky left-0 bg-white border-b border-slate-100">
                          <span className="inline-block w-5 text-slate-400">{openCi ? '▼' : '▶'}</span>
                          {city.key}
                        </td>
                        {colKeys.map((k) => (
                          <AggregateMetricCell
                            key={k}
                            leaves={cityLeaves}
                            metricKey={k}
                            unitsMeta={unitsMeta}
                            additive={k === 'trips_completed' || k === 'revenue_yego_net' || k === 'trips_cancelled'}
                          />
                        ))}
                      </tr>
                      {openCi && city.slices.map((slice) => {
                        const ps = pathSlice(country.key, city.key, slice.key)
                        const openSl = expanded[ps]
                        return (
                          <Fragment key={ps}>
                            <tr className="hover:bg-slate-50/50 cursor-pointer" onClick={() => toggle(ps)}>
                              <td className="px-3 py-2 pl-12 text-slate-600 sticky left-0 bg-white border-b border-slate-100">
                                <span className="inline-block w-5 text-slate-400">{openSl ? '▼' : '▶'}</span>
                                {slice.key}
                              </td>
                              {colKeys.map((k) => (
                                <AggregateMetricCell
                                  key={k}
                                  leaves={slice.leaves}
                                  metricKey={k}
                                  unitsMeta={unitsMeta}
                                  additive={k === 'trips_completed' || k === 'revenue_yego_net' || k === 'trips_cancelled'}
                                />
                              ))}
                            </tr>
                            {openSl && slice.leaves.map(({ row, label }) => (
                              <tr
                                key={`${ps}|${label}`}
                                className="hover:bg-emerald-50/40 cursor-pointer border-l-2 border-l-emerald-500/40"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  onLeafClick(row)
                                }}
                              >
                                <td className="px-3 py-2 pl-16 text-slate-600 sticky left-0 bg-white border-b border-slate-100">
                                  <span className="text-slate-400 mr-2">└</span>
                                  {label}
                                </td>
                                {colKeys.map((k) => (
                                  <LeafMetricCell key={k} row={row} metricKey={k} unitsMeta={unitsMeta} />
                                ))}
                              </tr>
                            ))}
                          </Fragment>
                        )
                      })}
                    </Fragment>
                  )
                })}
              </Fragment>
            )
          })}
        </tbody>
      </table>
      <p className="text-xs text-slate-500 px-3 py-2 border-t border-slate-100">
        Clic en una fila de flota para abrir el panel de detalle. País usa subtotales del backend; ciudad/tajada muestran sumas de trips/revenue/canc. de hijos.
      </p>
    </div>
  )
}
