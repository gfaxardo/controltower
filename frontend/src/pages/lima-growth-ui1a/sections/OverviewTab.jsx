import { KPICard, LoadingSpinner, ErrorBlock, SectionHeader, formatNum, StatusBadge } from '../components/SharedComponents.jsx'

export default function OverviewTab({ data, loading, errors, onRetry }) {
  const overviewLoading = loading.overview || loading.driverState
  const overviewError = errors.overview || errors.driverState
  const healthLoading = loading.health
  const health = data.health
  const overview = data.overview
  const driverState = data.driverState
  const truth = data.operationalTruth
  const movementSummary = data.movementSummary

  if (overviewError && !overview) {
    return <ErrorBlock message={overviewError} onRetry={onRetry} />
  }

  if (overviewLoading && !overview) {
    return <LoadingSpinner text="Cargando resumen operacional..." />
  }

  const totalDrivers = driverState?.total_drivers ?? overview?.universe_total ?? truth?.total_drivers ?? 0
  const driversWithProgram = overview?.drivers_with_program ?? truth?.drivers_with_program ?? 0
  const driversWithoutProgram = overview?.drivers_without_program ?? 0
  const activePrograms = overview?.active_programs ?? truth?.active_programs?.length ?? 0
  const queueReady = overview?.queue_ready ?? 0
  const queueHeld = overview?.queue_held ?? 0
  const movementEntries = movementSummary?.entries ?? movementSummary?.total_entries ?? 0
  const movementExits = movementSummary?.exits ?? movementSummary?.total_exits ?? 0
  const rnaDrivers = data.loyaltySummary?.total_rna ?? 0

  const programDistribution = overview?.program_distribution || truth?.program_distribution || []
  const channelUtilization = overview?.channel_utilization || []

  return (
    <div>
      <SectionHeader title="Overview" subtitle="Estado general del universo de drivers Lima" />

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <KPICard label="Total Drivers" value={formatNum(totalDrivers)} color="blue" />
        <KPICard label="Con Programa" value={formatNum(driversWithProgram)} subtitle={`${driversWithoutProgram} sin programa`} color="green" />
        <KPICard label="Programas Activos" value={activePrograms} color="purple" />
        <KPICard label="Queue READY" value={formatNum(queueReady)} subtitle={`${formatNum(queueHeld)} HELD`} color="amber" />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <KPICard label="Movement Entries" value={formatNum(movementEntries)} color="green" />
        <KPICard label="Movement Exits" value={formatNum(movementExits)} color="red" />
        <KPICard label="RNA Drivers" value={formatNum(rnaDrivers)} color="purple" />
        <KPICard label="Driver State" value={driverState?.dominant_lifecycle || '—'} subtitle={driverState?.total_drivers ? `${formatNum(driverState.total_drivers)} total` : ''} color="blue" />
      </div>

      {/* Program Distribution */}
      {programDistribution.length > 0 && (
        <div className="bg-white border rounded-lg p-4 mb-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Distribución de Programas</h3>
          <div className="space-y-2">
            {programDistribution.map((p) => {
              const pct = totalDrivers > 0 ? (p.count / totalDrivers) * 100 : 0
              return (
                <div key={p.program || p.code}>
                  <div className="flex justify-between text-xs text-gray-600 mb-0.5">
                    <span>{p.program || p.code}</span>
                    <span>{formatNum(p.count)} ({pct.toFixed(1)}%)</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2">
                    <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${Math.min(pct, 100)}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Queue Status */}
      {(queueReady > 0 || queueHeld > 0) && (
        <div className="bg-white border rounded-lg p-4 mb-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Estado de Queue</h3>
          <div className="flex items-center gap-6">
            <div className="text-center">
              <span className="text-2xl font-bold text-green-600">{formatNum(queueReady)}</span>
              <p className="text-xs text-gray-400">READY</p>
            </div>
            <div className="text-center">
              <span className="text-2xl font-bold text-yellow-600">{formatNum(queueHeld)}</span>
              <p className="text-xs text-gray-400">HELD</p>
            </div>
          </div>
        </div>
      )}

      {/* Channel Utilization */}
      {channelUtilization.length > 0 && (
        <div className="bg-white border rounded-lg p-4 mb-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Utilización de Canales</h3>
          <div className="space-y-2">
            {channelUtilization.map((ch) => (
              <div key={ch.channel}>
                <div className="flex justify-between text-xs text-gray-600 mb-0.5">
                  <span>{ch.channel}</span>
                  <span>{ch.utilization_pct != null ? `${ch.utilization_pct}%` : '—'}</span>
                </div>
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div className="bg-green-500 h-2 rounded-full" style={{ width: `${Math.min(ch.utilization_pct || 0, 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
