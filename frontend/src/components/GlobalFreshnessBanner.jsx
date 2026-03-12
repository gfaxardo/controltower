/**
 * Banner global de frescura de datos.
 * Muestra de forma muy visible: fuente viva, última data en vista, lag y estado.
 * Regla: "Falta data" solo cuando derived_max_date <= ayer-1 (regla global del sistema).
 */
import { useState, useEffect } from 'react'
import { getDataFreshnessGlobal, getDataPipelineHealth } from '../services/api'

const STATUS_STYLES = {
  fresca: { bg: 'bg-emerald-50 border-emerald-300', text: 'text-emerald-800', label: 'Fresca' },
  parcial_esperada: { bg: 'bg-amber-50 border-amber-300', text: 'text-amber-800', label: 'Parcial esperada' },
  atrasada: { bg: 'bg-orange-50 border-orange-300', text: 'text-orange-800', label: 'Atrasada' },
  falta_data: { bg: 'bg-red-50 border-red-300', text: 'text-red-800', label: 'Falta data' },
  sin_datos: { bg: 'bg-slate-100 border-slate-300', text: 'text-slate-700', label: 'Sin datos' }
}

export default function GlobalFreshnessBanner () {
  const [data, setData] = useState(null)
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getDataFreshnessGlobal()
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e?.message || 'Error al cargar estado de frescura')
          setData(null)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!expanded) return
    let cancelled = false
    getDataPipelineHealth(true)
      .then((res) => { if (!cancelled) setHealth(res) })
      .catch(() => { if (!cancelled) setHealth(null) })
    return () => { cancelled = true }
  }, [expanded])

  if (loading) {
    return (
      <div className="px-4 py-2 bg-slate-100 border-b border-slate-200 text-sm text-slate-600">
        Estado de datos: cargando…
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-4 py-2 bg-amber-50 border-b border-amber-200 text-sm text-amber-800">
        <span className="font-medium">Estado de datos:</span> no se pudo obtener ({error}). Ejecute el backend y, si aplica, <code className="text-xs bg-amber-100 px-1 rounded">POST /ops/data-freshness/run</code>.
      </div>
    )
  }

  if (!data) return null

  const style = STATUS_STYLES[data.status] || STATUS_STYLES.sin_datos
  const isOk = data.status === 'fresca' || data.status === 'parcial_esperada'
  const derivedStr = data.derived_max_date ? `Vista: ${data.derived_max_date}` : 'Vista: —'
  const sourceStr = data.source_max_date ? `Fuente: ${data.source_max_date}` : null
  const lagStr = data.lag_days != null && data.lag_days > 0 ? `Lag: ${data.lag_days} día(s)` : null

  return (
    <div className={`px-4 py-2 border-b ${style.bg} ${style.text}`} role="status" aria-live="polite">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        <span className="font-semibold">
          Salud: <span className={style.text}>{data.label || style.label}</span>
        </span>
        {!isOk && <span className="text-opacity-90">{derivedStr}</span>}
        {!isOk && sourceStr && <span className="text-opacity-90">{sourceStr}</span>}
        {lagStr && <span className="text-opacity-90 font-medium">{lagStr}</span>}
        {!isOk && data.message && (
          <span className="text-opacity-80 max-w-2xl hidden sm:inline">{data.message}</span>
        )}
        {isOk && <span className="text-opacity-90">{derivedStr}</span>}
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="ml-auto text-xs underline font-medium opacity-90 hover:opacity-100"
        >
          {expanded ? 'Ocultar salud del pipeline' : 'Ver salud del pipeline'}
        </button>
      </div>
      {expanded && (
        <div className="mt-2 pt-2 border-t border-current border-opacity-20 text-xs overflow-x-auto">
          {health?.datasets?.length ? (
            <>
              <p className="mb-1 text-opacity-90">SOURCE_STALE = fuente atrasada (más severo). DERIVED_STALE = derivado desactualizado (ejecutar backfill/refresh).</p>
              <table className="w-full border-collapse">
                <thead>
                  <tr className="text-left">
                    <th className="pr-2 py-1">Dataset</th>
                    <th className="pr-2 py-1">Fuente máx</th>
                    <th className="pr-2 py-1">Derivado máx</th>
                    <th className="pr-2 py-1">Lag</th>
                    <th className="pr-2 py-1">Estado</th>
                    <th className="py-1">Motivo</th>
                  </tr>
                </thead>
                <tbody>
                  {health.datasets.map((d, i) => {
                    const status = (d.status || '').toUpperCase()
                    const isSourceStale = status === 'SOURCE_STALE'
                    const isDerivedStale = status === 'DERIVED_STALE' || status === 'LAGGING'
                    const rowClass = isSourceStale ? 'bg-red-50' : isDerivedStale ? 'bg-amber-50' : ''
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
            </>
          ) : (
            <p className="text-opacity-80">Sin datos de auditoría. Ejecute <code>POST /ops/data-freshness/run</code> o <code>python -m scripts.run_data_freshness_audit</code>.</p>
          )}
        </div>
      )}
    </div>
  )
}
