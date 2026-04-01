/**
 * BusinessSliceInsightsPanel — insights agrupados por fila/periodo, filtros y leyenda.
 */
import { useMemo, useState, useEffect } from 'react'
import { saveInsightUserPatch } from './omniview/insightUserSettings.js'

const SEV_STYLES = {
  critical: { bg: 'bg-red-50', border: 'border-red-200', badge: 'bg-red-600 text-white', dot: 'bg-red-500', text: 'text-red-800' },
  warning: { bg: 'bg-amber-50', border: 'border-amber-200', badge: 'bg-amber-500 text-white', dot: 'bg-amber-400', text: 'text-amber-800' },
}

const METRIC_GROUPS = [
  { id: 'all', label: 'Todas', keys: null },
  { id: 'revenue_yego_net', label: 'Revenue', keys: ['revenue_yego_net'] },
  { id: 'trips_completed', label: 'Viajes', keys: ['trips_completed'] },
  { id: 'active_drivers', label: 'Conductores', keys: ['active_drivers'] },
  { id: 'cancel_rate_pct', label: 'Cancel', keys: ['cancel_rate_pct'] },
  { id: 'avg_ticket', label: 'Ticket', keys: ['avg_ticket'] },
]

const fmtPct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : null

export default function BusinessSliceInsightsPanel ({
  insights,
  onInsightClick,
  compact,
  transparency,
  defaultTopN = 10,
  onOpenSettings,
  onUserPatchPersist,
}) {
  const [sevFilter, setSevFilter] = useState('all')
  const [metricFilter, setMetricFilter] = useState('all')
  const [topN, setTopN] = useState(defaultTopN)
  const [legendOpen, setLegendOpen] = useState(false)

  useEffect(() => {
    setTopN(defaultTopN)
  }, [defaultTopN])

  const metricKeys = useMemo(() => {
    const g = METRIC_GROUPS.find((x) => x.id === metricFilter)
    return g?.keys
  }, [metricFilter])

  const filtered = useMemo(() => {
    let list = insights
    if (sevFilter === 'critical') list = list.filter((i) => i.severity === 'critical')
    else if (sevFilter === 'warning') list = list.filter((i) => i.severity === 'warning')
    if (metricKeys) {
      list = list.filter((i) => metricKeys.includes(i.metric)
        || (i.secondarySignals || []).some((s) => metricKeys.includes(s.metric)))
    }
    return list
  }, [insights, sevFilter, metricKeys])

  const displayed = useMemo(() => filtered.slice(0, topN), [filtered, topN])

  const criticalCount = useMemo(() => insights.filter((i) => i.severity === 'critical').length, [insights])
  const warningCount = useMemo(() => insights.filter((i) => i.severity === 'warning').length, [insights])

  const handleTopNChange = (n) => {
    const v = Number(n)
    setTopN(v)
    saveInsightUserPatch({ panelTopN: v })
    onUserPatchPersist?.()
  }

  if (!insights.length) return null

  const mini = 'text-[10px] border border-gray-200 rounded px-1.5 py-0.5 bg-white text-gray-600'

  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
      <div className="px-3 py-2 bg-slate-800 flex flex-wrap items-center gap-2 justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[11px] font-bold text-white uppercase tracking-wider">Insights</span>
          {criticalCount > 0 && (
            <span className="px-1.5 py-px rounded text-[9px] font-bold bg-red-600 text-white">{criticalCount} critical</span>
          )}
          {warningCount > 0 && (
            <span className="px-1.5 py-px rounded text-[9px] font-bold bg-amber-500 text-white">{warningCount} warning</span>
          )}
          <span className="text-[10px] text-slate-400">{insights.length} filas · impacto ↓</span>
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          <select className={mini} value={sevFilter} onChange={(e) => setSevFilter(e.target.value)} aria-label="Severidad">
            <option value="all">Severidad: todas</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
          </select>
          <select className={mini} value={metricFilter} onChange={(e) => setMetricFilter(e.target.value)} aria-label="Métrica">
            {METRIC_GROUPS.map((m) => <option key={m.id} value={m.id}>Métrica: {m.label}</option>)}
          </select>
          <select className={mini} value={topN} onChange={(e) => handleTopNChange(e.target.value)} aria-label="Top N">
            <option value={5}>Top 5</option>
            <option value={10}>Top 10</option>
            <option value={20}>Top 20</option>
          </select>
          {onOpenSettings && (
            <button type="button" className={`${mini} hover:bg-gray-50 font-medium`} onClick={onOpenSettings}>
              Ajustes
            </button>
          )}
          <button type="button" className={`${mini} hover:bg-gray-50`} onClick={() => setLegendOpen((o) => !o)}>
            {legendOpen ? 'Ocultar leyenda' : 'Leyenda'}
          </button>
        </div>
      </div>

      {legendOpen && transparency && (
        <div className="px-3 py-2 bg-slate-50 border-b border-gray-100 text-[10px] text-gray-600 space-y-1 leading-relaxed">
          <p><span className="font-semibold text-gray-800">Critical:</span> {transparency.critical}</p>
          <p><span className="font-semibold text-gray-800">Warning:</span> {transparency.warning}</p>
          <p><span className="font-semibold text-gray-800">Impacto:</span> {transparency.impactSummary}</p>
          <p className="text-gray-500 italic">{transparency.disclaimer}</p>
        </div>
      )}

      <div className={`grid gap-2 ${compact ? 'grid-cols-2 lg:grid-cols-4 p-2' : 'grid-cols-2 lg:grid-cols-3 p-3'}`}>
        {displayed.map((ins) => {
          const s = SEV_STYLES[ins.severity] || SEV_STYLES.warning
          const deltaTxt = ins.metric === 'cancel_rate_pct'
            ? (ins.delta_abs_pp != null ? `+${(ins.delta_abs_pp / 100).toFixed(1)} pp` : '')
            : fmtPct(ins.delta_pct)

          return (
            <button
              key={ins.id}
              type="button"
              onClick={() => onInsightClick?.(ins)}
              className={`${s.bg} ${s.border} border rounded-lg ${compact ? 'px-2.5 py-1.5' : 'px-3 py-2'} text-left transition-all hover:shadow-md hover:scale-[1.01] active:scale-[0.99] cursor-pointer group`}
            >
              <div className="flex items-center gap-1.5 mb-0.5 flex-wrap">
                <span className={`${s.badge} px-1 py-px rounded text-[8px] font-bold uppercase`}>
                  {ins.severity}
                </span>
                <span className={`text-[10px] font-bold ${s.text} truncate`}>
                  {ins.city} — {ins.business_slice}
                </span>
                {ins.groupedCount > 1 && (
                  <span className="text-[8px] font-semibold text-gray-500 bg-white/80 px-1 rounded border border-gray-200">
                    +{ins.groupedCount - 1} señales
                  </span>
                )}
              </div>

              <div className={`text-[11px] font-semibold ${s.text} leading-tight`}>
                {ins.metricLabel} {deltaTxt && <span className="font-bold">{deltaTxt}</span>}
              </div>

              {(ins.secondarySignals || []).length > 0 && (
                <div className="text-[9px] text-gray-500 mt-0.5 truncate" title={(ins.secondarySignals || []).map((x) => x.metricLabel).join(', ')}>
                  También: {(ins.secondarySignals || []).map((x) => x.metricLabel).join(', ')}
                </div>
              )}

              <div className="text-[10px] text-gray-500 leading-tight mt-0.5 truncate">
                {ins.explanation.cause}
              </div>

              <div className="text-[9px] text-gray-400 mt-0.5 flex items-center gap-1 group-hover:text-blue-500 transition-colors">
                <svg className="w-2.5 h-2.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                </svg>
                <span className="truncate">{ins.action.action.slice(0, 40)}{ins.action.action.length > 40 ? '…' : ''}</span>
              </div>
            </button>
          )
        })}
      </div>

      {filtered.length > displayed.length && (
        <div className="px-3 py-1.5 border-t border-gray-100 text-center">
          <span className="text-[10px] text-gray-400">
            +{filtered.length - displayed.length} más con filtros actuales (sube Top N o afina filtros)
          </span>
        </div>
      )}

      {filtered.length === 0 && (
        <div className="px-3 py-4 text-center text-[11px] text-gray-400 border-t border-gray-50">
          Ningún insight con estos filtros.
        </div>
      )}
    </div>
  )
}
