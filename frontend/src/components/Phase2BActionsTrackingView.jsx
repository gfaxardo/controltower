import { useEffect, useState } from 'react'
import { getPhase2BActions, updatePhase2BAction } from '../services/api'

const STATUS_OPTIONS = ['OPEN', 'IN_PROGRESS', 'DONE', 'MISSED']
const STATUS_COLORS = {
  'OPEN': 'bg-blue-100 text-blue-800',
  'IN_PROGRESS': 'bg-yellow-100 text-yellow-800',
  'DONE': 'bg-green-100 text-green-800',
  'MISSED': 'bg-red-100 text-red-800'
}

function Phase2BActionsTrackingView() {
  const [actions, setActions] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({
    week_start: '',
    owner_role: '',
    status: ''
  })
  const [updatingId, setUpdatingId] = useState(null)

  useEffect(() => {
    loadActions()
  }, [filters])

  const loadActions = async () => {
    try {
      setLoading(true)
      const filterParams = {}
      if (filters.week_start) filterParams.week_start = filters.week_start
      if (filters.owner_role) filterParams.owner_role = filters.owner_role
      if (filters.status) filterParams.status = filters.status

      const response = await getPhase2BActions(filterParams)
      setActions(response.data || [])
    } catch (error) {
      console.error('Error al cargar acciones:', error)
      setActions([])
    } finally {
      setLoading(false)
    }
  }

  const handleStatusChange = async (actionId, newStatus) => {
    try {
      setUpdatingId(actionId)
      await updatePhase2BAction(actionId, { status: newStatus })
      loadActions()
    } catch (error) {
      console.error('Error al actualizar acción:', error)
      alert('Error al actualizar acción: ' + (error.response?.data?.detail || error.message))
    } finally {
      setUpdatingId(null)
    }
  }

  const formatDate = (dateStr) => {
    if (!dateStr) return '-'
    const date = new Date(dateStr)
    return date.toLocaleDateString('es-ES', { year: 'numeric', month: 'short', day: 'numeric' })
  }

  const formatDateTime = (dateStr) => {
    if (!dateStr) return '-'
    const date = new Date(dateStr)
    return date.toLocaleString('es-ES', { 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const getOwnerRoles = () => {
    const roles = new Set()
    actions.forEach(action => {
      if (action.owner_role) roles.add(action.owner_role)
    })
    return Array.from(roles).sort()
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow-md mt-8">
      <div className="mb-6">
        <h3 className="text-lg font-semibold">Seguimiento Fase 2B - Acciones</h3>
        <p className="text-sm text-gray-600">
          Gestión y seguimiento de acciones operativas para alertas semanales.
        </p>
      </div>

      {/* Filtros */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Semana</label>
          <input
            type="date"
            value={filters.week_start}
            onChange={(e) => setFilters({ ...filters, week_start: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Owner</label>
          <select
            value={filters.owner_role}
            onChange={(e) => setFilters({ ...filters, owner_role: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todos</option>
            {getOwnerRoles().map(role => (
              <option key={role} value={role}>{role}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
          <select
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Todos</option>
            {STATUS_OPTIONS.map(status => (
              <option key={status} value={status}>{status}</option>
            ))}
          </select>
        </div>
        <div className="flex items-end">
          <button
            onClick={() => setFilters({ week_start: '', owner_role: '', status: '' })}
            className="w-full px-4 py-2 rounded bg-gray-200 text-gray-700 hover:bg-gray-300"
          >
            Limpiar filtros
          </button>
        </div>
      </div>

      {/* Tabla */}
      {loading ? (
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
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Causa</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Acción</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Owner</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Due Date</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Creado</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {actions.length === 0 ? (
                <tr>
                  <td colSpan="8" className="px-4 py-4 text-center text-gray-500">
                    No hay acciones disponibles
                  </td>
                </tr>
              ) : (
                actions.map((action) => (
                  <tr key={action.phase2b_action_id} className="hover:bg-gray-50">
                    <td className="px-3 py-2 text-sm text-gray-900 whitespace-nowrap">
                      {formatDate(action.week_start)}
                    </td>
                    <td className="px-3 py-2 text-sm text-gray-700">
                      <div className="text-xs">
                        {action.country || '-'}
                        {action.city_norm && ` · ${action.city_norm}`}
                        {action.lob_base && ` · ${action.lob_base}`}
                        {action.segment && ` · ${action.segment}`}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-sm text-gray-700 max-w-xs truncate" title={action.root_cause}>
                      {action.root_cause}
                    </td>
                    <td className="px-3 py-2 text-sm text-gray-700 max-w-xs">
                      <div className="font-semibold text-xs">{action.action_type}</div>
                      <div className="text-xs text-gray-500 truncate" title={action.action_description}>
                        {action.action_description}
                      </div>
                    </td>
                    <td className="px-3 py-2 text-sm text-gray-700">
                      {action.owner_role}
                    </td>
                    <td className="px-3 py-2 text-sm text-gray-700">
                      <span className={action.due_date && new Date(action.due_date) < new Date() && action.status !== 'DONE' ? 'text-red-600 font-semibold' : ''}>
                        {formatDate(action.due_date)}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-sm">
                      {updatingId === action.phase2b_action_id ? (
                        <span className="text-gray-400">Actualizando...</span>
                      ) : action.status === 'DONE' ? (
                        <span className={`px-2 py-1 rounded-full text-xs font-semibold ${STATUS_COLORS[action.status] || 'bg-gray-100 text-gray-800'}`}>
                          {action.status}
                        </span>
                      ) : (
                        <select
                          value={action.status}
                          onChange={(e) => handleStatusChange(action.phase2b_action_id, e.target.value)}
                          className={`px-2 py-1 rounded-full text-xs font-semibold border-0 ${STATUS_COLORS[action.status] || 'bg-gray-100 text-gray-800'}`}
                        >
                          {STATUS_OPTIONS.map(status => (
                            <option key={status} value={status}>{status}</option>
                          ))}
                        </select>
                      )}
                    </td>
                    <td className="px-3 py-2 text-sm text-gray-500 text-xs">
                      {formatDateTime(action.created_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {!loading && actions.length > 0 && (
        <div className="mt-4 text-sm text-gray-600">
          Total: {actions.length} acción(es)
        </div>
      )}
    </div>
  )
}

export default Phase2BActionsTrackingView
