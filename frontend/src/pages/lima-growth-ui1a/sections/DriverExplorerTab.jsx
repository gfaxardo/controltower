import { useState, useMemo } from 'react'
import { LoadingSpinner, ErrorBlock, SectionHeader, formatNum, StatusBadge } from '../components/SharedComponents.jsx'
import ExplainabilityPanel from '../components/ExplainabilityPanel.jsx'
import { createExport } from '../../../services/api.js'
import api from '../../../services/api.js'

const PROGRAM_OPTIONS = [
  { value: '', label: 'All Programs' },
  { value: 'PROGRAM_ACTIVE_GROWTH', label: 'Active Growth' },
  { value: 'PROGRAM_CHURN_PREVENTION', label: 'Churn Prevention' },
  { value: 'PROGRAM_14_90', label: '14/90' },
  { value: 'PROGRAM_HIGH_VALUE_RECOVERY', label: 'High Value Recovery' },
]

const LIFECYCLE_OPTIONS = [
  { value: '', label: 'All Lifecycles' },
  { value: 'ACTIVE', label: 'Active' },
  { value: 'NEW_ACTIVE', label: 'New Active' },
  { value: 'AT_RISK', label: 'At Risk' },
  { value: 'DECLINING', label: 'Declining' },
  { value: 'CHURNED', label: 'Churned' },
]

export default function DriverExplorerTab({ data, loading, errors, onRetry, initialFilter }) {
  const [filters, setFilters] = useState({
    program: initialFilter?.program || '',
    lifecycle: initialFilter?.lifecycle || '',
    segment: initialFilter?.segment || '',
    search: initialFilter?.search || '',
  })
  const [driverData, setDriverData] = useState(null)
  const [driverLoading, setDriverLoading] = useState(false)
  const [driverError, setDriverError] = useState(null)
  const [selectedDriver, setSelectedDriver] = useState(null)
  const [exporting, setExporting] = useState(false)
  const [exportResult, setExportResult] = useState(null)

  const fetchDrivers = async (override = {}) => {
    const params = { ...filters, ...override, limit: 100, offset: 0 }
    const clean = {}
    Object.entries(params).forEach(([k, v]) => { if (v) clean[k] = v })
    setDriverLoading(true)
    setDriverError(null)
    try {
      const resp = await api.get('/drivers/activity-summary', { params: clean, timeout: 30000 })
      setDriverData(resp.data)
    } catch (e) {
      setDriverError(e?.response?.data?.detail || e.message || 'Error fetching drivers')
    } finally {
      setDriverLoading(false)
    }
  }

  const handleFilterChange = (key, value) => {
    const next = { ...filters, [key]: value }
    setFilters(next)
    fetchDrivers({ [key]: value })
  }

  const handleExport = async () => {
    setExporting(true)
    setExportResult(null)
    try {
      const result = await createExport({
        source: 'driver_explorer',
        filters: {
          program: filters.program || undefined,
          lifecycle: filters.lifecycle || undefined,
          segment: filters.segment || undefined,
          search: filters.search || undefined,
        },
        export_reason: 'Driver Explorer export',
      })
      setExportResult(result)
      if (result.csv_content) {
        const blob = new Blob([result.csv_content], { type: 'text/csv' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `${result.export_id}.csv`
        a.click()
        URL.revokeObjectURL(url)
      }
    } catch (e) {
      setExportResult({ error: e?.response?.data?.detail || e.message || 'Export failed' })
    } finally {
      setExporting(false)
    }
  }

  const handleSearch = (e) => {
    if (e.key === 'Enter') {
      fetchDrivers()
    }
  }

  const drivers = driverData?.drivers || driverData?.data || driverData?.records || []
  const total = driverData?.total || drivers.length
  const hasData = driverData !== null

  return (
    <div>
      <SectionHeader title="Driver Explorer" subtitle="Tabla maestra con busqueda y filtros" />

      {/* Filters */}
      <div className="bg-white border rounded-lg p-4 mb-4">
        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex-1 min-w-[180px]">
            <label className="block text-xs text-gray-500 mb-1">Search</label>
            <input
              type="text"
              value={filters.search}
              onChange={(e) => setFilters((p) => ({ ...p, search: e.target.value }))}
              onKeyDown={handleSearch}
              placeholder="driver_id, name..."
              className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Program</label>
            <select
              value={filters.program}
              onChange={(e) => handleFilterChange('program', e.target.value)}
              className="border rounded px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400"
            >
              {PROGRAM_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Lifecycle</label>
            <select
              value={filters.lifecycle}
              onChange={(e) => handleFilterChange('lifecycle', e.target.value)}
              className="border rounded px-3 py-1.5 text-sm focus:outline-none focus:border-blue-400"
            >
              {LIFECYCLE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <button
            onClick={() => fetchDrivers()}
            className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm hover:bg-blue-700"
          >
            Search
          </button>
          <button
            onClick={handleExport}
            disabled={exporting}
            className="bg-green-600 text-white px-4 py-1.5 rounded text-sm hover:bg-green-700 disabled:opacity-50"
          >
            {exporting ? 'Exporting...' : 'Export CSV'}
          </button>
        </div>
      </div>

      {/* Results */}
      {driverLoading && <LoadingSpinner text="Buscando drivers..." />}
      {driverError && <ErrorBlock message={driverError} onRetry={() => fetchDrivers()} />}

      {!hasData && !driverLoading && !driverError && (
        <div className="bg-gray-50 border rounded-lg p-6 text-center text-sm text-gray-500">
          Use los filtros para buscar drivers.
        </div>
      )}

      {hasData && !driverLoading && !driverError && (
        <div className="bg-white border rounded-lg">
            <div className="px-4 py-2 border-b text-xs text-gray-500 flex justify-between items-center">
              <span>{formatNum(total)} drivers encontrados</span>
              <div className="flex items-center gap-2">
                {exportResult && !exportResult.error && (
                  <span className="text-green-600">Exported {exportResult.rows_count} rows</span>
                )}
                {exportResult?.error && (
                  <span className="text-red-500">Export failed</span>
                )}
              </div>
            </div>
          {drivers.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b bg-gray-50 text-gray-500">
                    <th className="text-left py-2 px-2">Driver ID</th>
                    <th className="text-left py-2 px-2">Lifecycle</th>
                    <th className="text-left py-2 px-2">Segment</th>
                    <th className="text-left py-2 px-2">Program</th>
                    <th className="text-left py-2 px-2">Movement</th>
                    <th className="text-left py-2 px-2">RNA</th>
                    <th className="text-left py-2 px-2">Last Activity</th>
                    <th className="text-center py-2 px-2">Why</th>
                  </tr>
                </thead>
                <tbody>
                  {drivers.slice(0, 100).map((d, i) => {
                    const driverId = d.driver_id || d.driver_profile_id || '—'
                    const lifecycle = d.lifecycle || d.lifecycle_stage || '—'
                    const segment = d.segment || d.driver_segment || '—'
                    const program = d.program || d.program_code || '—'
                    const movement = d.movement_status || d.movement || '—'
                    const rnaStatus = d.rna_status || (d.is_rna ? 'RNA' : 'Active')
                    const lastActivity = d.last_activity || d.last_trip_date || d.last_active || '—'
                    return (
                      <tr key={i} className="border-b last:border-0 hover:bg-gray-50">
                        <td className="py-2 px-2 font-mono text-gray-700">{driverId}</td>
                        <td className="py-2 px-2">
                          <StatusBadge status={lifecycle === 'ACTIVE' ? 'FRESH' : 'STALE'} label={lifecycle} />
                        </td>
                        <td className="py-2 px-2 text-gray-600">{segment}</td>
                        <td className="py-2 px-2 text-gray-600">{program?.replace('PROGRAM_', '')}</td>
                        <td className="py-2 px-2 text-gray-600">{movement}</td>
                        <td className="py-2 px-2">
                          <StatusBadge status={rnaStatus === 'RNA' ? 'WARNING' : 'FRESH'} label={rnaStatus} />
                        </td>
                        <td className="py-2 px-2 text-gray-500">{lastActivity}</td>
                        <td className="py-2 px-2 text-center">
                          <button
                            onClick={() => setSelectedDriver(driverId)}
                            className="text-blue-500 hover:text-blue-700 text-xs underline font-medium"
                          >
                            Why?
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-6 text-center text-sm text-gray-500">
              No se encontraron drivers con los filtros actuales.
            </div>
          )}
        </div>
      )}

      {selectedDriver && (
        <ExplainabilityPanel driverId={selectedDriver} onClose={() => setSelectedDriver(null)} />
      )}
    </div>
  )
}
