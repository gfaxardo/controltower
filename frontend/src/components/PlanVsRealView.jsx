import { useState, useEffect } from 'react'
import { getPlanVsRealMonthly, getPlanVsRealAlerts } from '../services/api'

function PlanVsRealView({ filters = {} }) {
  const [comparisonData, setComparisonData] = useState([])
  const [alertsData, setAlertsData] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('comparison') // 'comparison' o 'alerts'

  useEffect(() => {
    if (activeTab === 'comparison') {
      loadComparisonData()
    } else {
      loadAlertsData()
    }
  }, [filters, activeTab])

  const loadComparisonData = async () => {
    try {
      setLoading(true)
      const response = await getPlanVsRealMonthly({
        country: filters.country || undefined,
        city: filters.city || undefined,
        lob_base: filters.line_of_business || undefined,
        segment: filters.segment || undefined,
        month: filters.month || undefined
      })
      setComparisonData(response.data || [])
    } catch (error) {
      console.error('Error al cargar comparación Plan vs Real:', error)
      setComparisonData([])
    } finally {
      setLoading(false)
    }
  }

  const loadAlertsData = async () => {
    try {
      setLoading(true)
      const response = await getPlanVsRealAlerts({
        country: filters.country || undefined,
        month: filters.month || undefined,
        alert_level: filters.alert_level || undefined
      })
      setAlertsData(response.data || [])
    } catch (error) {
      console.error('Error al cargar alertas Plan vs Real:', error)
      setAlertsData([])
    } finally {
      setLoading(false)
    }
  }

  const formatNumber = (num) => {
    if (num === null || num === undefined) return '-'
    return Math.round(num).toLocaleString('es-ES')
  }

  const formatCurrency = (num, currencyCode = 'PEN') => {
    if (num === null || num === undefined) return '-'
    // Mapeo de currency_code a locale y símbolo
    const currencyMap = {
      'PEN': { currency: 'PEN', locale: 'es-PE' },
      'COP': { currency: 'COP', locale: 'es-CO' }
    }
    const config = currencyMap[currencyCode] || currencyMap['PEN']
    return num.toLocaleString(config.locale, { style: 'currency', currency: config.currency, maximumFractionDigits: 0 })
  }

  const formatPercent = (num) => {
    if (num === null || num === undefined) return '-'
    return `${num.toFixed(1)}%`
  }

  const getStatusBadge = (status) => {
    const styles = {
      'matched': 'bg-green-100 text-green-800',
      'plan_only': 'bg-blue-100 text-blue-800',
      'real_only': 'bg-yellow-100 text-yellow-800',
      'unknown': 'bg-gray-100 text-gray-800'
    }
    
    const labels = {
      'matched': 'Match',
      'plan_only': 'Solo Plan',
      'real_only': 'Solo Real',
      'unknown': 'Desconocido'
    }
    
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-semibold ${styles[status] || 'bg-gray-100'}`}>
        {labels[status] || status}
      </span>
    )
  }

  const getAlertBadge = (level) => {
    const styles = {
      'CRITICO': 'bg-red-100 text-red-800',
      'MEDIO': 'bg-orange-100 text-orange-800',
      'OK': 'bg-green-100 text-green-800'
    }
    
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-semibold ${styles[level] || 'bg-gray-100'}`}>
        {level}
      </span>
    )
  }

  const formatMonth = (monthStr) => {
    if (!monthStr) return '-'
    const date = new Date(monthStr)
    return date.toLocaleDateString('es-ES', { year: 'numeric', month: 'short' })
  }

  if (loading) {
    return (
      <div className="bg-white p-6 rounded-lg shadow-md">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-12 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">Plan vs Real - Comparación Mensual</h3>
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('comparison')}
            className={`px-4 py-2 rounded ${activeTab === 'comparison' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            Comparación
          </button>
          <button
            onClick={() => setActiveTab('alerts')}
            className={`px-4 py-2 rounded ${activeTab === 'alerts' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            Alertas ({alertsData.length})
          </button>
        </div>
      </div>

      {activeTab === 'comparison' ? (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Mes</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">País</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ciudad</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">LOB</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Segmento</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Trips Plan</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Trips Real</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Gap Trips</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Revenue Plan</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Revenue Real</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Gap Revenue</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Estado</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {comparisonData.length === 0 ? (
                <tr>
                  <td colSpan="12" className="px-4 py-4 text-center text-gray-500">
                    No hay datos disponibles
                  </td>
                </tr>
              ) : (
                comparisonData.slice(0, 50).map((row, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatMonth(row.month)}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                      {row.country || '-'}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                      {row.city_norm_real || '-'}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                      {row.lob_base || '-'}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                      {row.segment || '-'}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900 text-right">
                      {formatNumber(row.projected_trips)}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900 text-right">
                      {formatNumber(row.trips_real_completed)}
                    </td>
                    <td className={`px-4 py-4 whitespace-nowrap text-sm text-right ${
                      row.gap_trips < 0 ? 'text-red-600' : row.gap_trips > 0 ? 'text-green-600' : 'text-gray-900'
                    }`}>
                      {formatNumber(row.gap_trips)}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900 text-right">
                      {formatCurrency(row.projected_revenue)}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900 text-right">
                      {formatCurrency(row.revenue_real_proxy)}
                    </td>
                    <td className={`px-4 py-4 whitespace-nowrap text-sm text-right ${
                      row.gap_revenue_proxy < 0 ? 'text-red-600' : row.gap_revenue_proxy > 0 ? 'text-green-600' : 'text-gray-900'
                    }`}>
                      {formatCurrency(row.gap_revenue_proxy)}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-center">
                      {getStatusBadge(row.status_bucket)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          {comparisonData.length > 50 && (
            <div className="mt-2 text-sm text-gray-500 text-center">
              Mostrando 50 de {comparisonData.length} registros
            </div>
          )}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Mes</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">País</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ciudad</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">LOB</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Segmento</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Gap Trips</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Gap Trips %</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Gap Revenue</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Gap Revenue %</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Nivel</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {alertsData.length === 0 ? (
                <tr>
                  <td colSpan="10" className="px-4 py-4 text-center text-gray-500">
                    No hay alertas disponibles
                  </td>
                </tr>
              ) : (
                alertsData.map((row, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatMonth(row.month)}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                      {row.country || '-'}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                      {row.city_norm_real || '-'}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                      {row.lob_base || '-'}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                      {row.segment || '-'}
                    </td>
                    <td className={`px-4 py-4 whitespace-nowrap text-sm text-right ${
                      row.gap_trips < 0 ? 'text-red-600' : 'text-gray-900'
                    }`}>
                      {formatNumber(row.gap_trips)}
                    </td>
                    <td className={`px-4 py-4 whitespace-nowrap text-sm text-right ${
                      row.gap_trips_pct < 0 ? 'text-red-600' : 'text-gray-900'
                    }`}>
                      {formatPercent(row.gap_trips_pct)}
                    </td>
                    <td className={`px-4 py-4 whitespace-nowrap text-sm text-right ${
                      row.gap_revenue_proxy < 0 ? 'text-red-600' : 'text-gray-900'
                    }`}>
                      {formatCurrency(row.gap_revenue_proxy)}
                    </td>
                    <td className={`px-4 py-4 whitespace-nowrap text-sm text-right ${
                      row.gap_revenue_pct < 0 ? 'text-red-600' : 'text-gray-900'
                    }`}>
                      {formatPercent(row.gap_revenue_pct)}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-center">
                      {getAlertBadge(row.alert_level)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default PlanVsRealView
