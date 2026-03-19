import { useState, useEffect } from 'react'
import KPICards from './KPICards'
import DataStateBadge from './DataStateBadge'
import DataTrustBadge from './DataTrustBadge'
import { getRealSourceStatus, getDataTrustStatus } from '../services/api'

/**
 * Snapshot estratégico compacto: Plan vs Real (KPIs + Revenue por país).
 * Señal de fuente: canonical o migrating según USE_CANONICAL_REAL_MONTHLY.
 * Data Trust: estado combinado Real LOB + Plan vs Real.
 */
function ExecutiveSnapshotView({ filters = {}, refreshKey = 0 }) {
  const [sourceStatus, setSourceStatus] = useState(null)
  const [dataTrust, setDataTrust] = useState({
    status: 'warning',
    message: 'Estado de data no disponible',
    last_update: null
  })

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

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-lg font-medium text-gray-700">Plan vs Real — KPIs</h3>
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
