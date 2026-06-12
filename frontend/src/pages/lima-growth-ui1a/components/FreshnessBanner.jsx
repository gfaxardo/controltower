import { HealthDot, StatusBadge } from './SharedComponents.jsx'

export default function FreshnessBanner({ health, freshness, operability, loading }) {
  if (loading) {
    return (
      <div className="bg-gray-50 border-b border-gray-200 px-4 py-2 flex items-center gap-3 text-xs text-gray-400">
        <div className="animate-pulse flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-gray-300" />
          Verificando salud del sistema...
        </div>
      </div>
    )
  }

  const sysStatus = health?.system_status || operability?.system_status || 'UNKNOWN'
  const staleAssets = health?.stale_assets || operability?.stale_assets || []
  const componentsHealthy = health?.components_healthy ?? operability?.components_healthy ?? 0
  const componentsDegraded = health?.components_degraded ?? operability?.components_degraded ?? 0
  const componentsCritical = health?.components_critical ?? operability?.components_critical ?? 0
  const schedulerStatus = health?.scheduler_status || operability?.scheduler_status || 'UNKNOWN'

  let bannerColor = 'bg-gray-50 border-gray-200'
  let textColor = 'text-gray-600'
  if (sysStatus === 'CRITICAL') {
    bannerColor = 'bg-red-50 border-red-200'
    textColor = 'text-red-700'
  } else if (sysStatus === 'DEGRADED') {
    bannerColor = 'bg-orange-50 border-orange-200'
    textColor = 'text-orange-700'
  } else if (sysStatus === 'WARNING' || sysStatus === 'HEALTHY_WITH_WARNINGS') {
    bannerColor = 'bg-yellow-50 border-yellow-200'
    textColor = 'text-yellow-700'
  } else if (sysStatus === 'HEALTHY') {
    bannerColor = 'bg-green-50 border-green-200'
    textColor = 'text-green-700'
  }

  return (
    <div className={`border-b px-4 py-2 flex items-center gap-3 text-xs ${bannerColor} ${textColor} flex-wrap`}>
      <span className="font-medium">System:</span>
      <StatusBadge status={sysStatus} />
      <span className="text-gray-300">|</span>
      <span>Healthy: {componentsHealthy}</span>
      {componentsDegraded > 0 && <span>Degraded: {componentsDegraded}</span>}
      {componentsCritical > 0 && <span className="font-bold">Critical: {componentsCritical}</span>}
      <span className="text-gray-300">|</span>
      <span>Scheduler: <HealthDot status={schedulerStatus === 'RUNNING' ? 'HEALTHY' : 'STALE'} /> {schedulerStatus}</span>
      {staleAssets.length > 0 && (
        <>
          <span className="text-gray-300">|</span>
          <span className="text-yellow-600">
            {staleAssets.length} stale asset{staleAssets.length !== 1 ? 's' : ''}
          </span>
        </>
      )}
      {health?.remediation && (
        <>
          <span className="text-gray-300">|</span>
          <span className="italic">{health.remediation}</span>
        </>
      )}
    </div>
  )
}
