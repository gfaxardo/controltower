import { useState, useEffect, useCallback, useMemo } from 'react'
import api from '../../services/api'
import { getYangoLoyaltyPerformance } from '../../services/api'
import DecisionPriorityStrip from '../operational/DecisionPriorityStrip'
import { getDecisionSeverity } from '../../utils/operationalDecisionSeverity'
import DiagnosticDominantFactor from '../diagnostics/DiagnosticDominantFactor'

/* ── Color system ── */
const RC = {
  ON_TRACK:       { dot: 'bg-emerald-500', bg: 'bg-emerald-500/10', text: 'text-emerald-400', label: 'On Track' },
  SLIGHTLY_BEHIND:{ dot: 'bg-blue-500',    bg: 'bg-blue-500/10',    text: 'text-blue-400',    label: 'Behind' },
  RECOVERABLE:    { dot: 'bg-amber-500',   bg: 'bg-amber-500/10',   text: 'text-amber-400',   label: 'Recoverable' },
  HIGH_RISK:      { dot: 'bg-orange-500',  bg: 'bg-orange-500/10',  text: 'text-orange-400',  label: 'High Risk' },
  UNREACHABLE:    { dot: 'bg-red-500',     bg: 'bg-red-500/10',     text: 'text-red-400',     label: 'Unreachable' },
  DATA_MISSING:   { dot: 'bg-gray-500',    bg: 'bg-gray-500/10',    text: 'text-gray-400',    label: 'No Data' },
}

const CAT = {
  ORO:   { bg: 'bg-amber-500/10', text: 'text-amber-400',  border:'border-amber-500/25', fill:'bg-amber-500' },
  PLATA: { bg: 'bg-slate-400/10', text: 'text-slate-300',  border:'border-slate-400/25', fill:'bg-slate-400' },
  BRONCE:{ bg: 'bg-orange-700/10',text: 'text-orange-400', border:'border-orange-700/25',fill:'bg-orange-700' },
}

const KPI_GROUPS = {
  performance:{ label:'Performance', kpis:['ad','supply_hours','nuevos_reactivados'], rule:'3 metas = Oro | 2 = Plata | 0-1 = Bronce' },
  calls:      { label:'Calls + Conversion', kpis:['calls_efectivas','conversion_nuevos','conversion_reactivados'], rule:'Calls efectivas + tasa conversion' },
  ufc:        { label:'UFC', kpis:['ufc'], rule:'Lima Oro 40% Plata 30% | Prov Oro 25% Plata 20%' },
  comms:      { label:'Comms', kpis:['comms'], rule:'Oro >=100 Plata >=65 | Min 30% educacion' },
  support:    { label:'Support', kpis:['support'], rule:'Oro >=80 Plata >=50' },
  social:     { label:'Social', kpis:['social'], rule:'Oro >=70 Plata >=40' },
}

const LOYALTY_KPIS_LIST = [
  { key:'ad', label:'AD', source:'auto', tooltip:'Active Drivers mensuales' },
  { key:'supply_hours', label:'Supply Hours', source:'manual', tooltip:'Horas de supply totales' },
  { key:'nuevos_reactivados', label:'Nuevos + Reac.', source:'auto', tooltip:'Activaciones + Reactivaciones' },
  { key:'calls_efectivas', label:'Calls', source:'manual', tooltip:'Llamadas efectivas' },
  { key:'conversion_nuevos', label:'Conv Nuevos', source:'manual', tooltip:'% conversion nuevos' },
  { key:'conversion_reactivados', label:'Conv Reac.', source:'manual', tooltip:'% conversion reactivados' },
  { key:'ufc', label:'UFC', source:'manual', tooltip:'Tasa UFC' },
  { key:'comms', label:'Comms', source:'manual', tooltip:'Comunicaciones' },
  { key:'support', label:'Support', source:'manual', tooltip:'Tickets resueltos' },
  { key:'social', label:'Social', source:'manual', tooltip:'Interacciones sociales' },
]

/* ── Safe helpers ── */
function safeNum(n, fallback = 0) { if (n == null || n === '') return fallback; const v = Number(n); return Number.isNaN(v) ? fallback : v }
function fmtNum(n) { if (n == null || n === '') return '—'; const v = Number(n); return Number.isNaN(v) ? '—' : v.toLocaleString('es-ES', { maximumFractionDigits: 1 }) }
function fmtPct(n) { if (n == null || n === '') return '—'; const v = safeNum(n); if (v === 0 && n === 0) return '0%'; return v ? `${v.toFixed(0)}%` : '—' }
function safeArr(arr) { return Array.isArray(arr) ? arr : [] }

/* ── Skeleton loader ── */
function Skeleton({ h = 4, w = 'full', className = '' }) {
  return <div className={`animate-pulse bg-ct-border/30 rounded ${className}`} style={{ height: h * 4, width: w === 'full' ? '100%' : w }} />
}

/* ── Progress bar (safe) ── */
function ProgressBar({ pct, color = 'bg-ct-accent', height = 3, showLabel }) {
  const w = Math.max(0, Math.min(100, safeNum(pct, 0)))
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-ct-border/20 rounded-full" style={{ height: height * 4 }}>
        <div className={`h-full rounded-full transition-all duration-500 ${color}`} style={{ width: `${w}%` }} />
      </div>
      {showLabel && <span className="text-2xs text-ct-text3 w-9 text-right">{w.toFixed(0)}%</span>}
    </div>
  )
}

function Badge({ label, color }) {
  return <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${color?.bg || ''} ${color?.text || ''}`}>{label}</span>
}

/* ── KPI Status badge ── */
function KpiStatusBadge({ hasReal, hasTarget, meetsOro, meetsPlata, source }) {
  if (source === 'manual' && !hasReal) return <span className="text-xs text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded">Pendiente</span>
  if (hasReal && !hasTarget) return <span className="text-xs text-ct-text3 bg-ct-surface px-1.5 py-0.5 rounded border border-ct-border">Sin meta</span>
  if (meetsOro) return <Badge label="Oro" color={CAT.ORO} />
  if (meetsPlata) return <Badge label="Plata" color={CAT.PLATA} />
  if (hasTarget) return <Badge label="Bronce" color={CAT.BRONCE} />
  return <span className="text-xs text-ct-text3">—</span>
}

/* ── Executive Summary Hero ── */
function ExecutiveSummary({ cityRanking, kpiGaps, data_complete, manual_kpis_pending, expected_progress_pct, cities, has_any_targets }) {
  const totalCities = Math.max(cities.length, 1)
  const oroCount = cityRanking.filter(c => c.cat.category === 'ORO').length
  const plataCount = cityRanking.filter(c => c.cat.category === 'PLATA').length
  const dominant = !has_any_targets ? 'SIN_METAS' : oroCount >= totalCities * 0.5 ? 'ORO' : plataCount >= totalCities * 0.5 ? 'PLATA' : 'BRONCE'
  const domCat = CAT[dominant] || CAT.BRONCE
  const oroPct = Math.round((oroCount / totalCities) * 100)
  const worstKpi = kpiGaps[0]
  const worstCity = cityRanking[0]
  const riskKpis = kpiGaps.filter(k => safeNum(k.avgGap) > 15).length
  const dataPct = kpiGaps.length ? Math.round((kpiGaps.filter(k => k.totalWithData > 0).length / kpiGaps.length) * 100) : 0
  const worstGapKpis = kpiGaps.filter(k => safeNum(k.avgGap) > 5).slice(0, 3)
  const worstCities = cityRanking.slice(0, 2)

  const narrative = dominant === 'ORO'
    ? `YEGO proyecta categoria Oro con ${oroPct}% de ciudades en nivel Oro. El tracker esta en rango objetivo.`
    : dominant === 'PLATA'
      ? `YEGO proyecta categoria Plata. ${oroCount} ciudades en Oro, ${plataCount} en Plata. Se requieren ${Math.max(0, 3 - oroCount)} ciudades mas en Oro.`
      : dominant === 'SIN_METAS'
        ? `YEGO Loyalty Tracker activo. Configura metas para activar el scoring de categoria Oro/Plata/Bronce.`
        : `YEGO proyecta categoria Bronce. Solo ${oroCount} ciudades en Oro. Se requiere acelerar KPIs de performance.`

  return (
    <div className="space-y-3 mb-4">
      <div className="bg-ct-card border border-ct-border rounded-xl p-4">
        <p className="text-sm font-semibold text-ct-text mb-2">{narrative}</p>
        <div className="space-y-1 text-xs text-ct-text2">
          {worstGapKpis.length > 0 && (
            <p>Los blockers principales son: {worstGapKpis.map((k, i) => <span key={k.key}>{i > 0 ? ', ' : ''}<span className="text-red-400 font-medium">{k.label}</span></span>)}</p>
          )}
          {!has_any_targets && <p>Sin metas configuradas. Ve a <span className="text-ct-accent font-medium">Configurar Metas</span> para activar el scoring.</p>}
          {has_any_targets && worstCities.length > 0 && (
            <p>Ciudades criticas: {worstCities.map((c, i) => <span key={c.city}>{i > 0 ? ', ' : ''}<span className={`font-medium ${(CAT[c.cat.category] || CAT.BRONCE).text}`}>{c.city}</span></span>)}</p>
          )}
          <p>Completitud de datos: <span className={data_complete ? 'text-emerald-400 font-medium' : 'text-amber-400 font-medium'}>{dataPct}%</span></p>
          {riskKpis > 0 && <p>KPIs en riesgo: <span className="text-red-400 font-medium">{riskKpis}</span></p>}
          {manual_kpis_pending > 0 && <p>KPIs pendientes de carga manual: <span className="text-amber-400 font-medium">{manual_kpis_pending}</span></p>}
        </div>
      </div>
      <div className={`rounded-2xl border-2 p-5 ${domCat.border} bg-gradient-to-br ${dominant === 'ORO' ? 'from-amber-500/15 via-amber-500/5 to-transparent' : dominant === 'PLATA' ? 'from-slate-400/10 via-slate-400/5 to-transparent' : 'from-orange-700/10 via-orange-700/5 to-transparent'}`}>
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          <div className="text-center">
            <p className="text-xs text-ct-text3 mb-1">Vamos a Oro?</p>
            <p className={`text-3xl font-black ${domCat.text}`}>{dominant === 'ORO' ? 'SI' : dominant === 'PLATA' ? 'CASI' : dominant === 'SIN_METAS' ? '—' : 'NO'}</p>
            <p className="text-xs text-ct-text3 mt-0.5">{has_any_targets ? `${oroPct}% ciudades en Oro` : 'Sin metas'}</p>
          </div>
          <div className="text-center">
            <p className="text-xs text-ct-text3 mb-1">KPI Bloqueador</p>
            <p className="text-lg font-bold text-red-400">{worstKpi?.label || '—'}</p>
            <p className="text-xs text-ct-text3">{worstKpi && safeNum(worstKpi.avgGap) > 0 ? `${safeNum(worstKpi.avgGap).toFixed(0)}% de gap` : 'Sin bloqueos'}</p>
          </div>
          <div className="text-center">
            <p className="text-xs text-ct-text3 mb-1">Ciudad Critica</p>
            <p className="text-lg font-bold text-ct-text">{worstCity?.city || '—'}</p>
            <p className="text-xs text-ct-text3">{worstCity ? `${worstCity.cat?.category || '—'} · ${safeNum(worstCity.oroCount)} KPIs Oro` : ''}</p>
          </div>
          <div className="text-center">
            <p className="text-xs text-ct-text3 mb-1">Avance vs Esperado</p>
            <p className="text-lg font-bold text-ct-text">{safeNum(expected_progress_pct).toFixed(0)}%</p>
            <div className="mt-1 bg-ct-border/20 rounded-full h-1.5 mx-auto w-24">
              <div className="bg-ct-accent h-full rounded-full" style={{ width: `${Math.min(safeNum(expected_progress_pct), 100)}%` }} />
            </div>
          </div>
          <div className="text-center">
            <p className="text-xs text-ct-text3 mb-1">Estado de Datos</p>
            <p className={`text-lg font-bold ${data_complete ? 'text-emerald-400' : 'text-amber-400'}`}>
              {data_complete ? 'Completo' : 'Incompleto'}
            </p>
            <p className="text-xs text-ct-text3">{manual_kpis_pending > 0 ? `${manual_kpis_pending} KPIs pendientes` : has_any_targets ? 'Todo cargado' : 'Sin metas'}</p>
          </div>
        </div>
      </div>
    </div>
  )
}

/* ── Drillable Blocker ── */
function DrillableBlocker({ kpi, cities, expanded, onToggle }) {
  const worstCities = safeArr(cities)
    .filter(c => c.target && !c.meets_oro)
    .sort((a, b) => safeNum(b.gap_pct) - safeNum(a.gap_pct))
    .slice(0, 3)

  return (
    <div className="bg-ct-surface/50 rounded-lg overflow-hidden">
      <button onClick={onToggle} className="w-full flex items-center gap-3 px-3 py-2 hover:bg-ct-border/20 transition-colors text-left">
        <div className="flex-1 flex items-center gap-3">
          <span className="text-xs text-ct-text font-medium">{kpi.label}</span>
          <ProgressBar pct={100 - Math.min(safeNum(kpi.avgGap), 100)} color={safeNum(kpi.avgGap) > 30 ? 'bg-red-500' : safeNum(kpi.avgGap) > 15 ? 'bg-amber-500' : 'bg-blue-500'} height={2} />
          <span className={`text-2xs font-mono ${safeNum(kpi.avgGap) > 30 ? 'text-red-400' : safeNum(kpi.avgGap) > 15 ? 'text-amber-400' : 'text-blue-400'}`}>{safeNum(kpi.avgGap).toFixed(0)}% gap</span>
        </div>
        <span className="text-2xs text-ct-text3">{expanded ? '▲' : '▼'}</span>
      </button>
      {expanded && worstCities.length > 0 && (
        <div className="px-3 pb-2 space-y-1">
          {worstCities.map(c => (
            <div key={c.city} className="flex items-center gap-2 text-2xs">
              <span className="text-ct-text2 w-24 truncate">{c.city}</span>
              <ProgressBar pct={safeNum(c.attainment_pct)} color={c.meets_oro ? 'bg-amber-500' : c.meets_plata ? 'bg-slate-400' : 'bg-red-500'} height={1.5} />
              <span className="text-ct-text3 w-14 text-right">{safeNum(c.real)}/{safeNum(c.target)}</span>
              <span className={c.meets_oro ? 'text-amber-400' : c.meets_plata ? 'text-slate-400' : 'text-red-400'}>
                {fmtPct(c.attainment_pct)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/* ── Main component ── */
export default function YangoLoyaltyView() {
  const [summary, setSummary] = useState(null)
  const [summaryError, setSummaryError] = useState(null)
  const [perfData, setPerfData] = useState(null)
  const [perfError, setPerfError] = useState(null)
  const [initialLoading, setInitialLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('overview')
  const [configCity, setConfigCity] = useState('')
  const [configTargets, setConfigTargets] = useState({})
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState(null)
  const [showRubric, setShowRubric] = useState(false)
  const [expandedBlocker, setExpandedBlocker] = useState(null)
  const [expandedCities, setExpandedCities] = useState({})

  const fetchSummary = useCallback(async () => {
    setSummaryError(null)
    try {
      const res = await api.get('/yango-loyalty/summary', { timeout: 15000 })
      setSummary(res.data)
    } catch (err) {
      setSummaryError(err.response?.data?.detail || err.message || 'Error de conexion')
    }
  }, [])

  const fetchPerformance = useCallback(async () => {
    setPerfError(null)
    try {
      const res = await getYangoLoyaltyPerformance({ country: 'peru', include_missing_targets: true })
      setPerfData(res)
    } catch (err) {
      setPerfError(err?.response?.data?.detail || err?.message || 'Error al cargar performance')
    }
  }, [])

  const fetchData = useCallback(async () => {
    setInitialLoading(true)
    await Promise.allSettled([fetchSummary(), fetchPerformance()])
    setInitialLoading(false)
  }, [fetchSummary, fetchPerformance])

  useEffect(() => { fetchData() }, [fetchData])

  const handleBatchConfig = async (e) => {
    e.preventDefault()
    if (!configCity) return
    setSaving(true)
    setSaveMsg(null)
    const targets = {}
    for (const [k, v] of Object.entries(configTargets)) {
      const n = parseFloat(v)
      if (!isNaN(n) && n >= 0) targets[k] = n
    }
    try {
      await api.post('/yango-loyalty/batch-targets', {
        city: configCity,
        month: summary?.month || new Date().toISOString().slice(0, 7),
        targets,
      }, { timeout: 15000 })
      setSaveMsg({ type: 'success', text: `Metas guardadas para ${configCity}` })
      setConfigTargets({})
      await fetchData()
    } catch (err) {
      setSaveMsg({ type: 'error', text: err.response?.data?.detail || err.message || 'Error al guardar' })
    } finally {
      setSaving(false)
    }
  }

  /* ── Loading skeleton — only when nothing loaded at all ── */
  if (initialLoading && !summary && !perfData) return (
    <div className="w-full space-y-4 p-1">
      <div className="flex items-center gap-3 mb-4"><Skeleton h={6} w="48" /><Skeleton h={4} w="64" /></div>
      <div className="grid grid-cols-4 gap-3">{Array.from({ length: 4 }).map((_, i) => <div key={i} className="bg-ct-card rounded-xl p-4 border border-ct-border space-y-2"><Skeleton h={4} /><Skeleton h={8} /><Skeleton h={3} /></div>)}</div>
      <Skeleton h={40} />
    </div>
  )

  /* ── Global error only if BOTH sections failed ── */
  if (!summary && !perfData && !initialLoading && (summaryError || perfError)) return (
    <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
      <p className="font-medium">Error al cargar datos</p>
      <p className="text-sm mt-1">{summaryError || perfError}</p>
      <button onClick={fetchData} className="mt-3 px-3 py-1 bg-red-500/20 rounded text-sm hover:bg-red-500/30">Reintentar</button>
    </div>
  )

  if (!summary && !perfData) return null

  const { month = perfData?.month || new Date().toISOString().slice(0, 7), day_of_month = new Date().getDate(), total_days = 30, expected_progress_pct = 0, data_complete = false, manual_kpis_pending = 0, kpis = [], cities = [], city_categories = {}, has_any_targets = false } = summary || {}

  /* ── Compute city ranking (safe) ── */
  const cityRanking = safeArr(cities).map(city => {
    const cat = city_categories?.[city] || { category:'BRONCE', oro_kpis:0, plata_kpis:0 }
    const cityKpis = safeArr(kpis).flatMap(k => {
      const v = safeArr(k.values).find(x => x.city === city)
      return v ? [{ ...v, kpiKey: k.kpi_key, kpiLabel: k.kpi_label, group: k.group, source: k.source }] : []
    })
    const perfKpis = cityKpis.filter(k => k.group === 'performance')
    const oroCount = perfKpis.filter(k => k.meets_oro).length
    const avgScore = perfKpis.length ? perfKpis.reduce((s, k) => s + safeNum(k.attainment_pct), 0) / perfKpis.length : 0
    const blockers = perfKpis.filter(k => k.target && !k.meets_oro).sort((a, b) => safeNum(b.gap_pct) - safeNum(a.gap_pct))
    return { city, cat, oroCount, avgScore, blockers, cityKpis }
  }).sort((a, b) => {
    const order = { ORO: 3, PLATA: 2, BRONCE: 1 }
    return (order[a.cat.category] || 0) - (order[b.cat.category] || 0) || a.avgScore - b.avgScore
  })

  const totalOroCities = cityRanking.filter(c => c.cat.category === 'ORO').length
  const totalPlataCities = cityRanking.filter(c => c.cat.category === 'PLATA').length

  /* ── Compute KPI gaps (include KPIs without targets) ── */
  const kpiGaps = LOYALTY_KPIS_LIST.map(k => {
    const kpiData = kpis.find(x => x.kpi_key === k.key)
    const vals = safeArr(kpiData?.values)
    const withTarget = vals.filter(v => v.target != null)
    const withData = vals.filter(v => v.real != null)
    const avgGap = withTarget.length ? withTarget.reduce((s, v) => s + safeNum(v.gap_pct), 0) / withTarget.length : 0
    return { ...k, avgGap, totalWithTarget: withTarget.length, totalWithData: withData.length, hasData: withData.length > 0 }
  }).sort((a, b) => safeNum(b.avgGap) - safeNum(a.avgGap))

  return (
    <div className="w-full ct-page-section" style={{gap: 'var(--ct-space-3)'}}>
      {/* ═══ HEADER ═══ */}
      <div className="ct-workbench-header">
        <div className="ct-workbench-header-left">
          <h2 className="ct-workbench-title">Yango Loyalty Tracker</h2>
          <p className="ct-workbench-subtitle">Mes {month} &middot; Dia {safeNum(day_of_month)}/{safeNum(total_days)} &middot; Avance esperado {safeNum(expected_progress_pct).toFixed(0)}%</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-ct-text3">Actualizado: {new Date().toLocaleTimeString('es-PE', { hour: '2-digit', minute: '2-digit' })}</span>
          <button onClick={() => setShowRubric(!showRubric)} className={`ct-secondary-action ${showRubric ? 'ct-secondary-action--active' : ''}`}>
            Reglas
          </button>
          {['overview','by_kpi','config'].map(t => (
            <button key={t} onClick={() => setActiveTab(t)}
              className={`ct-secondary-action ${activeTab === t ? 'ct-secondary-action--active' : ''}`}>
              {t === 'overview' ? 'Resumen' : t === 'by_kpi' ? 'Detalle KPI' : 'Configurar Metas'}
            </button>
          ))}
        </div>
      </div>

      {/* ═══ NON-BLOCKING BANNERS ═══ */}
      {(!has_any_targets || !data_complete || manual_kpis_pending > 0) && (
        <DiagnosticDominantFactor
          signals={{
            has_any_targets,
            data_complete,
            manual_kpis_pending,
          }}
          className="px-3 py-1.5"
        />
      )}

      {/* ═══ TAB: RUBRIC ═══ */}
      {showRubric && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
          {Object.entries(KPI_GROUPS).map(([key, g]) => (
            <div key={key} className="bg-ct-card border border-ct-border rounded-lg p-3">
              <p className="text-2xs font-semibold text-ct-text mb-1">{g.label}</p>
              <p className="text-2xs text-ct-text3 leading-relaxed">{g.rule}</p>
            </div>
          ))}
        </div>
      )}

      {/* ═══ TAB: OVERVIEW ═══ */}
      {activeTab === 'overview' && (
        <>
          {/* ── Per-section error ── */}
          {perfError && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 mb-3">
              <p className="text-sm text-red-400">No se pudo cargar Performance. AD y SH no disponibles.</p>
              <p className="text-xs text-red-400/70 mt-1">{perfError}</p>
              <button onClick={fetchPerformance} className="mt-2 px-3 py-1 bg-red-500/20 rounded text-xs text-red-400 hover:bg-red-500/30">Reintentar</button>
            </div>
          )}
          {summaryError && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 mb-3">
              <p className="text-sm text-red-400">No se pudo cargar el resumen de scoring.</p>
              <p className="text-xs text-red-400/70 mt-1">{summaryError}</p>
              <button onClick={fetchSummary} className="mt-2 px-3 py-1 bg-red-500/20 rounded text-xs text-red-400 hover:bg-red-500/30">Reintentar</button>
            </div>
          )}

          {/* ── Piloto Lima — Performance Foundation ── */}
          {perfData && (
            <div className="space-y-3 mb-4">
              {/* Pilot scope badge */}
              <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="px-2 py-0.5 rounded text-xs font-bold bg-blue-500/20 text-blue-400 border border-blue-500/40">Lima only</span>
                  <span className="text-sm font-medium text-ct-text">Piloto Lima</span>
                </div>
                <p className="text-xs text-ct-text3">La fuente actual de actividad diaria esta habilitada para Lima. Provincias se activaran cuando la tabla sea enriquecida.</p>
              </div>

              {/* Remediation / Reconciliation banner */}
              {(perfData.remediation?.length > 0 || perfData.reconciliation) && (
                <div className={`rounded-lg p-3 ${perfData.scoring_status === 'blocked_pending_reconciliation' ? 'bg-amber-500/10 border border-amber-500/30' : 'bg-amber-500/10 border border-amber-500/30'}`}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`font-medium text-sm ${perfData.scoring_status === 'blocked_pending_reconciliation' ? 'text-amber-400' : 'text-amber-400'}`}>
                      {perfData.scoring_status === 'blocked_pending_reconciliation'
                        ? 'Abril Lima pendiente de reconciliacion. Scoring bloqueado.'
                        : perfData.scoring_status === 'enabled'
                          ? `Scoring activo: ${perfData.summary?.performance_category || ''} (${perfData.summary?.performance_goals_completed || 0}/3)`
                          : 'Scoring bloqueado.'}
                    </span>
                  </div>
                  {perfData.remediation?.map((r, i) => (
                    <p key={i} className="text-xs text-amber-300/80">{r.message}</p>
                  ))}
                  {perfData.reconciliation?.guardrail_flags?.length > 0 && (
                    <p className="text-xs text-amber-300/80 mt-1">
                      Flags: {perfData.reconciliation.guardrail_flags.join(', ')}
                    </p>
                  )}
                  {perfData.target_status !== 'configured' && (
                    <button onClick={() => setActiveTab('config')} className="mt-2 text-xs text-ct-accent hover:underline">
                      Configurar metas
                    </button>
                  )}
                </div>
              )}

              {/* KPI Cards — Lima (3 metrics + scoring status) */}
              <div className="ct-kpi-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))' }}>
                <div className="ct-kpi-card border-ct-border bg-ct-card">
                  <span className="ct-kpi-card-label">Active Drivers Lima MTD</span>
                  <span className="ct-kpi-card-value text-ct-text">{fmtNum(perfData.summary?.active_drivers_mtd)}</span>
                  {perfData.reconciliation && (
                    <span className="text-2xs text-ct-text3">Yango: {fmtNum(perfData.reconciliation.ad_reference)} ({perfData.reconciliation.ad_drift_pct}% dif)</span>
                  )}
                </div>
                <div className="ct-kpi-card border-ct-border bg-ct-card">
                  <span className="ct-kpi-card-label">Supply Hours Lima MTD</span>
                  <span className="ct-kpi-card-value text-ct-text">{fmtNum(perfData.summary?.supply_hours_mtd)}</span>
                  {perfData.reconciliation && (
                    <span className={`text-2xs ${perfData.reconciliation.sh_drift_pct > 5 ? 'text-amber-400' : 'text-ct-text3'}`}>
                      Yango: {fmtNum(perfData.reconciliation.sh_reference)} ({perfData.reconciliation.sh_drift_pct}% dif)
                    </span>
                  )}
                </div>
                <div className="ct-kpi-card border-ct-border bg-ct-card">
                  <span className="ct-kpi-card-label">Nuevos + Reactivados MTD</span>
                  <span className="ct-kpi-card-value text-ct-text">{fmtNum(perfData.summary?.new_plus_reactivated_mtd)}</span>
                  <span className="text-2xs text-amber-400">Definicion provisional</span>
                  {perfData.reconciliation && (
                    <span className="text-2xs text-amber-300/80">Yango: {fmtNum(perfData.reconciliation.nr_reference)} ({perfData.reconciliation.nr_drift_pct}% dif)</span>
                  )}
                </div>
                <div className={`ct-kpi-card border-amber-500/30 ${perfData.scoring_status === 'blocked_pending_reconciliation' ? 'bg-amber-500/5' : 'bg-ct-card'}`}>
                  <span className="ct-kpi-card-label">Scoring</span>
                  <span className="ct-kpi-card-value text-amber-400">
                    {perfData.scoring_status === 'blocked_pending_reconciliation' ? 'Pendiente Reconciliacion' :
                     perfData.scoring_status === 'enabled' ? 'Activo' : 'Bloqueado'}
                  </span>
                  {perfData.reconciliation?.guardrail_flags?.length > 0 && (
                    <span className="text-2xs text-amber-400 block mt-0.5">{perfData.reconciliation.guardrail_flags.join(', ')}</span>
                  )}
                </div>
              </div>

              {/* Lima detail + gaps */}
              {perfData.cities?.length > 0 && (
                <div className="bg-ct-card border border-ct-border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-ct-text">Piloto Lima — Detalle</h3>
                    <span className="text-2xs text-ct-text3">Mes: {perfData.month}</span>
                  </div>
                  {perfData.cities.map(city => (
                    <div key={city.city_norm} className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                      <div className="bg-ct-surface rounded-lg p-3">
                        <p className="text-2xs text-ct-text3 mb-1">AD MTD</p>
                        <p className="text-lg font-bold text-ct-text">{fmtNum(city.active_drivers_mtd)}</p>
                        {city.target_active_drivers != null && (
                          <p className={`text-2xs mt-0.5 ${city.gap_active_drivers_vs_target >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            Gap: {city.gap_active_drivers_vs_target >= 0 ? '+' : ''}{fmtNum(city.gap_active_drivers_vs_target)} vs meta {fmtNum(city.target_active_drivers)}
                          </p>
                        )}
                      </div>
                      <div className="bg-ct-surface rounded-lg p-3">
                        <p className="text-2xs text-ct-text3 mb-1">Supply Hours MTD</p>
                        <p className="text-lg font-bold text-ct-text">{fmtNum(city.supply_hours_mtd)}</p>
                        {city.target_supply_hours != null && (
                          <p className={`text-2xs mt-0.5 ${city.gap_supply_hours_vs_target >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                            Gap: {city.gap_supply_hours_vs_target >= 0 ? '+' : ''}{fmtNum(city.gap_supply_hours_vs_target)} vs meta {fmtNum(city.target_supply_hours)}
                          </p>
                        )}
                      </div>
                      <div className="bg-ct-surface rounded-lg p-3">
                        <p className="text-2xs text-ct-text3 mb-1">Proyeccion SH EOM</p>
                        <p className="text-lg font-bold text-ct-text">{city.projected_supply_hours_eom != null ? fmtNum(city.projected_supply_hours_eom) : '—'}</p>
                        <p className="text-2xs text-ct-text3 mt-0.5">Avance: {(safeNum(city.expected_progress_pct) * 100).toFixed(0)}%</p>
                      </div>
                      <div className="bg-ct-surface rounded-lg p-3">
                        <p className="text-2xs text-ct-text3 mb-1">Trazabilidad</p>
                        <p className="text-2xs text-ct-text2">{city.city_assignment_method || 'forced_lima_pilot'}</p>
                        <p className="text-2xs text-emerald-400 mt-0.5">{city.city_assignment_confidence || 'high'}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Unsupported cities */}
              {perfData.unsupported_cities?.length > 0 && (
                <div className="bg-ct-surface/50 border border-ct-border rounded-lg p-3">
                  <h4 className="text-xs font-medium text-ct-text3 mb-2">Ciudades pendientes de enriquecimiento</h4>
                  <div className="flex gap-2">
                    {perfData.unsupported_cities.map(c => (
                      <span key={c.city_norm} className="px-2 py-1 rounded text-2xs bg-ct-border/20 text-ct-text3 border border-ct-border capitalize">
                        {c.city_norm} — pendiente
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Metric Definition Status */}
              <div className="bg-ct-surface/50 border border-ct-border rounded-lg p-3">
                <h4 className="text-xs font-medium text-ct-text3 mb-1">Definiciones de Metricas</h4>
                <p className="text-2xs text-ct-text3">
                  AD: Auto regular (1.9% dif vs Yango) | SH: fleet_summary (13% dif, cobertura parcial) | N+R: provisional (+176% dif)
                </p>
                <p className="text-2xs text-amber-400 mt-1">
                  Scoring bloqueado hasta validacion Yango de definicion N+R.
                </p>
              </div>

              {/* YEGO Operational Flow — Enriched */}
              <div className="bg-blue-500/5 border border-blue-500/30 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <h4 className="text-xs font-medium text-blue-400">YEGO Operational Flow</h4>
                  <span className="px-1 py-0.5 rounded text-2xs bg-green-500/20 text-green-400">Enriched</span>
                </div>
                <p className="text-2xs text-ct-text3 mb-2">
                  Entrada y recuperacion de conductores en YEGO. Enriquecido con trips 2025/2026. No equivale al N+R oficial Yango.
                </p>
                <div className="grid grid-cols-4 gap-2">
                  <div className="bg-ct-surface rounded p-2 text-center">
                    <p className="text-2xs text-ct-text3">Nuevos YEGO</p>
                    <p className="text-sm font-bold text-ct-text">{fmtNum(perfData.summary?.new_drivers_mtd || '—')}</p>
                  </div>
                  <div className="bg-ct-surface rounded p-2 text-center">
                    <p className="text-2xs text-ct-text3">Reactivados</p>
                    <p className="text-sm font-bold text-ct-text">{fmtNum(perfData.summary?.reactivated_drivers_mtd || '—')}</p>
                  </div>
                  <div className="bg-ct-surface rounded p-2 text-center">
                    <p className="text-2xs text-ct-text3">Flujo Total</p>
                    <p className="text-sm font-bold text-ct-text">{fmtNum(perfData.summary?.new_plus_reactivated_mtd || '—')}</p>
                  </div>
                  <div className="bg-ct-surface rounded p-2 text-center">
                    <p className="text-2xs text-amber-400/80">Falsos Nuevos</p>
                    <p className="text-sm font-bold text-orange-400">—</p>
                  </div>
                </div>
                <div className="flex gap-1 mt-2">
                  <span className="px-1.5 py-0.5 rounded text-2xs bg-blue-500/20 text-blue-400">Internal Mgmt</span>
                  <span className="px-1.5 py-0.5 rounded text-2xs bg-amber-500/20 text-amber-400">Not Yango Scoring</span>
                  <span className="px-1.5 py-0.5 rounded text-2xs bg-green-500/20 text-green-400">Hist Enrichment</span>
                </div>
              </div>
            </div>
          )}

          <ExecutiveSummary {...{ cityRanking, kpiGaps, data_complete, manual_kpis_pending, expected_progress_pct, cities, has_any_targets }} />

          <div className="ct-kpi-grid">
            {['ORO','PLATA','BRONCE'].map(cat => {
              const cs = CAT[cat]
              const count = cat === 'ORO' ? totalOroCities : cat === 'PLATA' ? totalPlataCities : Math.max(0, cities.length - totalOroCities - totalPlataCities)
              return (
                <div key={cat} className={`ct-kpi-card ${cs.border} ${cs.bg}`}>
                  <span className="ct-kpi-card-label">Ciudades {cat === 'ORO' ? 'Oro' : cat === 'PLATA' ? 'Plata' : 'Bronce'}</span>
                  <span className={`ct-kpi-card-value ${cs.text}`}>{count}</span>
                </div>
              )
            })}
          </div>

          {/* ── City ranking (worst → best, collapsible) ── */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-ct-text">Ranking por ciudad (peor → mejor)</h3>
              <DecisionPriorityStrip
                items={cityRanking}
                signalExtractor={(city) => ({
                  meets_oro: city.cat?.category === 'ORO',
                  data_complete,
                  has_any_targets,
                  attainment_pct: city.avgScore,
                  __signals: { city: city.city, category: city.cat?.category },
                })}
              />
            </div>
            {cityRanking.map((city, idx) => {
              const cs = CAT[city.cat.category] || CAT.BRONCE
              const isOpen = expandedCities[city.city] !== undefined ? expandedCities[city.city] : idx === 0
              return (
                <div key={city.city} className={`ct-collapsible ${isOpen ? 'ct-collapsible--open' : ''}`}>
                  <button onClick={() => setExpandedCities(p => ({ ...p, [city.city]: !isOpen }))}
                    className="ct-collapsible-header">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <span className="text-xs font-semibold text-ct-text">{city.city}</span>
                      {has_any_targets ? (
                        <span className={`ct-badge ${city.cat.category === 'ORO' ? 'ct-badge--ok' : city.cat.category === 'PLATA' ? 'ct-badge--neutral' : 'ct-badge--warn'}`}>
                          {city.cat.category} ({safeNum(city.oroCount)}O/{safeNum(city.cat.plata_kpis)}P)
                        </span>
                      ) : (
                        <span className="text-xs text-ct-text3">Sin metas</span>
                      )}
                      {city.blockers.length > 0 && city.cat.category !== 'ORO' && (
                        <span className="text-xs text-ct-text2 truncate max-w-[200px] hidden sm:inline">
                          {city.blockers[0]?.kpiLabel} ({safeNum(city.blockers[0]?.gap_pct).toFixed(0)}%)
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-ct-text3">{safeNum(city.avgScore).toFixed(0)}%</span>
                      <svg className="ct-collapsible-header-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </button>
                  {isOpen && (
                    <div className="ct-collapsible-content">
                      {city.cityKpis.filter(k => k.group === 'performance').map(kpi => {
                        const pct = safeNum(kpi.attainment_pct)
                        const barColor = kpi.meets_oro ? 'bg-amber-500' : kpi.meets_plata ? 'bg-slate-400' : pct > 0 ? 'bg-orange-700' : 'bg-ct-border/40'
                        return (
                          <div key={kpi.kpiKey} className="flex items-center gap-2">
                            <span className="text-xs text-ct-text3 w-20 truncate">{kpi.kpiLabel}</span>
                            <ProgressBar pct={pct} color={barColor} height={2} showLabel />
                            <span className="text-xs text-ct-text3 w-10 text-right">{fmtNum(kpi.real)}</span>
                            <span className={`text-xs w-14 text-right ${kpi.meets_oro ? 'text-amber-400' : kpi.meets_plata ? 'text-slate-400' : kpi.target ? 'text-orange-400' : 'text-ct-text3'}`}>
                              {kpi.target ? fmtPct(kpi.attainment_pct) : '—'}
                            </span>
                          </div>
                        )
                      })}
                      {city.blockers.length > 0 && city.cat.category !== 'ORO' && (
                        <p className="text-xs text-ct-text2 pt-1">
                          Impide Oro: {city.blockers.map(b => `${b.kpiLabel} (${safeNum(b.gap_pct).toFixed(0)}%)`).join(', ')}
                        </p>
                      )}
                      {!has_any_targets && (
                        <p className="text-xs text-ct-text3 pt-1">Configura metas para ver scoring de categoria.</p>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          {/* ── KPI Blocker Section (drillable) ── */}
          {has_any_targets && (
            <div className="bg-ct-card border border-ct-border rounded-lg p-4">
              <h3 className="text-sm font-semibold text-ct-text mb-3">Que impide ser Oro</h3>
              <div className="space-y-1">
                {kpiGaps.filter(k => safeNum(k.avgGap) > 5 && k.totalWithTarget > 0).slice(0, 5).map(kpi => {
                  const cityValues = safeArr(kpis.find(x => x.kpi_key === kpi.key)?.values).filter(v => v.target)
                  return (
                    <DrillableBlocker key={kpi.key} kpi={kpi}
                      cities={cityValues}
                      expanded={expandedBlocker === kpi.key}
                      onToggle={() => setExpandedBlocker(expandedBlocker === kpi.key ? null : kpi.key)} />
                  )
                })}
                {kpiGaps.filter(k => safeNum(k.avgGap) > 5 && k.totalWithTarget > 0).length === 0 && (
                  <p className="text-xs text-ct-text3">Todos los KPIs estan en rango. No hay bloqueos detectados.</p>
                )}
              </div>
            </div>
          )}

          {/* ── Data completeness panel ── */}
          <div className="bg-ct-card border border-ct-border rounded-lg p-4">
            <h3 className="text-sm font-semibold text-ct-text mb-3">Completitud de datos</h3>
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-2">
              {safeArr(kpis).map(kpi => {
                const totalVals = safeArr(kpi.values).length
                const withData = safeArr(kpi.values).filter(v => v.real != null).length
                const withTarget = safeArr(kpi.values).filter(v => v.target != null).length
                const pct = totalVals ? Math.round((withData / totalVals) * 100) : 0
                const icon = pct === 100 ? '✓' : pct > 0 ? '~' : '—'
                const color = pct === 100 ? 'text-emerald-400' : pct > 0 ? 'text-amber-400' : 'text-red-400'
                return (
                  <div key={kpi.kpi_key} className="bg-ct-surface rounded-lg p-2.5 text-center">
                    <p className={`text-lg font-bold ${color}`}>{icon}</p>
                    <p className="text-2xs text-ct-text3">{kpi.kpi_label}</p>
                    <p className="text-2xs text-ct-text3">{withData}/{totalVals} data &middot; {withTarget} metas</p>
                  </div>
                )
              })}
            </div>
          </div>
        </>
      )}

      {/* ═══ TAB: BY KPI (detail) ═══ */}
      {activeTab === 'by_kpi' && (
        <div className="space-y-3">
          {Object.entries(KPI_GROUPS).map(([groupKey, group]) => {
            const groupKpis = safeArr(kpis).filter(k => k.group === groupKey)
            const flat = groupKpis.flatMap(kpi => safeArr(kpi.values).map(v => ({ ...v, kpiLabel: kpi.kpi_label, kpiKey: kpi.kpi_key, kpiSource: kpi.source })))
              .sort((a, b) => safeNum(b.gap_pct) - safeNum(a.gap_pct))
            if (!flat.length) return null

            return (
              <div key={groupKey} className="bg-ct-card border border-ct-border rounded-lg overflow-hidden">
                <div className="px-3 py-2 bg-ct-surface border-b border-ct-border flex justify-between items-center">
                  <span className="text-xs font-semibold text-ct-text">{group.label}</span>
                  <span className="text-2xs text-ct-text3">{group.rule}</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-ct-border/30 text-ct-text3 text-2xs">
                        <th className="text-left px-3 py-1.5 font-medium sticky top-0 bg-ct-card">KPI</th>
                        <th className="text-left px-3 py-1.5 font-medium">Ciudad</th>
                        <th className="text-right px-3 py-1.5 font-medium">Meta</th>
                        <th className="text-right px-3 py-1.5 font-medium">Real</th>
                        <th className="text-right px-3 py-1.5 font-medium">%</th>
                        <th className="text-center px-3 py-1.5 font-medium">Nivel</th>
                        <th className="text-center px-3 py-1.5 font-medium w-6"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {flat.map((row, idx) => {
                        const reach = RC[row.reachability] || RC.DATA_MISSING
                        const pct = safeNum(row.attainment_pct)
                        const barColor = row.meets_oro ? 'bg-amber-500' : row.meets_plata ? 'bg-slate-400' : (row.target ? 'bg-orange-700' : 'bg-ct-border/30')
                        const zebra = idx % 2 === 0 ? '' : 'bg-ct-border/5'
                        return (
                          <tr key={idx} className={`border-b border-ct-border/20 hover:bg-ct-surface/30 ${zebra}`}>
                            <td className="px-3 py-1.5 text-ct-text">
                              {row.kpiLabel}
                              {row.kpiSource === 'manual' && <span className="ml-1 text-2xs text-amber-500">(m)</span>}
                            </td>
                            <td className="px-3 py-1.5 text-ct-text2">{row.city}</td>
                            <td className="px-3 py-1.5 text-right text-ct-text text-2xs">
                              {row.target != null ? fmtNum(row.target)
                                : <span className="text-ct-text3 italic">sin meta</span>}
                            </td>
                            <td className="px-3 py-1.5 text-right text-ct-text text-2xs">
                              {row.real != null ? fmtNum(row.real)
                                : row.kpiSource === 'manual' ? <span className="text-amber-400 italic">pendiente</span>
                                : <span className="text-ct-text3">—</span>}
                            </td>
                            <td className="px-3 py-1.5 text-right">
                              {row.target ? (
                                <div className="flex items-center gap-1.5">
                                  <div className="flex-1 bg-ct-border/20 rounded-full h-1.5">
                                    <div className={`h-full rounded-full ${barColor}`} style={{ width: `${Math.min(pct, 100)}%` }} />
                                  </div>
                                  <span className="text-2xs w-8 text-right">{fmtPct(row.attainment_pct)}</span>
                                </div>
                              ) : (
                                <span className="text-2xs text-ct-text3">—</span>
                              )}
                            </td>
                            <td className="px-3 py-1.5 text-center">
                              <KpiStatusBadge hasReal={row.real != null} hasTarget={row.target != null}
                                meetsOro={row.meets_oro} meetsPlata={row.meets_plata} source={row.kpiSource} />
                            </td>
                            <td className="px-3 py-1.5 text-center">
                              <span className={`inline-block w-2 h-2 rounded-full ${reach.dot}`} title={reach.label} />
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* ═══ TAB: CONFIG ═══ */}
      {activeTab === 'config' && (
        <div className="ct-compact-config-panel">
          <div className="ct-panel-header">
            <div>
              <h3 className="text-sm font-semibold text-ct-text">Configurar metas del mes — {month}</h3>
              <p className="text-2xs text-ct-text3 mt-0.5">Define los targets mensuales por ciudad. No es necesario cargar todos los KPIs.</p>
            </div>
          </div>
          <div className="ct-panel-body">
            {saveMsg && (
              <div className={`rounded p-2 mb-3 text-xs flex items-center gap-2 ${saveMsg.type === 'success' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-red-500/10 text-red-400 border border-red-500/30'}`}>
                <span>{saveMsg.type === 'success' ? '✓' : '✗'}</span>
                <span>{saveMsg.text}</span>
                <button type="button" onClick={() => setSaveMsg(null)} className="ml-auto text-ct-text3 hover:text-ct-text">&times;</button>
              </div>
            )}
            <form onSubmit={handleBatchConfig}>
              <div className="flex flex-wrap gap-2 items-end mb-3">
                <div className="ct-form-field" style={{minWidth: 200}}>
                  <span className="ct-form-label">Ciudad</span>
                  <select value={configCity} onChange={e => { setConfigCity(e.target.value); setSaveMsg(null) }}
                    className="ct-select w-full" required>
                    <option value="">Seleccionar ciudad...</option>
                    {safeArr(cities).map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
              </div>
              <div className="ct-form-grid--dense">
                {LOYALTY_KPIS_LIST.map(kpi => (
                  <div key={kpi.key} className="ct-form-field">
                    <label className="ct-form-label" title={kpi.tooltip}>
                      {kpi.label} {kpi.source === 'auto' ? '(auto)' : ''}
                    </label>
                    <input type="number" min="0" step="any" placeholder="Meta" value={configTargets[kpi.key] || ''}
                      onChange={e => setConfigTargets(p => ({ ...p, [kpi.key]: e.target.value }))}
                      className="ct-input" />
                  </div>
                ))}
              </div>
              <div className="ct-action-zone">
                <button type="submit" disabled={saving || !configCity}
                  className="ct-primary-action">
                  {saving ? 'Guardando...' : configCity ? `Guardar metas para ${configCity}` : 'Selecciona una ciudad'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
