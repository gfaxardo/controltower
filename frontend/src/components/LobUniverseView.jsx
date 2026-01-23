import { useState, useEffect } from 'react'
import { getLobUniverse, getUnmatchedTrips } from '../services/api'

function LobUniverseView({ filters = {} }) {
  const [universeData, setUniverseData] = useState(null)
  const [unmatchedData, setUnmatchedData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [activeSection, setActiveSection] = useState('universe') // 'universe' o 'unmatched'

  useEffect(() => {
    loadData()
  }, [filters, activeSection])

  const loadData = async () => {
    try {
      setLoading(true)
      if (activeSection === 'universe') {
        const response = await getLobUniverse({
          country: filters.country || undefined,
          city: filters.city || undefined,
          lob_name: filters.line_of_business || undefined
        })
        setUniverseData(response)
      } else {
        const response = await getUnmatchedTrips({
          country: filters.country || undefined,
          city: filters.city || undefined
        })
        setUnmatchedData(response)
      }
    } catch (error) {
      console.error('Error al cargar datos:', error)
    } finally {
      setLoading(false)
    }
  }

  const formatNumber = (num) => {
    if (num === null || num === undefined) return '-'
    return num.toLocaleString('es-ES', { maximumFractionDigits: 0 })
  }

  const formatPercentage = (num) => {
    if (num === null || num === undefined) return '-'
    return `${num.toFixed(2)}%`
  }

  const getStatusBadgeColor = (status) => {
    const colors = {
      'OK': 'bg-green-100 text-green-800',
      'PLAN_ONLY': 'bg-yellow-100 text-yellow-800'
    }
    return colors[status] || 'bg-gray-100 text-gray-800'
  }

  return (
    <div className="space-y-6">
      {/* Sección de navegación */}
      <div className="bg-white p-4 rounded-lg shadow-md">
        <div className="flex space-x-4 border-b border-gray-200">
          <button
            onClick={() => setActiveSection('universe')}
            className={`py-2 px-4 border-b-2 font-medium text-sm ${
              activeSection === 'universe'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Universo LOB (Plan vs Real)
          </button>
          <button
            onClick={() => setActiveSection('unmatched')}
            className={`py-2 px-4 border-b-2 font-medium text-sm ${
              activeSection === 'unmatched'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Viajes sin Mapeo
          </button>
        </div>
      </div>

      {/* Sección: Universo LOB */}
      {activeSection === 'universe' && (
        <div className="space-y-4">
          {/* Alerta si no hay plan catalog */}
          {universeData && !universeData.has_plan_catalog && (
            <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 rounded-md">
              <p className="text-yellow-800 text-sm">
                ⚠️ <strong>Modo REAL-only:</strong> No se encontró catálogo de LOB del plan. 
                El sistema muestra solo viajes reales sin mapeo. Carga el plan para habilitar comparación Plan vs Real.
              </p>
            </div>
          )}
          
          {/* KPIs */}
          {universeData?.kpis && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-white p-4 rounded-lg shadow-md">
                <div className="text-sm text-gray-600">Total LOB Planificadas</div>
                <div className="text-2xl font-bold text-gray-900">{formatNumber(universeData.kpis.total_lob_plan)}</div>
                {!universeData.has_plan_catalog && (
                  <div className="text-xs text-yellow-600 mt-1">Sin plan catalog</div>
                )}
              </div>
              <div className="bg-white p-4 rounded-lg shadow-md">
                <div className="text-sm text-gray-600">LOB con Real</div>
                <div className="text-2xl font-bold text-green-600">{formatNumber(universeData.kpis.lob_with_real)}</div>
                {universeData.has_plan_catalog && (
                  <div className="text-xs text-gray-500">{formatPercentage(universeData.kpis.pct_lob_with_real)}</div>
                )}
              </div>
              <div className="bg-white p-4 rounded-lg shadow-md">
                <div className="text-sm text-gray-600">LOB sin Real</div>
                <div className="text-2xl font-bold text-yellow-600">{formatNumber(universeData.kpis.lob_without_real)}</div>
              </div>
              <div className="bg-white p-4 rounded-lg shadow-md">
                <div className="text-sm text-gray-600">% Viajes UNMATCHED</div>
                <div className="text-2xl font-bold text-red-600">{formatPercentage(universeData.kpis.pct_unmatched)}</div>
                <div className="text-xs text-gray-500">{formatNumber(universeData.kpis.total_unmatched)} de {formatNumber(universeData.kpis.total_trips)}</div>
              </div>
            </div>
          )}

          {/* Tabla de universo */}
          <div className="bg-white p-6 rounded-lg shadow-md">
            <h3 className="text-lg font-semibold mb-4">
              Universo LOB - Plan vs Real
              {!universeData?.has_plan_catalog && (
                <span className="ml-2 text-sm font-normal text-yellow-600">(Modo REAL-only)</span>
              )}
            </h3>
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
                {universeData?.universe && universeData.universe.length > 0 ? (
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">País</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ciudad</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">LOB</th>
                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Viajes Real</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {universeData.universe.map((row, idx) => (
                        <tr key={idx}>
                          <td className="px-4 py-3 text-sm text-gray-900">{row.country || '-'}</td>
                          <td className="px-4 py-3 text-sm text-gray-900">{row.city || '-'}</td>
                          <td className="px-4 py-3 text-sm text-gray-900">{row.lob_name || '-'}</td>
                          <td className="px-4 py-3 text-sm text-gray-900 text-right">{formatNumber(row.real_trips)}</td>
                          <td className="px-4 py-3 text-sm">
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusBadgeColor(row.coverage_status)}`}>
                              {row.coverage_status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div className="text-center py-8">
                    <p className="text-gray-500 mb-2">No hay datos de universo LOB disponible.</p>
                    {!universeData?.has_plan_catalog && (
                      <p className="text-sm text-yellow-600">Carga el plan para habilitar esta vista.</p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Sección: Viajes sin Mapeo */}
      {activeSection === 'unmatched' && (
        <div className="space-y-4">
          {/* Resumen */}
          {unmatchedData && (
            <div className="bg-white p-4 rounded-lg shadow-md">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <div className="text-sm text-gray-600">Total Viajes UNMATCHED</div>
                  <div className="text-2xl font-bold text-red-600">{formatNumber(unmatchedData.total_unmatched)}</div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Grupos Únicos</div>
                  <div className="text-2xl font-bold text-gray-900">{formatNumber(unmatchedData.total_groups)}</div>
                </div>
              </div>
            </div>
          )}

          {/* Tabla de viajes unmatched */}
          <div className="bg-white p-6 rounded-lg shadow-md">
            <h3 className="text-lg font-semibold mb-4">Viajes Reales sin Mapeo a LOB del Plan</h3>
            <p className="text-sm text-gray-600 mb-4">
              Muestra viajes reales agrupados por país, ciudad, LOB base y market type (B2B/B2C).
            </p>
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
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ciudad (Resolved)</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ciudad (Raw)</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">LOB Base</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Market Type</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Viajes</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Primer Viaje</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Último Viaje</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {unmatchedData?.unmatched_trips?.map((row, idx) => (
                      <tr key={idx}>
                        <td className="px-4 py-3 text-sm text-gray-900">{row.country || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{row.city || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-500">
                          {row.city_raw && row.city_raw !== row.city ? (
                            <span className="italic">{row.city_raw}</span>
                          ) : (
                            <span className="text-gray-400">-</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-900 font-medium">{row.lob_base || '-'}</td>
                        <td className="px-4 py-3 text-sm">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            row.market_type === 'B2B' 
                              ? 'bg-blue-100 text-blue-800' 
                              : 'bg-gray-100 text-gray-800'
                          }`}>
                            {row.market_type || 'B2C'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-900 text-right">{formatNumber(row.trips_count)}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">
                          {row.first_seen_date ? new Date(row.first_seen_date).toLocaleDateString('es-ES') : '-'}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-900">
                          {row.last_seen_date ? new Date(row.last_seen_date).toLocaleDateString('es-ES') : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {(!unmatchedData?.unmatched_trips || unmatchedData.unmatched_trips.length === 0) && (
                  <p className="text-gray-500 text-center py-8">No hay viajes sin mapeo</p>
                )}
              </div>
            )}
          </div>

          {/* Tabla de unmatched por ubicación */}
          {unmatchedData?.unmatched_by_location && unmatchedData.unmatched_by_location.length > 0 && (
            <div className="bg-white p-6 rounded-lg shadow-md">
              <h3 className="text-lg font-semibold mb-4">Viajes UNMATCHED por Ubicación</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">País</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Ciudad</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Viajes UNMATCHED</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Tipos Servicio Distintos</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">% del Total Ubicación</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {unmatchedData.unmatched_by_location.map((row, idx) => (
                      <tr key={idx}>
                        <td className="px-4 py-3 text-sm text-gray-900">{row.country || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{row.city || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-900 text-right">{formatNumber(row.unmatched_trips)}</td>
                        <td className="px-4 py-3 text-sm text-gray-900 text-right">{formatNumber(row.distinct_tipo_servicio)}</td>
                        <td className="px-4 py-3 text-sm text-gray-900 text-right">{formatPercentage(row.pct_of_location_trips)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default LobUniverseView
