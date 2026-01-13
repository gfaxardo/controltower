import { useState, useEffect } from 'react'
import { getPlanOutOfUniverse, getPlanMissing, getIngestionStatus } from '../services/api'

function PlanTabs({ filters = {}, activeTab, onTabChange }) {
  const [outOfUniverse, setOutOfUniverse] = useState([])
  const [missing, setMissing] = useState([])
  const [loading, setLoading] = useState(false)
  const [ingestionStatus, setIngestionStatus] = useState(null)

  useEffect(() => {
    if (activeTab === 'out_of_universe' || activeTab === 'missing') {
      loadData()
    }
    loadIngestionStatus()
  }, [activeTab, filters])

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
      if (activeTab === 'out_of_universe') {
        const response = await getPlanOutOfUniverse({
          country: filters.country || undefined,
          city: filters.city || undefined,
          line_of_business: filters.line_of_business || undefined,
          year: filters.year_plan || 2026
        })
        setOutOfUniverse(response.data || [])
      } else if (activeTab === 'missing') {
        const response = await getPlanMissing({
          country: filters.country || undefined,
          city: filters.city || undefined,
          line_of_business: filters.line_of_business || undefined
        })
        setMissing(response.data || [])
      }
    } catch (error) {
      console.error('Error al cargar datos:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatNumber = (num) => {
    if (num === null || num === undefined) return '-'
    return num.toLocaleString('es-ES', { maximumFractionDigits: 2 })
  }

  const getReasonBadgeColor = (reason) => {
    const colors = {
      'UNMAPPED_COUNTRY': 'bg-red-100 text-red-800',
      'UNMAPPED_LINE': 'bg-orange-100 text-orange-800',
      'NOT_IN_UNIVERSE_YET': 'bg-yellow-100 text-yellow-800',
      'LIKELY_EXPANSION': 'bg-purple-100 text-purple-800',
      'MISSING_CITY_IN_UNIVERSE': 'bg-gray-100 text-gray-800'
    }
    return colors[reason] || 'bg-gray-100 text-gray-800'
  }

  if (activeTab === 'out_of_universe') {
    const isComplete2025 = ingestionStatus?.is_complete_2025 || false
    const maxMonth = ingestionStatus?.max_month || 0
    
    return (
      <div className="bg-white p-6 rounded-lg shadow-md">
        <h3 className="text-lg font-semibold mb-4">Expansión / Fuera de Universo Operativo</h3>
        
        {!isComplete2025 && (
          <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 rounded-md mb-4">
            <p className="text-yellow-800">
              ⚠️ Real 2025 incompleto: algunas combinaciones pueden aparecer fuera de universo hasta que termine la ingesta. Mes máximo cargado: {maxMonth}
            </p>
          </div>
        )}
        
        {loading ? (
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
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
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">País</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ciudad</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Línea</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Métrica</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Período</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Valor Plan</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Razón</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {outOfUniverse.slice(0, 20).map((row, idx) => (
                  <tr key={idx}>
                    <td className="px-4 py-3 text-sm text-gray-900">{row.country || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">{row.city || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">{row.line_of_business || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">{row.metric || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">{row.period || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-900 text-right">{formatNumber(row.plan_value)}</td>
                    <td className="px-4 py-3 text-sm">
                      {row.reason ? (
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getReasonBadgeColor(row.reason)}`}>
                          {row.reason}
                        </span>
                      ) : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {outOfUniverse.length === 0 && (
              <p className="text-gray-500 text-center py-8">No hay datos fuera de universo</p>
            )}
          </div>
        )}
      </div>
    )
  }

  if (activeTab === 'missing') {
    return (
      <div className="bg-white p-6 rounded-lg shadow-md">
        <h3 className="text-lg font-semibold mb-4">Huecos del Plan (Operación sin Plan)</h3>
        {loading ? (
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-1/4 mb-4"></div>
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
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">País</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ciudad</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Línea</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Métrica</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {missing.map((row, idx) => (
                  <tr key={idx}>
                    <td className="px-4 py-3 text-sm text-gray-900">{row.country || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">{row.city || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">{row.line_of_business || '-'}</td>
                    <td className="px-4 py-3 text-sm text-gray-900">{row.metric || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {missing.length === 0 && (
              <p className="text-gray-500 text-center py-8">No hay huecos en el plan</p>
            )}
          </div>
        )}
      </div>
    )
  }

  return null
}

export default PlanTabs

