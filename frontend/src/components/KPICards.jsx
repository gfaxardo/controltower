import { useState, useEffect } from 'react'
import { getPlanMonthlySummary, getRealMonthlySummary, getPlanMonthlySplit, getRealMonthlySplit } from '../services/api'

function KPICards({ filters = {}, compact = false }) {
  const [kpis, setKpis] = useState({
    tripsRealYTD: 0,
    tripsPlanYTD: 0,
    driversRealYTD: 0,
    driversPlanYTD: 0,
    revenueRealYTD: null,
    revenuePlanYTD: null,
    revenuePlanYTD_PE: null,
    revenuePlanYTD_CO: null,
    revenueRealYTD_PE: null,
    revenueRealYTD_CO: null
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
      const isAll = !filters.country || filters.country === '' || filters.country === 'ALL' || filters.country === 'All' || filters.country === 'Todos'
      
      if (isAll) {
        // Vista ALL: cargar datos globales y por país separado
        const [planDataGlobal, realDataGlobal, planDataPE, realDataPE, planDataCO, realDataCO] = await Promise.all([
          getPlanMonthlySplit({
            country: undefined,
            city: filters.city || undefined,
            lob_base: filters.line_of_business || undefined,
            year: yearPlan
          }),
          getRealMonthlySplit({
            country: undefined,
            city: filters.city || undefined,
            lob_base: filters.line_of_business || undefined,
            year: yearReal
          }),
          getPlanMonthlySplit({
            country: 'PE',
            city: filters.city || undefined,
            lob_base: filters.line_of_business || undefined,
            year: yearPlan
          }),
          getRealMonthlySplit({
            country: 'PE',
            city: filters.city || undefined,
            lob_base: filters.line_of_business || undefined,
            year: yearReal
          }),
          getPlanMonthlySplit({
            country: 'CO',
            city: filters.city || undefined,
            lob_base: filters.line_of_business || undefined,
            year: yearPlan
          }),
          getRealMonthlySplit({
            country: 'CO',
            city: filters.city || undefined,
            lob_base: filters.line_of_business || undefined,
            year: yearReal
          })
        ])
        
        // KPIs globales (unitless)
        const tripsRealYTD = (realDataGlobal.data || []).reduce((sum, row) => sum + (row.trips_real_completed || 0), 0)
        const tripsPlanYTD = (planDataGlobal.data || []).reduce((sum, row) => sum + (row.projected_trips || 0), 0)
        const driversRealYTD = (realDataGlobal.data || []).reduce((sum, row) => sum + (row.active_drivers_real || 0), 0)
        const driversPlanYTD = (planDataGlobal.data || []).reduce((sum, row) => sum + (row.projected_drivers || 0), 0)
        
        // Monetarios por país
        const revenuePlanYTD_PE = (planDataPE.data || []).reduce((sum, row) => sum + (row.projected_revenue || 0), 0)
        const revenuePlanYTD_CO = (planDataCO.data || []).reduce((sum, row) => sum + (row.projected_revenue || 0), 0)
        const revenueRealYTD_PE = (realDataPE.data || []).reduce((sum, row) => sum + (row.revenue_real_yego || 0), 0)
        const revenueRealYTD_CO = (realDataCO.data || []).reduce((sum, row) => sum + (row.revenue_real_yego || 0), 0)
        
        setKpis({
          tripsRealYTD,
          tripsPlanYTD,
          driversRealYTD,
          driversPlanYTD,
          revenueRealYTD: null,
          revenuePlanYTD: null,
          revenuePlanYTD_PE: revenuePlanYTD_PE > 0 ? revenuePlanYTD_PE : null,
          revenuePlanYTD_CO: revenuePlanYTD_CO > 0 ? revenuePlanYTD_CO : null,
          revenueRealYTD_PE: revenueRealYTD_PE > 0 ? revenueRealYTD_PE : null,
          revenueRealYTD_CO: revenueRealYTD_CO > 0 ? revenueRealYTD_CO : null
        })
      } else {
        // Vista específica por país
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
        
        // Primero obtener datos split para drivers y revenue
        const [planDataSplit, realDataSplit] = await Promise.all([
          getPlanMonthlySplit({
            country: filters.country || undefined,
            city: filters.city || undefined,
            lob_base: filters.line_of_business || undefined,
            year: yearPlan
          }),
          getRealMonthlySplit({
            country: filters.country || undefined,
            city: filters.city || undefined,
            lob_base: filters.line_of_business || undefined,
            year: yearReal
          })
        ])
        
        // Calcular KPIs
        const tripsRealYTD = (realData.data || []).reduce((sum, row) => sum + (row.trips_real || 0), 0)
        const tripsPlanYTD = (planData.data || []).reduce((sum, row) => sum + (row.trips_plan || 0), 0)
        const revenueRealYTD = (realData.data || []).reduce((sum, row) => sum + (row.revenue_real || 0), 0)
        // Usar projected_revenue de la respuesta split que tiene el valor directo
        const revenuePlanYTD = (planDataSplit.data || []).reduce((sum, row) => sum + (row.projected_revenue || 0), 0)
        const driversRealYTD = (realDataSplit.data || []).reduce((sum, row) => sum + (row.active_drivers_real || 0), 0)
        const driversPlanYTD = (planDataSplit.data || []).reduce((sum, row) => sum + (row.projected_drivers || 0), 0)
        
        setKpis({
          tripsRealYTD,
          tripsPlanYTD,
          driversRealYTD,
          driversPlanYTD,
          revenueRealYTD: revenueRealYTD > 0 ? revenueRealYTD : null,
          revenuePlanYTD: revenuePlanYTD > 0 ? revenuePlanYTD : null,
          revenuePlanYTD_PE: null,
          revenuePlanYTD_CO: null,
          revenueRealYTD_PE: null,
          revenueRealYTD_CO: null
        })
      }
    } catch (error) {
      console.error('Error al cargar KPIs:', error)
    } finally {
      setLoading(false)
    }
  }

  const cardGridCls = compact ? 'grid grid-cols-2 md:grid-cols-4 gap-3 mb-4' : 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6'
  const cardCls = compact ? 'p-4 rounded-lg shadow border-l-4' : 'p-6 rounded-lg shadow-md border-l-4'
  const titleCls = compact ? 'text-sm font-semibold text-gray-700 mb-1' : 'text-lg font-semibold text-gray-700 mb-2'
  const valueCls = compact ? 'text-xl font-bold' : 'text-3xl font-bold'
  const hintCls = compact ? 'text-xs text-gray-600 mt-1' : 'text-sm text-gray-600 mt-2'
  const revenueGridCls = compact ? 'grid grid-cols-1 md:grid-cols-2 gap-3 mb-4' : 'grid grid-cols-1 md:grid-cols-2 gap-6 mb-6'
  const revenueCardCls = compact ? 'bg-white p-4 rounded-lg shadow border-2' : 'bg-white p-6 rounded-lg shadow-md border-2'
  const revenueTitleCls = compact ? 'text-base font-bold' : 'text-xl font-bold'
  const revenueValueCls = compact ? 'text-lg font-bold' : 'text-2xl font-bold'

  if (loading) {
    return (
      <div className={cardGridCls}>
        {[...Array(4)].map((_, i) => (
          <div key={i} className={`bg-white ${compact ? 'p-4' : 'p-6'} rounded-lg shadow-md`}>
            <div className="animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-1/2 mb-4"></div>
              <div className="h-8 bg-gray-200 rounded w-3/4"></div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  const isAll = !filters.country || filters.country === '' || filters.country === 'ALL' || filters.country === 'All' || filters.country === 'Todos'
  const currencyCode = filters.country === 'CO' ? 'COP' : (filters.country === 'PE' ? 'PEN' : 'PEN')
  
  const formatCurrency = (num, currency = currencyCode) => {
    if (num === null || num === undefined) return '-'
    const currencyMap = {
      'PEN': { currency: 'PEN', locale: 'es-PE' },
      'COP': { currency: 'COP', locale: 'es-CO' }
    }
    const config = currencyMap[currency] || currencyMap['PEN']
    return num.toLocaleString(config.locale, { style: 'currency', currency: config.currency, maximumFractionDigits: 2 })
  }

  // Vista ALL: KPIs globales + bloques monetarios por país
  if (isAll) {
    return (
      <div>
        {/* KPIs GLOBALES (unitless) */}
        <div className={cardGridCls}>
          <div className={`bg-blue-50 ${cardCls} border-blue-500`}>
            <h3 className={titleCls}>Trips Real YTD</h3>
            <p className={`${valueCls} text-blue-600`}>
              {kpis.tripsRealYTD.toLocaleString('es-ES', { maximumFractionDigits: 0 })}
            </p>
            <p className={hintCls}>Año {filters.year_real || 2025}</p>
          </div>
          <div className={`bg-green-50 ${cardCls} border-green-500`}>
            <h3 className={titleCls}>Trips Plan YTD</h3>
            <p className={`${valueCls} text-green-600`}>
              {kpis.tripsPlanYTD.toLocaleString('es-ES', { maximumFractionDigits: 0 })}
            </p>
            <p className={hintCls}>Año {filters.year_plan || 2026}</p>
          </div>
          <div className={`bg-indigo-50 ${cardCls} border-indigo-500`}>
            <h3 className={titleCls}>Drivers Real YTD</h3>
            <p className={`${valueCls} text-indigo-600`}>
              {kpis.driversRealYTD.toLocaleString('es-ES', { maximumFractionDigits: 0 })}
            </p>
            <p className={hintCls}>Año {filters.year_real || 2025}</p>
          </div>
          <div className={`bg-teal-50 ${cardCls} border-teal-500`}>
            <h3 className={titleCls}>Drivers Plan YTD</h3>
            <p className={`${valueCls} text-teal-600`}>
              {kpis.driversPlanYTD.toLocaleString('es-ES', { maximumFractionDigits: 0 })}
            </p>
            <p className={hintCls}>Año {filters.year_plan || 2026}</p>
          </div>
        </div>

        {/* BLOQUES MONETARIOS POR PAÍS */}
        <div className={revenueGridCls}>
          <div className={`${revenueCardCls} border-red-200`}>
            <div className={`flex items-center ${compact ? 'mb-2' : 'mb-4'}`}>
              <span className={compact ? 'text-lg mr-1' : 'text-2xl mr-2'}>🇵🇪</span>
              <h3 className={`${revenueTitleCls} text-gray-800`}>PERÚ — PEN</h3>
            </div>
            <div className={compact ? 'space-y-2' : 'space-y-4'}>
              {kpis.revenuePlanYTD_PE !== null && (
                <div>
                  <h4 className="text-sm font-medium text-gray-600 mb-1 flex items-center">
                    Revenue Plan YTD
                    <span className="ml-1 text-xs text-gray-400" title="Revenue Plan corresponde al ingreso neto esperado cargado en el Plan. No es GMV.">ℹ️</span>
                  </h4>
                  <p className={`${revenueValueCls} text-orange-600`}>
                    {formatCurrency(kpis.revenuePlanYTD_PE, 'PEN')}
                  </p>
                </div>
              )}
              {kpis.revenueRealYTD_PE !== null && (
                <div>
                  <h4 className="text-sm font-medium text-gray-600 mb-1">Revenue Real (Comisión Yego)</h4>
                  <p className={`${revenueValueCls} text-blue-600`}>
                    {formatCurrency(kpis.revenueRealYTD_PE, 'PEN')}
                  </p>
                </div>
              )}
            </div>
          </div>
          <div className={`${revenueCardCls} border-yellow-200`}>
            <div className={`flex items-center ${compact ? 'mb-2' : 'mb-4'}`}>
              <span className={compact ? 'text-lg mr-1' : 'text-2xl mr-2'}>🇨🇴</span>
              <h3 className={`${revenueTitleCls} text-gray-800`}>COLOMBIA — COP</h3>
            </div>
            <div className={compact ? 'space-y-2' : 'space-y-4'}>
              {kpis.revenuePlanYTD_CO !== null && (
                <div>
                  <h4 className="text-sm font-medium text-gray-600 mb-1 flex items-center">
                    Revenue Plan YTD
                    <span className="ml-1 text-xs text-gray-400" title="Revenue Plan corresponde al ingreso neto esperado cargado en el Plan. No es GMV.">ℹ️</span>
                  </h4>
                  <p className={`${revenueValueCls} text-orange-600`}>
                    {formatCurrency(kpis.revenuePlanYTD_CO, 'COP')}
                  </p>
                </div>
              )}
              {kpis.revenueRealYTD_CO !== null && (
                <div>
                  <h4 className="text-sm font-medium text-gray-600 mb-1">Revenue Real (Comisión Yego)</h4>
                  <p className={`${revenueValueCls} text-blue-600`}>
                    {formatCurrency(kpis.revenueRealYTD_CO, 'COP')}
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {!compact && (
          <div className="mb-6 p-3 bg-gray-50 border-l-4 border-gray-400 rounded">
            <p className="text-sm text-gray-700">
              Vista ALL: las métricas monetarias se presentan por país para evitar mezcla de monedas.
            </p>
          </div>
        )}
      </div>
    )
  }

  // Vista específica por país
  return (
    <div>
      <div className={cardGridCls}>
        <div className={`bg-blue-50 ${cardCls} border-blue-500`}>
          <h3 className={titleCls}>Trips Real YTD</h3>
          <p className={`${valueCls} text-blue-600`}>
            {kpis.tripsRealYTD.toLocaleString('es-ES', { maximumFractionDigits: 0 })}
          </p>
          <p className={hintCls}>Año {filters.year_real || 2025}</p>
        </div>
        <div className={`bg-green-50 ${cardCls} border-green-500`}>
          <h3 className={titleCls}>Trips Plan YTD</h3>
          <p className={`${valueCls} text-green-600`}>
            {kpis.tripsPlanYTD.toLocaleString('es-ES', { maximumFractionDigits: 0 })}
          </p>
          <p className={hintCls}>Año {filters.year_plan || 2026}</p>
        </div>
        {kpis.revenueRealYTD !== null && (
          <div className={`bg-purple-50 ${cardCls} border-purple-500`}>
            <h3 className={titleCls}>Revenue Real YTD ({currencyCode})</h3>
            <p className={`${valueCls} text-purple-600`}>
              {formatCurrency(kpis.revenueRealYTD)}
            </p>
            <p className={hintCls}>Año {filters.year_real || 2025}</p>
          </div>
        )}
        {kpis.revenuePlanYTD !== null && (
          <div className={`bg-orange-50 ${cardCls} border-orange-500`}>
            <h3 className={`${titleCls} flex items-center`}>
              Revenue Plan YTD ({currencyCode})
              <span className="ml-1 text-xs text-gray-400" title="Revenue Plan corresponde al ingreso neto esperado cargado en el Plan. No es GMV.">ℹ️</span>
            </h3>
            <p className={`${valueCls} text-orange-600`}>
              {formatCurrency(kpis.revenuePlanYTD)}
            </p>
            <p className={hintCls}>Año {filters.year_plan || 2026}</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default KPICards
