import { useState } from 'react'
import { KPICard, LoadingSpinner, ErrorBlock, SectionHeader, formatNum, StatusBadge } from '../components/SharedComponents.jsx'
import { createExport } from '../../../services/api.js'

const PROGRAM_LABELS = {
  PROGRAM_ACTIVE_GROWTH: 'Active Growth',
  PROGRAM_CHURN_PREVENTION: 'Churn Prevention',
  PROGRAM_14_90: '14/90',
  PROGRAM_HIGH_VALUE_RECOVERY: 'High Value Recovery',
}

const PROGRAM_COLORS = {
  PROGRAM_ACTIVE_GROWTH: 'green',
  PROGRAM_CHURN_PREVENTION: 'red',
  PROGRAM_14_90: 'amber',
  PROGRAM_HIGH_VALUE_RECOVERY: 'purple',
}

export default function ProgramsTab({ data, loading, errors, onRetry, onDrilldown }) {
  const programsLoading = loading.programs || loading.programStatus
  const programsError = errors.programs || errors.programStatus
  const programs = data.programs
  const programStatus = data.programStatus
  const totalDrivers = data.driverState?.total_drivers ?? data.overview?.universe_total ?? 0
  const [exporting, setExporting] = useState(false)

  const handleExport = async () => {
    setExporting(true)
    try {
      await createExport({ source: 'programs', export_reason: 'Programs tab export' })
    } finally { setExporting(false) }
  }

  if (programsError && !programs) {
    return <ErrorBlock message={programsError} onRetry={onRetry} />
  }

  if (programsLoading && !programs) {
    return <LoadingSpinner text="Cargando programas..." />
  }

  const programList = programs?.programs || programs?.data || []

  return (
    <div>
      <SectionHeader title="Programs" subtitle="Programas activos con drivers asignados" />

      <div className="flex justify-end mb-3">
        <button onClick={handleExport} disabled={exporting}
          className="text-xs bg-green-600 text-white px-3 py-1 rounded hover:bg-green-700 disabled:opacity-50">
          {exporting ? 'Exporting...' : 'Export CSV'}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {programList.map((program) => {
          const code = program.program_code || program.program || program.code
          const label = PROGRAM_LABELS[code] || code?.replace('PROGRAM_', '') || 'Program'
          const color = PROGRAM_COLORS[code] || 'blue'
          const eligible = program.eligible_drivers ?? program.drivers ?? program.count ?? 0
          const prioritized = program.prioritized ?? program.prioritized_count ?? 0
          const queueCount = program.queue_count ?? program.queued ?? 0
          const priority = program.priority ?? program.effective_priority ?? '—'
          const pct = totalDrivers > 0 ? ((eligible / totalDrivers) * 100).toFixed(1) : '—'

          return (
            <div key={code} className="bg-white border rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-gray-800">{label}</h3>
                <span className="text-xs text-gray-400">{code}</span>
              </div>
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div>
                  <span className="text-xs text-gray-400">Elegible</span>
                  <p className="text-lg font-bold text-gray-800">{formatNum(eligible)}</p>
                  <span className="text-xs text-gray-400">{pct}% del total</span>
                </div>
                <div>
                  <span className="text-xs text-gray-400">Priorizados</span>
                  <p className="text-lg font-bold text-gray-800">{formatNum(prioritized)}</p>
                </div>
                <div>
                  <span className="text-xs text-gray-400">En Queue</span>
                  <p className="text-lg font-bold text-gray-800">{formatNum(queueCount)}</p>
                </div>
                <div>
                  <span className="text-xs text-gray-400">Prioridad</span>
                  <p className="text-lg font-bold text-gray-800">{priority}</p>
                </div>
              </div>
              <div className="flex gap-2 mt-3 pt-3 border-t border-gray-100">
                <button
                  onClick={() => onDrilldown && onDrilldown(code)}
                  className="text-xs text-blue-600 hover:text-blue-800 underline"
                >
                  Ver drivers →
                </button>
                <button
                  onClick={() => onDrilldown && onDrilldown({ program: code, lifecycle: '' })}
                  className="text-xs text-purple-600 hover:text-purple-800 underline"
                  title={`Why ${label}?`}
                >
                  Why this program?
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {(!programList || programList.length === 0) && (
        <div className="bg-gray-50 border rounded-lg p-6 text-center text-sm text-gray-500">
          No se encontraron programas activos.
        </div>
      )}
    </div>
  )
}
