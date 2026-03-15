/**
 * Fase 2A — Real vs Proyección.
 * Muestra: overview (readiness), dimensiones, cobertura de mapping, métricas reales disponibles,
 * contrato de plantilla y placeholders de comparación. Sin visualizaciones complejas.
 */
import { useState, useEffect } from 'react'
import {
  getRealVsProjectionOverview,
  getRealVsProjectionDimensions,
  getRealVsProjectionMappingCoverage,
  getRealVsProjectionRealMetrics,
  getRealVsProjectionTemplateContract
} from '../services/api'

function RealVsProjectionView () {
  const [overview, setOverview] = useState(null)
  const [dimensions, setDimensions] = useState([])
  const [mappingCoverage, setMappingCoverage] = useState([])
  const [realMetrics, setRealMetrics] = useState([])
  const [contract, setContract] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [ov, dim, mapCov, metrics, ctr] = await Promise.all([
        getRealVsProjectionOverview(),
        getRealVsProjectionDimensions(),
        getRealVsProjectionMappingCoverage(),
        getRealVsProjectionRealMetrics({ limit: 50 }),
        getRealVsProjectionTemplateContract()
      ])
      setOverview(ov?.error ? null : ov)
      setDimensions(Array.isArray(dim) ? dim : [])
      setMappingCoverage(Array.isArray(mapCov) ? mapCov : [])
      setRealMetrics(Array.isArray(metrics) ? metrics : [])
      setContract(ctr?.error ? null : ctr)
    } catch (e) {
      setError(e?.message || e?.response?.data?.detail || 'Error al cargar Real vs Proyección')
      setOverview(null)
      setDimensions([])
      setMappingCoverage([])
      setRealMetrics([])
      setContract(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  if (loading) {
    return (
      <div className="p-6 text-gray-600">Cargando Real vs Proyección…</div>
    )
  }

  if (error) {
    return (
      <div className="p-6 rounded-lg bg-red-50 text-red-800">
        <p className="font-medium">Error</p>
        <p className="text-sm mt-1">{error}</p>
        <p className="text-xs mt-2 text-gray-600">Compruebe que la migración 097 (real_vs_projection) esté aplicada y que exista ops.mv_real_trips_monthly.</p>
        <button type="button" onClick={load} className="mt-3 px-3 py-1.5 rounded border border-red-300 bg-white text-red-700 text-sm hover:bg-red-50">
          Reintentar
        </button>
      </div>
    )
  }

  const ready = overview?.ready_for_comparison === true
  const projectionLoaded = overview?.projection_loaded === true
  const realAvailable = overview?.real_metrics_available === true

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 className="text-xl font-semibold text-gray-800">Real vs Proyección</h2>
        <button type="button" onClick={load} className="px-3 py-1.5 rounded border border-gray-300 bg-white text-gray-700 text-sm hover:bg-gray-50">
          Actualizar
        </button>
      </div>

      <p className="text-sm text-gray-600">
        Base analítica para comparar resultados reales con metas/proyección. Cuando se cargue la plantilla Excel de proyección, aquí se mostrará el comparativo por segmentación del sistema y por segmentación de la proyección.
      </p>

      {/* Readiness */}
      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-gray-800 mb-3">Estado del comparativo</h3>
        <ul className="space-y-1 text-sm">
          <li><span className="font-medium">Métricas reales disponibles:</span> {realAvailable ? 'Sí' : 'No'} {overview?.real_metrics_rows != null && `(${overview.real_metrics_rows} filas)`}</li>
          <li><span className="font-medium">Proyección cargada:</span> {projectionLoaded ? 'Sí' : 'No'} {overview?.projection_staging_rows != null && `(${overview.projection_staging_rows} filas en staging)`}</li>
          <li><span className="font-medium">Reglas de mapping:</span> {overview?.mapping_rules_count ?? 0}</li>
          <li><span className="font-medium">Listo para comparar:</span> {ready ? 'Sí' : 'No (falta cargar proyección o no hay datos reales)'}</li>
        </ul>
      </section>

      {/* Dimensiones */}
      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-gray-800 mb-3">Dimensiones disponibles (sistema)</h3>
        <ul className="flex flex-wrap gap-2">
          {dimensions.map((d, i) => (
            <li key={i} className="px-2 py-1 rounded bg-gray-100 text-gray-700 text-xs">{d.id}</li>
          ))}
          {dimensions.length === 0 && <li className="text-gray-500 text-sm">No disponibles (compruebe backend /ops/real-vs-projection/dimensions)</li>}
        </ul>
      </section>

      {/* Cobertura de mapping */}
      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-gray-800 mb-3">Cobertura de mapping</h3>
        {mappingCoverage.length === 0 ? (
          <p className="text-sm text-gray-500">Sin reglas de mapping aún. Cuando se cargue la proyección, aquí aparecerá la cobertura por tipo de dimensión.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-2">Dimensión</th>
                <th className="text-right py-2">Reglas</th>
                <th className="text-right py-2">Matched</th>
              </tr>
            </thead>
            <tbody>
              {mappingCoverage.map((row, i) => (
                <tr key={i} className="border-b border-gray-100">
                  <td className="py-1">{row.dimension_type}</td>
                  <td className="text-right">{row.rule_count}</td>
                  <td className="text-right">{row.matched_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Métricas reales (muestra) */}
      <section className="rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-gray-800 mb-3">Métricas reales disponibles (muestra)</h3>
        {realMetrics.length === 0 ? (
          <p className="text-sm text-gray-500">No hay filas en ops.v_real_metrics_monthly. Compruebe que ops.mv_real_trips_monthly exista y tenga datos.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-2">period</th>
                  <th className="text-left py-2">country</th>
                  <th className="text-left py-2">city</th>
                  <th className="text-right py-2">drivers_real</th>
                  <th className="text-right py-2">trips_real</th>
                  <th className="text-right py-2">revenue_real</th>
                </tr>
              </thead>
              <tbody>
                {realMetrics.slice(0, 15).map((row, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    <td className="py-1">{row.period}</td>
                    <td className="py-1">{row.country}</td>
                    <td className="py-1">{row.city ?? row.city_norm}</td>
                    <td className="text-right py-1">{row.drivers_real != null ? Number(row.drivers_real).toLocaleString() : '—'}</td>
                    <td className="text-right py-1">{row.trips_real != null ? Number(row.trips_real).toLocaleString() : '—'}</td>
                    <td className="text-right py-1">{row.revenue_real != null ? Number(row.revenue_real).toLocaleString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-gray-500 mt-2">Mostrando hasta 15 de {realMetrics.length} filas.</p>
          </div>
        )}
      </section>

      {/* Contrato plantilla */}
      {contract && (
        <section className="rounded-lg border border-gray-200 bg-white p-4">
          <h3 className="text-sm font-semibold text-gray-800 mb-3">Contrato esperado (plantilla Excel)</h3>
          <p className="text-xs text-gray-600 mb-2">{contract.description}</p>
          <p className="text-xs text-gray-500">Columnas sugeridas: {contract.expected_columns_suggested?.join(', ')}</p>
        </section>
      )}

      {/* Placeholder comparación */}
      <section className="rounded-lg border border-amber-200 bg-amber-50 p-4">
        <h3 className="text-sm font-semibold text-amber-900 mb-2">Comparación Real vs Proyección</h3>
        <p className="text-sm text-amber-800">
          Cuando se suba la plantilla de proyección, aquí se mostrarán las vistas por segmentación del sistema y por segmentación de la proyección, con brechas (drivers, viajes, ticket, revenue) y descomposición de palancas.
        </p>
      </section>
    </div>
  )
}

export default RealVsProjectionView
