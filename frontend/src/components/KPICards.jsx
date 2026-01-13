import { useState, useEffect } from 'react'
import { getPlanMonthlySummary, getRealMonthlySummary } from '../services/api'

function KPICards({ filters = {} }) {
  const [kpis, setKpis] = useState({
    tripsRealYTD: 0,
    tripsPlanYTD: 0,
    revenueRealYTD: null,
    revenuePlanYTD: null
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadKPIs()
  }, [filters])

  const loadKPIs = async () => {
    try {
      setLoading(true)
      
      const yearReal = filters.year_real || 2025
      const yearPlan = filters.year_plan || 2026
      
      const [planData, realData] = await Promise.all([
        getPlanMonthlySummary({
          country: filters.country || undefined,
          city: filters.city || undefined,
          line_of_business: filters.line_of_business || undefined,
          year: yearPlan
        }),
        getRealMonthlySummary({
          country: filters.country || undefined,
          city: filters.city || undefined,
          line_of_business: filters.line_of_business || undefined,
          year: yearReal
        })
      ])
      
      const tripsRealYTD = (realData.data || []).reduce((sum, row) => sum + (row.trips_real || 0), 0)
      const tripsPlanYTD = (planData.data || []).reduce((sum, row) => sum + (row.trips_plan || 0), 0)
      const revenueRealYTD = (realData.data || []).reduce((sum, row) => sum + (row.revenue_real || 0), 0)
      const revenuePlanYTD = (planData.data || []).reduce((sum, row) => sum + (row.revenue_plan || 0), 0)
      
      setKpis({
        tripsRealYTD,
        tripsPlanYTD,
        revenueRealYTD: revenueRealYTD > 0 ? revenueRealYTD : null,
        revenuePlanYTD: revenuePlanYTD > 0 ? revenuePlanYTD : null
      })
    } catch (error) {
      console.error('Error al cargar KPIs:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-white p-6 rounded-lg shadow-md">
            <div className="animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-1/2 mb-4"></div>
              <div className="h-8 bg-gray-200 rounded w-3/4"></div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
      <div className="bg-blue-50 p-6 rounded-lg shadow-md border-l-4 border-blue-500">
        <h3 className="text-lg font-semibold text-gray-700 mb-2">Trips Real YTD</h3>
        <p className="text-3xl font-bold text-blue-600">
          {kpis.tripsRealYTD.toLocaleString('es-ES', { maximumFractionDigits: 0 })}
        </p>
        <p className="text-sm text-gray-600 mt-2">Año {filters.year_real || 2025}</p>
      </div>
      
      <div className="bg-green-50 p-6 rounded-lg shadow-md border-l-4 border-green-500">
        <h3 className="text-lg font-semibold text-gray-700 mb-2">Trips Plan YTD</h3>
        <p className="text-3xl font-bold text-green-600">
          {kpis.tripsPlanYTD.toLocaleString('es-ES', { maximumFractionDigits: 0 })}
        </p>
        <p className="text-sm text-gray-600 mt-2">Año {filters.year_plan || 2026}</p>
      </div>
      
      {kpis.revenueRealYTD !== null && (
        <div className="bg-purple-50 p-6 rounded-lg shadow-md border-l-4 border-purple-500">
          <h3 className="text-lg font-semibold text-gray-700 mb-2">Revenue Real YTD</h3>
          <p className="text-3xl font-bold text-purple-600">
            {kpis.revenueRealYTD.toLocaleString('es-ES', { maximumFractionDigits: 2 })}
          </p>
          <p className="text-sm text-gray-600 mt-2">Año {filters.year_real || 2025}</p>
        </div>
      )}
      
      {kpis.revenuePlanYTD !== null && (
        <div className="bg-orange-50 p-6 rounded-lg shadow-md border-l-4 border-orange-500">
          <h3 className="text-lg font-semibold text-gray-700 mb-2">Revenue Plan YTD</h3>
          <p className="text-3xl font-bold text-orange-600">
            {kpis.revenuePlanYTD.toLocaleString('es-ES', { maximumFractionDigits: 2 })}
          </p>
          <p className="text-sm text-gray-600 mt-2">Año {filters.year_plan || 2026}</p>
        </div>
      )}
    </div>
  )
}

export default KPICards
