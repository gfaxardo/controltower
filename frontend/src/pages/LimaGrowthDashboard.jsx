import { useState, useEffect, useCallback } from 'react'
import {
  getLimaGrowthPrioritizedOpportunities,
  getLoopControlConfig,
  getLoopControlExports,
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
  { id: 'config', label: 'Configuracion', color: '#4b5563' },
]

const PROGRAMAS = [
  { code: 'PROGRAM_14_90', name: '14/90', objetivo: 'Nuevos conductores a 50 viajes en 14 dias', color: '#0891b2' },
  { code: 'PROGRAM_ACTIVE_GROWTH', name: 'Active Growth', objetivo: 'Incrementar viajes en activos', color: '#059669' },
  { code: 'PROGRAM_CHURN_PREVENTION', name: 'Churn Prevention', objetivo: 'Evitar fuga de conductores', color: '#dc2626' },
  { code: 'PROGRAM_HIGH_VALUE_RECOVERY', name: 'High Value Recovery', objetivo: 'Recuperar conductores de alto valor', color: '#d97706' },
]

function formatNum(n) { if (n == null) return '—'; return Number(n).toLocaleString('es-PE') }
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
      {subtitle && <span className="text-xs text-gray-400 mt-1">{subtitle}</span>}
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
  const [loading, setLoading] = useState({})
  const [errors, setErrors] = useState({})

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
  }, [fetchSafely])

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

  const engineHealth = {
    loopcontrol: config?.enabled ? 'green' : config ? 'yellow' : 'red',
    opportunity: opportunities ? 'green' : 'red',
    export: exportedCampaigns.length > 0 ? 'green' : 'yellow',
  }

  const healthLabel = { green: 'Operativo', yellow: 'Degradado', red: 'Caido' }
  const healthColor = { green: 'bg-green-400', yellow: 'bg-yellow-400', red: 'bg-red-400' }
  const healthBorder = { green: 'border-green-400', yellow: 'border-yellow-400', red: 'border-red-400' }

  function ExecutiveKpiCard({ label, value, color, subtitle, tooltip }) {
    return (
      <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 relative group" style={{ borderTopWidth: 3, borderTopColor: color }} title={tooltip || ''}>
        <span className="text-xs text-gray-400 uppercase tracking-wide">{label}</span>
        <span className="text-2xl font-bold text-gray-800 mt-1 block">{value}</span>
        {subtitle && <span className="text-xs text-gray-400 mt-1 block">{subtitle}</span>}
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
            <span>Oportunidades: {opportunities?.total || '...'}</span>
          </div>
        </header>

        <div className="p-6">
          {/* ======== RESUMEN ======== */}
          {activeTab === 'resumen' && (
            <div className="space-y-5">
              <ExecutiveCommandCenter />
              <div className="grid grid-cols-4 gap-3">
                <KpiCard label="Oportunidades Totales" value={formatNum(opportunities?.total)} color="#1a56db" />
                <KpiCard label="Accionables Hoy" value={formatNum(opps.filter(o => o.is_actionable_today).length)} color="#059669" />
                <KpiCard label="Exportados a LC" value={formatNum(totalExported)} color="#7c3aed" subtitle={`${exportedCampaigns.length} campanas`} />
                <KpiCard label="Contact Rate Est." value="—" color="#0891b2" subtitle="Pendiente LC-2" />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <ModuleCard title="Lo que queremos lograr" color="#059669">
                  <div className="space-y-2">
                    {[
                      { label: 'Objetivo A', desc: 'Nuevos conductores hagan 50 viajes en 14 dias', color: '#0891b2' },
                      { label: 'Objetivo B', desc: 'Conductores permanezcan activos 90 dias', color: '#059669' },
                      { label: 'Objetivo C', desc: 'Conductores activos incrementen viajes semanales', color: '#1a56db' },
                      { label: 'Objetivo D', desc: 'Conductores en riesgo no abandonen la plataforma', color: '#dc2626' },
                    ].map((o, i) => (
                      <div key={i} className="flex items-start gap-2 text-sm">
                        <span className="w-2 h-2 rounded-full mt-1.5 flex-shrink-0" style={{ backgroundColor: o.color }} />
                        <div><span className="font-medium text-gray-700">{o.label}:</span> <span className="text-gray-500">{o.desc}</span></div>
                      </div>
                    ))}
                  </div>
                </ModuleCard>

                <div className="space-y-4">
                  <ModuleCard title="Problema del modelo anterior" color="#dc2626">
                    <p className="text-sm text-gray-600">Antes mezclabamos segmentos, programas y listas. Un mismo conductor podia estar en todo al mismo tiempo. Sin trazabilidad de accion a impacto.</p>
                  </ModuleCard>
                  <ModuleCard title="Nuevo modelo operativo" color="#059669">
                    <p className="text-sm text-gray-600 mb-3">Primero describimos al conductor. Luego decidimos que hacer con el.</p>
                    <div className="flex items-center gap-1 text-xs text-gray-400">
                      {['Estado', 'Programas', 'Listas', 'Accion', 'Impacto'].map((step, i) => (
                        <span key={i} className="flex items-center gap-1">
                          <span className="px-2 py-1 rounded bg-gray-100 text-gray-600 font-medium">{step}</span>
                          {i < 4 && <span className="text-gray-300">→</span>}
                        </span>
                      ))}
                    </div>
                  </ModuleCard>
                </div>
              </div>
            </div>
          )}

          {/* ======== ESTADO DEL CONDUCTOR ======== */}
          {activeTab === 'estado' && (
            <ModuleCard title="Estado del Conductor — Lifecycle / Performance / Retention" color="#1a56db">
              <EmptyState title="Vista en construccion" message="Los estados de lifecycle, performance y retention se integraran desde Driver State Snapshot cuando el motor de diagnostico este activo." />
            </ModuleCard>
          )}

          {/* ======== PROGRAMAS ======== */}
          {activeTab === 'programas' && (
            <div className="grid grid-cols-2 gap-4">
              {PROGRAMAS.map((prog) => {
                const count = oppsByProgram[prog.code] || 0
                return (
                  <ModuleCard key={prog.code} title={`${prog.name} — ${prog.objetivo}`} color={prog.color}>
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-3xl font-bold text-gray-800">{formatNum(count)}</span>
                        <p className="text-xs text-gray-400 mt-1">accionables hoy</p>
                      </div>
                      <div className="text-right">
                        <span className={`px-2 py-1 rounded text-xs font-medium ${count > 0 ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                          {count > 0 ? 'ACTIVO' : 'SIN DATOS'}
                        </span>
                      </div>
                    </div>
                  </ModuleCard>
                )
              })}
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
                            <td className="py-2 font-medium text-gray-700">{o.opportunity_score?.toFixed(1)}</td>
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
              <EmptyState title="Pendiente LC-2 — LoopControl Result Sync" message="Cuando el endpoint de resultados de Miguel este disponible, aqui se mostraran: conductores que subieron viajes, aumentaron supply, salieron de riesgo, llegaron a target, siguen activos." />
              <div className="grid grid-cols-5 gap-3 mt-4">
                {['Subio viajes', 'Mas supply', 'Salio de riesgo', 'Llego a target', 'Sigue activo'].map((label, i) => (
                  <div key={i} className="bg-gray-50 rounded-xl p-3 text-center">
                    <span className="text-xl font-bold text-gray-300">—</span>
                    <p className="text-xs text-gray-400 mt-1">{label}</p>
                  </div>
                ))}
              </div>
            </ModuleCard>
          )}

          {/* ======== MOVIMIENTO ======== */}
          {activeTab === 'movimiento' && (
            <ModuleCard title="Movimiento de Conductores" color="#7c3aed">
              <EmptyState title="Pendiente de serving fact / LC-2" message="Los datos de transicion entre segmentos (migration) se integraran cuando el pipeline de serving facts este estable." />
            </ModuleCard>
          )}

          {/* ======== ATRIBUCION ======== */}
          {activeTab === 'atribucion' && (
            <div className="grid grid-cols-3 gap-4">
              {[
                { title: 'Por Agente', desc: 'Desempeno individual de agentes' },
                { title: 'Por Campana', desc: 'Efectividad por tipo de campana' },
                { title: 'Por Iniciativa', desc: 'ROI por programa operativo' },
              ].map((item, i) => (
                <ModuleCard key={i} title={item.title} color="#0891b2">
                  <EmptyState title="Pendiente LoopControl Result Sync" message={item.desc} />
                </ModuleCard>
              ))}
            </div>
          )}

          {/* ======== CONFIGURACION ======== */}
          {activeTab === 'config' && (
            <div className="space-y-5">
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
