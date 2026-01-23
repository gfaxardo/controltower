import { useEffect, useState } from 'react'
import { getPhase2CScoreboard, getPhase2CBacklog, getPhase2CBreaches, runPhase2CSnapshot } from '../services/api'
import RegisterActionModal from './RegisterActionModal'

function Phase2CAccountabilityView() {
  const [scoreboard, setScoreboard] = useState([])
  const [backlog, setBacklog] = useState([])
  const [breaches, setBreaches] = useState([])
  const [loading, setLoading] = useState({ scoreboard: true, backlog: true, breaches: true })
  const [filters, setFilters] = useState({
    country: '',
    week_from: '',
    week_to: ''
  })
  const [selectedAlert, setSelectedAlert] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [snapshotRunning, setSnapshotRunning] = useState(false)

  useEffect(() => {
    loadScoreboard()
    loadBacklog()
    loadBreaches()
  }, [filters])

  const loadScoreboard = async () => {
    try {
      setLoading(prev => ({ ...prev, scoreboard: true }))
      const response = await getPhase2CScoreboard({
        country: filters.country || undefined,
        week_from: filters.week_from || undefined,
        week_to: filters.week_to || undefined
      })
      setScoreboard(response.data || [])
    } catch (error) {
      console.error('Error al cargar scoreboard:', error)
      setScoreboard([])
    } finally {
      setLoading(prev => ({ ...prev, scoreboard: false }))
    }
  }

  const loadBacklog = async () => {
    try {
      setLoading(prev => ({ ...prev, backlog: true }))
      const response = await getPhase2CBacklog()
      setBacklog(response.data || [])
    } catch (error) {
      console.error('Error al cargar backlog:', error)
      setBacklog([])
    } finally {
      setLoading(prev => ({ ...prev, backlog: false }))
    }
  }

  const loadBreaches = async () => {
    try {
      setLoading(prev => ({ ...prev, breaches: true }))
      const response = await getPhase2CBreaches({
        country: filters.country || undefined
      })
      setBreaches(response.data || [])
    } catch (error) {
      console.error('Error al cargar breaches:', error)
      setBreaches([])
    } finally {
      setLoading(prev => ({ ...prev, breaches: false }))
    }
  }

  const handleRunSnapshot = async () => {
    try {
      setSnapshotRunning(true)
      await runPhase2CSnapshot()
      alert('Snapshot ejecutado exitosamente')
      loadScoreboard()
      loadBreaches()
    } catch (error) {
      alert('Error al ejecutar snapshot: ' + (error.response?.data?.detail || error.message))
    } finally {
      setSnapshotRunning(false)
    }
  }

  const handleRegisterAction = (breach) => {
    // Construir alert desde breach para el modal
    const alert = {
      week_start: breach.week_start,
      country: breach.country,
      city_norm: breach.city_norm,
      lob_base: breach.lob_base,
      segment: breach.segment,
      why: breach.why,
      alert_key: breach.alert_key
    }
    setSelectedAlert(alert)
    setIsModalOpen(true)
  }

  const handleActionRegistered = () => {
    loadBreaches()
    loadScoreboard()
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return '-'
    const date = new Date(dateStr)
    return date.toLocaleDateString('es-ES', { year: 'numeric', month: 'short', day: 'numeric' })
  }

  const formatPercent = (num) => {
    if (num === null || num === undefined) return '-'
    return `${(num * 100).toFixed(1)}%`
  }

  const formatCurrency = (num) => {
    if (num === null || num === undefined) return '-'
    return num.toLocaleString('es-ES', { style: 'currency', currency: 'PEN', maximumFractionDigits: 0 })
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow-md mt-8">
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold">Fase 2C – Ejecución y Accountability</h3>
            <p className="text-sm text-gray-600">
              Medición de disciplina de ejecución de alertas/acciones 2B, SLA y seguimiento.
            </p>
          </div>
          <button
            onClick={handleRunSnapshot}
            disabled={snapshotRunning}
            className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:bg-gray-400"
          >
            {snapshotRunning ? 'Ejecutando...' : 'Ejecutar Snapshot'}
          </button>
        </div>
      </div>

      {/* Filtros */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">País</label>
          <select
            value={filters.country}
            onChange={(e) => setFilters({ ...filters, country: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todos</option>
            <option value="PE">Perú</option>
            <option value="CO">Colombia</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Semana desde</label>
          <input
            type="date"
            value={filters.week_from}
            onChange={(e) => setFilters({ ...filters, week_from: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Semana hasta</label>
          <input
            type="date"
            value={filters.week_to}
            onChange={(e) => setFilters({ ...filters, week_to: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="flex items-end">
          <button
            onClick={() => setFilters({ country: '', week_from: '', week_to: '' })}
            className="w-full px-4 py-2 rounded bg-gray-200 text-gray-700 hover:bg-gray-300"
          >
            Limpiar filtros
          </button>
        </div>
      </div>

      {/* A) Scoreboard */}
      <div className="mb-8">
        <h4 className="text-md font-semibold mb-2">A) Scoreboard Semanal</h4>
        {loading.scoreboard ? (
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-1/3 mb-4"></div>
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-10 bg-gray-200 rounded"></div>
              ))}
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Semana</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">País</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Alertas Total</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Alertas Críticas</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">% Críticas con Acción</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Breaches</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">DONE</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">MISSED</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">OPEN</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">% DONE a Tiempo</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {scoreboard.length === 0 ? (
                  <tr>
                    <td colSpan="10" className="px-4 py-4 text-center text-gray-500">
                      No hay datos disponibles
                    </td>
                  </tr>
                ) : (
                  scoreboard.map((row) => (
                    <tr key={`${row.week_start}-${row.country}`} className="hover:bg-gray-50">
                      <td className="px-3 py-2 text-sm text-gray-900">{formatDate(row.week_start)}</td>
                      <td className="px-3 py-2 text-sm text-gray-700">{row.country}</td>
                      <td className="px-3 py-2 text-sm text-right">{row.alerts_total || 0}</td>
                      <td className="px-3 py-2 text-sm text-right font-semibold">{row.alerts_critical || 0}</td>
                      <td className="px-3 py-2 text-sm text-right">{formatPercent(row.pct_critical_with_action)}</td>
                      <td className="px-3 py-2 text-sm text-right">
                        <span className={`font-semibold ${(row.sla_breaches || 0) > 0 ? 'text-red-600' : 'text-gray-700'}`}>
                          {row.sla_breaches || 0}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-sm text-right text-green-600">{row.actions_done || 0}</td>
                      <td className="px-3 py-2 text-sm text-right text-red-600">{row.actions_missed || 0}</td>
                      <td className="px-3 py-2 text-sm text-right text-yellow-600">{row.actions_open || 0}</td>
                      <td className="px-3 py-2 text-sm text-right">{formatPercent(row.pct_done_on_time)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* B) Backlog */}
      <div className="mb-8">
        <h4 className="text-md font-semibold mb-2">B) Backlog por Owner</h4>
        {loading.backlog ? (
          <div className="animate-pulse space-y-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="h-16 bg-gray-200 rounded"></div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {backlog.length === 0 ? (
              <div className="text-gray-500 text-sm">No hay datos disponibles</div>
            ) : (
              backlog.map((item) => (
                <div key={`${item.owner_role}-${item.country}`} className="border rounded-lg p-4">
                  <div className="font-semibold text-sm mb-2">{item.owner_role}</div>
                  <div className="text-xs text-gray-600 mb-3">{item.country || 'Todos'}</div>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm">Open:</span>
                      <span className="font-semibold">{item.open_count || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Next 7d:</span>
                      <span className="font-semibold text-yellow-600">{item.due_next_7d || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Overdue:</span>
                      <span className="font-semibold text-red-600">{item.overdue_count || 0}</span>
                    </div>
                    {item.oldest_open_age_days !== null && (
                      <div className="flex justify-between text-xs text-gray-500 mt-2">
                        <span>Más antigua:</span>
                        <span>{item.oldest_open_age_days} días</span>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* C) Breaches */}
      <div>
        <h4 className="text-md font-semibold mb-2">C) Breaches de SLA</h4>
        {loading.breaches ? (
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-1/3 mb-4"></div>
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-12 bg-gray-200 rounded"></div>
              ))}
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Semana</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">País/Ciudad/LOB</th>
                  <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Severidad</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Causa</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">SLA Due</th>
                  <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase">Acción</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {breaches.length === 0 ? (
                  <tr>
                    <td colSpan="6" className="px-4 py-4 text-center text-gray-500">
                      No hay breaches de SLA
                    </td>
                  </tr>
                ) : (
                  breaches.map((breach) => (
                    <tr key={breach.alert_key} className="hover:bg-gray-50">
                      <td className="px-3 py-2 text-sm text-gray-900">{formatDate(breach.week_start)}</td>
                      <td className="px-3 py-2 text-sm text-gray-700">
                        <div className="text-xs">
                          {breach.country || '-'}
                          {breach.city_norm && ` · ${breach.city_norm}`}
                          {breach.lob_base && ` · ${breach.lob_base}`}
                          {breach.segment && ` · ${breach.segment}`}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-sm text-right font-semibold">
                        {formatCurrency(breach.severity_score)}
                      </td>
                      <td className="px-3 py-2 text-sm text-gray-700 max-w-xs truncate" title={breach.why}>
                        {breach.why}
                      </td>
                      <td className="px-3 py-2 text-sm text-gray-700">
                        {breach.sla_due_at ? formatDate(breach.sla_due_at.split('T')[0]) : '-'}
                      </td>
                      <td className="px-3 py-2 text-sm text-center">
                        {!breach.has_action ? (
                          <button
                            onClick={() => handleRegisterAction(breach)}
                            className="px-3 py-1 text-xs rounded bg-red-600 text-white hover:bg-red-700"
                          >
                            Crear acción
                          </button>
                        ) : (
                          <span className="text-xs text-green-600">✓ Acción registrada</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <RegisterActionModal
        alert={selectedAlert}
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false)
          setSelectedAlert(null)
        }}
        onSuccess={handleActionRegistered}
      />
    </div>
  )
}

export default Phase2CAccountabilityView
