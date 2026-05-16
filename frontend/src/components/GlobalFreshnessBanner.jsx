/**
 * Banner compacto de frescura de datos — paleta armónica.
 */
import { useState, useEffect } from 'react'
import { getDataFreshnessGlobal, getDataPipelineHealth } from '../services/api'

const STATUS_STYLES = {
  fresca: { bg: 'bg-ct-good-lo/60 border-ct-good/30', text: 'text-ct-good', label: 'Fresca' },
  parcial_esperada: { bg: 'bg-ct-warn-lo/60 border-ct-warn/30', text: 'text-ct-warn', label: 'Parcial esperada' },
  atrasada: { bg: 'bg-orange-50/80 border-orange-300', text: 'text-orange-800', label: 'Atrasada' },
  falta_data: { bg: 'bg-ct-bad-lo/60 border-ct-bad/30', text: 'text-ct-bad', label: 'Falta data' },
  sin_datos: { bg: 'bg-ct-surface border-ct-border', text: 'text-ct-text2', label: 'Sin datos' }
}

export default function GlobalFreshnessBanner ({ activeTab } = {}) {
  const [data, setData] = useState(null)
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(false)
  const group = activeTab === 'real' ? 'operational' : undefined

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    const fetchWithRetry = (attempt = 1) => {
      getDataFreshnessGlobal({ group })
        .then((res) => { if (!cancelled) { setData(res); setLoading(false) } })
        .catch((e) => {
          if (cancelled) return
          if (attempt < 2) setTimeout(() => fetchWithRetry(attempt + 1), 1500)
          else { setError(e?.message || 'Error al cargar estado de frescura'); setData(null); setLoading(false) }
        })
    }
    fetchWithRetry()
    return () => { cancelled = true }
  }, [group])

  useEffect(() => {
    if (!expanded) return
    let cancelled = false
    getDataPipelineHealth(true)
      .then((res) => { if (!cancelled) setHealth(res) })
      .catch(() => { if (!cancelled) setHealth(null) })
    return () => { cancelled = true }
  }, [expanded])

  if (loading) return <div className="px-3 py-1.5 text-2xs text-ct-text2">Estado de datos: cargando…</div>
  if (error) return <div className="px-3 py-1.5 text-2xs text-ct-warn bg-ct-warn-lo/50 rounded-md border border-ct-warn/20 mb-2">Estado de datos: no disponible ({error})</div>
  if (!data) return null

  const style = STATUS_STYLES[data.status] || STATUS_STYLES.sin_datos
  const isOk = data.status === 'fresca' || data.status === 'parcial_esperada'
  const derivedStr = data.derived_max_date ? `Vista: ${data.derived_max_date}` : 'Vista: —'
  const lagStr = data.lag_days != null && data.lag_days > 0 ? `Lag: ${data.lag_days}d` : null

  return (
    <div className={`px-3 py-1.5 rounded-md border ${style.bg} ${style.text} text-2xs mb-2`} role="status">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
        <span className="font-semibold">Salud: {data.label || style.label}</span>
        {isOk ? <span>{derivedStr}</span> : <><span>{derivedStr}</span>{lagStr && <span className="font-medium">{lagStr}</span>}</>}
        <button type="button" onClick={() => setExpanded(!expanded)} className="ml-auto underline font-medium opacity-80 hover:opacity-100">
          {expanded ? 'Ocultar pipeline' : 'Pipeline'}
        </button>
      </div>
      {expanded && (
        <div className="mt-1.5 pt-1.5 border-t border-current/20 text-2xs overflow-x-auto">
          {health?.datasets?.length ? (
            <table className="w-full border-collapse">
              <thead><tr className="text-left"><th className="pr-2 py-0.5">Dataset</th><th className="pr-2 py-0.5">Fuente</th><th className="pr-2 py-0.5">Derivado</th><th className="pr-2 py-0.5">Lag</th><th className="pr-2 py-0.5">Estado</th><th className="py-0.5">Motivo</th></tr></thead>
              <tbody>
                {health.datasets.map((d, i) => {
                  const status = (d.status || '').toUpperCase()
                  const rowClass = status === 'SOURCE_STALE' ? 'bg-ct-bad-lo/30' : status === 'DERIVED_STALE' || status === 'LAGGING' ? 'bg-ct-warn-lo/30' : ''
                  return (
                    <tr key={d.dataset_name || i} className={rowClass}>
                      <td className="pr-2 py-0.5 font-medium">{d.dataset_name}</td>
                      <td className="pr-2 py-0.5">{d.source_max_date ?? '—'}</td>
                      <td className="pr-2 py-0.5">{d.derived_max_date ?? '—'}</td>
                      <td className="pr-2 py-0.5">{d.lag_days != null ? `${d.lag_days}d` : '—'}</td>
                      <td className="pr-2 py-0.5 font-medium">{d.status}</td>
                      <td className="py-0.5 opacity-90">{d.alert_reason ?? ''}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          ) : <p className="opacity-80">Sin datos de pipeline.</p>}
        </div>
      )}
    </div>
  )
}
