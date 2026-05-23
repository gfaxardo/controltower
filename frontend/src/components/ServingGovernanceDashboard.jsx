/**
 * ServingGovernanceDashboard — FASE 1H.1
 * Dashboard técnico mínimo de gobernanza de serving facts.
 */
import { useEffect, useState, useMemo } from 'react'

const API = '/api/ops/serving'

export default function ServingGovernanceDashboard() {
  const [health, setHealth] = useState(null)
  const [risks, setRisks] = useState([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      fetch(`${API}/health`).then(r => r.json()),
      fetch(`${API}/runtime-risks`).then(r => r.json()),
    ])
      .then(([h, r]) => { setHealth(h); setRisks(Array.isArray(r) ? r : []); setLoading(false) })
      .catch(e => { setErr(e.message); setLoading(false) })
  }, [])

  const statusBadge = useMemo(() => {
    if (!health) return null
    const m = {
      healthy: 'bg-emerald-100 text-emerald-800 border-emerald-200',
      degraded: 'bg-amber-100 text-amber-800 border-amber-200',
      attention: 'bg-red-100 text-red-800 border-red-200',
    }
    return m[health.status] || m.healthy
  }, [health])

  if (loading) return <div className="p-4 text-xs text-ct-text2">Cargando serving governance...</div>
  if (err) return <div className="p-4 text-xs text-red-600">Error: {err}</div>
  if (!health) return null

  return (
    <div className="rounded-lg border border-ct-border bg-ct-card shadow-sm overflow-hidden">
      <div className="px-4 py-3 border-b border-ct-border bg-ct-surface flex items-center gap-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-ct-text">Serving Governance</span>
        <span className={`px-2 py-px rounded-full text-[10px] font-semibold border ${statusBadge}`}>
          {health.status}
        </span>
        <span className="ml-auto text-[10px] text-ct-text3">
          {health.total_facts} facts · {health.total_rows.toLocaleString()} rows
        </span>
      </div>

      <div className="p-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatBox label="Integridad" value={`${health.details?.grains?.length || 0}/3 grains`} ok={health.status === 'healthy'} />
        <StatBox label="Stale" value={health.stale_count} ok={health.stale_count === 0} />
        <StatBox label="Missing Grains" value={health.missing_grains?.length || 0} ok={!health.missing_grains?.length} />
        <StatBox label="Runtime Risks" value={risks.length} ok={risks.length === 0} />
      </div>

      {risks.length > 0 && (
        <div className="px-4 pb-3">
          <p className="text-[10px] font-semibold text-amber-700 mb-1">Runtime Risks</p>
          {risks.map(r => (
            <div key={r.serving_key} className="text-[9px] text-amber-600 flex gap-2">
              <span>{r.serving_key}</span>
              <span className="opacity-60">{r.freshness_status} · {r.risk_level}</span>
            </div>
          ))}
        </div>
      )}

      {health.details?.stale_facts?.length > 0 && (
        <div className="px-4 pb-3">
          <p className="text-[10px] font-semibold text-red-700 mb-1">Stale Facts</p>
          {health.details.stale_facts.map(s => (
            <div key={s.serving_key} className="text-[9px] text-red-600">
              {s.serving_key} — {Math.round(s.hours_since)}h since last refresh
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function StatBox({ label, value, ok }) {
  return (
    <div className={`rounded-lg border px-3 py-2 ${ok ? 'border-emerald-200 bg-emerald-50/50' : 'border-amber-200 bg-amber-50/50'}`}>
      <p className="text-[9px] font-semibold uppercase tracking-wide text-ct-text3">{label}</p>
      <p className={`text-sm font-bold ${ok ? 'text-emerald-700' : 'text-amber-700'}`}>{value}</p>
    </div>
  )
}
