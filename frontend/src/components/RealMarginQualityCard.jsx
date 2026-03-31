/**
 * Card de calidad de margen en fuente (REAL).
 * Muestra estado OK / Warning / Critical, cobertura de margen en completados,
 * cantidad afectada y anomalía secundaria (cancelados con margen) si aplica.
 */
import { useState, useEffect } from 'react'
import { getRealMarginQuality } from '../services/api'

const STATUS_STYLES = {
  OK: { bg: 'bg-emerald-50 border-emerald-300', text: 'text-emerald-800', label: 'OK' },
  INFO: { bg: 'bg-sky-50 border-sky-300', text: 'text-sky-800', label: 'Info' },
  WARNING: { bg: 'bg-amber-50 border-amber-300', text: 'text-amber-800', label: 'Aviso' },
  CRITICAL: { bg: 'bg-red-50 border-red-300', text: 'text-red-800', label: 'Crítico' }
}

export default function RealMarginQualityCard () {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getRealMarginQuality({ days_recent: 90 })
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e?.message || 'Error al cargar calidad de margen')
          setData(null)
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  if (loading) {
    return (
      <div className="px-4 py-2 bg-slate-50 border-b border-slate-200 text-sm text-slate-600">
        Calidad de margen: cargando…
      </div>
    )
  }

  if (error) {
    return (
      <div className="px-4 py-2 bg-amber-50 border-b border-amber-200 text-sm text-amber-800">
        <span className="font-medium">Calidad de margen:</span> no se pudo obtener ({error}).
      </div>
    )
  }

  if (!data) return null

  const status = (data.margin_quality_status || 'OK').toUpperCase()
  const style = STATUS_STYLES[status] || STATUS_STYLES.OK
  const agg = data.aggregate || {}
  const coverage = agg.margin_coverage_pct != null ? Number(agg.margin_coverage_pct) : null
  const withoutMargin = agg.completed_trips_without_margin ?? 0
  const completedTotal = agg.completed_trips ?? 0
  const hasGap = data.has_margin_source_gap === true
  const hasCancelledWithMargin = data.has_cancelled_with_margin_issue === true

  return (
    <div className={`px-4 py-2 border-b ${style.bg} ${style.text}`} role="status" aria-live="polite">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        <span className="font-semibold">
          Calidad de margen: <span className={style.text}>{style.label}</span>
        </span>
        <span className="opacity-90">
          Cobertura de margen en completados: {coverage != null ? `${coverage.toFixed(1)}%` : '—'}
        </span>
        {hasGap && (
          <>
            <span className="opacity-90">
              {withoutMargin.toLocaleString()} viajes completados sin margen en fuente
              {completedTotal > 0 ? ` (últimos ${data.days_recent ?? 90} días)` : ''}.
            </span>
            <span className="opacity-80 text-xs">
              El margen o WoW de margen puede estar incompleto en el periodo afectado. Los cancelados sin margen no se consideran error.
            </span>
          </>
        )}
      </div>
      {hasCancelledWithMargin && agg.cancelled_trips_with_margin != null && (
        <div className="mt-1.5 pt-1.5 border-t border-current border-opacity-20 text-xs opacity-90">
          Anomalía de consistencia: {agg.cancelled_trips_with_margin} viajes cancelados con comisión/margen en fuente ({agg.cancelled_with_margin_pct != null ? `${Number(agg.cancelled_with_margin_pct).toFixed(2)}%` : ''} de cancelados).
        </div>
      )}
    </div>
  )
}
