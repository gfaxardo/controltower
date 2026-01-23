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

const PRODUCTIVIDAD_TOOLTIP = "Promedio mensual de viajes realizados por cada driver activo.\nFórmula: Trips del mes / Drivers activos del mes.\nNo representa horas trabajadas ni eficiencia individual."
const MARGEN_UNITARIO_TOOLTIP = "Ingreso promedio real de YEGO por cada viaje completado.\nFórmula: Comisión YEGO real / Viajes reales."

function MonthlySplitView({ filters = {} }) {
  const [activeTab, setActiveTab] = useState('real')
  const [realData, setRealData] = useState([])
  const [planData, setPlanData] = useState([])
  const [overlapData, setOverlapData] = useState([])
  const [loading, setLoading] = useState(true)
  const [hasOverlap, setHasOverlap] = useState(false)
  
  // Datos separados por país para vista ALL
  const [realDataPE, setRealDataPE] = useState([])
  const [planDataPE, setPlanDataPE] = useState([])
  const [realDataCO, setRealDataCO] = useState([])
  const [planDataCO, setPlanDataCO] = useState([])

  const yearReal = filters.year_real || 2025
  const yearPlan = filters.year_plan || 2026
  const isAll = !filters.country || filters.country === '' || filters.country === 'ALL' || filters.country === 'All' || filters.country === 'Todos'

  useEffect(() => {
    loadAllData()
  }, [filters])

  const loadAllData = async () => {
    try {
      setLoading(true)
      
      if (isAll) {
        // Vista ALL: cargar datos separados por país
        const [realResponsePE, planResponsePE, realResponseCO, planResponseCO] = await Promise.all([
          getRealMonthlySplit({
            country: 'PE',
            city: filters.city || undefined,
            lob_base: filters.line_of_business || undefined,
            segment: filters.segment || undefined,
            year: yearReal
          }),
          getPlanMonthlySplit({
            country: 'PE',
            city: filters.city || undefined,
            lob_base: filters.line_of_business || undefined,
            segment: filters.segment || undefined,
            year: yearPlan
          }),
          getRealMonthlySplit({
            country: 'CO',
            city: filters.city || undefined,
            lob_base: filters.line_of_business || undefined,
            segment: filters.segment || undefined,
            year: yearReal
          }),
          getPlanMonthlySplit({
            country: 'CO',
            city: filters.city || undefined,
            lob_base: filters.line_of_business || undefined,
            segment: filters.segment || undefined,
            year: yearPlan
          })
        ])
        
        setRealDataPE(realResponsePE.data || [])
        setPlanDataPE(planResponsePE.data || [])
        setRealDataCO(realResponseCO.data || [])
        setPlanDataCO(planResponseCO.data || [])
        setRealData([])
        setPlanData([])
        setOverlapData([])
        setHasOverlap(false)
      } else {
        // Vista específica por país
        const overlapFilters = {
          country: filters.country || undefined,
          city: filters.city || undefined,
          lob_base: filters.line_of_business || undefined,
          segment: filters.segment || undefined
        }

        const overlapPromise = yearReal === yearPlan
          ? getOverlapMonthly({ ...overlapFilters, year: yearPlan })
          : Promise.resolve({ data: [], has_overlap: false })

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
          overlapPromise
        ])
        
        setRealData(realResponse.data || [])
        setPlanData(planResponse.data || [])
        setOverlapData(overlapResponse.data || [])
        setHasOverlap(overlapResponse.has_overlap || false)
        setRealDataPE([])
        setPlanDataPE([])
        setRealDataCO([])
        setPlanDataCO([])
      }
    } catch (error) {
      console.error('Error al cargar datos:', error)
      setRealData([])
      setPlanData([])
      setOverlapData([])
      setHasOverlap(false)
      setRealDataPE([])
      setPlanDataPE([])
      setRealDataCO([])
      setPlanDataCO([])
    } finally {
      setLoading(false)
    }
  }

  const formatNumber = (num) => {
    if (num === null || num === undefined) return '-'
    return num.toLocaleString('es-ES', { maximumFractionDigits: 2 })
  }

  const formatCurrency = (num, currencyCode = 'PEN') => {
    if (num === null || num === undefined) return '-'
    // Mapeo de currency_code a locale y símbolo
    const currencyMap = {
      'PEN': { currency: 'PEN', locale: 'es-PE' },
      'COP': { currency: 'COP', locale: 'es-CO' }
    }
    const config = currencyMap[currencyCode] || currencyMap['PEN']
    return num.toLocaleString(config.locale, { style: 'currency', currency: config.currency, maximumFractionDigits: 2 })
  }

  // Helper para extraer periodo de forma segura (maneja period, month como string o Date)
  const getPeriodString = (row) => {
    if (row.period) return row.period
    if (row.month) {
      if (typeof row.month === 'string') return row.month
      if (row.month instanceof Date) {
        const year = row.month.getFullYear()
        const month = String(row.month.getMonth() + 1).padStart(2, '0')
        return `${year}-${month}`
      }
    }
    return null
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

  const renderCountryRealTable = (countryCode, countryData, currencyCode, countryName, flag) => {
    return (
      <div className="mb-8">
        <h4 className="text-lg font-bold mb-4 flex items-center">
          <span className="text-2xl mr-2">{flag}</span>
          <span>{countryName} ({currencyCode})</span>
        </h4>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mes</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Trips Real</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  Revenue Real (Comisión Yego)
                  <span className="ml-1 text-xs text-gray-400" title="Fuente: comision_empresa_asociada viene negativa; se invierte para mostrar revenue positivo. Ver commission_yego_signed para auditoría.">ℹ️</span>
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  <div className="flex items-center justify-end gap-1 whitespace-normal max-w-[180px]">
                    <span className="block leading-tight">Ingreso YEGO por Viaje</span>
                    <span className="text-xs text-gray-400" title={MARGEN_UNITARIO_TOOLTIP} aria-label={MARGEN_UNITARIO_TOOLTIP}>ℹ️</span>
                  </div>
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Drivers Activos</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  <div className="flex items-center justify-end gap-1 whitespace-normal max-w-[180px]">
                    <span className="block leading-tight">Trips por Driver Activo (Mes)</span>
                    <span className="text-xs text-gray-400" title={PRODUCTIVIDAD_TOOLTIP} aria-label={PRODUCTIVIDAD_TOOLTIP}>ℹ️</span>
                  </div>
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {countryData.length > 0 ? (
                countryData.map((row) => {
                  const periodStr = getPeriodString(row)
                  const [yearStr, monthStr] = periodStr ? periodStr.split('-') : ['', '']
                  const monthNum = parseInt(monthStr)
                  const mes = MESES.find(m => m.num === monthNum) || { nombre: monthStr }
                  return (
                    <tr key={periodStr || row.month || row.period} className="hover:bg-gray-50">
                      <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                        {mes.nombre} {yearStr}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                        {formatNumber(row.trips_real_completed)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                        {formatCurrency(row.revenue_real_yego || 0, currencyCode)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                        {formatCurrency(row.margen_unitario_yego, currencyCode)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                        {formatNumber(row.active_drivers_real)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                        {row.trips_per_driver ? formatNumber(row.trips_per_driver) : '-'}
                      </td>
                    </tr>
                  )
                })
              ) : (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                    No hay datos Real para {countryName} en {yearReal}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  const renderRealTable = () => {
    if (isAll) {
      // Vista ALL: subtablas por país
      return (
        <div>
          {renderCountryRealTable('PE', realDataPE, 'PEN', 'PERÚ', '🇵🇪')}
          {renderCountryRealTable('CO', realDataCO, 'COP', 'COLOMBIA', '🇨🇴')}
        </div>
      )
    }
    
    // Vista específica por país
    const currencyCode = filters.country === 'CO' ? 'COP' : 'PEN'
    
    return (
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mes</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Trips Real</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Revenue Real (Comisión Yego)</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                <div className="flex items-center justify-end gap-1 whitespace-normal max-w-[180px]">
                  <span className="block leading-tight">Ingreso YEGO por Viaje</span>
                  <span className="text-xs text-gray-400" title={MARGEN_UNITARIO_TOOLTIP} aria-label={MARGEN_UNITARIO_TOOLTIP}>ℹ️</span>
                </div>
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Drivers Activos</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                <div className="flex items-center justify-end gap-1 whitespace-normal max-w-[180px]">
                  <span className="block leading-tight">Trips por Driver Activo (Mes)</span>
                  <span className="text-xs text-gray-400" title={PRODUCTIVIDAD_TOOLTIP} aria-label={PRODUCTIVIDAD_TOOLTIP}>ℹ️</span>
                </div>
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {realData.length > 0 ? (
              realData.map((row) => {
                const periodStr = getPeriodString(row)
                const [yearStr, monthStr] = periodStr ? periodStr.split('-') : ['', '']
                const monthNum = parseInt(monthStr)
                const mes = MESES.find(m => m.num === monthNum) || { nombre: monthStr }
                const rowCurrency = row.currency_code || currencyCode
                return (
                  <tr key={periodStr || row.month || row.period} className="hover:bg-gray-50">
                    <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                      {mes.nombre} {yearStr}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                      {formatNumber(row.trips_real_completed)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                      {formatCurrency(row.revenue_real_yego || 0, rowCurrency)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                      {formatCurrency(row.margen_unitario_yego, rowCurrency)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                      {formatNumber(row.active_drivers_real)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                      {row.trips_per_driver ? formatNumber(row.trips_per_driver) : '-'}
                    </td>
                  </tr>
                )
              })
            ) : (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                  No hay datos Real para {yearReal}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    )
  }

  const renderCountryPlanTable = (countryCode, countryData, currencyCode, countryName, flag) => {
    return (
      <div className="mb-8">
        <h4 className="text-lg font-bold mb-4 flex items-center">
          <span className="text-2xl mr-2">{flag}</span>
          <span>{countryName} ({currencyCode})</span>
        </h4>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mes</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Trips Plan</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  Revenue Plan
                  <span className="ml-1 text-xs text-gray-400" title="Revenue Plan corresponde al ingreso neto esperado cargado en el Plan. No es GMV.">ℹ️</span>
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Drivers Plan</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  <div className="flex items-center justify-end gap-1 whitespace-normal max-w-[180px]">
                    <span className="block leading-tight">Trips por Driver Activo (Mes)</span>
                    <span className="text-xs text-gray-400" title={PRODUCTIVIDAD_TOOLTIP} aria-label={PRODUCTIVIDAD_TOOLTIP}>ℹ️</span>
                  </div>
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {countryData.length > 0 ? (
                countryData.map((row) => {
                  const periodStr = getPeriodString(row)
                  const [yearStr, monthStr] = periodStr ? periodStr.split('-') : ['', '']
                  const monthNum = parseInt(monthStr)
                  const mes = MESES.find(m => m.num === monthNum) || { nombre: monthStr }
                  const tripsPerDriver = row.projected_drivers > 0 ? row.projected_trips / row.projected_drivers : null
                  return (
                    <tr key={periodStr || row.month || row.period} className="hover:bg-gray-50">
                      <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                        {mes.nombre} {yearStr}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                        {formatNumber(row.projected_trips)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                        {formatCurrency(row.projected_revenue, currencyCode)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                        {formatNumber(row.projected_drivers)}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                        {tripsPerDriver ? formatNumber(tripsPerDriver) : '-'}
                      </td>
                    </tr>
                  )
                })
              ) : (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                    No hay datos Plan para {countryName} en {yearPlan}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  const renderPlanTable = () => {
    if (isAll) {
      // Vista ALL: subtablas por país
      return (
        <div>
          {renderCountryPlanTable('PE', planDataPE, 'PEN', 'PERÚ', '🇵🇪')}
          {renderCountryPlanTable('CO', planDataCO, 'COP', 'COLOMBIA', '🇨🇴')}
        </div>
      )
    }
    
    // Vista específica por país
    const currencyCode = filters.country === 'CO' ? 'COP' : 'PEN'
    
    return (
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mes</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Trips Plan</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Revenue Plan</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Drivers Plan</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                <div className="flex items-center justify-end gap-1 whitespace-normal max-w-[180px]">
                  <span className="block leading-tight">Trips por Driver Activo (Mes)</span>
                  <span className="text-xs text-gray-400" title={PRODUCTIVIDAD_TOOLTIP} aria-label={PRODUCTIVIDAD_TOOLTIP}>ℹ️</span>
                </div>
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {planData.length > 0 ? (
              planData.map((row) => {
                const periodStr = getPeriodString(row)
                const [yearStr, monthStr] = periodStr ? periodStr.split('-') : ['', '']
                const monthNum = parseInt(monthStr)
                const mes = MESES.find(m => m.num === monthNum) || { nombre: monthStr }
                const tripsPerDriver = row.projected_drivers > 0 ? row.projected_trips / row.projected_drivers : null
                return (
                  <tr key={periodStr || row.month || row.period} className="hover:bg-gray-50">
                    <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                      {mes.nombre} {yearStr}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                      {formatNumber(row.projected_trips)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                      {formatCurrency(row.projected_revenue, currencyCode)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                      {formatNumber(row.projected_drivers)}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                      {tripsPerDriver ? formatNumber(tripsPerDriver) : '-'}
                    </td>
                  </tr>
                )
              })
            ) : (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-500">
                  No hay datos Plan para {yearPlan}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    )
  }

  const renderOverlapTable = () => {
    if (!hasOverlap || overlapData.length === 0) {
      return (
        <div className="p-8 text-center text-gray-600 bg-gray-50 rounded-lg">
          <p className="text-lg font-medium mb-2">
            No hay comparación disponible para los filtros seleccionados
          </p>
          <p className="text-sm mt-2">
            {yearReal !== yearPlan
              ? `Actualmente: Real ${yearReal} vs Plan ${yearPlan}. Para comparar, selecciona el mismo año.`
              : `Año ${yearPlan}: no hay datos reales suficientes para comparar.`}
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
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                <div className="flex items-center justify-end gap-1 whitespace-normal max-w-[180px]">
                  <span className="block leading-tight">Ingreso YEGO por Viaje</span>
                  <span className="text-xs text-gray-400" title={MARGEN_UNITARIO_TOOLTIP} aria-label={MARGEN_UNITARIO_TOOLTIP}>ℹ️</span>
                </div>
              </th>
              <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Gap Revenue</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {overlapData.map((row) => {
              const periodStr = getPeriodString(row)
              const [yearStr, monthStr] = periodStr ? periodStr.split('-') : ['', '']
              const monthNum = parseInt(monthStr)
              const mes = MESES.find(m => m.num === monthNum) || { nombre: monthStr }
              return (
                <tr key={row.period} className="hover:bg-gray-50">
                  <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                    <div className="flex items-center gap-2">
                      <span>{mes.nombre} {yearStr}</span>
                      {row.is_partial_real && (
                        <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800">
                          REAL PARCIAL
                        </span>
                      )}
                    </div>
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
                    {formatNumber(row.revenue_real_yego || 0)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900 text-right">
                    {formatCurrency(row.margen_unitario_yego, currencyCode)}
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
        <h3 className="text-lg font-semibold mb-2">Vista Mensual - Plan {yearPlan} vs Real {yearReal}</h3>
        <p className="text-sm text-gray-600 mb-4">
          Fase 2A: mostramos Real histórico y Plan futuro. Comparable se activa cuando exista Real del mismo año del Plan.
        </p>
        
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
