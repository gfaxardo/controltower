import { useEffect, useMemo, useState } from 'react'
import { getPlanVsRealWeekly, getWeeklyAlerts } from '../services/api'
import RegisterActionModal from './RegisterActionModal'

const MARGEN_UNITARIO_TOOLTIP = "Ingreso promedio real de YEGO por cada viaje completado.\nFórmula: Comisión YEGO real / Viajes reales."
const PRODUCTIVIDAD_TOOLTIP = "Promedio semanal de viajes realizados por cada driver activo.\nFórmula: Trips semana / Drivers activos semana."

function WeeklyPlanVsRealView({ filters = {} }) {
  const [comparisonData, setComparisonData] = useState([])
  const [alertsData, setAlertsData] = useState([])
  const [loadingComparison, setLoadingComparison] = useState(true)
  const [loadingAlerts, setLoadingAlerts] = useState(true)
  const [expandedRows, setExpandedRows] = useState({})
  const [selectedAlert, setSelectedAlert] = useState(null)
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [alertFilter, setAlertFilter] = useState('all') // all, unit, vol, unit_alert

  const [weekStartFrom, setWeekStartFrom] = useState('')
  const [weekStartTo, setWeekStartTo] = useState('')

  useEffect(() => {
    setExpandedRows({})
    loadComparisonData()
    loadAlertsData()
  }, [filters, weekStartFrom, weekStartTo, alertFilter])

  const buildWeeklyFilters = () => ({
    country: filters.country || undefined,
    city: filters.city || undefined,
    lob_base: filters.line_of_business || undefined,
    segment: filters.segment || undefined,
    week_start_from: weekStartFrom || undefined,
    week_start_to: weekStartTo || undefined
  })

  const buildAlertFilters = () => {
    const baseFilters = buildWeeklyFilters()
    if (alertFilter === 'unit') {
      baseFilters.dominant_driver = 'UNIT'
    } else if (alertFilter === 'vol') {
      baseFilters.dominant_driver = 'VOL'
    } else if (alertFilter === 'unit_alert') {
      baseFilters.unit_alert = true
    }
    return baseFilters
  }

  const loadComparisonData = async () => {
    try {
      setLoadingComparison(true)
      const response = await getPlanVsRealWeekly(buildWeeklyFilters())
      setComparisonData(response.data || [])
    } catch (error) {
      console.error('Error al cargar comparación semanal:', error)
      setComparisonData([])
    } finally {
      setLoadingComparison(false)
    }
  }

  const loadAlertsData = async () => {
    try {
      setLoadingAlerts(true)
      const response = await getWeeklyAlerts(buildAlertFilters())
      setAlertsData(response.data || [])
    } catch (error) {
      console.error('Error al cargar alertas semanales:', error)
      setAlertsData([])
    } finally {
      setLoadingAlerts(false)
    }
  }

  const formatNumber = (num) => {
    if (num === null || num === undefined) return '-'
    return num.toLocaleString('es-ES', { maximumFractionDigits: 2 })
  }

  const formatCurrency = (num) => {
    if (num === null || num === undefined) return '-'
    return num.toLocaleString('es-ES', { style: 'currency', currency: 'PEN', maximumFractionDigits: 0 })
  }

  const formatPercent = (num) => {
    if (num === null || num === undefined) return '-'
    return `${(num * 100).toFixed(1)}%`
  }

  const formatWeek = (weekStr) => {
    if (!weekStr) return '-'
    const date = new Date(weekStr)
    return date.toLocaleDateString('es-ES', { year: 'numeric', month: 'short', day: 'numeric' })
  }

  const toggleRow = (key) => {
    setExpandedRows(prev => ({ ...prev, [key]: !prev[key] }))
  }

  const topAlerts = useMemo(() => alertsData.slice(0, 30), [alertsData])

  const handleRegisterAction = (alert) => {
    setSelectedAlert(alert)
    setIsModalOpen(true)
  }

  const handleActionRegistered = () => {
    loadAlertsData() // Recargar alertas para actualizar has_action
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow-md mt-8">
      <div className="mb-4">
        <h3 className="text-lg font-semibold">Fase 2B - Semanal</h3>
        <p className="text-sm text-gray-600">
          Comparación Plan vs Real semanal con descomposición y alertas accionables.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Semana desde</label>
          <input
            type="date"
            value={weekStartFrom}
            onChange={(e) => setWeekStartFrom(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Semana hasta</label>
          <input
            type="date"
            value={weekStartTo}
            onChange={(e) => setWeekStartTo(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        <div className="md:col-span-2 flex items-end justify-end">
          <button
            onClick={() => {
              setWeekStartFrom('')
              setWeekStartTo('')
            }}
            className="px-4 py-2 rounded bg-gray-200 text-gray-700"
          >
            Limpiar rango
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <h4 className="text-md font-semibold mb-2">A) Tabla Plan vs Real (semanal)</h4>
          {loadingComparison ? (
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
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Week</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Trips R/P/Δ/Δ%</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Drivers R/P/Δ</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Ingreso YEGO R/P/Δ/Δ%</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                      <div className="flex items-center justify-end gap-1 whitespace-normal max-w-[180px]">
                        <span className="block leading-tight">Ingreso por viaje R/P/Δ/Δ%</span>
                        <span className="text-xs text-gray-400" title={MARGEN_UNITARIO_TOOLTIP} aria-label={MARGEN_UNITARIO_TOOLTIP}>ℹ️</span>
                      </div>
                    </th>
                    <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase">Driver</th>
                    <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                      <div className="flex items-center justify-end gap-1 whitespace-normal max-w-[180px]">
                        <span className="block leading-tight">Trips/Driver R/P/Δ</span>
                        <span className="text-xs text-gray-400" title={PRODUCTIVIDAD_TOOLTIP} aria-label={PRODUCTIVIDAD_TOOLTIP}>ℹ️</span>
                      </div>
                    </th>
                    <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase">Detalle</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {comparisonData.length === 0 ? (
                    <tr>
                      <td colSpan="8" className="px-4 py-4 text-center text-gray-500">
                        No hay datos disponibles
                      </td>
                    </tr>
                  ) : (
                    comparisonData.slice(0, 50).map((row, idx) => {
                      const key = `${row.week_start}-${row.country}-${row.city_norm}-${row.lob_base}-${row.segment}-${idx}`
                      const isExpanded = expandedRows[key]
                      return (
                        <>
                          <tr key={key} className="hover:bg-gray-50">
                            <td className="px-3 py-2 text-sm text-gray-900 whitespace-nowrap">
                              {formatWeek(row.week_start)}
                            </td>
                            <td className="px-3 py-2 text-sm text-right">
                              <div className="text-gray-900">{formatNumber(row.trips_real)} / {formatNumber(row.trips_plan)}</div>
                              <div className={`${row.gap_trips < 0 ? 'text-red-600' : row.gap_trips > 0 ? 'text-green-600' : 'text-gray-500'}`}>
                                {formatNumber(row.gap_trips)} · {formatPercent(row.gap_trips_pct)}
                              </div>
                            </td>
                            <td className="px-3 py-2 text-sm text-right">
                              <div className="text-gray-900">{formatNumber(row.drivers_real)} / {formatNumber(row.drivers_plan)}</div>
                              <div className={`${row.gap_drivers < 0 ? 'text-red-600' : row.gap_drivers > 0 ? 'text-green-600' : 'text-gray-500'}`}>
                                {formatNumber(row.gap_drivers)}
                              </div>
                            </td>
                            <td className="px-3 py-2 text-sm text-right">
                              <div className="text-gray-900">{formatCurrency(row.revenue_real)} / {formatCurrency(row.revenue_plan)}</div>
                              <div className={`${row.gap_revenue < 0 ? 'text-red-600' : row.gap_revenue > 0 ? 'text-green-600' : 'text-gray-500'}`}>
                                {formatCurrency(row.gap_revenue)} · {formatPercent(row.gap_revenue_pct)}
                              </div>
                            </td>
                            <td className="px-3 py-2 text-sm text-right">
                              <div className="text-gray-900">{formatCurrency(row.ingreso_por_viaje_real)} / {formatCurrency(row.ingreso_por_viaje_plan)}</div>
                              <div className={`${row.gap_unitario < 0 ? 'text-red-600' : row.gap_unitario > 0 ? 'text-green-600' : 'text-gray-500'}`}>
                                {formatCurrency(row.gap_unitario)} · {formatPercent(row.gap_unitario_pct)}
                              </div>
                            </td>
                            <td className="px-3 py-2 text-sm text-center">
                              {row.dominant_driver ? (
                                <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                                  row.dominant_driver === 'UNIT' 
                                    ? 'bg-purple-100 text-purple-800' 
                                    : 'bg-blue-100 text-blue-800'
                                }`}>
                                  {row.dominant_driver}
                                </span>
                              ) : (
                                <span className="text-gray-400 text-xs">-</span>
                              )}
                            </td>
                            <td className="px-3 py-2 text-sm text-right">
                              <div className="text-gray-900">{formatNumber(row.productividad_real)} / {formatNumber(row.productividad_plan)}</div>
                              <div className={`${row.gap_prod < 0 ? 'text-red-600' : row.gap_prod > 0 ? 'text-green-600' : 'text-gray-500'}`}>
                                {formatNumber(row.gap_prod)}
                              </div>
                            </td>
                            <td className="px-3 py-2 text-sm text-center">
                              <button
                                onClick={() => toggleRow(key)}
                                className="px-2 py-1 text-xs rounded bg-gray-100 text-gray-700"
                              >
                                {isExpanded ? 'Ocultar' : 'Ver'}
                              </button>
                            </td>
                          </tr>
                          {isExpanded && (
                            <tr>
                              <td colSpan="8" className="bg-gray-50 px-4 py-3 text-sm text-gray-700">
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                  <div>
                                    <div className="font-semibold mb-1">Descomposición revenue</div>
                                    <div>Efecto volumen: {formatCurrency(row.efecto_volumen)}</div>
                                    <div>Efecto unitario: {formatCurrency(row.efecto_unitario)}</div>
                                  </div>
                                  <div>
                                    <div className="font-semibold mb-1">Palancas de trips</div>
                                    <div>Trips por drivers: {formatNumber(row.trips_teoricos_por_drivers)}</div>
                                    <div>Trips por productividad: {formatNumber(row.trips_teoricos_por_prod)}</div>
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-md font-semibold">B) Panel Alertas</h4>
            <div className="flex gap-1">
              <button
                onClick={() => setAlertFilter('all')}
                className={`px-2 py-1 text-xs rounded ${
                  alertFilter === 'all' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                Todas
              </button>
              <button
                onClick={() => setAlertFilter('unit')}
                className={`px-2 py-1 text-xs rounded ${
                  alertFilter === 'unit' 
                    ? 'bg-purple-600 text-white' 
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                UNIT
              </button>
              <button
                onClick={() => setAlertFilter('vol')}
                className={`px-2 py-1 text-xs rounded ${
                  alertFilter === 'vol' 
                    ? 'bg-blue-600 text-white' 
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                VOL
              </button>
              <button
                onClick={() => setAlertFilter('unit_alert')}
                className={`px-2 py-1 text-xs rounded ${
                  alertFilter === 'unit_alert' 
                    ? 'bg-red-600 text-white' 
                    : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                }`}
              >
                UNIT Alert
              </button>
            </div>
          </div>
          {loadingAlerts ? (
            <div className="animate-pulse space-y-3">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="h-12 bg-gray-200 rounded"></div>
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              {topAlerts.length === 0 ? (
                <div className="text-gray-500 text-sm">No hay alertas disponibles</div>
              ) : (
                topAlerts.map((alert, idx) => {
                  const badge = alert.dominant_driver || alert.dominant_effect || '-'
                  const badgeStyle = badge === 'UNIT'
                    ? 'bg-purple-100 text-purple-800'
                    : badge === 'VOL'
                      ? 'bg-blue-100 text-blue-800'
                      : 'bg-gray-100 text-gray-700'
                  const hasUnitAlert = alert.unit_alert === true
                  return (
                    <div key={`${alert.week_start}-${idx}`} className={`border rounded-md p-3 ${hasUnitAlert ? 'border-red-300 bg-red-50' : ''}`}>
                      <div className="flex items-center justify-between">
                        <div className="text-sm font-semibold">{formatWeek(alert.week_start)}</div>
                        <div className="flex gap-1 items-center">
                          {hasUnitAlert && (
                            <span className="px-1.5 py-0.5 rounded text-xs font-bold bg-red-600 text-white" title="Alerta unitaria (gap_unitario_pct <= -10%, trips >= 10k)">
                              ⚠
                            </span>
                          )}
                          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${badgeStyle}`}>{badge}</span>
                        </div>
                      </div>
                      <div className="text-xs text-gray-600 mt-1">
                        {alert.country || '-'} · {alert.city_norm || '-'} · {alert.lob_base || '-'}
                      </div>
                      <div className="text-sm mt-2 space-y-1">
                        <div className={`${alert.gap_revenue < 0 ? 'text-red-600' : 'text-gray-700'}`}>
                          Δ Revenue: {formatCurrency(alert.gap_revenue)} ({formatPercent(alert.gap_revenue_pct)})
                        </div>
                        <div className={`${alert.gap_trips < 0 ? 'text-red-600' : 'text-gray-700'}`}>
                          Δ Trips: {formatNumber(alert.gap_trips)} ({formatPercent(alert.gap_trips_pct)})
                        </div>
                        {alert.gap_unitario_pct !== null && alert.gap_unitario_pct !== undefined && (
                          <div className={`${alert.gap_unitario_pct < 0 ? 'text-red-600 font-semibold' : 'text-gray-700'}`}>
                            Δ Unitario: {formatPercent(alert.gap_unitario_pct)}
                          </div>
                        )}
                      </div>
                      <div className="text-xs text-gray-700 mt-2 font-medium">{alert.why}</div>
                      {alert.severity_score !== null && alert.severity_score !== undefined && (
                        <div className="text-xs text-gray-500 mt-1">
                          Severidad: {formatCurrency(Math.abs(alert.severity_score))}
                        </div>
                      )}
                      <div className="mt-3 flex items-center justify-between">
                        {alert.has_action ? (
                          <span className="text-xs text-green-600 font-semibold">✓ Acción registrada</span>
                        ) : (
                          <button
                            onClick={() => handleRegisterAction(alert)}
                            className="px-3 py-1 text-xs rounded bg-blue-600 text-white hover:bg-blue-700"
                          >
                            Registrar acción
                          </button>
                        )}
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          )}
        </div>
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

export default WeeklyPlanVsRealView
