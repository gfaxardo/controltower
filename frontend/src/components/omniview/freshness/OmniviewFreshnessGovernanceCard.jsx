/**
 * OmniviewFreshnessGovernanceCard.jsx
 *
 * Capa de gobernanza: muestra estado de freshness RAW → FACT → SERVING.
 * Compacta. Sin invasión visual si está OK.
 * Clara si hay WARNING/BLOCKED.
 *
 * Refresh Remediation Control (CF-H1G):
 *   Si BLOCKED, muestra botón "Refrescar Omniview" que ejecuta
 *   POST /ops/omniview/refresh y luego re-evalúa freshness.
 */
import { useState, useEffect } from 'react'
import { getOmniviewFreshnessGovernance, postOmniviewRefresh } from '../../../services/api.js'

const STATUS_STYLES = {
  ok: { bg: 'bg-emerald-50/60', text: 'text-emerald-800', dot: 'bg-emerald-500', label: 'OK' },
  warning: { bg: 'bg-amber-50/60', text: 'text-amber-800', dot: 'bg-amber-500', label: 'WARNING' },
  blocked: { bg: 'bg-red-50/60', text: 'text-red-800', dot: 'bg-red-500', label: 'BLOCKED' },
  error: { bg: 'bg-red-50/60', text: 'text-red-800', dot: 'bg-red-500', label: 'ERROR' },
}

const LAYER_LABELS = {
  raw: 'RAW',
  daily: 'Daily',
  weekly: 'Weekly',
  monthly: 'Monthly',
  projection_daily: 'Proj',
}

function FreshnessRow({ label, dateStr, status, lagDays }) {
  const style = STATUS_STYLES[status] || STATUS_STYLES.ok
  const lagStr = lagDays != null ? `(-${lagDays}d)` : ''
  return (
    <span className="inline-flex items-center gap-1 text-[10px]">
      <span className={`w-1.5 h-1.5 rounded-full ${style.dot}`} />
      <span className="text-ct-text3 font-medium w-12">{label}</span>
      <span className={`font-semibold ${style.text}`}>
        {dateStr || '—'}
      </span>
      {lagStr && (
        <span className="text-ct-text3 text-[9px]">{lagStr}</span>
      )}
    </span>
  )
}

export default function OmniviewFreshnessGovernanceCard({ compact = false }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshResult, setRefreshResult] = useState(null)

  const fetchFreshness = async ({ signal } = {}) => {
    try {
      setError(null)
      const res = await getOmniviewFreshnessGovernance({ signal })
      setData(res)
    } catch (e) {
      setError(e.message || 'Error')
    }
  }

  useEffect(() => {
    let cancelled = false
    const doFetch = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await getOmniviewFreshnessGovernance({ signal: cancelled ? {} : undefined })
        if (!cancelled) setData(res)
      } catch (e) {
        if (!cancelled) setError(e.message || 'Error')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    doFetch()
    return () => { cancelled = true }
  }, [])

  const handleRefresh = async () => {
    if (!window.confirm(
      '¿Ejecutar refresh completo de Omniview?\n\n' +
      'Esto recalcula day_fact + week_fact + month_fact para el mes actual y anterior.\n' +
      'El proceso puede tardar varios segundos.'
    )) {
      return
    }

    setRefreshing(true)
    setRefreshResult(null)
    try {
      const result = await postOmniviewRefresh(true)
      setRefreshResult(result)
      await fetchFreshness()
    } catch (e) {
      setRefreshResult({ status: 'error', errors: [{ error: e.message || 'Error de red' }] })
    } finally {
      setRefreshing(false)
    }
  }

  if (loading) return null
  if (error) return null
  if (!data) return null

  const overall = data.status
  const isOk = overall === 'ok'
  const isBlocked = overall === 'blocked'
  const style = STATUS_STYLES[overall] || STATUS_STYLES.ok

  const rawDate = data.raw?.max_date
  const daily = data.facts?.daily || {}
  const weekly = data.facts?.weekly || {}
  const monthly = data.facts?.monthly || {}
  const proj = data.facts?.projection_daily || {}

  return (
    <div className={`rounded-lg border px-4 ${compact ? 'py-1' : 'py-1.5'} ${isOk ? 'border-ct-border bg-ct-surface' : `border-${overall === 'blocked' ? 'red' : 'amber'}-300 bg-${overall === 'blocked' ? 'red' : 'amber'}-50/40`} shadow-sm`}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className={`text-[10px] font-bold uppercase tracking-wider ${isOk ? 'text-ct-text2' : style.text}`}>
          {isOk ? 'Freshness' : `Freshness [${style.label}]`}
        </span>

        <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5">
          <FreshnessRow label={LAYER_LABELS.raw} dateStr={rawDate} status="ok" />
          <FreshnessRow label={LAYER_LABELS.daily} dateStr={daily.max_date} status={daily.status} lagDays={daily.lag_days} />
          <FreshnessRow label={LAYER_LABELS.weekly} dateStr={weekly.max_week_start} status={weekly.status} lagDays={weekly.lag_days} />
          <FreshnessRow label={LAYER_LABELS.monthly} dateStr={monthly.max_month_start} status={monthly.status} />
          <FreshnessRow label={LAYER_LABELS.projection_daily} dateStr={proj.max_date} status={proj.status} lagDays={proj.lag_days} />
        </div>

        {isBlocked && (
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="text-[10px] font-semibold px-2 py-0.5 rounded border border-red-300 bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {refreshing ? 'Refrescando...' : 'Refrescar Omniview'}
          </button>
        )}

        {!isOk && data.message && (
          <div className="w-full mt-0.5">
            <span className={`text-[10px] ${style.text} font-medium`}>{data.message}</span>
            {data.remediation && (
              <details className="mt-0.5">
                <summary className="text-[9px] text-ct-text3 cursor-pointer">Remediación</summary>
                <code className="text-[9px] text-ct-text3 bg-gray-100 px-1 py-0.5 rounded">{data.remediation}</code>
              </details>
            )}
          </div>
        )}

        {refreshResult && (
          <div className={`w-full mt-0.5 text-[10px] ${refreshResult.status === 'ok' ? 'text-emerald-700' : 'text-red-700'} font-medium`}>
            {refreshResult.status === 'ok'
              ? `Refresh completado en ${refreshResult.duration_seconds?.toFixed(1) || '?'}s.`
              : `Error en refresh: ${refreshResult.errors?.[0]?.error || 'Desconocido'}`
            }
          </div>
        )}
      </div>
    </div>
  )
}
