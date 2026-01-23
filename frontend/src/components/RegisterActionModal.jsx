import { useState } from 'react'
import { createPhase2BAction } from '../services/api'

const ROOT_CAUSES = [
  'Falta supply (drivers por debajo del plan)',
  'Baja productividad (trips/driver)',
  'Cae ingreso por viaje (take/promos/reversos)',
  'Principalmente unitario',
  'Principalmente volumen',
  'Sin clasificar'
]

const ACTION_TYPES = [
  'Ajuste de pricing',
  'Campaña de promociones',
  'Aumento de supply',
  'Mejora de productividad',
  'Análisis de reversos',
  'Ajuste de comisiones',
  'Otro'
]

const OWNER_ROLES = [
  'Operations Manager',
  'Revenue Manager',
  'Supply Manager',
  'Product Manager',
  'Country Manager',
  'Analyst'
]

function RegisterActionModal({ alert, isOpen, onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    root_cause: '',
    action_type: '',
    action_description: '',
    owner_role: '',
    due_date: ''
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  if (!isOpen || !alert) return null

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const actionData = {
        week_start: alert.week_start,
        country: alert.country,
        city_norm: alert.city_norm || null,
        lob_base: alert.lob_base || null,
        segment: alert.segment || null,
        alert_type: alert.why || 'Alerta semanal',
        root_cause: formData.root_cause,
        action_type: formData.action_type,
        action_description: formData.action_description,
        owner_role: formData.owner_role,
        due_date: formData.due_date
      }

      await createPhase2BAction(actionData)
      onSuccess()
      onClose()
      // Reset form
      setFormData({
        root_cause: '',
        action_type: '',
        action_description: '',
        owner_role: '',
        due_date: ''
      })
    } catch (err) {
      setError(err.response?.data?.detail || 'Error al registrar acción')
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    })
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold">Registrar Acción</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            ✕
          </button>
        </div>

        <div className="mb-4 p-3 bg-gray-50 rounded">
          <div className="text-sm text-gray-600">
            <div><strong>Semana:</strong> {alert.week_start}</div>
            <div><strong>País/Ciudad/LOB:</strong> {alert.country} · {alert.city_norm || '-'} · {alert.lob_base || '-'}</div>
            <div><strong>Alerta:</strong> {alert.why}</div>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Causa raíz <span className="text-red-500">*</span>
              </label>
              <select
                name="root_cause"
                value={formData.root_cause}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Seleccionar...</option>
                {ROOT_CAUSES.map(cause => (
                  <option key={cause} value={cause}>{cause}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Tipo de acción <span className="text-red-500">*</span>
              </label>
              <select
                name="action_type"
                value={formData.action_type}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Seleccionar...</option>
                {ACTION_TYPES.map(type => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Descripción de la acción <span className="text-red-500">*</span>
              </label>
              <textarea
                name="action_description"
                value={formData.action_description}
                onChange={handleChange}
                required
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Describe la acción a realizar..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Owner (Rol) <span className="text-red-500">*</span>
              </label>
              <select
                name="owner_role"
                value={formData.owner_role}
                onChange={handleChange}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Seleccionar...</option>
                {OWNER_ROLES.map(role => (
                  <option key={role} value={role}>{role}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Fecha límite <span className="text-red-500">*</span>
              </label>
              <input
                type="date"
                name="due_date"
                value={formData.due_date}
                onChange={handleChange}
                required
                min={new Date().toISOString().split('T')[0]}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {error && (
            <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
              {error}
            </div>
          )}

          <div className="mt-6 flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded bg-gray-200 text-gray-700 hover:bg-gray-300"
              disabled={loading}
            >
              Cancelar
            </button>
            <button
              type="submit"
              className="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:bg-gray-400"
              disabled={loading}
            >
              {loading ? 'Guardando...' : 'Registrar Acción'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default RegisterActionModal
