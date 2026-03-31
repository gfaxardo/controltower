/**
 * Panel lateral: detalle de fila Omniview (solo lectura del payload backend).
 */
import { formatDeltaLine, formatMetricValue } from './omniview/omniviewUtils.js'

const METRIC_LABELS = {
  trips_completed: 'Viajes completados',
  trips_cancelled: 'Cancelaciones',
  active_drivers: 'Conductores activos',
  avg_ticket: 'Ticket medio',
  revenue_yego_net: 'Revenue YEGO',
  commission_pct: 'Comisión % (ratio 0–1 en dato)',
  trips_per_driver: 'Viajes / conductor',
  cancel_rate_pct: 'Tasa cancelación %'
}

export default function BusinessSliceOmniviewSidebar ({
  open,
  onClose,
  row,
  detailMeta,
  warnings
}) {
  if (!open || !row) return null

  const dims = row.dims || {}
  const cur = row.current || {}
  const prev = row.previous || {}
  const delta = row.delta || {}
  const flags = row.flags || {}
  const signals = row.signals || {}
  const units = detailMeta?.units || {}

  return (
    <>
      <button
        type="button"
        className="fixed inset-0 bg-slate-900/30 z-40 lg:hidden"
        aria-label="Cerrar panel"
        onClick={onClose}
      />
      <aside
        className="fixed top-0 right-0 h-full w-full max-w-md z-50 bg-white shadow-xl border-l border-slate-200 flex flex-col"
        role="dialog"
        aria-labelledby="omniview-sidebar-title"
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-slate-50">
          <h2 id="omniview-sidebar-title" className="text-lg font-semibold text-slate-800">
            Detalle de fila
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-2 py-1 text-sm text-slate-600 hover:bg-slate-200"
          >
            Cerrar
          </button>
        </div>
        <div className="overflow-y-auto flex-1 p-4 space-y-4 text-sm">
          <section>
            <h3 className="font-semibold text-slate-700 mb-2">Dimensiones</h3>
            <dl className="grid grid-cols-1 gap-1 text-slate-600">
              {Object.entries(dims).map(([k, v]) => (
                <div key={k} className="flex justify-between gap-2">
                  <dt className="text-slate-500">{k}</dt>
                  <dd className="text-right font-medium text-slate-800">{v != null ? String(v) : '—'}</dd>
                </div>
              ))}
            </dl>
          </section>

          <section>
            <h3 className="font-semibold text-slate-700 mb-2">Métricas</h3>
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-200 text-xs text-slate-500">
                  <th className="py-1 pr-2">Métrica</th>
                  <th className="py-1 pr-2">Actual</th>
                  <th className="py-1 pr-2">Anterior</th>
                  <th className="py-1">Δ</th>
                </tr>
              </thead>
              <tbody>
                {Object.keys(METRIC_LABELS).map((key) => {
                  const d = delta[key] || {}
                  const sig = signals[key]
                  return (
                    <tr key={key} className="border-b border-slate-100">
                      <td className="py-2 pr-2 text-slate-700">
                        {METRIC_LABELS[key]}
                        {sig && (
                          <span className="block text-xs text-slate-400">
                            {sig.direction} · {sig.signal}
                          </span>
                        )}
                      </td>
                      <td className="py-2 pr-2 tabular-nums">{formatMetricValue(key, cur[key], units)}</td>
                      <td className="py-2 pr-2 tabular-nums">{formatMetricValue(key, prev[key], units)}</td>
                      <td className="py-2 text-xs tabular-nums">
                        {d.delta_abs != null && <div>Δ {formatMetricValue(key, d.delta_abs, units)}</div>}
                        {d.delta_pct != null && <div>{d.delta_pct > 0 ? '+' : ''}{Number(d.delta_pct).toFixed(2)}%</div>}
                        {d.delta_abs_pp != null && <div>{d.delta_abs_pp > 0 ? '+' : ''}{Number(d.delta_abs_pp).toFixed(2)} pp</div>}
                        {d.delta_abs == null && d.delta_pct == null && d.delta_abs_pp == null && '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </section>

          <section>
            <h3 className="font-semibold text-slate-700 mb-2">Flags</h3>
            <ul className="list-disc pl-5 text-slate-600 space-y-1">
              <li>not_comparable: {String(flags.not_comparable)}</li>
              {flags.not_comparable_reason && (
                <li>Motivo: {flags.not_comparable_reason}</li>
              )}
              <li>coverage_unknown: {String(flags.coverage_unknown)}</li>
            </ul>
          </section>

          <section className="text-xs text-slate-500 border-t border-slate-100 pt-3 space-y-1">
            <div><span className="font-medium text-slate-600">detail_source:</span> {detailMeta?.detail_source || '—'}</div>
            <div><span className="font-medium text-slate-600">totals_source:</span> {detailMeta?.totals_source || '—'}</div>
            <div><span className="font-medium text-slate-600">coverage_level:</span> {detailMeta?.coverage_level || '—'}</div>
            <p className="mt-2">{detailMeta?.coverage_reference}</p>
            <p className="mt-1">
              <span className="font-medium">commission_pct</span> en API es ratio 0–1; en tabla se muestra como %.
            </p>
            {warnings?.length > 0 && (
              <div className="mt-2 text-amber-700">
                {warnings.map((w, i) => (
                  <div key={i}>{w}</div>
                ))}
              </div>
            )}
          </section>
        </div>
      </aside>
    </>
  )
}
