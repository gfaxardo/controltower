/**
 * OmniviewAttentionSummary — Resumen de atención operacional para el Command Header.
 * 
 * Muestra conteo de blocked/critical basado en el sistema de severities existente.
 * Compacto: solo chips numerados, sin texto excesivo.
 * 
 * Motor: Control Foundation + Diagnostic Engine
 */
import { useMemo } from 'react'
import { getDecisionSeverity } from '../../../utils/operationalDecisionSeverity'

/**
 * @param {object} props
 * @param {Array}  [props.rows=[]] — Filas de la matrix (city rows con periodos)
 * @param {object} [props.matrixTrust] — Estado de trust (si existe)
 * @param {string} [props.freshnessStatus] — Estado de frescura
 */
export default function OmniviewAttentionSummary({
  rows = [],
  matrixTrust,
  freshnessStatus,
}) {
  const summary = useMemo(() => {
    let blocked = 0
    let critical = 0

    // Trust-based
    if (matrixTrust?.trust_status === 'blocked') {
      blocked++
    } else if (matrixTrust?.trust_status === 'warning') {
      const severity = getDecisionSeverity({ trust_status: matrixTrust.trust_status })
      if (severity === 'critical' || severity === 'elevated') critical++
    }

    // Freshness-based
    if (freshnessStatus === 'critical' || freshnessStatus === 'atrasada') {
      blocked++
    }

    // Scan matrix rows for cells with critical signals (sample, no heavy scan)
    // Only count if there are indicators — not a deep scan
    const hasAlerts = rows.some(row =>
      row.periods && Array.from(row.periods.values()).some(p =>
        p.raw?.signal === 'danger' || p.raw?.unit_alert
      )
    )
    if (hasAlerts) critical++

    return { blocked, critical }
  }, [rows, matrixTrust, freshnessStatus])

  if (summary.blocked === 0 && summary.critical === 0) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-ct-text3">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
        Clear
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1.5">
      {summary.blocked > 0 && (
        <span className="inline-flex items-center gap-1 px-1.5 py-px rounded text-xs font-bold bg-red-100 text-red-800 border border-red-200">
          <span className="w-1.5 h-1.5 rounded-full bg-red-600" />
          {summary.blocked}
        </span>
      )}
      {summary.critical > 0 && (
        <span className="inline-flex items-center gap-1 px-1.5 py-px rounded text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
          {summary.critical}
        </span>
      )}
    </span>
  )
}
