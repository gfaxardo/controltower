import { useState, useEffect } from 'react'
import KPICards from './KPICards'
import DataStateBadge from './DataStateBadge'
import DataTrustBadge from './DataTrustBadge'
import { getRealSourceStatus, getDataTrustStatus, getDecisionSignal } from '../services/api'

/** Indicador mínimo: STOP / CAUTION / OK según decision_signal de resumen */
function DecisionIndicator({ decision }) {
  if (!decision?.action) return null
  const a = decision.action
  const isStop = a === 'STOP_DECISIONS' || a === 'LIMIT_DECISIONS'
  const isCaution = a === 'USE_WITH_CAUTION' || a === 'MONITOR_CLOSELY' || a === 'MONITOR'
  const label = isStop ? 'STOP' : isCaution ? 'CAUTION' : 'OK'
  const emoji = isStop ? '🔴' : isCaution ? '🟡' : '🟢'
  const title = [decision.message, decision.priority ? `Prioridad: ${decision.priority}` : ''].filter(Boolean).join(' · ')
  return (
    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium" title={title}>
      {emoji} {label}
    </span>
  )
}

/**
 * Snapshot estratégico compacto: Plan vs Real (KPIs + Revenue por país).
 * Señal de fuente: canonical o migrating según USE_CANONICAL_REAL_MONTHLY.
 * Data Trust: estado combinado Real LOB + Plan vs Real.
 * Decision Layer: indicador operativo STOP / CAUTION / OK en header.
 */
function ExecutiveSnapshotView({ filters = {}, refreshKey = 0 }) {
  const [sourceStatus, setSourceStatus] = useState(null)
  const [dataTrust, setDataTrust] = useState({
    status: 'warning',
    message: 'Estado de data no disponible',
    last_update: null
  })
  const [decisionSignal, setDecisionSignal] = useState(null)

  useEffect(() => {
    getRealSourceStatus()
      .then((res) => {
        const screen = (res?.screens || []).find((s) => s.screen_id === 'performance_resumen')
        setSourceStatus(screen?.source_status || 'migrating')
      })
      .catch(() => setSourceStatus('migrating'))
  }, [refreshKey])

  useEffect(() => {
    getDataTrustStatus('resumen')
      .then(setDataTrust)
      .catch(() => setDataTrust({
        status: 'warning',
        message: 'Estado de data no disponible',
        last_update: null
      }))
  }, [refreshKey])

  useEffect(() => {
    getDecisionSignal('resumen')
      .then(setDecisionSignal)
      .catch(() => setDecisionSignal(null))
  }, [refreshKey])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-lg font-medium text-gray-700">Plan vs Real — KPIs</h3>
        <DecisionIndicator decision={decisionSignal} />
        <DataTrustBadge status={dataTrust.status} message={dataTrust.message} last_update={dataTrust.last_update} />
        {sourceStatus && (
          <DataStateBadge state={sourceStatus} />
        )}
      </div>
      <KPICards key={`snapshot-kpis-${refreshKey}`} filters={filters} compact />
    </div>
  )
}

export default ExecutiveSnapshotView
