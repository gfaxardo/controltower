import { useState, useEffect, useCallback } from 'react'
import { getYangoLoyaltySummary, getYangoLoyaltyReachability, getYangoLoyaltyGaps } from '../services/api'
import { GoalManagementTable, ManualKpiInputForm, DailySnapshotCard, HistoricalTable, CompletenessPanel } from './YangoLoyaltyOperatingLayer'

const CITIES = ['Lima', 'Trujillo', 'Arequipa']

const REACHABILITY_LABELS = {
  ON_TRACK: 'On Track', SLIGHTLY_BEHIND: 'Ligeramente atrás', RECOVERABLE: 'Recuperable',
  HIGH_RISK: 'Alto riesgo', UNREACHABLE: 'Inalcanzable', DATA_MISSING: 'Sin datos',
}
const REACHABILITY_COLORS = {
  ON_TRACK: 'text-green-400', SLIGHTLY_BEHIND: 'text-yellow-400', RECOVERABLE: 'text-amber-500',
  HIGH_RISK: 'text-orange-500', UNREACHABLE: 'text-red-500', DATA_MISSING: 'text-gray-500',
}
const REACHABILITY_BG = {
  ON_TRACK: 'bg-green-500/10 border-green-500/30', SLIGHTLY_BEHIND: 'bg-yellow-500/10 border-yellow-500/30',
  RECOVERABLE: 'bg-amber-500/10 border-amber-500/30', HIGH_RISK: 'bg-orange-500/10 border-orange-500/30',
  UNREACHABLE: 'bg-red-500/10 border-red-500/30', DATA_MISSING: 'bg-gray-500/10 border-gray-500/30',
}
const CATEGORY_COLORS = {
  ORO: 'text-yellow-300', PLATA: 'text-slate-300', BRONCE: 'text-amber-600', SIN_CATEGORIA: 'text-red-400', DATA_MISSING: 'text-gray-500',
}
const CATEGORY_BG = {
  ORO: 'bg-yellow-500/15 border-yellow-500/40', PLATA: 'bg-slate-400/15 border-slate-400/40',
  BRONCE: 'bg-amber-600/15 border-amber-600/40', SIN_CATEGORIA: 'bg-red-500/15 border-red-500/40',
  DATA_MISSING: 'bg-gray-500/10 border-gray-500/30',
}

function formatNum(n) {
  if (n == null || isNaN(n)) return '—'
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + 'M'
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K'
  return Number(n).toFixed(2)
}
function formatPct(n) {
  if (n == null || isNaN(n)) return '—'
  return Number(n).toFixed(1) + '%'
}

function CitySummaryCard({ city, summary }) {
  if (!summary) return null
  const status = summary.dominant_status || 'DATA_MISSING'
  const category = summary.dominant_category || 'DATA_MISSING'
  return (
    <div className={`rounded-lg border p-3 ${REACHABILITY_BG[status] || REACHABILITY_BG.DATA_MISSING}`}>
      <div className="text-sm font-semibold text-ct-text mb-1">{city}</div>
      <div className="flex items-center gap-2 mb-1">
        <span className={`text-xs font-bold ${CATEGORY_COLORS[category] || CATEGORY_COLORS.DATA_MISSING}`}>
          {category === 'DATA_MISSING' ? 'Sin datos' : category}
        </span>
        <span className={`text-2xs ${REACHABILITY_COLORS[status] || REACHABILITY_COLORS.DATA_MISSING}`}>
          {REACHABILITY_LABELS[status] || status}
        </span>
      </div>
      <div className="text-2xs text-ct-text3">{summary.kpi_count} KPIs · {summary.data_missing_count} sin datos</div>
    </div>
  )
}

function KpiRow({ kpi }) {
  const gapIsNegative = kpi.gap_abs != null && kpi.gap_abs < 0
  return (
    <tr className="border-b border-ct-border hover:bg-ct-surface/50">
      <td className="py-1.5 px-2 text-xs text-ct-text">
        <div className="font-medium">{kpi.kpi_name}</div>
        <div className="text-2xs text-ct-text3">{kpi.kpi_code}</div>
      </td>
      <td className="py-1.5 px-2 text-xs text-center text-ct-text3">{kpi.city}</td>
      <td className="py-1.5 px-2 text-xs text-center text-ct-text">{formatNum(kpi.target_value)}</td>
      <td className="py-1.5 px-2 text-xs text-center text-ct-text">{formatNum(kpi.real_value)}</td>
      <td className="py-1.5 px-2 text-xs text-center">
        <span className={gapIsNegative ? 'text-red-400' : 'text-green-400'}>
          {kpi.gap_pct != null ? (kpi.gap_pct >= 0 ? '+' : '') + formatPct(kpi.gap_pct) : '—'}
        </span>
      </td>
      <td className="py-1.5 px-2 text-xs text-center text-ct-text3">
        {kpi.freshness_status && kpi.freshness_status !== 'MISSING' ? (
          <span className={`text-2xs ${kpi.freshness_status === 'FRESH' ? 'text-green-400' : kpi.freshness_status === 'WARNING' ? 'text-amber-400' : 'text-red-400'}`}>
            {kpi.freshness_hours}h
          </span>
        ) : <span className="text-2xs text-ct-text3">—</span>}
      </td>
      <td className="py-1.5 px-2 text-xs text-center">
        <span className={`inline-block px-1.5 py-0.5 rounded text-2xs font-bold ${CATEGORY_COLORS[kpi.current_category] || CATEGORY_COLORS.DATA_MISSING} ${CATEGORY_BG[kpi.current_category] || CATEGORY_BG.DATA_MISSING} border`}>
          {kpi.current_category || '—'}
        </span>
      </td>
      <td className="py-1.5 px-2 text-xs text-center">
        <span className={`inline-block px-1.5 py-0.5 rounded text-2xs font-bold ${CATEGORY_COLORS[kpi.projected_category] || CATEGORY_COLORS.DATA_MISSING} ${CATEGORY_BG[kpi.projected_category] || CATEGORY_BG.DATA_MISSING} border`}>
          {kpi.projected_category || '—'}
        </span>
      </td>
      <td className="py-1.5 px-2 text-xs text-center">
        <span className={`inline-block px-1.5 py-0.5 rounded text-2xs font-semibold ${REACHABILITY_COLORS[kpi.reachability_status] || REACHABILITY_COLORS.DATA_MISSING} ${REACHABILITY_BG[kpi.reachability_status] || REACHABILITY_BG.DATA_MISSING} border`}>
          {REACHABILITY_LABELS[kpi.reachability_status] || kpi.reachability_status}
        </span>
      </td>
    </tr>
  )
}

const OPERATING_TABS = [
  { key: 'reachability', label: 'Reachability' },
  { key: 'goals',       label: 'Goal Management' },
  { key: 'manual',      label: 'Manual KPI Input' },
  { key: 'snapshot',    label: 'Daily Snapshot' },
  { key: 'completeness',label: 'Completitud' },
  { key: 'historical',  label: 'Histórico' },
]

export default function YangoLoyaltyReachabilityDashboard() {
  const [summary, setSummary] = useState(null)
  const [reachability, setReachability] = useState(null)
  const [gaps, setGaps] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedCity, setSelectedCity] = useState('')
  const [viewMode, setViewMode] = useState('all')
  const [opTab, setOpTab] = useState('reachability')

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = {}
      if (selectedCity) params.city = selectedCity
      const [sumRes, reachRes, gapsRes] = await Promise.all([
        getYangoLoyaltySummary(params),
        getYangoLoyaltyReachability(params),
        getYangoLoyaltyGaps(params),
      ])
      setSummary(sumRes)
      setReachability(reachRes)
      setGaps(gapsRes)
    } catch (e) {
      setError(e.message || 'Error al cargar datos')
    } finally {
      setLoading(false)
    }
  }, [selectedCity])

  useEffect(() => { loadData() }, [loadData])

  const filteredKpis = summary?.kpis?.filter((k) => {
    if (viewMode === 'gaps') return k.gap_abs != null && k.gap_abs < 0
    if (viewMode === 'at_risk') return ['HIGH_RISK', 'UNREACHABLE'].includes(k.reachability_status)
    if (viewMode === 'missing') return k.reachability_status === 'DATA_MISSING'
    return true
  }) || []

  if (loading && !summary) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-ct-accent" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
        <p className="text-red-400 text-sm">{error}</p>
        <button onClick={loadData} className="mt-2 px-3 py-1 text-xs bg-red-500/20 text-red-300 rounded hover:bg-red-500/30">Reintentar</button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-bold text-ct-text">Yango Loyalty · Oro Tracker</h2>
          <p className="text-xs text-ct-text3">
            Mes: {summary?.month || '—'} · Día {summary?.today_day || '—'}/{summary?.total_days || '—'} · KPIs: {summary?.total_kpis || 0}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select value={selectedCity} onChange={(e) => setSelectedCity(e.target.value)}
            className="bg-ct-card border border-ct-border rounded px-2 py-1 text-xs text-ct-text">
            <option value="">Todas las ciudades</option>
            {CITIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>

      {/* Data Missing Banner */}
      {summary?.has_data_missing && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 flex items-start gap-2">
          <svg className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
          </svg>
          <div>
            <p className="text-amber-400 text-xs font-semibold">Data Missing</p>
            <p className="text-amber-400/70 text-2xs">Hay KPIs sin datos. Usa Goal Management y Manual KPI Input para completar.</p>
          </div>
        </div>
      )}

      {/* Operating Tabs */}
      <div className="flex flex-wrap gap-1.5 border-b border-ct-border pb-2">
        {OPERATING_TABS.map(({ key, label }) => (
          <button key={key} type="button" onClick={() => setOpTab(key)}
            className={`px-3 py-1.5 rounded-t text-xs font-medium transition-all ${
              opTab === key ? 'bg-ct-card text-ct-text border border-ct-border border-b-ct-card -mb-[1px]' : 'text-ct-text3 hover:text-ct-text hover:bg-ct-surface/50'
            }`}>
            {label}
          </button>
        ))}
      </div>

      {/* Reachability Tab */}
      {opTab === 'reachability' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {CITIES.map((city) => (
              <CitySummaryCard key={city} city={city} summary={summary?.city_summaries?.[city]} />
            ))}
          </div>

          {reachability && (
            <div className="bg-ct-card rounded-lg border border-ct-border p-3">
              <h3 className="text-sm font-semibold text-ct-text mb-2">Distribución de Reachability</h3>
              <div className="flex flex-wrap gap-2">
                {Object.entries(reachability.reachability_distribution || {}).map(([status, count]) => (
                  <div key={status} className={`flex items-center gap-1.5 px-2 py-1 rounded text-2xs border ${REACHABILITY_BG[status] || ''}`}>
                    <span className={`font-semibold ${REACHABILITY_COLORS[status] || ''}`}>{REACHABILITY_LABELS[status] || status}</span>
                    <span className="text-ct-text font-bold">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-1.5">
            {[
              { key: 'all', label: 'Todos' }, { key: 'gaps', label: 'Con Gap' },
              { key: 'at_risk', label: 'En Riesgo' }, { key: 'missing', label: 'Sin Datos' },
            ].map(({ key, label }) => (
              <button key={key} type="button" onClick={() => setViewMode(key)}
                className={`px-2.5 py-1 rounded text-2xs font-medium transition-all ${
                  viewMode === key ? 'bg-ct-accent text-white shadow-sm' : 'text-ct-text2 hover:text-ct-text hover:bg-ct-border'}`}>
                {label}
              </button>
            ))}
          </div>

          <div className="bg-ct-card rounded-lg border border-ct-border overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-ct-border bg-ct-surface/50">
                  <th className="py-2 px-2 text-2xs text-ct-text3 uppercase">KPI</th>
                  <th className="py-2 px-2 text-2xs text-ct-text3 uppercase text-center">Ciudad</th>
                  <th className="py-2 px-2 text-2xs text-ct-text3 uppercase text-center">Meta</th>
                  <th className="py-2 px-2 text-2xs text-ct-text3 uppercase text-center">Real</th>
                  <th className="py-2 px-2 text-2xs text-ct-text3 uppercase text-center">Gap %</th>
                  <th className="py-2 px-2 text-2xs text-ct-text3 uppercase text-center">Fresh.</th>
                  <th className="py-2 px-2 text-2xs text-ct-text3 uppercase text-center">Cat. Actual</th>
                  <th className="py-2 px-2 text-2xs text-ct-text3 uppercase text-center">Cat. Proy.</th>
                  <th className="py-2 px-2 text-2xs text-ct-text3 uppercase text-center">Reachability</th>
                </tr>
              </thead>
              <tbody>
                {filteredKpis.length === 0 ? (
                  <tr><td colSpan={9} className="py-8 text-center text-xs text-ct-text3">No hay KPIs con el filtro actual.</td></tr>
                ) : (
                  filteredKpis.map((kpi, idx) => <KpiRow key={`${kpi.city}-${kpi.kpi_code}-${idx}`} kpi={kpi} />)
                )}
              </tbody>
            </table>
          </div>

          {gaps && gaps.total_gaps > 0 && (
            <div className="bg-ct-card rounded-lg border border-ct-border p-3">
              <h3 className="text-sm font-semibold text-ct-text mb-2">Gaps ({gaps.total_gaps})</h3>
              <div className="space-y-1">
                {gaps.gaps.slice(0, 10).map((g, idx) => (
                  <div key={idx} className="flex items-center justify-between text-xs py-1 border-b border-ct-border/50 last:border-b-0">
                    <span className="text-ct-text3">{g.city} · {g.kpi_name}</span>
                    <span className="text-red-400 font-medium">{formatPct(g.gap_pct)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Goal Management Tab */}
      {opTab === 'goals' && <GoalManagementTable />}

      {/* Manual KPI Input Tab */}
      {opTab === 'manual' && <ManualKpiInputForm />}

      {/* Daily Snapshot Tab */}
      {opTab === 'snapshot' && <DailySnapshotCard />}

      {/* Completeness Tab */}
      {opTab === 'completeness' && <CompletenessPanel />}

      {/* Historical Tab */}
      {opTab === 'historical' && <HistoricalTable />}

      {/* Limitaciones */}
      <details className="bg-ct-card rounded-lg border border-ct-border p-3">
        <summary className="text-2xs text-ct-text3 cursor-pointer">Limitaciones y notas</summary>
        <div className="mt-2 text-2xs text-ct-text3 space-y-1">
          <p>· Solo AD y N+R tienen fuente automatizada (available_now).</p>
          <p>· 8 KPIs requieren ingreso manual vía la pestaña 'Manual KPI Input'.</p>
          <p>· Las metas se gestionan en 'Goal Management' (incluye copiar de mes anterior).</p>
          <p>· La proyección es lineal. El Daily Snapshot muestra gap vs progreso esperado.</p>
          <p>· Freshness WARNING {'>'}48h sin update, STALE {'>'}96h.</p>
          <p>· NO se generan recomendaciones automáticas. NO se automatizan acciones.</p>
        </div>
      </details>
    </div>
  )
}
