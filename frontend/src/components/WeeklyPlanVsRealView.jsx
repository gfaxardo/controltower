import { useEffect, useMemo, useState } from 'react'
import { getPlanVsRealWeekly, getWeeklyAlerts } from '../services/api'
import RegisterActionModal from './RegisterActionModal'
import DecisionSeverityBadge from './operational/DecisionSeverityBadge'
import DecisionPriorityStrip from './operational/DecisionPriorityStrip'
import { getDecisionSeverity } from '../utils/operationalDecisionSeverity'
import DiagnosticDominantFactor from './diagnostics/DiagnosticDominantFactor'

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

  /** Signal extractor para severidad operacional de alertas */
  const alertSignalExtractor = useMemo(() => (alert) => ({
    gap_revenue_pct: alert.gap_revenue_pct != null ? alert.gap_revenue_pct * 100 : undefined,
    gap_trips_pct: alert.gap_trips_pct != null ? alert.gap_trips_pct * 100 : undefined,
    gap_unitario_pct: alert.gap_unitario_pct != null ? alert.gap_unitario_pct * 100 : undefined,
    unit_alert: alert.unit_alert,
    __signals: alert.__signals,
  }), [])

  const handleRegisterAction = (alert) => {
    setSelectedAlert(alert)
    setIsModalOpen(true)
  }

  const handleActionRegistered = () => {
    loadAlertsData() // Recargar alertas para actualizar has_action
  }

  return (
    <div className="ct-panel shadow-sm mt-4">
      <div className="ct-panel-header">
        <div>
          <h3 className="text-base font-semibold text-ct-text">Fase 2B - Semanal</h3>
          <p className="text-xs text-ct-text2 mt-0.5">
            Comparación Plan vs Real semanal con descomposición y alertas accionables.
          </p>
        </div>
      </div>
      <div className="ct-panel-body">

      {/* Filter strip */}
      <div className="ct-form-row mb-3">
        <div className="ct-form-field" style={{minWidth: 160}}>
          <span className="ct-form-label">Semana desde</span>
          <input
            type="date"
            value={weekStartFrom}
            onChange={(e) => setWeekStartFrom(e.target.value)}
            className="ct-input"
          />
        </div>
        <div className="ct-form-field" style={{minWidth: 160}}>
          <span className="ct-form-label">Semana hasta</span>
          <input
            type="date"
            value={weekStartTo}
            onChange={(e) => setWeekStartTo(e.target.value)}
            className="ct-input"
          />
        </div>
        <button
          onClick={() => { setWeekStartFrom(''); setWeekStartTo('') }}
          className="ct-secondary-action"
          style={{alignSelf: 'flex-end'}}
        >
          Limpiar rango
        </button>
      </div>

      {/* Main content: table + alerts */}
      <div className="ct-content-grid">
        {/* Table panel */}
        <div>
          <div className="ct-table-card">
            <div className="ct-table-card-header">
              <span>A) Tabla Plan vs Real (semanal)</span>
            </div>
            {loadingComparison ? (
              <div className="p-4 animate-pulse">
                <div className="h-4 bg-ct-border/40 rounded w-1/3 mb-4"></div>
                <div className="space-y-2">
                  {[...Array(5)].map((_, i) => (
                    <div key={i} className="h-8 bg-ct-border/30 rounded"></div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-ct-border">
                  <thead className="bg-ct-surface">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-semibold text-ct-text2 uppercase">Week</th>
                      <th className="px-3 py-2 text-right text-xs font-semibold text-ct-text2 uppercase">Trips R/P/Δ/Δ%</th>
                      <th className="px-3 py-2 text-right text-xs font-semibold text-ct-text2 uppercase">Drivers R/P/Δ</th>
                      <th className="px-3 py-2 text-right text-xs font-semibold text-ct-text2 uppercase">Ingreso YEGO R/P/Δ/Δ%</th>
                      <th className="px-3 py-2 text-right text-xs font-semibold text-ct-text2 uppercase">
                        <div className="flex items-center justify-end gap-1 whitespace-normal max-w-[180px]">
                          <span className="block leading-tight">Ingreso por viaje R/P/Δ/Δ%</span>
                          <span className="text-ct-text3" title={MARGEN_UNITARIO_TOOLTIP} aria-label={MARGEN_UNITARIO_TOOLTIP}>ℹ️</span>
                        </div>
                      </th>
                      <th className="px-3 py-2 text-center text-xs font-semibold text-ct-text2 uppercase">Driver</th>
                      <th className="px-3 py-2 text-right text-xs font-semibold text-ct-text2 uppercase">
                        <div className="flex items-center justify-end gap-1 whitespace-normal max-w-[180px]">
                          <span className="block leading-tight">Trips/Driver R/P/Δ</span>
                          <span className="text-ct-text3" title={PRODUCTIVIDAD_TOOLTIP} aria-label={PRODUCTIVIDAD_TOOLTIP}>ℹ️</span>
                        </div>
                      </th>
                      <th className="px-3 py-2 text-center text-xs font-semibold text-ct-text2 uppercase">Detalle</th>
                    </tr>
                  </thead>
                  <tbody className="bg-ct-card divide-y divide-ct-border">
                    {comparisonData.length === 0 ? (
                      <tr>
                        <td colSpan="8" className="px-4 py-4 text-center text-ct-text3 text-sm">
                          No hay datos disponibles
                        </td>
                      </tr>
                    ) : (
                      comparisonData.slice(0, 50).map((row, idx) => {
                        const key = `${row.week_start}-${row.country}-${row.city_norm}-${row.lob_base}-${row.segment}-${idx}`
                        const isExpanded = expandedRows[key]
                        return (
                          <>
                            <tr key={key} className="hover:bg-ct-surface/60">
                              <td className="px-3 py-2 text-sm text-ct-text whitespace-nowrap">
                                {formatWeek(row.week_start)}
                              </td>
                              <td className="px-3 py-2 text-sm text-right">
                                <div className="text-ct-text">{formatNumber(row.trips_real)} / {formatNumber(row.trips_plan)}</div>
                                <div className={`${row.gap_trips < 0 ? 'text-ct-bad font-medium' : row.gap_trips > 0 ? 'text-ct-good font-medium' : 'text-ct-text3'}`}>
                                  {formatNumber(row.gap_trips)} · {formatPercent(row.gap_trips_pct)}
                                </div>
                              </td>
                              <td className="px-3 py-2 text-sm text-right">
                                <div className="text-ct-text">{formatNumber(row.drivers_real)} / {formatNumber(row.drivers_plan)}</div>
                                <div className={`${row.gap_drivers < 0 ? 'text-ct-bad font-medium' : row.gap_drivers > 0 ? 'text-ct-good font-medium' : 'text-ct-text3'}`}>
                                  {formatNumber(row.gap_drivers)}
                                </div>
                              </td>
                              <td className="px-3 py-2 text-sm text-right">
                                <div className="text-ct-text">{formatCurrency(row.revenue_real)} / {formatCurrency(row.revenue_plan)}</div>
                                <div className={`${row.gap_revenue < 0 ? 'text-ct-bad font-medium' : row.gap_revenue > 0 ? 'text-ct-good font-medium' : 'text-ct-text3'}`}>
                                  {formatCurrency(row.gap_revenue)} · {formatPercent(row.gap_revenue_pct)}
                                </div>
                              </td>
                              <td className="px-3 py-2 text-sm text-right">
                                <div className="text-ct-text">{formatCurrency(row.ingreso_por_viaje_real)} / {formatCurrency(row.ingreso_por_viaje_plan)}</div>
                                <div className={`${row.gap_unitario < 0 ? 'text-ct-bad font-medium' : row.gap_unitario > 0 ? 'text-ct-good font-medium' : 'text-ct-text3'}`}>
                                  {formatCurrency(row.gap_unitario)} · {formatPercent(row.gap_unitario_pct)}
                                </div>
                              </td>
                              <td className="px-3 py-2 text-sm text-center">
                                {row.dominant_driver ? (
                                  <span className={`ct-badge ${row.dominant_driver === 'UNIT' ? 'ct-badge--info' : 'ct-badge--neutral'}`}>
                                    {row.dominant_driver}
                                  </span>
                                ) : (
                                  <span className="text-ct-text3 text-xs">-</span>
                                )}
                              </td>
                              <td className="px-3 py-2 text-sm text-right">
                                <div className="text-ct-text">{formatNumber(row.productividad_real)} / {formatNumber(row.productividad_plan)}</div>
                                <div className={`${row.gap_prod < 0 ? 'text-ct-bad font-medium' : row.gap_prod > 0 ? 'text-ct-good font-medium' : 'text-ct-text3'}`}>
                                  {formatNumber(row.gap_prod)}
                                </div>
                              </td>
                              <td className="px-3 py-2 text-sm text-center">
                                <button
                                  onClick={() => toggleRow(key)}
                                  className="ct-secondary-action"
                                >
                                  {isExpanded ? 'Ocultar' : 'Ver'}
                                </button>
                              </td>
                            </tr>
                            {isExpanded && (
                              <tr>
                                <td colSpan="8" className="bg-ct-surface px-4 py-3 text-sm text-ct-text2">
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    <div>
                                      <div className="font-semibold text-ct-text mb-1">Descomposición revenue</div>
                                      <div>Efecto volumen: {formatCurrency(row.efecto_volumen)}</div>
                                      <div>Efecto unitario: {formatCurrency(row.efecto_unitario)}</div>
                                    </div>
                                    <div>
                                      <div className="font-semibold text-ct-text mb-1">Palancas de trips</div>
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
        </div>

        {/* Alerts panel */}
        <div>
          <DecisionPriorityStrip items={topAlerts} signalExtractor={alertSignalExtractor} className="mb-1.5" />
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-semibold text-ct-text">B) Panel Alertas</h4>
            <div className="flex gap-1">
              <button onClick={() => setAlertFilter('all')}
                className={`ct-secondary-action ${alertFilter === 'all' ? 'ct-secondary-action--active' : ''}`}>
                Todas
              </button>
              <button onClick={() => setAlertFilter('unit')}
                className={`ct-secondary-action ${alertFilter === 'unit' ? 'ct-secondary-action--active' : ''}`}>
                UNIT
              </button>
              <button onClick={() => setAlertFilter('vol')}
                className={`ct-secondary-action ${alertFilter === 'vol' ? 'ct-secondary-action--active' : ''}`}>
                VOL
              </button>
              <button onClick={() => setAlertFilter('unit_alert')}
                className={`ct-secondary-action ${alertFilter === 'unit_alert' ? 'ct-secondary-action--active' : ''}`}>
                UNIT Alert
              </button>
            </div>
          </div>
          {loadingAlerts ? (
            <div className="animate-pulse space-y-3">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="h-12 bg-ct-border/30 rounded"></div>
              ))}
            </div>
          ) : (
            <div className="ct-scroll-y" style={{'--scroll-max-h': 'calc(100vh - 360px)'}}>
              {topAlerts.length === 0 ? (
                <div className="text-ct-text3 text-sm py-4 text-center">No hay alertas disponibles</div>
              ) : (
                <div className="flex flex-col gap-2">
                  {topAlerts.map((alert, idx) => {
                    const badge = alert.dominant_driver || alert.dominant_effect || '-'
                    const hasUnitAlert = alert.unit_alert === true
                    return (
                      <div key={`${alert.week_start}-${idx}`} className={`border rounded-md p-3 ${hasUnitAlert ? 'border-ct-bad/40 bg-red-50/80' : 'border-ct-border bg-ct-card'}`}>
                        <div className="flex items-center justify-between">
                          <div className="text-sm font-semibold text-ct-text">{formatWeek(alert.week_start)}</div>
                          <div className="flex gap-1 items-center">
                            {hasUnitAlert && (
                              <span className="px-1.5 py-0.5 rounded text-xs font-bold bg-ct-bad text-white" title="Alerta unitaria">
                                ⚠
                              </span>
                            )}
                            <span className={`ct-badge ${badge === 'UNIT' ? 'ct-badge--info' : badge === 'VOL' ? 'ct-badge--neutral' : 'ct-badge--neutral'}`}>
                              {badge}
                            </span>
                          </div>
                        </div>
                        <div className="text-xs text-ct-text2 mt-1">
                          {alert.country || '-'} · {alert.city_norm || '-'} · {alert.lob_base || '-'}
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <DecisionSeverityBadge signals={alertSignalExtractor(alert)} compact />
                          <DiagnosticDominantFactor signals={alertSignalExtractor(alert)} className="min-w-0" />
                        </div>
                        <div className="text-sm mt-2 space-y-1">
                          <div className={`${alert.gap_revenue < 0 ? 'text-ct-bad font-medium' : 'text-ct-text'}`}>
                            Δ Revenue: {formatCurrency(alert.gap_revenue)} ({formatPercent(alert.gap_revenue_pct)})
                          </div>
                          <div className={`${alert.gap_trips < 0 ? 'text-ct-bad font-medium' : 'text-ct-text'}`}>
                            Δ Trips: {formatNumber(alert.gap_trips)} ({formatPercent(alert.gap_trips_pct)})
                          </div>
                          {alert.gap_unitario_pct !== null && alert.gap_unitario_pct !== undefined && (
                            <div className={`${alert.gap_unitario_pct < 0 ? 'text-ct-bad font-semibold' : 'text-ct-text'}`}>
                              Δ Unitario: {formatPercent(alert.gap_unitario_pct)}
                            </div>
                          )}
                        </div>
                        <div className="text-xs text-ct-text mt-2 font-medium">{alert.why}</div>
                        {alert.severity_score !== null && alert.severity_score !== undefined && (
                          <div className="text-xs text-ct-text2 mt-1">
                            Severidad: {formatCurrency(Math.abs(alert.severity_score))}
                          </div>
                        )}
                        <div className="mt-3 flex items-center justify-between">
                          {alert.has_action ? (
                            <span className="text-xs text-ct-good font-semibold">✓ Acción registrada</span>
                          ) : (
                            <button
                              onClick={() => handleRegisterAction(alert)}
                              className="ct-primary-action"
                              style={{fontSize: 'var(--ct-font-xs)', padding: '2px 10px'}}
                            >
                              Registrar acción
                            </button>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
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
    </div>
  )
}

export default WeeklyPlanVsRealView
