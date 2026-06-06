import { useState, useEffect, useCallback } from 'react'
import {
  getLimaGrowthPrioritizedOpportunities,
  getLoopControlConfig,
  getLoopControlExports,
  getLimaGrowthCapacityConfig,
  getLimaGrowthCapacitySummary,
  updateLimaGrowthCapacityConfig,
  getLimaGrowthPriorityAllocation,
  getLimaGrowthChannelAllocation,
  getLimaGrowthOpportunityWorklist,
  buildLimaGrowthAssignmentQueue,
  getLimaGrowthAssignmentQueue,
  getLimaGrowthOperationalSummary,
  getLimaGrowthDriverStateSummary,
  getLimaGrowthProgramsSummary,
} from '../services/api.js'

const TABS = [
  { id: 'resumen', label: 'Resumen', color: '#1a56db' },
  { id: 'estado', label: 'Estado del Conductor', color: '#1a56db' },
  { id: 'programas', label: 'Programas', color: '#059669' },
  { id: 'oportunidades', label: 'Oportunidades', color: '#d97706' },
  { id: 'loopcontrol', label: 'Ejecucion Loop', color: '#7c3aed' },
  { id: 'impacto', label: 'Impacto', color: '#059669' },
  { id: 'movimiento', label: 'Movimiento', color: '#7c3aed' },
  { id: 'atribucion', label: 'Atribucion', color: '#0891b2' },
  { id: 'worklist', label: 'Worklist', color: '#059669' },
  { id: 'assignment_queue', label: 'Queue', color: '#d97706' },
  { id: 'config', label: 'Configuracion', color: '#4b5563' },
]

const PROGRAMAS = [
  { code: 'PROGRAM_14_90', name: '14/90', objetivo: 'Nuevos conductores a 50 viajes en 14 dias', color: '#0891b2' },
  { code: 'PROGRAM_ACTIVE_GROWTH', name: 'Active Growth', objetivo: 'Incrementar viajes en activos', color: '#059669' },
  { code: 'PROGRAM_CHURN_PREVENTION', name: 'Churn Prevention', objetivo: 'Evitar fuga de conductores', color: '#dc2626' },
  { code: 'PROGRAM_HIGH_VALUE_RECOVERY', name: 'High Value Recovery', objetivo: 'Recuperar conductores de alto valor', color: '#d97706' },
]

// ── LG-2.2B: Default fallback si backend no disponible ──
const DEFAULT_CAPACITY_CONFIG = [
  { channel: 'Call Center', agents: 2, capacity_per_agent: 40 },
  { channel: 'SAC', agents: 1, capacity_per_agent: 30 },
  { channel: 'Bot / WhatsApp', agents: 1, capacity_per_agent: 200 },
]

function formatNum(n) { if (n == null) return '—'; const num = Number(n); if (isNaN(num)) return '—'; return num.toLocaleString('es-PE') }
function formatDate(d) { if (!d) return '—'; return new Date(d).toLocaleDateString('es-PE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) }

function StatusPill({ status }) {
  const map = { exported: 'bg-green-100 text-green-800', failed: 'bg-red-100 text-red-800', draft: 'bg-gray-100 text-gray-600', draft_dry_run: 'bg-blue-100 text-blue-800' }
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${map[status] || 'bg-gray-100 text-gray-600'}`}>{status}</span>
}

function EmptyState({ title, message }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <svg className="w-10 h-10 text-gray-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
      </svg>
      <p className="text-sm font-medium text-gray-500">{title}</p>
      {message && <p className="text-xs text-gray-400 mt-1 max-w-xs">{message}</p>}
    </div>
  )
}

function KpiCard({ label, value, color = '#1a56db', subtitle }) {
  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 flex flex-col" style={{ borderLeftWidth: 3, borderLeftColor: color }}>
      <span className="text-xs text-gray-400 uppercase tracking-wide">{label}</span>
      <span className="text-2xl font-bold text-gray-800 mt-1">{value}</span>
      {subtitle != null && subtitle !== '' && <span className="text-xs text-gray-400 mt-1">{subtitle}</span>}
    </div>
  )
}

function ModuleCard({ title, color, children }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-50 flex items-center gap-2" style={{ borderLeftWidth: 4, borderLeftColor: color }}>
        <span className="text-sm font-semibold text-gray-700">{title}</span>
      </div>
      <div className="p-5">{children}</div>
    </div>
  )
}

export default function LimaGrowthDashboard() {
  const [activeTab, setActiveTab] = useState('resumen')
  const [opportunities, setOpportunities] = useState(null)
  const [config, setConfig] = useState(null)
  const [exports, setExports] = useState(null)
  const [capacityData, setCapacityData] = useState(null)
  const [capacitySource, setCapacitySource] = useState(null)
  const [loading, setLoading] = useState({})
  const [errors, setErrors] = useState({})

  const [editChannels, setEditChannels] = useState(null)
  const [capacitySaving, setCapacitySaving] = useState(false)
  const [priorityAllocation, setPriorityAllocation] = useState(null)
  const [channelAllocation, setChannelAllocation] = useState(null)
  const [worklist, setWorklist] = useState(null)
  const [worklistFilters, setWorklistFilters] = useState({ program: '', channel: '', city: '' })
  const [queue, setQueue] = useState(null)
  const [queueFilters, setQueueFilters] = useState({ status: '', program: '', channel: '' })
  const [buildingQueue, setBuildingQueue] = useState(false)
  const [buildResult, setBuildResult] = useState(null)
  const [opSummary, setOpSummary] = useState(null)
  const [driverState, setDriverState] = useState(null)
  const [programsSummary, setProgramsSummary] = useState(null)

  const today = '2026-06-02'

  const fetchSafely = useCallback(async (key, fn) => {
    setLoading((p) => ({ ...p, [key]: true }))
    setErrors((p) => ({ ...p, [key]: null }))
    try {
      const data = await fn()
      return data
    } catch (e) {
      setErrors((p) => ({ ...p, [key]: e.message || 'Error' }))
      return null
    } finally {
      setLoading((p) => ({ ...p, [key]: false }))
    }
  }, [])

  useEffect(() => {
    fetchSafely('opportunities', () => getLimaGrowthPrioritizedOpportunities({ opportunity_date: today, is_actionable_today: true, limit: 500 })).then(setOpportunities)
    fetchSafely('config', getLoopControlConfig).then(setConfig)
    fetchSafely('exports', () => getLoopControlExports({ limit: 10 })).then(setExports)
    fetchSafely('capacity', () => getLimaGrowthCapacityConfig(today)).then((data) => {
      if (data?.channels?.length) {
        setCapacityData(data)
        setCapacitySource('backend')
      } else {
        setCapacityData(null)
        setCapacitySource('fallback')
      }
    }).catch(() => {
      setCapacityData(null)
      setCapacitySource('fallback')
    })
    fetchSafely('priorityAllocation', () => getLimaGrowthPriorityAllocation(today)).then(setPriorityAllocation)
    fetchSafely('channelAllocation', () => getLimaGrowthChannelAllocation(today)).then(setChannelAllocation)
    fetchSafely('worklist', () => getLimaGrowthOpportunityWorklist({ date: today, limit: 1000 })).then(setWorklist)
    fetchSafely('opSummary', () => getLimaGrowthOperationalSummary(today)).then(setOpSummary)
    fetchSafely('driverState', () => getLimaGrowthDriverStateSummary(today)).then(setDriverState)
    fetchSafely('programsSummary', () => getLimaGrowthProgramsSummary(today)).then(setProgramsSummary)
  }, [fetchSafely])

  const fetchWorklist = useCallback(async (filters = {}) => {
    const params = { date: today }
    if (filters.program) params.program = filters.program
    if (filters.channel) params.channel = filters.channel
    if (filters.city) params.city = filters.city
    const data = await fetchSafely('worklist', () => getLimaGrowthOpportunityWorklist(params))
    if (data) setWorklist(data)
  }, [fetchSafely, today])

  const opps = opportunities?.opportunities || []
  const oppsByProgram = {}
  opps.forEach((o) => { const p = o.selected_program_code; if (!oppsByProgram[p]) oppsByProgram[p] = 0; oppsByProgram[p]++ })

  const exportedCampaigns = (exports || []).filter((e) => e.export_status === 'exported')
  const totalExported = exportedCampaigns.reduce((sum, e) => sum + (e.contacts_inserted || 0), 0)
  const lastExport = exports?.[0]

  const dominantProgram = Object.entries(oppsByProgram).sort((a, b) => b[1] - a[1])[0]
  const dominantProgName = dominantProgram ? PROGRAMAS.find(p => p.code === dominantProgram[0])?.name || dominantProgram[0] : '—'
  const dominantProgCount = dominantProgram ? dominantProgram[1] : 0

  const riskBuckets = {}
  opps.forEach((o) => { const b = o.productivity_bucket || 'Unknown'; if (!riskBuckets[b]) riskBuckets[b] = 0; riskBuckets[b]++ })
  const dominantRisk = Object.entries(riskBuckets).sort((a, b) => b[1] - a[1])[0]

  const actionableCount = opps.filter(o => o.is_actionable_today).length
  const totalOpps = opportunities?.total || opps.length
  const coveragePct = totalOpps > 0 ? Math.round((actionableCount / totalOpps) * 100) : 0

  // ── LG-2.2B Daily Capacity Calculations (backend + fallback) ──
  const activeCapacityChannels = capacityData?.channels?.length
    ? capacityData.channels
    : DEFAULT_CAPACITY_CONFIG
  const totalCapacity = activeCapacityChannels.reduce((sum, c) => sum + ((c.agents || 0) * (c.capacity_per_agent || c.capacityPerAgent || 0)), 0)
  const capacityGap = actionableCount - totalCapacity
  const coverageRate = actionableCount > 0 ? totalCapacity / actionableCount : 0
  const utilizationStatus = coverageRate >= 1 ? 'green' : coverageRate >= 0.7 ? 'yellow' : 'red'

  const engineHealth = {
    loopcontrol: config?.enabled
      ? (opSummary?.loopcontrol_campaigns_exported > 0 ? 'green' : 'yellow')
      : config ? 'yellow' : 'red',
    opportunity: opSummary?.prioritized_total > 0 ? 'green' : opSummary ? 'yellow' : 'red',
    export: opSummary?.loopcontrol_campaigns_exported > 0 ? 'green' : opSummary ? 'yellow' : 'red',
  }

  const healthLabel = { green: 'Operativo', yellow: 'Degradado', red: 'Caido' }
  const healthColor = { green: 'bg-green-400', yellow: 'bg-yellow-400', red: 'bg-red-400' }
  const healthBorder = { green: 'border-green-400', yellow: 'border-yellow-400', red: 'border-red-400' }

  function ExecutiveKpiCard({ label, value, color, subtitle, tooltip }) {
    return (
      <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 relative group" style={{ borderTopWidth: 3, borderTopColor: color }} title={tooltip || ''}>
        <span className="text-xs text-gray-400 uppercase tracking-wide">{label}</span>
        <span className="text-2xl font-bold text-gray-800 mt-1 block">{value}</span>
        {subtitle != null && subtitle !== '' && <span className="text-xs text-gray-400 mt-1 block">{subtitle}</span>}
      </div>
    )
  }

  function HealthDot({ status }) {
    return (
      <span className="flex items-center gap-1.5">
        <span className={`w-2.5 h-2.5 rounded-full ${healthColor[status] || 'bg-gray-300'}`} />
        <span className="text-xs text-gray-500">{healthLabel[status] || status}</span>
      </span>
    )
  }

  function ExecutiveCommandCenter() {
    if (!opportunities && !config && !exports) {
      return (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 text-center">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[#06244a] mx-auto mb-3" />
          <p className="text-sm text-gray-400">Cargando Command Center...</p>
        </div>
      )
    }

    const execSummaryParts = []
    if (totalOpps > 0) execSummaryParts.push(`Lima tiene ${formatNum(totalOpps)} oportunidades accionables`)
    if (dominantProgram) execSummaryParts.push(`El programa dominante es ${dominantProgName} (${formatNum(dominantProgCount)})`)
    if (config?.enabled) execSummaryParts.push('LoopControl esta operativo')
    if (exportedCampaigns.length > 0) execSummaryParts.push(`Se exportaron ${formatNum(totalExported)} contactos en ${formatNum(exportedCampaigns.length)} campanas`)
    if (dominantRisk) execSummaryParts.push(`El riesgo dominante es ${dominantRisk[0]} (${formatNum(dominantRisk[1])} conductores)`)

    if (priorityAllocation?.programs?.length) {
      const allocParts = priorityAllocation.programs.map(p =>
        `${Math.round((p.allocation_rate || 0) * 100)}% de ${p.program_name || p.program_code?.replace('PROGRAM_', '') || '?'}`
      )
      execSummaryParts.push(`Capacidad asignada: ${allocParts.join(', ')}`)
    }
    const execSummary = execSummaryParts.length > 0 ? execSummaryParts.join('. ') + '.' : 'Cargando datos operativos...'

    return (
      <div className="space-y-4">
        {/* ── Executive Summary ── */}
        <div className="bg-gradient-to-r from-[#06244a] to-[#0d3b7a] rounded-2xl p-5 text-white shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <svg className="w-4 h-4 text-white/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                <span className="text-xs font-semibold text-white/70 uppercase tracking-wider">Executive Command Center</span>
              </div>
              <p className="text-sm text-white/90 leading-relaxed max-w-4xl">{execSummary}</p>
            </div>
            <div className="hidden lg:block text-right text-white/50 text-xs">
              {today}
            </div>
          </div>
        </div>

        {/* ── Row 1: KPIs ── */}
        <div className="grid grid-cols-4 gap-3">
          <ExecutiveKpiCard label="Oportunidades Totales" value={formatNum(totalOpps)} color="#1a56db" tooltip="Total de oportunidades priorizadas para hoy" />
          <ExecutiveKpiCard label="Accionables Hoy" value={formatNum(actionableCount)} color="#059669" tooltip="Conductores con is_actionable_today = true" />
          <ExecutiveKpiCard label="Campanas Exportadas" value={formatNum(exportedCampaigns.length)} color="#7c3aed" tooltip="Campanas DRAFT enviadas a LoopControl" />
          <ExecutiveKpiCard label="Contactos Exportados" value={formatNum(totalExported)} color="#d97706" subtitle={`${exportedCampaigns.length} campanas`} tooltip="Total de contactos insertados en LoopControl" />
        </div>

        {/* ── Row 2: Diagnostic ── */}
        <div className="grid grid-cols-4 gap-3">
          <ExecutiveKpiCard
            label="Programa Dominante"
            value={dominantProgName}
            color="#059669"
            subtitle={`${formatNum(dominantProgCount)} conductores`}
            tooltip="Programa con mas conductores accionables hoy"
          />
          <ExecutiveKpiCard
            label="Riesgo Dominante"
            value={dominantRisk ? dominantRisk[0] : '—'}
            color="#dc2626"
            subtitle={dominantRisk ? `${formatNum(dominantRisk[1])} conductores` : ''}
            tooltip="Productivity bucket con mas conductores"
          />
          <ExecutiveKpiCard
            label="Cobertura Operacional"
            value={`${coveragePct}%`}
            color={coveragePct >= 90 ? '#059669' : coveragePct >= 50 ? '#d97706' : '#dc2626'}
            subtitle={`${formatNum(actionableCount)} / ${formatNum(totalOpps)}`}
            tooltip="Porcentaje de oportunidades que son accionables hoy"
          />
          <ExecutiveKpiCard
            label="Estado LoopControl"
            value={config?.mode || '—'}
            color={config?.enabled ? '#059669' : '#dc2626'}
            subtitle={config?.enabled ? 'Integrado' : 'DRY RUN'}
            tooltip="Estado de la integracion con LoopControl"
          />
        </div>

        {/* ── Row 3: Daily Capacity ── */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
          <div className="flex items-center gap-2 mb-3">
            <svg className="w-4 h-4 text-[#0891b2]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Capacidad Diaria</span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ml-auto ${capacitySource === 'backend' ? 'text-green-600 bg-green-50' : 'text-amber-500 bg-amber-50'}`} title={capacitySource === 'backend' ? 'Config desde backend' : 'Fallback: config hardcodeada'}>
              {capacitySource === 'backend' ? 'BACKEND' : 'FALLBACK'}
            </span>
          </div>
          <div className="grid grid-cols-4 gap-3">
            <ExecutiveKpiCard label="Capacidad Total" value={formatNum(totalCapacity)} color="#0891b2" subtitle={`${activeCapacityChannels.length} canales`} tooltip={capacitySource === 'backend' ? 'Capacidad operativa desde backend' : 'Capacidad operativa (fallback hardcodeado)'} />
            <ExecutiveKpiCard label="Accionables Hoy" value={formatNum(actionableCount)} color="#059669" tooltip="Conductores con is_actionable_today = true" />
            <ExecutiveKpiCard label="Gap" value={capacityGap > 0 ? `+${formatNum(capacityGap)}` : formatNum(capacityGap)} color={capacityGap > 0 ? '#dc2626' : '#059669'} subtitle={capacityGap > 0 ? 'Faltan gestiones' : 'Capacidad suficiente'} tooltip="Diferencia entre accionables y capacidad operativa" />
            <ExecutiveKpiCard label="Cobertura" value={`${Math.round(coverageRate * 100)}%`} color={utilizationStatus === 'green' ? '#059669' : utilizationStatus === 'yellow' ? '#d97706' : '#dc2626'} subtitle={utilizationStatus === 'green' ? 'Verde' : utilizationStatus === 'yellow' ? 'Amarillo' : 'Rojo'} tooltip="Capacidad / Accionables" />
          </div>
        </div>

        {/* ── Health Bar ── */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
          <div className="flex items-center gap-6">
            <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Engine Health</span>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50">
                <span className="text-xs text-gray-500">LoopControl</span>
                <HealthDot status={engineHealth.loopcontrol} />
              </div>
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50">
                <span className="text-xs text-gray-500">Opportunity Engine</span>
                <HealthDot status={engineHealth.opportunity} />
              </div>
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50">
                <span className="text-xs text-gray-500">Export Engine</span>
                <HealthDot status={engineHealth.export} />
              </div>
            </div>
            <div className="flex-1" />
            <div className="flex items-center gap-3 text-xs text-gray-400">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-400" /> Operativo</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-yellow-400" /> Degradado</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-400" /> Caido</span>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-screen bg-[#f6f8fb]">
      {/* Sidebar */}
      <aside className="w-56 flex-shrink-0 flex flex-col" style={{ backgroundColor: '#06244a' }}>
        <div className="px-4 py-5 border-b border-white/10">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            <span className="text-white font-semibold text-sm">Lima Growth</span>
          </div>
          <p className="text-xs text-white/50 mt-1">Engine v1.0</p>
        </div>
        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all flex items-center gap-2 ${
                activeTab === tab.id ? 'bg-white/15 text-white font-medium' : 'text-white/60 hover:text-white hover:bg-white/5'
              }`}
            >
              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: tab.color }} />
              {tab.label}
            </button>
          ))}
        </nav>
        <div className="px-3 py-3 border-t border-white/10">
          <div className="flex items-center gap-2 text-xs text-white/40">
            <span className={`w-2 h-2 rounded-full ${config?.enabled ? 'bg-green-400' : 'bg-gray-400'}`} />
            LC: {config?.mode || '...'}
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">
        {/* Top bar */}
        <header className="bg-white border-b border-gray-100 px-6 py-3 flex items-center justify-between sticky top-0 z-10">
          <div>
            <h1 className="text-lg font-bold text-gray-800">YEGO Lima Growth Engine</h1>
            <p className="text-xs text-gray-400">Estado del conductor → Programas → Oportunidades → Ejecucion → Impacto</p>
          </div>
          <div className="flex items-center gap-4 text-xs text-gray-400">
            <span>Fecha: {today}</span>
            <span>Universo: {formatNum(opSummary?.universe_total) || '...'}</span>
            <span>Accionables: {formatNum(opSummary?.actionable_today) || '...'}</span>
          </div>
        </header>

        <div className="p-6">
          {/* ======== RESUMEN ======== */}
          {activeTab === 'resumen' && (
            <div className="space-y-5">
              {/* ── TRUTH BAR: Operational Pipeline ── */}
              {opSummary && (
                <div className="bg-gradient-to-r from-[#06244a] to-[#0d3b7a] rounded-2xl p-5 text-white shadow-md">
                  <div className="flex items-center gap-2 mb-2">
                    <svg className="w-4 h-4 text-white/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                    <span className="text-xs font-semibold text-white/70 uppercase tracking-wider">Pipeline Operacional</span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-white/80 flex-wrap">
                    <span className="bg-white/10 px-2 py-0.5 rounded">Universo: {formatNum(opSummary.universe_total)}</span>
                    <span className="text-white/40">→</span>
                    <span className="bg-white/10 px-2 py-0.5 rounded">Elegibles: {formatNum(opSummary.eligible_total)}</span>
                    <span className="text-white/40">→</span>
                    <span className="bg-white/10 px-2 py-0.5 rounded">Priorizados: {formatNum(opSummary.prioritized_total)}</span>
                    <span className="text-white/40">→</span>
                    <span className="bg-white/20 px-2 py-0.5 rounded font-bold">Accionables: {formatNum(opSummary.actionable_today)}</span>
                  </div>
                </div>
              )}

              {/* ── Row 1: Core Truth KPIs ── */}
              <div className="grid grid-cols-4 gap-3">
                <ExecutiveKpiCard label="Universo Total" value={formatNum(opSummary?.universe_total)} color="#1a56db" tooltip="Total de drivers en el state snapshot mas reciente" />
                <ExecutiveKpiCard label="Priorizados" value={formatNum(opSummary?.prioritized_total)} color="#7c3aed" tooltip="Drivers con programa asignado y ranking definido" />
                <ExecutiveKpiCard label="Accionables Hoy" value={formatNum(opSummary?.actionable_today)} color="#059669" tooltip={`Limitado por daily_action_capacity = ${formatNum(opSummary?.daily_action_capacity)}`} />
                <ExecutiveKpiCard label="Capacidad Diaria" value={formatNum(opSummary?.capacity_total || totalCapacity)} color="#0891b2" tooltip="Capacidad operativa total (agentes x capacidad)" />
              </div>

              {/* ── Row 2: Queue + Export ── */}
              <div className="grid grid-cols-4 gap-3">
                <ExecutiveKpiCard label="En Cola" value={formatNum(opSummary?.queue_total)} color="#d97706" subtitle={`${formatNum(opSummary?.queue_ready)} READY / ${formatNum(opSummary?.queue_held)} HELD`} tooltip="Registros en assignment queue" />
                <ExecutiveKpiCard label="Contactos Exportados" value={formatNum(opSummary?.loopcontrol_contacts_inserted)} color="#7c3aed" subtitle={`${formatNum(opSummary?.loopcontrol_campaigns_exported)} campanas`} tooltip="Total de contactos insertados en LoopControl" />
                <ExecutiveKpiCard label="LoopControl" value={config?.mode || '...'} color={config?.enabled ? '#059669' : '#dc2626'} subtitle={config?.enabled ? 'Integrado' : 'DRY RUN'} tooltip="Estado de la integracion" />
                <ExecutiveKpiCard label="Gap Capacidad" value={opSummary ? formatNum(opSummary.actionable_today - (opSummary.capacity_total || totalCapacity)) : '...'} color={(opSummary?.actionable_today || 0) > (opSummary?.capacity_total || totalCapacity) ? '#dc2626' : '#059669'} tooltip="Accionables - Capacidad" />
              </div>

              {/* ── Capacity explanation ── */}
              {opSummary && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-3 text-sm text-yellow-800">
                  <span className="font-medium">Accionables hoy ({formatNum(opSummary.actionable_today)})</span> estan limitados por <span className="font-mono bg-yellow-100 px-1 rounded">daily_action_capacity = {formatNum(opSummary.daily_action_capacity)}</span>. 
                  Universo total: {formatNum(opSummary.universe_total)}, elegibles: {formatNum(opSummary.eligible_total)}, priorizados: {formatNum(opSummary.prioritized_total)}.
                </div>
              )}

              {/* ── By Program Distribution ── */}
              {opSummary?.by_program && (
                <ModuleCard title="Distribucion por Programa (Priorizados)" color="#7c3aed">
                  <div className="grid grid-cols-4 gap-3">
                    {opSummary.by_program.map((p) => (
                      <div key={p.program_code} className="bg-gray-50 rounded-xl p-3 text-center">
                        <span className="text-xl font-bold text-gray-800">{formatNum(p.prioritized)}</span>
                        <p className="text-xs text-gray-500 mt-1">{p.program_code.replace('PROGRAM_', '')}</p>
                      </div>
                    ))}
                  </div>
                </ModuleCard>
              )}

              {/* ── Engine Health ── */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
                <div className="flex items-center gap-6">
                  <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Engine Health</span>
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50">
                      <span className="text-xs text-gray-500">LoopControl</span>
                      <HealthDot status={engineHealth.loopcontrol} />
                    </div>
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50">
                      <span className="text-xs text-gray-500">Opportunity Engine</span>
                      <HealthDot status={engineHealth.opportunity} />
                    </div>
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50">
                      <span className="text-xs text-gray-500">Export Engine</span>
                      <HealthDot status={engineHealth.export} />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ======== ESTADO DEL CONDUCTOR ======== */}
          {activeTab === 'estado' && (
            <div className="space-y-5">
              {driverState ? (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <ExecutiveKpiCard label="Total Drivers" value={formatNum(driverState.total_drivers)} color="#1a56db" tooltip="Drivers en el state snapshot mas reciente" />
                    <ExecutiveKpiCard label="Snapshot Date" value={driverState.latest_date} color="#0891b2" tooltip="Fecha del ultimo snapshot de estado" />
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    <ModuleCard title="Lifecycle State" color="#1a56db">
                      <div className="space-y-1.5">
                        {(driverState.by_lifecycle_state || []).map((s) => {
                          const pct = driverState.total_drivers > 0 ? Math.round((s.count / driverState.total_drivers) * 100) : 0
                          return (
                            <div key={s.state}>
                              <div className="flex justify-between text-xs mb-0.5"><span className="text-gray-600">{s.state}</span><span className="font-medium text-gray-700">{formatNum(s.count)} ({pct}%)</span></div>
                              <div className="w-full bg-gray-200 rounded-full h-1.5"><div className="h-1.5 rounded-full bg-[#1a56db]" style={{ width: `${pct}%` }} /></div>
                            </div>
                          )
                        })}
                      </div>
                    </ModuleCard>
                    <ModuleCard title="Performance State" color="#059669">
                      <div className="space-y-1.5">
                        {(driverState.by_performance_state || []).map((s) => {
                          const pct = driverState.total_drivers > 0 ? Math.round((s.count / driverState.total_drivers) * 100) : 0
                          return (
                            <div key={s.state}>
                              <div className="flex justify-between text-xs mb-0.5"><span className="text-gray-600">{s.state}</span><span className="font-medium text-gray-700">{formatNum(s.count)} ({pct}%)</span></div>
                              <div className="w-full bg-gray-200 rounded-full h-1.5"><div className="h-1.5 rounded-full bg-[#059669]" style={{ width: `${pct}%` }} /></div>
                            </div>
                          )
                        })}
                      </div>
                    </ModuleCard>
                    <ModuleCard title="Retention State" color="#dc2626">
                      <div className="space-y-1.5">
                        {(driverState.by_retention_state || []).map((s) => {
                          const pct = driverState.total_drivers > 0 ? Math.round((s.count / driverState.total_drivers) * 100) : 0
                          return (
                            <div key={s.state}>
                              <div className="flex justify-between text-xs mb-0.5"><span className="text-gray-600">{s.state}</span><span className="font-medium text-gray-700">{formatNum(s.count)} ({pct}%)</span></div>
                              <div className="w-full bg-gray-200 rounded-full h-1.5"><div className="h-1.5 rounded-full bg-[#dc2626]" style={{ width: `${pct}%` }} /></div>
                            </div>
                          )
                        })}
                      </div>
                    </ModuleCard>
                  </div>
                </>
              ) : (
                <EmptyState title="Cargando estado del conductor..." />
              )}
            </div>
          )}

          {/* ======== PROGRAMAS ======== */}
          {activeTab === 'programas' && (
            <div className="space-y-4">
              {programsSummary ? (
                <>
                  <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 text-sm text-blue-800">
                    Programas actualmente definidos en <span className="font-mono bg-blue-100 px-1 rounded">STATIC_REGISTRY</span>. Program Builder pendiente P2.
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    {(programsSummary.programs || []).map((prog) => {
                      const eligible = prog.eligible_total || prog.total || 0
                      const prioritized = prog.prioritized_total || 0
                      const actionable = prog.actionable_today || 0
                      const queued = prog.queued_total || 0
                      const exported = prog.exported_total || 0
                      return (
                      <ModuleCard key={prog.program_code} title={`${prog.program_code.replace('PROGRAM_', '')} — P${prog.priority_rank || '?'}`} color={prog.color || '#059669'}>
                        <div className="grid grid-cols-3 gap-2 text-center">
                          <div className="bg-gray-50 rounded-lg p-2">
                            <span className="text-lg font-bold text-gray-800">{formatNum(eligible)}</span>
                            <p className="text-[10px] text-gray-400">Elegibles</p>
                          </div>
                          <div className="bg-gray-50 rounded-lg p-2">
                            <span className="text-lg font-bold text-gray-800">{formatNum(prioritized)}</span>
                            <p className="text-[10px] text-gray-400">Priorizados</p>
                          </div>
                          <div className="bg-gray-50 rounded-lg p-2">
                            <span className="text-lg font-bold text-gray-800">{formatNum(actionable)}</span>
                            <p className="text-[10px] text-gray-400">Accionables</p>
                          </div>
                          <div className="bg-gray-50 rounded-lg p-2">
                            <span className="text-lg font-bold text-gray-800">{formatNum(queued)}</span>
                            <p className="text-[10px] text-gray-400">En Cola</p>
                          </div>
                          <div className="bg-gray-50 rounded-lg p-2">
                            <span className="text-lg font-bold text-gray-800">{formatNum(exported)}</span>
                            <p className="text-[10px] text-gray-400">Exportados</p>
                          </div>
                          <div className="bg-gray-50 rounded-lg p-2 flex items-center justify-center">
                            <span className={`px-2 py-1 rounded text-xs font-medium ${eligible > 0 ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                              {prog.status || 'ACTIVO'}
                            </span>
                          </div>
                        </div>
                        <div className="mt-2 text-[10px] text-gray-400 text-right">source: {prog.source || 'STATIC_REGISTRY'}</div>
                      </ModuleCard>
                      )
                    })}
                  </div>
                </>
              ) : (
                <EmptyState title="Cargando programas..." />
              )}
            </div>
          )}

          {/* ======== OPORTUNIDADES ======== */}
          {activeTab === 'oportunidades' && (
            <ModuleCard title="Daily Opportunity Lists" color="#d97706">
              {!opps.length ? (
                <EmptyState title="Cargando oportunidades..." />
              ) : (
                <div className="space-y-3">
                  <div className="grid grid-cols-4 gap-3">
                    {PROGRAMAS.map((prog) => {
                      const count = oppsByProgram[prog.code] || 0
                      return (
                        <div key={prog.code} className="bg-gray-50 rounded-xl p-3 text-center">
                          <span className="text-2xl font-bold" style={{ color: prog.color }}>{formatNum(count)}</span>
                          <p className="text-xs text-gray-500 mt-1">{prog.name}</p>
                        </div>
                      )
                    })}
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-gray-100 text-gray-400">
                          <th className="text-left py-2 font-medium">Rank</th>
                          <th className="text-left py-2 font-medium">Driver ID</th>
                          <th className="text-left py-2 font-medium">Programa</th>
                          <th className="text-left py-2 font-medium">Lifecycle</th>
                          <th className="text-left py-2 font-medium">Performance</th>
                          <th className="text-left py-2 font-medium">Score</th>
                          <th className="text-left py-2 font-medium">Bucket</th>
                        </tr>
                      </thead>
                      <tbody>
                        {opps.slice(0, 20).map((o, i) => (
                          <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                            <td className="py-2 font-medium text-gray-600">{o.final_rank}</td>
                            <td className="py-2 text-gray-500 font-mono">{o.driver_profile_id?.slice(0, 12)}...</td>
                            <td className="py-2">
                              <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700">{o.selected_program_code?.replace('PROGRAM_', '')}</span>
                            </td>
                            <td className="py-2 text-gray-600">{o.lifecycle_state}</td>
                            <td className="py-2 text-gray-600">{o.performance_state}</td>
                            <td className="py-2 font-medium text-gray-700">{Number(o.opportunity_score)?.toFixed?.(1) || '—'}</td>
                            <td className="py-2 text-gray-500">{o.productivity_bucket}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </ModuleCard>
          )}

          {/* ======== EJECUCION LOOPCONTROL ======== */}
          {activeTab === 'loopcontrol' && (
            <div className="space-y-4">
              <div className="grid grid-cols-4 gap-3">
                <KpiCard label="Campanas Exportadas" value={formatNum(exportedCampaigns.length)} color="#7c3aed" />
                <KpiCard label="Contactos Totales" value={formatNum(totalExported)} color="#059669" />
                <KpiCard label="Ultimo Campaign ID" value={lastExport?.campaign_id_external || '—'} color="#1a56db" />
                <KpiCard label="LC Mode" value={config?.mode || '...'} color={config?.enabled ? '#059669' : '#dc2626'} />
              </div>
              <ModuleCard title="Export History" color="#7c3aed">
                {!exports?.length ? (
                  <EmptyState title="Sin exports registrados" />
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-gray-100 text-gray-400">
                          <th className="text-left py-2 font-medium">Fecha</th>
                          <th className="text-left py-2 font-medium">Campana</th>
                          <th className="text-left py-2 font-medium">LC ID</th>
                          <th className="text-left py-2 font-medium">Programa</th>
                          <th className="text-left py-2 font-medium">Enviados</th>
                          <th className="text-left py-2 font-medium">Insertados</th>
                          <th className="text-left py-2 font-medium">Saltados</th>
                          <th className="text-left py-2 font-medium">Estado</th>
                        </tr>
                      </thead>
                      <tbody>
                        {exports.map((e) => (
                          <tr key={e.export_id} className="border-b border-gray-50 hover:bg-gray-50">
                            <td className="py-2 text-gray-500">{formatDate(e.exported_at)}</td>
                            <td className="py-2 font-medium text-gray-700">{e.campaign_name}</td>
                            <td className="py-2 text-gray-500 font-mono">{e.campaign_id_external || '—'}</td>
                            <td className="py-2"><span className="px-1.5 py-0.5 rounded text-xs bg-purple-50 text-purple-700">{e.program_code?.replace('PROGRAM_', '')}</span></td>
                            <td className="py-2 text-gray-600">{e.contacts_sent}</td>
                            <td className="py-2 font-medium text-green-600">{e.contacts_inserted}</td>
                            <td className="py-2 text-gray-500">{e.contacts_skipped}</td>
                            <td className="py-2"><StatusPill status={e.export_status} /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </ModuleCard>
            </div>
          )}

          {/* ======== IMPACTO ======== */}
          {activeTab === 'impacto' && (
            <ModuleCard title="Impacto de Campanas LoopControl" color="#059669">
              <EmptyState title="No certificada — Pendiente LC-2" message="Result Sync debe implementarse primero. Cuando el endpoint de resultados de Miguel este disponible, aqui se mostraran metricas de impacto real." />
            </ModuleCard>
          )}

          {/* ======== MOVIMIENTO ======== */}
          {activeTab === 'movimiento' && (
            <ModuleCard title="Movimiento de Conductores" color="#7c3aed">
              <EmptyState title="No certificada — Pendiente LC-2" message="Los datos de transicion entre segmentos (migration) se integraran cuando el pipeline de serving facts este estable." />
            </ModuleCard>
          )}

          {/* ======== ATRIBUCION ======== */}
          {activeTab === 'atribucion' && (
            <ModuleCard title="Atribucion de Impacto" color="#0891b2">
              <EmptyState title="No certificada — Pendiente LC-2" message="Atribucion por agente, campana e iniciativa requiere Result Sync funcional. Pendiente de implementacion." />
            </ModuleCard>
          )}

          {/* ======== WORKLIST ======== */}
          {activeTab === 'worklist' && (
            <div className="space-y-4">
              {/* Filters */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Filtros</span>
                  <select
                    value={worklistFilters.program}
                    onChange={(e) => { const f = { ...worklistFilters, program: e.target.value }; setWorklistFilters(f); fetchWorklist(f) }}
                    className="text-xs border border-gray-200 rounded-lg px-3 py-1.5 text-gray-600"
                  >
                    <option value="">Todos los programas</option>
                    {['PROGRAM_HIGH_VALUE_RECOVERY', 'PROGRAM_CHURN_PREVENTION', 'PROGRAM_14_90', 'PROGRAM_ACTIVE_GROWTH'].map(p => (
                      <option key={p} value={p}>{p.replace('PROGRAM_', '')}</option>
                    ))}
                  </select>
                  <select
                    value={worklistFilters.channel}
                    onChange={(e) => { const f = { ...worklistFilters, channel: e.target.value }; setWorklistFilters(f); fetchWorklist(f) }}
                    className="text-xs border border-gray-200 rounded-lg px-3 py-1.5 text-gray-600"
                  >
                    <option value="">Todos los canales</option>
                    <option value="CALL_CENTER">Call Center</option>
                    <option value="SAC">SAC</option>
                    <option value="BOT">Bot / WhatsApp</option>
                    <option value="UNASSIGNED">Sin canal</option>
                  </select>
                  <input
                    type="text"
                    placeholder="Ciudad..."
                    value={worklistFilters.city}
                    onChange={(e) => { const f = { ...worklistFilters, city: e.target.value }; setWorklistFilters(f); fetchWorklist(f) }}
                    className="text-xs border border-gray-200 rounded-lg px-3 py-1.5 text-gray-600 w-32"
                  />
                  <div className="flex-1" />
                  <span className="text-xs text-gray-400">
                    {worklist ? formatNum(worklist.total_records) : '...'} registros
                  </span>
                </div>
              </div>

              {/* Table */}
              {!worklist ? (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 text-center">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[#06244a] mx-auto mb-3" />
                  <p className="text-sm text-gray-400">Cargando worklist...</p>
                </div>
              ) : !worklist.records?.length ? (
                <EmptyState title="Sin registros" message="No se encontraron conductores accionables con los filtros actuales." />
              ) : (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-gray-100 text-gray-400 bg-gray-50">
                          <th className="text-left py-2.5 px-3 font-medium">Nombre</th>
                          <th className="text-left py-2.5 px-3 font-medium">Telefono</th>
                          <th className="text-left py-2.5 px-3 font-medium">Programa</th>
                          <th className="text-left py-2.5 px-3 font-medium w-8">P</th>
                          <th className="text-left py-2.5 px-3 font-medium">Canal</th>
                          <th className="text-left py-2.5 px-3 font-medium">Motivo</th>
                          <th className="text-left py-2.5 px-3 font-medium">Ultimo Viaje</th>
                          <th className="text-left py-2.5 px-3 font-medium">Viajes Rec.</th>
                          <th className="text-left py-2.5 px-3 font-medium">Ciudad</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(worklist.records || []).map((r, i) => (
                          <tr key={r.driver_id || i} className="border-b border-gray-50 hover:bg-gray-50">
                            <td className="py-2 px-3 font-medium text-gray-700">{r.driver_name}</td>
                            <td className="py-2 px-3 text-gray-500 font-mono">{r.phone || '—'}</td>
                            <td className="py-2 px-3">
                              <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700">{r.program_code?.replace('PROGRAM_', '')}</span>
                            </td>
                            <td className="py-2 px-3 text-gray-400">P{r.priority_rank}</td>
                            <td className="py-2 px-3">
                              <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                                r.assigned_channel === 'CALL_CENTER' ? 'bg-blue-50 text-blue-700' :
                                r.assigned_channel === 'SAC' ? 'bg-purple-50 text-purple-700' :
                                r.assigned_channel === 'BOT' ? 'bg-cyan-50 text-cyan-700' :
                                'bg-red-50 text-red-700'
                              }`}>
                                {r.assigned_channel === 'CALL_CENTER' ? 'Call Center' :
                                 r.assigned_channel === 'SAC' ? 'SAC' :
                                 r.assigned_channel === 'BOT' ? 'Bot' : 'Sin canal'}
                              </span>
                            </td>
                            <td className="py-2 px-3 text-gray-500 max-w-[200px] truncate" title={r.opportunity_reason}>{r.opportunity_reason}</td>
                            <td className="py-2 px-3 text-gray-500">{r.last_trip_date || '—'}</td>
                            <td className="py-2 px-3 text-gray-700 font-medium">{r.recent_trips}</td>
                            <td className="py-2 px-3 text-gray-500">{r.city}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ======== ASSIGNMENT QUEUE ======== */}
          {activeTab === 'assignment_queue' && (
            <div className="space-y-4">
              {/* KPIs + Build Button */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
                <div className="flex items-center justify-between flex-wrap gap-3">
                  <div className="flex items-center gap-4">
                    <div className="text-center px-3">
                      <span className="text-xl font-bold text-gray-800">{queue ? formatNum(queue.total_records) : '—'}</span>
                      <p className="text-xs text-gray-400">En Cola</p>
                    </div>
                    <div className="text-center px-3">
                      <span className="text-xl font-bold text-green-600">{queue ? formatNum(queue.ready_count) : '—'}</span>
                      <p className="text-xs text-gray-400">READY</p>
                    </div>
                    <div className="text-center px-3">
                      <span className="text-xl font-bold text-yellow-600">{queue ? formatNum(queue.held_count) : '—'}</span>
                      <p className="text-xs text-gray-400">HELD</p>
                    </div>
                    {buildResult && (
                      <div className="text-center px-3 border-l border-gray-200">
                        <span className="text-xs text-gray-400">Ultimo build</span>
                        <p className="text-xs text-gray-500">+{buildResult.created_count} creados, {buildResult.skipped_duplicates} dup</p>
                      </div>
                    )}
                  </div>
                  <button
                    onClick={async () => {
                      setBuildingQueue(true)
                      try {
                        const result = await buildLimaGrowthAssignmentQueue(today)
                        setBuildResult(result)
                        const q = await fetchSafely('queue', () => getLimaGrowthAssignmentQueue({ date: today }))
                        if (q) setQueue(q)
                      } catch (e) {
                        setErrors((p) => ({ ...p, queue: e.message || 'Error al construir cola' }))
                      } finally {
                        setBuildingQueue(false)
                      }
                    }}
                    disabled={buildingQueue}
                    className="text-xs bg-[#d97706] text-white px-4 py-2 rounded-lg hover:bg-[#b65c00] disabled:opacity-50 font-medium"
                  >
                    {buildingQueue ? 'Construyendo...' : 'Construir cola del dia'}
                  </button>
                </div>
              </div>

              {/* Filters */}
              <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-3">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Filtros</span>
                  <select
                    value={queueFilters.status}
                    onChange={(e) => {
                      const f = { ...queueFilters, status: e.target.value }
                      setQueueFilters(f)
                      getLimaGrowthAssignmentQueue({ date: today, status: f.status || undefined, program: f.program || undefined, channel: f.channel || undefined }).then(setQueue).catch(() => {})
                    }}
                    className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 text-gray-600"
                  >
                    <option value="">Todos</option>
                    <option value="READY">READY</option>
                    <option value="HELD">HELD</option>
                  </select>
                  <select
                    value={queueFilters.program}
                    onChange={(e) => {
                      const f = { ...queueFilters, program: e.target.value }
                      setQueueFilters(f)
                      getLimaGrowthAssignmentQueue({ date: today, status: f.status || undefined, program: f.program || undefined, channel: f.channel || undefined }).then(setQueue)
                    }}
                    className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 text-gray-600"
                  >
                    <option value="">Todos los programas</option>
                    {['PROGRAM_HIGH_VALUE_RECOVERY', 'PROGRAM_CHURN_PREVENTION', 'PROGRAM_14_90', 'PROGRAM_ACTIVE_GROWTH'].map(p => (
                      <option key={p} value={p}>{p.replace('PROGRAM_', '')}</option>
                    ))}
                  </select>
                  <select
                    value={queueFilters.channel}
                    onChange={(e) => {
                      const f = { ...queueFilters, channel: e.target.value }
                      setQueueFilters(f)
                      getLimaGrowthAssignmentQueue({ date: today, status: f.status || undefined, program: f.program || undefined, channel: f.channel || undefined }).then(setQueue)
                    }}
                    className="text-xs border border-gray-200 rounded-lg px-2 py-1.5 text-gray-600"
                  >
                    <option value="">Todos los canales</option>
                    <option value="CALL_CENTER">Call Center</option>
                    <option value="SAC">SAC</option>
                    <option value="BOT">Bot</option>
                    <option value="UNASSIGNED">Sin canal</option>
                  </select>
                </div>
              </div>

              {/* Table */}
              {!queue ? (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-8 text-center">
                  <p className="text-sm text-gray-400">Usa "Construir cola del dia" para generar la cola.</p>
                </div>
              ) : !queue.records?.length ? (
                <EmptyState title="Sin registros" message="No hay conductores en la cola con los filtros actuales." />
              ) : (
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-gray-100 text-gray-400 bg-gray-50">
                          <th className="text-left py-2.5 px-3 font-medium">Nombre</th>
                          <th className="text-left py-2.5 px-3 font-medium">Telefono</th>
                          <th className="text-left py-2.5 px-3 font-medium">Programa</th>
                          <th className="text-left py-2.5 px-3 font-medium w-8">P</th>
                          <th className="text-left py-2.5 px-3 font-medium">Canal</th>
                          <th className="text-left py-2.5 px-3 font-medium">Estado</th>
                          <th className="text-left py-2.5 px-3 font-medium">Motivo</th>
                          <th className="text-left py-2.5 px-3 font-medium">Ultimo Viaje</th>
                          <th className="text-left py-2.5 px-3 font-medium">Viajes Rec.</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(queue.records || []).map((r, i) => (
                          <tr key={r.id || i} className="border-b border-gray-50 hover:bg-gray-50">
                            <td className="py-2 px-3 font-medium text-gray-700">{r.driver_name || '—'}</td>
                            <td className="py-2 px-3 text-gray-500 font-mono">{r.phone || '—'}</td>
                            <td className="py-2 px-3">
                              <span className="px-1.5 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700">{r.program_code?.replace('PROGRAM_', '')}</span>
                            </td>
                            <td className="py-2 px-3 text-gray-400">{r.priority_rank ? `P${r.priority_rank}` : '—'}</td>
                            <td className="py-2 px-3">
                              <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                                r.assigned_channel === 'CALL_CENTER' ? 'bg-blue-50 text-blue-700' :
                                r.assigned_channel === 'SAC' ? 'bg-purple-50 text-purple-700' :
                                r.assigned_channel === 'BOT' ? 'bg-cyan-50 text-cyan-700' :
                                'bg-red-50 text-red-700'
                              }`}>
                                {r.assigned_channel === 'CALL_CENTER' ? 'Call Center' :
                                 r.assigned_channel === 'SAC' ? 'SAC' :
                                 r.assigned_channel === 'BOT' ? 'Bot' : 'Sin canal'}
                              </span>
                            </td>
                            <td className="py-2 px-3">
                              <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                                r.queue_status === 'READY' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                              }`}>
                                {r.queue_status}
                              </span>
                            </td>
                            <td className="py-2 px-3 text-gray-500 max-w-[200px] truncate" title={r.opportunity_reason}>{r.opportunity_reason || '—'}</td>
                            <td className="py-2 px-3 text-gray-500">{r.last_trip_date || '—'}</td>
                            <td className="py-2 px-3 text-gray-700 font-medium">{r.recent_trips ?? '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ======== CONFIGURACION ======== */}
          {activeTab === 'config' && (
            <div className="space-y-5">
              {/* Policy Config */}
              {opSummary && (
                <ModuleCard title="Politica de Oportunidades" color="#1a56db">
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div className="bg-gray-50 rounded-xl p-3">
                      <span className="text-xs text-gray-400">Daily Action Capacity</span>
                      <p className="font-bold text-gray-800 mt-0.5 text-lg">{formatNum(opSummary.daily_action_capacity)}</p>
                    </div>
                    <div className="bg-gray-50 rounded-xl p-3">
                      <span className="text-xs text-gray-400">Accionables Hoy</span>
                      <p className="font-bold text-gray-800 mt-0.5 text-lg">{formatNum(opSummary.actionable_today)}</p>
                    </div>
                    <div className="bg-gray-50 rounded-xl p-3">
                      <span className="text-xs text-gray-400">Priorizados Totales</span>
                      <p className="font-bold text-gray-800 mt-0.5 text-lg">{formatNum(opSummary.prioritized_total)}</p>
                    </div>
                  </div>
                </ModuleCard>
              )}

              <ModuleCard title="LoopControl Integration" color="#7c3aed">
                {config ? (
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    {[
                      ['Estado', config.enabled ? 'LIVE' : 'DRY_RUN'],
                      ['Base URL', config.base_url_configured ? 'Configurada' : 'Falta'],
                      ['Integration Key', config.integration_key_configured ? 'Configurada' : 'Falta'],
                      ['Mode', config.mode],
                      ['Issues', config.issues?.length ? config.issues.join(', ') : 'Ninguno'],
                    ].map(([label, value], i) => (
                      <div key={i} className="bg-gray-50 rounded-xl p-3">
                        <span className="text-xs text-gray-400">{label}</span>
                        <p className="font-medium text-gray-700 mt-0.5">{String(value)}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState title="Cargando configuracion..." />
                )}
              </ModuleCard>

              {/* ── LG-2.2B: Capacidad Operativa ── */}
              <ModuleCard title="Capacidad Operativa" color="#0891b2">
                {(() => {
                  const channelsForEdit = editChannels || activeCapacityChannels.map(ch => ({ ...ch, capacity_per_agent: ch.capacity_per_agent || ch.capacityPerAgent }))

                  const handleEditChange = (idx, field, value) => {
                    const next = [...channelsForEdit]
                    next[idx] = { ...next[idx], [field]: field === 'agents' || field === 'capacity_per_agent' ? parseInt(value) || 0 : value }
                    setEditChannels(next)
                  }

                  const handleSave = async () => {
                    setCapacitySaving(true)
                    try {
                      const payload = {
                        config_date: today,
                        channels: channelsForEdit.map(ch => ({
                          channel: ch.channel,
                          agents: ch.agents,
                          capacity_per_agent: ch.capacity_per_agent,
                        })),
                      }
                      const result = await updateLimaGrowthCapacityConfig(payload)
                      setCapacityData(result)
                      setCapacitySource('backend')
                      setEditChannels(null)
                    } catch (e) {
                      alert('Error al guardar: ' + (e.message || 'Error desconocido'))
                    } finally {
                      setCapacitySaving(false)
                    }
                  }

                  return (
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-xs text-gray-400">Configuracion de capacidad operativa diaria por canal</span>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setEditChannels(null)}
                            className="text-xs text-gray-400 hover:text-gray-600 px-2 py-1 rounded"
                          >
                            Cancelar
                          </button>
                          <button
                            onClick={handleSave}
                            disabled={capacitySaving}
                            className="text-xs bg-[#0891b2] text-white px-3 py-1.5 rounded-lg hover:bg-[#067a96] disabled:opacity-50"
                          >
                            {capacitySaving ? 'Guardando...' : 'Guardar configuracion'}
                          </button>
                        </div>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs">
                          <thead>
                            <tr className="border-b border-gray-100 text-gray-400">
                              <th className="text-left py-2 font-medium">Canal</th>
                              <th className="text-left py-2 font-medium">Agentes</th>
                              <th className="text-left py-2 font-medium">Capacidad / Agente</th>
                              <th className="text-left py-2 font-medium">Capacidad Total</th>
                            </tr>
                          </thead>
                          <tbody>
                            {channelsForEdit.map((ch, idx) => {
                              const total = (ch.agents || 0) * (ch.capacity_per_agent || 0)
                              return (
                                <tr key={ch.channel} className="border-b border-gray-50">
                                  <td className="py-2 font-medium text-gray-700">{ch.channel}</td>
                                  <td className="py-2">
                                    <input
                                      type="number"
                                      min={0}
                                      value={ch.agents}
                                      onChange={(e) => handleEditChange(idx, 'agents', e.target.value)}
                                      className="w-16 px-2 py-1 border border-gray-200 rounded text-gray-700 text-xs"
                                    />
                                  </td>
                                  <td className="py-2">
                                    <input
                                      type="number"
                                      min={0}
                                      value={ch.capacity_per_agent}
                                      onChange={(e) => handleEditChange(idx, 'capacity_per_agent', e.target.value)}
                                      className="w-20 px-2 py-1 border border-gray-200 rounded text-gray-700 text-xs"
                                    />
                                  </td>
                                  <td className="py-2 font-bold text-gray-800">{formatNum(total)}</td>
                                </tr>
                              )
                            })}
                            <tr className="bg-gray-50">
                              <td className="py-2 font-semibold text-gray-700">TOTAL</td>
                              <td className="py-2 text-gray-500">{channelsForEdit.reduce((s, c) => s + (c.agents || 0), 0)}</td>
                              <td className="py-2" />
                              <td className="py-2 font-bold text-gray-800">{formatNum(channelsForEdit.reduce((s, c) => s + (c.agents || 0) * (c.capacity_per_agent || 0), 0))}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )
                })()}
              </ModuleCard>

              <ModuleCard title="Opportunity Policy" color="#d97706">
                <EmptyState title="Configuracion de politicas" message="Los thresholds de opportunity policy (daily_action_capacity, weekly_trips_target, etc.) se cargaran cuando el endpoint de configuracion este disponible." />
              </ModuleCard>

              <ModuleCard title="Program Thresholds" color="#059669">
                <div className="grid grid-cols-2 gap-3">
                  {PROGRAMAS.map((prog) => (
                    <div key={prog.code} className="bg-gray-50 rounded-xl p-3 flex items-center justify-between">
                      <div>
                        <span className="text-sm font-medium text-gray-700">{prog.name}</span>
                        <p className="text-xs text-gray-400">{prog.objetivo}</p>
                      </div>
                      <span className="text-xs text-gray-400">Proximamente editable</span>
                    </div>
                  ))}
                </div>
              </ModuleCard>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
