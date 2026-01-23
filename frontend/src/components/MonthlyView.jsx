import { useState, useEffect } from 'react'
import { getCoreMonthlySummary, getIngestionStatus } from '../services/api'

const MESES = [
  { num: 1, nombre: 'Enero', abrev: 'Ene' },
  { num: 2, nombre: 'Febrero', abrev: 'Feb' },
  { num: 3, nombre: 'Marzo', abrev: 'Mar' },
  { num: 4, nombre: 'Abril', abrev: 'Abr' },
  { num: 5, nombre: 'Mayo', abrev: 'May' },
  { num: 6, nombre: 'Junio', abrev: 'Jun' },
  { num: 7, nombre: 'Julio', abrev: 'Jul' },
  { num: 8, nombre: 'Agosto', abrev: 'Ago' },
  { num: 9, nombre: 'Septiembre', abrev: 'Set' },
  { num: 10, nombre: 'Octubre', abrev: 'Oct' },
  { num: 11, nombre: 'Noviembre', abrev: 'Nov' },
  { num: 12, nombre: 'Diciembre', abrev: 'Dic' }
]

function MonthlyView({ filters = {} }) {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [ingestionStatus, setIngestionStatus] = useState(null)

  useEffect(() => {
    loadData()
    loadIngestionStatus()
  }, [filters])

  const loadIngestionStatus = async () => {
    try {
      const status = await getIngestionStatus()
      setIngestionStatus(status)
    } catch (error) {
      console.error('Error al cargar estado de ingesta:', error)
    }
  }

  const loadData = async () => {
    try {
      setLoading(true)
      const response = await getCoreMonthlySummary({
        country: filters.country || undefined,
        city: filters.city || undefined,
        line_of_business: filters.line_of_business || undefined,
        year_real: filters.year_real || 2025,
        year_plan: filters.year_plan || 2026
      })
      setData(response.data || [])
    } catch (error) {
      console.error('Error al cargar datos mensuales:', error)
      setData([])
    } finally {
      setLoading(false)
    }
  }

  const dataByPeriod = {}
  data.forEach(row => {
    if (row.period) {
      dataByPeriod[row.period] = row
    }
  })

  const formatNumber = (num) => {
    if (num === null || num === undefined) return '-'
    return num.toLocaleString('es-ES', { maximumFractionDigits: 2 })
  }

  const formatPercent = (num) => {
    if (num === null || num === undefined) return '-'
    return `${num.toFixed(2)}%`
  }

  if (loading) {
    return (
      <div className="bg-white p-6 rounded-lg shadow-md">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="space-y-3">
            {[...Array(12)].map((_, i) => (
              <div key={i} className="h-12 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  const year = filters.year_plan || 2026
  const displayedMonths = data.slice(0, 12)

  const ingestionStatusText = ingestionStatus 
    ? (ingestionStatus.is_complete_2025 
        ? `Real 2025 completo` 
        : `Real 2025 cargado hasta mes ${ingestionStatus.max_month || 0}`)
    : ''

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">Vista Mensual - Plan {filters.year_plan || 2026} vs Real {filters.year_real || 2025}</h3>
        {ingestionStatusText && (
          <span className="text-sm text-gray-600">{ingestionStatusText}</span>
        )}
      </div>
      
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Mes
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Trips Plan
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Revenue Plan
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Trips Real
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Revenue Real (Comisión Yego)
                <span className="ml-1 text-xs text-gray-400" title="Fuente: comision_empresa_asociada viene negativa; se invierte para mostrar revenue positivo. Ver commission_yego_signed para auditoría.">ℹ️</span>
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Delta Trips
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Delta Revenue
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                Estado
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {displayedMonths.map((row) => {
              const period = row.period
              const [yearStr, monthStr] = period.split('-')
              const monthNum = parseInt(monthStr)
              const mes = MESES.find(m => m.num === monthNum) || { nombre: monthStr }
              
              return (
                <tr key={period} className="hover:bg-gray-50">
                  <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                    {mes.nombre} {yearStr}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                    {formatNumber(row.trips_plan)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                    {formatNumber(row.revenue_plan)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                    {formatNumber(row.trips_real)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                    {formatNumber(row.revenue_real)}
                  </td>
                  <td className={`px-4 py-3 whitespace-nowrap text-sm text-right ${
                    row.delta_trips_abs && row.delta_trips_abs < 0 ? 'text-red-600' : 
                    row.delta_trips_abs && row.delta_trips_abs > 0 ? 'text-green-600' : 'text-gray-900'
                  }`}>
                    {row.comparison_status === 'COMPARABLE' ? formatNumber(row.delta_trips_abs) : '-'}
                  </td>
                  <td className={`px-4 py-3 whitespace-nowrap text-sm text-right ${
                    row.delta_revenue_abs && row.delta_revenue_abs < 0 ? 'text-red-600' : 
                    row.delta_revenue_abs && row.delta_revenue_abs > 0 ? 'text-green-600' : 'text-gray-900'
                  }`}>
                    {row.comparison_status === 'COMPARABLE' ? formatNumber(row.delta_revenue_abs) : '-'}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-center">
                    {row.comparison_status === 'COMPARABLE' && (
                      <span className="px-2 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-800">
                        OK
                      </span>
                    )}
                    {row.comparison_status === 'NO_REAL_YET' && (
                      <span className="px-2 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-800">
                        Sin Real
                      </span>
                    )}
                    {row.comparison_status === 'NOT_COMPARABLE' && (
                      <span className="px-2 py-1 rounded-full text-xs font-semibold bg-yellow-100 text-yellow-800">
                        No Comparable
                      </span>
                    )}
                    {row.is_partial_real && (
                      <span className="ml-2 px-2 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">
                        REAL PARCIAL
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default MonthlyView
