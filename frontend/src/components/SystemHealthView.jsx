import { useState, useEffect } from 'react'
import { getSystemHealth, runIntegrityAudit, getDataPipelineHealth, getObservabilityOverview, getObservabilityArtifacts } from '../services/api'

const statusColors = {
  OK: 'bg-green-100 text-green-800',
  WARNING: 'bg-amber-100 text-amber-800',
  CRITICAL: 'bg-red-100 text-red-800',
  STALE: 'bg-amber-100 text-amber-800',
  UNKNOWN: 'bg-gray-200 text-gray-700'
}

function SystemHealthView () {
  const [health, setHealth] = useState(null)
  const [pipeline, setPipeline] = useState(null)
  const [observability, setObservability] = useState(null)
  const [observabilityArtifacts, setObservabilityArtifacts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [auditRunning, setAuditRunning] = useState(false)
  const [auditResult, setAuditResult] = useState(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [h, p] = await Promise.all([
        getSystemHealth(),
        getDataPipelineHealth(true)
      ])
      setHealth(h)
      setPipeline(p)
    } catch (e) {
      setError(e?.message || e?.response?.data?.detail || 'Error al cargar System Health')
    } finally {
      setLoading(false)
    }
    try {
      const [obs, art] = await Promise.all([
        getObservabilityOverview(),
        getObservabilityArtifacts()
      ])
      setObservability(obs?.error ? null : obs)
      setObservabilityArtifacts(Array.isArray(art) ? art : [])
    } catch (_) {
      setObservability(null)
      setObservabilityArtifacts([])
    }
  }

  useEffect(() => {
    load()
  }, [])

  const runAudit = async () => {
    setAuditRunning(true)
    setAuditResult(null)
    try {
      const r = await runIntegrityAudit()
      setAuditResult(r)
      await load()
    } catch (e) {
      setAuditResult({ ok: false, stderr: e?.message || String(e) })
    } finally {
      setAuditRunning(false)
    }
  }

  if (loading && !health) {
    return (
      <div className="p-6 text-gray-600">Cargando System Health…</div>
    )
  }

  if (error) {
    return (
      <div className="p-6 rounded-lg bg-red-50 text-red-800">
        <p className="font-medium">Error</p>
        <p className="text-sm mt-1">{error}</p>
        <button type="button" onClick={load} className="mt-3 px-3 py-1.5 rounded border border-red-300 bg-white text-red-700 text-sm hover:bg-red-50">
          Reintentar
        </button>
      </div>
    )
  }

  const overall = health?.integrity?.overall || 'UNKNOWN'
  const summary = health?.integrity?.summary || { ok: 0, warning: 0, critical: 0 }
  const checks = health?.integrity?.checks || []
  const mvFreshness = health?.mv_freshness || []
  const ingestion = health?.ingestion_summary || []

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-xl font-semibold text-gray-800">System Health</h2>
        <div className="flex items-center gap-3">
          <span className={`px-3 py-1 rounded font-medium ${statusColors[overall] || statusColors.UNKNOWN}`}>
            {overall}
          </span>
          {health?.last_audit_ts && (
            <span className="text-sm text-gray-500">
              Última auditoría: {new Date(health.last_audit_ts).toLocaleString()}
            </span>
          )}
          <button
            type="button"
            disabled={auditRunning}
            onClick={runAudit}
            className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {auditRunning ? 'Ejecutando…' : 'Ejecutar auditoría'}
          </button>
        </div>
      </div>

      {auditResult && (
        <div className={`p-4 rounded-lg text-sm ${auditResult.ok ? 'bg-green-50 text-green-800' : 'bg-amber-50 text-amber-800'}`}>
          {auditResult.ok ? 'Auditoría completada correctamente.' : 'Auditoría falló o reportó errores.'}
          {auditResult.stdout && <pre className="mt-2 whitespace-pre-wrap font-mono text-xs">{auditResult.stdout}</pre>}
          {auditResult.stderr && <pre className="mt-2 whitespace-pre-wrap font-mono text-xs text-red-700">{auditResult.stderr}</pre>}
        </div>
      )}

      {/* Resumen integridad */}
      <section className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="font-medium text-gray-800 mb-3">Integridad</h3>
        <div className="flex gap-4 mb-4">
          <span className="text-green-700">OK: {summary.ok}</span>
          <span className="text-amber-700">WARNING: {summary.warning}</span>
          <span className="text-red-700">CRITICAL: {summary.critical}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-gray-600">
                <th className="py-2 pr-4">Check</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2">Severity</th>
              </tr>
            </thead>
            <tbody>
              {checks.map((c, i) => (
                <tr key={i} className="border-b border-gray-100">
                  <td className="py-2 pr-4">{c.check_name}</td>
                  <td className="py-2 pr-4">
                    <span className={`px-2 py-0.5 rounded ${statusColors[c.status] || statusColors.UNKNOWN}`}>
                      {c.status}
                    </span>
                  </td>
                  <td className="py-2">{c.severity}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Freshness MVs */}
      <section className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="font-medium text-gray-800 mb-3">Materialized views (freshness)</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-gray-600">
                <th className="py-2 pr-4">Vista</th>
                <th className="py-2 pr-4">Último periodo</th>
                <th className="py-2 pr-4">Lag (h)</th>
                <th className="py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {mvFreshness.map((m, i) => (
                <tr key={i} className="border-b border-gray-100">
                  <td className="py-2 pr-4 font-mono text-xs">{m.view_name}</td>
                  <td className="py-2 pr-4">{m.last_period_start ?? '—'}</td>
                  <td className="py-2 pr-4">{m.lag_hours != null ? Number(m.lag_hours).toFixed(1) : '—'}</td>
                  <td className="py-2">
                    <span className={`px-2 py-0.5 rounded ${statusColors[m.status] || statusColors.UNKNOWN}`}>
                      {m.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Ingestión (resumen por fuente/mes) */}
      <section className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="font-medium text-gray-800 mb-3">Ingestión (por fuente y mes)</h3>
        <div className="overflow-x-auto max-h-64 overflow-y-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-gray-600">
                <th className="py-2 pr-4">Fuente</th>
                <th className="py-2 pr-4">Mes</th>
                <th className="py-2 pr-4">Viajes</th>
                <th className="py-2 pr-4">B2B</th>
                <th className="py-2 pr-4">Drivers</th>
                <th className="py-2">Parks</th>
              </tr>
            </thead>
            <tbody>
              {ingestion.slice(0, 24).map((row, i) => (
                <tr key={i} className="border-b border-gray-100">
                  <td className="py-2 pr-4">{row.fuente}</td>
                  <td className="py-2 pr-4">{row.mes ?? '—'}</td>
                  <td className="py-2 pr-4">{row.viajes != null ? row.viajes.toLocaleString() : '—'}</td>
                  <td className="py-2 pr-4">{row.viajes_b2b != null ? row.viajes_b2b.toLocaleString() : '—'}</td>
                  <td className="py-2 pr-4">{row.drivers != null ? row.drivers.toLocaleString() : '—'}</td>
                  <td className="py-2">{row.parks != null ? row.parks.toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Pipeline health (freshness por dataset) */}
      {pipeline?.datasets?.length > 0 && (
        <section className="bg-white rounded-lg border border-gray-200 p-4">
          <h3 className="font-medium text-gray-800 mb-3">Pipeline (freshness por dataset)</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-left text-gray-600">
                  <th className="py-2 pr-4">Dataset</th>
                  <th className="py-2 pr-4">Source max</th>
                  <th className="py-2 pr-4">Derived max</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2">Checked</th>
                </tr>
              </thead>
              <tbody>
                {pipeline.datasets.map((d, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    <td className="py-2 pr-4">{d.dataset_name}</td>
                    <td className="py-2 pr-4">{d.source_max_date ?? '—'}</td>
                    <td className="py-2 pr-4">{d.derived_max_date ?? '—'}</td>
                    <td className="py-2 pr-4">
                      <span className={`px-2 py-0.5 rounded ${statusColors[d.status] || statusColors.UNKNOWN}`}>
                        {d.status}
                      </span>
                    </td>
                    <td className="py-2 text-gray-500">{d.checked_at ? new Date(d.checked_at).toLocaleString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Fase 1 — Observabilidad E2E */}
      {observability?.modules?.length === 0 && observability !== null && (
        <section className="bg-gray-50 rounded-lg border border-gray-200 p-3">
          <p className="text-sm text-gray-600">Observabilidad: sin módulos registrados (aplicar migración 092 o comprobar backend <code className="text-xs">/ops/observability/overview</code>).</p>
        </section>
      )}
      {observability === null && !loading && (
        <section className="bg-gray-50 rounded-lg border border-gray-200 p-3">
          <p className="text-sm text-gray-600">Observabilidad: no cargada (error de red o migración 092 no aplicada).</p>
        </section>
      )}
      {observability?.modules?.length > 0 && (
        <>
          <section className="bg-white rounded-lg border border-gray-200 p-4">
            <h3 className="font-medium text-gray-800 mb-3">Observabilidad por módulo</h3>
            <p className="text-xs text-gray-500 mb-3">Último refresh y cobertura por módulo. Supply usa supply_refresh_log; Real LOB/Driver Lifecycle pueden registrar en observability_refresh_log.</p>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-gray-600">
                    <th className="py-2 pr-4">Módulo</th>
                    <th className="py-2 pr-4">Artefactos</th>
                    <th className="py-2 pr-4">Con refresh</th>
                    <th className="py-2 pr-4">Último refresh</th>
                    <th className="py-2 pr-4">Cobertura</th>
                    <th className="py-2">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {observability.modules.map((m, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      <td className="py-2 pr-4 font-medium">{m.module_name}</td>
                      <td className="py-2 pr-4">{m.artifact_count ?? 0}</td>
                      <td className="py-2 pr-4">{m.with_refresh_count ?? 0}</td>
                      <td className="py-2 pr-4 text-gray-600">{m.latest_refresh_at ? new Date(m.latest_refresh_at).toLocaleString() : '—'}</td>
                      <td className="py-2 pr-4">{m.observability_coverage_pct != null ? `${m.observability_coverage_pct}%` : '—'}</td>
                      <td className="py-2">
                        <span className={`px-2 py-0.5 rounded ${m.all_fresh ? 'bg-green-100 text-green-800' : 'bg-amber-100 text-amber-800'}`}>
                          {m.all_fresh ? 'fresh' : 'stale/unknown'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {observability.recent_refreshes_7d != null && (
              <p className="text-xs text-gray-500 mt-2">Refreshes registrados (últimos 7 días): {observability.recent_refreshes_7d}</p>
            )}
          </section>
          <section className="bg-white rounded-lg border border-gray-200 p-4">
            <h3 className="font-medium text-gray-800 mb-3">Artefactos críticos</h3>
            <div className="overflow-x-auto max-h-64 overflow-y-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 text-left text-gray-600">
                    <th className="py-2 pr-4">Artefacto</th>
                    <th className="py-2 pr-4">Tipo</th>
                    <th className="py-2 pr-4">Módulo</th>
                    <th className="py-2 pr-4">Último refresh</th>
                    <th className="py-2">Origen</th>
                  </tr>
                </thead>
                <tbody>
                  {observabilityArtifacts.map((a, i) => (
                    <tr key={i} className="border-b border-gray-100">
                      <td className="py-2 pr-4 font-mono text-xs">{a.artifact_name}</td>
                      <td className="py-2 pr-4">{a.artifact_type ?? '—'}</td>
                      <td className="py-2 pr-4">{a.module_name ?? '—'}</td>
                      <td className="py-2 pr-4 text-gray-600">{a.latest_refresh_at ? new Date(a.latest_refresh_at).toLocaleString() : '—'}</td>
                      <td className="py-2 text-gray-500">{a.refresh_owner ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          {observability.modules.some(m => !m.all_fresh || (m.observability_coverage_pct != null && m.observability_coverage_pct < 100)) && (
            <section className="bg-amber-50 rounded-lg border border-amber-200 p-4">
              <h3 className="font-medium text-amber-900 mb-2">Riesgos detectados</h3>
              <ul className="text-sm text-amber-800 list-disc list-inside space-y-1">
                {observability.modules.filter(m => !m.all_fresh).map((m, i) => (
                  <li key={i}>Módulo <strong>{m.module_name}</strong>: datos stale o sin trazabilidad de refresh reciente.</li>
                ))}
                {observability.modules.filter(m => m.observability_coverage_pct != null && m.observability_coverage_pct < 100 && m.observability_coverage_pct > 0).map((m, i) => (
                  <li key={`cov-${i}`}>Módulo <strong>{m.module_name}</strong>: solo {m.observability_coverage_pct}% de artefactos con refresh registrado.</li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  )
}

export default SystemHealthView
