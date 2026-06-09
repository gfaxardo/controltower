import { MetricCard, SectionCard, HealthDot, LoadingState, ErrorState, formatNum, StatusBadge } from '../components/SharedComponents.jsx'
import FreshnessBadge from '../components/FreshnessBadge.jsx'
import { useState } from 'react'

const TRUTH_BADGES = {
  FRESH: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: 'FRESH' },
  VALID_ZERO: { bg: 'bg-gray-100', text: 'text-gray-600', label: 'VALID_ZERO' },
  NOT_GENERATED: { bg: 'bg-amber-100', text: 'text-amber-700', label: 'NOT_GENERATED' },
  STALE_PROPAGATED: { bg: 'bg-orange-100', text: 'text-orange-700', label: 'STALE' },
  ERROR: { bg: 'bg-red-100', text: 'text-red-700', label: 'ERROR' },
  OK: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: 'OK' },
}

function TruthBadge({ status }) {
  const cfg = TRUTH_BADGES[status] || TRUTH_BADGES.OK
  return <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${cfg.bg} ${cfg.text}`}>{cfg.label}</span>
}

function WhatIsHappening({ truth, operationalDate, onRunPipeline }) {
  const [confirming, setConfirming] = useState(false)
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  if (!truth) return null
  const { overall_status, warnings, kpis } = truth
  
  const notGenerated = (kpis || []).filter(k => k.status === 'NOT_GENERATED')
  const staleProps = (kpis || []).filter(k => k.status === 'STALE_PROPAGATED')
  
  let message = ''
  let action = ''
  let severity = 'bg-blue-50 border-blue-200 text-blue-800'
  let canRun = false
  
  if (overall_status === 'ERROR') {
    message = 'Error consultando datos operacionales. Verificar backend y DB.'
    severity = 'bg-red-50 border-red-200 text-red-800'
  } else if (notGenerated.length >= 3) {
    const lastDate = notGenerated[0]?.latest_data_date || 'desconocida'
    message = `Hoy no existen datos generados. Ultima fecha disponible: ${lastDate}. El sistema muestra 0 porque el pipeline diario no ha corrido para esta fecha.`
    severity = 'bg-amber-50 border-amber-200 text-amber-800'
    canRun = true
  } else if (staleProps.length > 0) {
    message = 'Algunos datos provienen de una fuente anterior a la fecha seleccionada (STALE_PROPAGATED).'
    severity = 'bg-orange-50 border-orange-200 text-orange-800'
  } else {
    message = 'Todos los datos operacionales estan frescos y disponibles.'
    severity = 'bg-emerald-50 border-emerald-200 text-emerald-800'
  }

  const handleRun = async () => {
    setConfirming(false)
    setRunning(true)
    setError(null)
    setResult(null)
    
    const steps = [
      'Validando fundacion...',
      'Generando driver snapshot...',
      'Generando program eligibility...',
      'Generando prioritized opportunities...',
      'Generando queue + serving facts...',
    ]
    
    try {
      const date = operationalDate || new Date().toISOString().slice(0, 10)
      for (let i = 0; i < steps.length; i++) {
        setProgress(steps[i])
        await new Promise(r => setTimeout(r, 800))
      }
      
      setProgress('Ejecutando pipeline...')
      const api = (await import('../../../../services/api.js')).default
      const resp = await api.post('/yego-lima-growth/pipeline/run-daily', { run_date: date, max_drivers: 250 }, { timeout: 300000 })
      setProgress('')
      
      if (resp.data?.overall_status === 'success') {
        setResult({ success: true, steps: resp.data.steps, run_date: date })
        if (onRunPipeline) onRunPipeline()
      } else {
        setError(resp.data?.error || 'Pipeline failed')
      }
    } catch (e) {
      setProgress('')
      setError(e.message || 'Pipeline execution error')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className={`rounded-xl p-4 border ${severity}`}>
      <div className="flex items-center gap-2 mb-2">
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />
        </svg>
        <span className="text-sm font-bold">Que esta pasando?</span>
      </div>
      <p className="text-xs mb-2">{message}</p>

      {canRun && !confirming && !running && !result && (
        <button onClick={() => setConfirming(true)}
          className="px-3 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-xs font-medium transition-colors">
          Ejecutar Pipeline
        </button>
      )}

      {confirming && (
        <div className="bg-white/60 rounded-lg p-3 text-xs space-y-2">
          <p className="font-medium">Se ejecutara la generacion diaria para {operationalDate || 'la fecha actual'}.</p>
          <p>Duracion estimada: ~60 segundos. No se exportaran campanas.</p>
          <div className="flex gap-2">
            <button onClick={handleRun} className="px-3 py-1 bg-amber-600 text-white rounded font-medium">Si, ejecutar</button>
            <button onClick={() => setConfirming(false)} className="px-3 py-1 bg-gray-200 text-gray-700 rounded">Cancelar</button>
          </div>
        </div>
      )}

      {running && (
        <div className="bg-white/60 rounded-lg p-3 text-xs">
          <div className="flex items-center gap-2 mb-1">
            <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-amber-600"></div>
            <span className="font-medium text-amber-700">Ejecutando pipeline...</span>
          </div>
          {progress && <p className="text-gray-500">{progress}</p>}
        </div>
      )}

      {result && (
        <div className="bg-emerald-50 rounded-lg p-3 text-xs space-y-1">
          <p className="font-medium text-emerald-700">Pipeline ejecutado correctamente.</p>
          <p className="text-gray-600">Fecha: {result.run_date}</p>
          <p className="text-gray-600">Pasos: {result.steps?.length || 0} completados</p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 rounded-lg p-3 text-xs">
          <p className="font-medium text-red-700">Pipeline fallo.</p>
          <p className="text-red-600">{error}</p>
        </div>
      )}
    </div>
  )
}

function TodayActionPlanHeader({ data }) {
  const plan = data.todaysActionPlan
  if (!plan) return null
  const c = { bg: 'bg-amber-500/20', text: 'text-amber-200' }
  return (
    <div className="bg-gradient-to-r from-[#0a1628] to-[#1a2a4a] rounded-2xl p-5 text-white shadow-md">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-bold uppercase tracking-wide">Plan de Accion de Hoy</span>
        <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${c.bg} ${c.text}`}>{plan.status}</span>
      </div>
      <p className="text-lg font-semibold mb-3">{plan.headline}</p>
      {plan.programs?.length > 0 && (
        <div className="mb-3 overflow-x-auto">
          <table className="w-full text-[11px]"><thead><tr className="text-white/40 border-b border-white/10">
            <th className="text-left py-1">Programa</th><th className="text-right py-1">Estado</th>
            <th className="text-right py-1">Accionables</th><th className="text-right py-1">Recomendado</th><th className="text-right py-1">Pendiente</th>
          </tr></thead><tbody>
            {plan.programs.map(p => (
              <tr key={p.program_code} className="border-b border-white/5">
                <td className="py-1 font-medium">{p.program_name}</td>
                <td className="py-1 text-right"><span className="px-1.5 py-0.5 rounded text-[9px] font-medium bg-white/10">{p.status}</span></td>
                <td className="py-1 text-right">{formatNum(p.actionable)}</td>
                <td className="py-1 text-right font-bold text-amber-300">{formatNum(p.recommended_take)}</td>
                <td className="py-1 text-right text-white/40">{formatNum(Math.max(0, p.actionable - p.recommended_take))}</td>
              </tr>
            ))}
          </tbody></table>
        </div>
      )}
      {plan.capacity && (
        <div className="grid grid-cols-4 gap-2 text-center text-xs">
          <div className="bg-white/5 rounded-lg p-2"><p className="text-white/40">Capacidad</p><p className="font-bold">{formatNum(plan.capacity.daily_action_capacity)}</p></div>
          <div className="bg-white/5 rounded-lg p-2"><p className="text-white/40">En Cola</p><p className="font-bold">{formatNum(plan.capacity.queue_ready)}</p></div>
          <div className="bg-white/5 rounded-lg p-2"><p className="text-white/40">Cobertura</p><p className="font-bold">{(plan.capacity.coverage_rate * 100).toFixed(0)}%</p></div>
          <div className="bg-white/5 rounded-lg p-2"><p className="text-white/40">Gap</p><p className="font-bold text-amber-300">{formatNum(plan.capacity.gap)}</p></div>
        </div>
      )}
      {plan.next_action && (
        <div className="mt-3 pt-3 border-t border-white/10">
          <span className="text-xs text-white/50">Siguiente: </span>
          <span className="text-xs font-bold text-amber-300">{plan.next_action.label}</span>
          <span className="text-[10px] text-white/30 ml-1">— {plan.next_action.reason}</span>
        </div>
      )}
      {plan.warnings?.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {plan.warnings.map((w,i)=><span key={i} className="text-[10px] text-amber-300/80 bg-amber-500/10 px-1.5 py-0.5 rounded">{w}</span>)}
        </div>
      )}
    </div>
  )
}

export default function CommandCenterSection({ data, loading, errors, onRetry, operationalDate, onRunPipeline }) {
  const summary = data.summary
  const config = data.config
  const exports = data.exports
  const truth = data.operationalTruth

  if (loading.summary && !summary) return <LoadingState text="Cargando Command Center..." />
  if (errors.summary && !summary) return <ErrorState message={errors.summary} onRetry={onRetry} />

  const exportedCampaigns = (exports || []).filter((e) => e.export_status === 'exported')
  const totalExported = exportedCampaigns.reduce((sum, e) => sum + (e.contacts_inserted || 0), 0)

  // Truth-based health reconciliation (NO FALSE GREEN)
  const getTruthStatus = (key) => {
    const kpi = (truth?.kpis || []).find(k => k.key === key)
    return kpi?.status || 'UNKNOWN'
  }
  
  const engineHealth = {
    opportunity: getTruthStatus('prioritized_total') === 'NOT_GENERATED' ? 'red'
      : getTruthStatus('prioritized_total') === 'STALE_PROPAGATED' ? 'yellow'
      : (summary?.prioritized_total > 0 ? 'green' : 'yellow'),
    queue: getTruthStatus('queue_total') === 'NOT_GENERATED' ? 'red'
      : getTruthStatus('queue_total') === 'STALE_PROPAGATED' ? 'yellow'
      : ((summary?.queue_total || 0) > 0 ? 'green' : 'yellow'),
    export: (summary?.loopcontrol_campaigns_exported || 0) > 0 ? 'green' : 'yellow',
    loopcontrol: config?.enabled ? (summary?.loopcontrol_campaigns_exported > 0 ? 'green' : 'yellow') : 'red',
  }

  const capacityTotal = summary?.capacity_total || data.capacity?.channels?.reduce((s, c) => s + ((c.agents || 0) * (c.capacity_per_agent || 0)), 0) || 0

  return (
    <div className="space-y-5">
      {/* ===== TODAY'S ACTION PLAN HEADER ===== */}
      {truth && (
        <TodayActionPlanHeader data={data} navigateToSection={(section) => {
          // Navigation handled via parent component
        }} />
      )}

      {/* What's Happening Panel */}
      <WhatIsHappening truth={truth} operationalDate={operationalDate} onRunPipeline={onRunPipeline} />

      {/* Pipeline Bar */}
      {summary && (
        <div className="bg-gradient-to-r from-[#06244a] to-[#0d3b7a] rounded-2xl p-5 text-white shadow-md">
          <div className="flex items-center gap-2 mb-2">
            <svg className="w-4 h-4 text-white/70" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            <span className="text-xs font-semibold text-white/70 uppercase tracking-wider">Pipeline Operacional</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-white/80 flex-wrap">
            <span className="bg-white/10 px-2 py-0.5 rounded">Universo: {formatNum(summary.universe_total)}</span>
            <span className="text-white/40">-></span>
            <span className="bg-white/10 px-2 py-0.5 rounded">Elegibles: {formatNum(summary.eligible_total)} <TruthBadge status={getTruthStatus('eligible_total')} /></span>
            <span className="text-white/40">-></span>
            <span className="bg-white/10 px-2 py-0.5 rounded">Priorizados: {formatNum(summary.prioritized_total)} <TruthBadge status={getTruthStatus('prioritized_total')} /></span>
            <span className="text-white/40">-></span>
            <span className="bg-white/20 px-2 py-0.5 rounded font-bold">Accionables: {formatNum(summary.actionable_today)} <TruthBadge status={getTruthStatus('actionable_today')} /></span>
          </div>
        </div>
      )}

      {/* Row 1: Core KPIs */}
      <div className="grid grid-cols-4 gap-3">
        <MetricCard label="Universo Total" value={formatNum(summary?.universe_total)} color="#1a56db" tooltip="Total drivers en snapshot mas reciente" explainability={summary?.explainability?.universe_total} />
        <MetricCard label="Priorizados" value={formatNum(summary?.prioritized_total)} color="#7c3aed" tooltip="Drivers con programa y ranking asignado" explainability={summary?.explainability?.prioritized_total} />
        <MetricCard label="Accionables Hoy" value={formatNum(summary?.actionable_today)} color="#059669" tooltip={`Limitado por daily_action_capacity = ${formatNum(summary?.daily_action_capacity)}`} explainability={summary?.explainability?.actionable_today} />
        <MetricCard label="Capacidad Diaria" value={formatNum(capacityTotal)} color="#0891b2" tooltip="Capacidad operativa total" explainability={summary?.explainability?.capacity_total} />
      </div>

      {/* KPI Explanations from truth */}
      {truth?.kpis && (
        <div className="grid grid-cols-2 gap-2 text-[10px] text-gray-500">
          {truth.kpis.filter(k => k.status !== 'OK' && k.status !== 'FRESH').slice(0, 4).map(k => (
            <div key={k.key} className="flex items-start gap-1">
              <TruthBadge status={k.status} />
              <span>{k.explanation}</span>
            </div>
          ))}
        </div>
      )}

      {/* Row 2: Queue + Export */}
      <div className="grid grid-cols-4 gap-3">
        <MetricCard label="En Cola" value={formatNum(summary?.queue_total)} color="#d97706" subtitle={`${formatNum(summary?.queue_ready)} READY / ${formatNum(summary?.queue_held)} HELD`} explainability={summary?.explainability?.queue_total} />
        <MetricCard label="Exportados" value={formatNum(summary?.loopcontrol_contacts_inserted)} color="#7c3aed" subtitle={`${formatNum(summary?.loopcontrol_campaigns_exported)} campanas`} explainability={summary?.explainability?.loopcontrol_contacts_inserted} />
        <MetricCard label="LoopControl" value={config?.mode || '...'} color={config?.enabled ? '#059669' : '#dc2626'} subtitle={config?.enabled ? 'Integrado' : 'DRY RUN'} />
        <MetricCard label="Gap Capacidad" value={summary ? formatNum((summary.actionable_today || 0) - capacityTotal) : '...'} color={(summary?.actionable_today || 0) > capacityTotal ? '#dc2626' : '#059669'} />
      </div>

      {/* Capacity Explanation */}
      {summary && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-3 text-sm text-yellow-800">
          <span className="font-medium">Accionables hoy ({formatNum(summary.actionable_today)})</span> estan limitados por <span className="font-mono bg-yellow-100 px-1 rounded">daily_action_capacity = {formatNum(summary.daily_action_capacity)}</span>.
          Universo: {formatNum(summary.universe_total)}, elegibles: {formatNum(summary.eligible_total)}, priorizados: {formatNum(summary.prioritized_total)}.
        </div>
      )}

      {/* Engine Health */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <div className="flex items-center gap-6 flex-wrap">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Engine Health</span>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50"><span className="text-xs text-gray-500">Opportunity</span><HealthDot status={engineHealth.opportunity} /></div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50"><span className="text-xs text-gray-500">Queue</span><HealthDot status={engineHealth.queue} /></div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50"><span className="text-xs text-gray-500">Export</span><HealthDot status={engineHealth.export} /></div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50"><span className="text-xs text-gray-500">LoopControl</span><HealthDot status={engineHealth.loopcontrol} /></div>
          <div className="flex-1" />
          {summary?.freshness && (
            <div className="flex items-center gap-2">
              <FreshnessBadge freshness={summary.freshness.driver_snapshot} compact />
              <FreshnessBadge freshness={summary.freshness.opportunity_engine} compact />
              <FreshnessBadge freshness={summary.freshness.exports} compact />
            </div>
          )}
        </div>
      </div>

      {/* By Program Distribution */}
      {summary?.by_program && (
        <SectionCard title="Distribucion por Programa" color="#7c3aed">
          <div className="grid grid-cols-4 gap-3">
            {summary.by_program.map((p) => (
              <div key={p.program_code} className="bg-gray-50 rounded-xl p-3 text-center">
                <span className="text-xl font-bold text-gray-800">{formatNum(p.prioritized)}</span>
                <p className="text-xs text-gray-500 mt-1">{p.program_code.replace('PROGRAM_', '')}</p>
              </div>
            ))}
          </div>
        </SectionCard>
      )}
    </div>
  )
}
