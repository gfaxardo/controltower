import { useState, useEffect } from 'react'
import { getRealMonthlySplit, getPlanMonthlySplit, getOverlapMonthly } from '../services/api'

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

function MonthlySplitView({ filters = {} }) {
  const [activeTab, setActiveTab] = useState('real')
  const [realData, setRealData] = useState([])
  const [planData, setPlanData] = useState([])
  const [overlapData, setOverlapData] = useState([])
  const [loading, setLoading] = useState(true)
  const [hasOverlap, setHasOverlap] = useState(false)

  const yearReal = filters.year_real || 2025
  const yearPlan = filters.year_plan || 2026

  useEffect(() => {
    loadAllData()
  }, [filters])

  const loadAllData = async () => {
    try {
      setLoading(true)
      
      const [realResponse, planResponse, overlapResponse] = await Promise.all([
        getRealMonthlySplit({
          country: filters.country || undefined,
          city: filters.city || undefined,
          lob_base: filters.line_of_business || undefined,
          segment: filters.segment || undefined,
          year: yearReal
        }),
        getPlanMonthlySplit({
          country: filters.country || undefined,
          city: filters.city || undefined,
          lob_base: filters.line_of_business || undefined,
          segment: filters.segment || undefined,
          year: yearPlan
        }),
        getOverlapMonthly({
          country: filters.country || undefined,
          city: filters.city || undefined,
          lob_base: filters.line_of_business || undefined,
          segment: filters.segment || undefined
        })
      ])
      
      setRealData(realResponse.data || [])
      setPlanData(planResponse.data || [])
      setOverlapData(overlapResponse.data || [])
      setHasOverlap(overlapResponse.has_overlap || false)
    } catch (error) {
      console.error('Error al cargar datos:', error)
      setRealData([])
      setPlanData([])
      setOverlapData([])
      setHasOverlap(false)
    } finally {
      setLoading(false)
    }
  }

  const formatNumber = (num) => {
    if (num === null || num === undefined) return '-'
    return num.toLocaleString('es-ES', { maximumFractionDigits: 2 })
  }

  const formatCurrency = (num) => {
    if (num === null || num === undefined) return '-'
    return num.toLocaleString('es-ES', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
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

  const renderRealTable = () => (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mes</th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Trips Real</th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Revenue Real</th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Drivers Activos</th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Ticket Promedio</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {realData.length > 0 ? (
            realData.map((row) => {
              const [yearStr, monthStr] = row.period.split('-')
              const monthNum = parseInt(monthStr)
              const mes = MESES.find(m => m.num === monthNum) || { nombre: monthStr }
              return (
                <tr key={row.period} className="hover:bg-gray-50">
                  <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                    {mes.nombre} {yearStr}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                    {formatNumber(row.trips_real_completed)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                    {formatNumber(row.revenue_real_proxy)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                    {formatNumber(row.active_drivers_real)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                    {formatCurrency(row.avg_ticket_real)}
                  </td>
                </tr>
              )
            })
          ) : (
            <tr>
              <td colSpan="5" className="px-4 py-8 text-center text-gray-500">
                No hay datos Real para {yearReal}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )

  const renderPlanTable = () => (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mes</th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Trips Plan</th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Revenue Plan</th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Drivers Plan</th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Ticket Plan</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {planData.length > 0 ? (
            planData.map((row) => {
              const [yearStr, monthStr] = row.period.split('-')
              const monthNum = parseInt(monthStr)
              const mes = MESES.find(m => m.num === monthNum) || { nombre: monthStr }
              return (
                <tr key={row.period} className="hover:bg-gray-50">
                  <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                    {mes.nombre} {yearStr}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                    {formatNumber(row.projected_trips)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                    {formatNumber(row.projected_revenue)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                    {formatNumber(row.projected_drivers)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                    {formatCurrency(row.projected_ticket)}
                  </td>
                </tr>
              )
            })
          ) : (
            <tr>
              <td colSpan="5" className="px-4 py-8 text-center text-gray-500">
                No hay datos Plan para {yearPlan}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )

  const renderOverlapTable = () => {
    if (!hasOverlap || overlapData.length === 0) {
      return (
        <div className="p-8 text-center text-gray-600 bg-gray-50 rounded-lg">
          <p className="text-lg font-medium mb-2">
            Aún no hay meses comparables entre Real {yearReal} y Plan {yearPlan}
          </p>
          <p className="text-sm">
            La comparación se activará cuando existan meses con datos en ambos (Plan y Real) para el mismo período.
          </p>
        </div>
      )
    }

    return (
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mes</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Trips Plan</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Trips Real</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Gap Trips</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Revenue Plan</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Revenue Real</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Gap Revenue</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {overlapData.map((row) => {
              const [yearStr, monthStr] = row.period.split('-')
              const monthNum = parseInt(monthStr)
              const mes = MESES.find(m => m.num === monthNum) || { nombre: monthStr }
              return (
                <tr key={row.period} className="hover:bg-gray-50">
                  <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                    {mes.nombre} {yearStr}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                    {formatNumber(row.projected_trips)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                    {formatNumber(row.trips_real_completed)}
                  </td>
                  <td className={`px-4 py-3 whitespace-nowrap text-sm text-right ${
                    row.gap_trips && row.gap_trips < 0 ? 'text-red-600' : 
                    row.gap_trips && row.gap_trips > 0 ? 'text-green-600' : 'text-gray-900'
                  }`}>
                    {formatNumber(row.gap_trips)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                    {formatNumber(row.projected_revenue)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                    {formatNumber(row.revenue_real_proxy)}
                  </td>
                  <td className={`px-4 py-3 whitespace-nowrap text-sm text-right ${
                    row.gap_revenue && row.gap_revenue < 0 ? 'text-red-600' : 
                    row.gap_revenue && row.gap_revenue > 0 ? 'text-green-600' : 'text-gray-900'
                  }`}>
                    {formatNumber(row.gap_revenue)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      <div className="mb-4">
        <h3 className="text-lg font-semibold mb-4">Vista Mensual - Plan {yearPlan} vs Real {yearReal}</h3>
        
        {/* Tabs */}
        <div className="border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('real')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'real'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Real (Mensual) - {yearReal}
            </button>
            <button
              onClick={() => setActiveTab('plan')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'plan'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Plan (Mensual) - {yearPlan}
            </button>
            <button
              onClick={() => setActiveTab('overlap')}
              className={`py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'overlap'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Comparable (Overlap)
            </button>
          </nav>
        </div>
      </div>

      {/* Tab Content */}
      <div className="mt-4">
        {activeTab === 'real' && renderRealTable()}
        {activeTab === 'plan' && renderPlanTable()}
        {activeTab === 'overlap' && renderOverlapTable()}
      </div>
    </div>
  )
}

export default MonthlySplitView
