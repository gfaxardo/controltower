/**
 * OwnershipServingView — FASE 1.1
 * Vista de ownership dentro de Omniview Matrix.
 * Muestra métricas plan vs real agrupadas por Jefe Producto.
 *
 * NO implementa rankings, leaderboards, gamificación, heatmaps.
 */
import { useMemo } from 'react'

const STATUS_COLORS = {
  on_track: 'bg-emerald-100 text-emerald-800',
  at_risk: 'bg-amber-100 text-amber-800',
  behind: 'bg-red-100 text-red-800',
  no_target: 'bg-gray-100 text-gray-500',
}

function fmtNum(n) {
  if (n == null || isNaN(n)) return '—'
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(1) + 'M'
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(0) + 'K'
  return Number(n).toFixed(0)
}

function fmtPct(n) {
  if (n == null || isNaN(n)) return '—'
  return Number(n).toFixed(1) + '%'
}

function fmtRevenue(n) {
  if (n == null || isNaN(n)) return '—'
  const abs = Math.abs(n)
  if (abs >= 1e9) return (n / 1e9).toFixed(2) + 'B'
  if (abs >= 1e6) return (n / 1e6).toFixed(1) + 'M'
  if (abs >= 1e3) return (n / 1e3).toFixed(0) + 'K'
  return Number(n).toFixed(0)
}

export default function OwnershipServingView({ rows = [], byOwner = [], loading, error }) {
  // Group rows by jefe_producto → lob_base → country → city
  const grouped = useMemo(() => {
    const map = new Map()
    for (const r of rows) {
      const owner = r.jefe_producto || 'Sin asignar'
      const lob = r.lob_base || '—'
      const country = r.country || '—'
      const city = r.city || '—'

      if (!map.has(owner)) map.set(owner, new Map())
      const lobMap = map.get(owner)
      if (!lobMap.has(lob)) lobMap.set(lob, [])
      lobMap.get(lob).push(r)
    }
    return map
  }, [rows])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-ct-text2">Cargando Ownership Perspective...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center max-w-md">
          <div className="text-3xl mb-3">⚠️</div>
          <p className="text-sm font-semibold text-red-600 mb-1">No se pudo cargar Ownership Perspective</p>
          <p className="text-xs text-ct-text2">Operational View sigue disponible.</p>
          <p className="text-xs text-red-400 mt-2 font-mono">{error}</p>
        </div>
      </div>
    )
  }

  if (rows.length === 0) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center max-w-md">
          <div className="text-3xl mb-3">📋</div>
          <p className="text-sm font-semibold text-ct-text mb-1">No hay ownership asignado para esta versión de proyección</p>
          <p className="text-xs text-ct-text2">Sube una plantilla con Jefe Producto o selecciona otra plan_version.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full overflow-auto">
      {/* Owner summary cards */}
      {byOwner && byOwner.length > 0 && (
        <div className="flex flex-wrap gap-3 mb-4 px-1">
          {byOwner.map((o) => (
            <div key={o.jefe_producto} className="flex-1 min-w-[220px] bg-ct-card border border-ct-border rounded-lg p-3">
              <p className="text-sm font-bold text-ct-text mb-2">{o.jefe_producto}</p>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                <span className="text-ct-text2">Líneas</span>
                <span className="text-ct-text font-semibold text-right">{o.row_count}</span>
                <span className="text-ct-text2">Proj Trips</span>
                <span className="text-ct-text font-semibold text-right">{fmtNum(o.projected_trips)}</span>
                <span className="text-ct-text2">Real Trips</span>
                <span className="text-ct-text font-semibold text-right">{fmtNum(o.real_trips)}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Grouped table */}
      {Array.from(grouped.entries()).map(([owner, lobMap]) => (
        <div key={owner} className="mb-6">
          <h3 className="text-base font-bold text-ct-text mb-2 px-1 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" />
            {owner}
          </h3>

          {Array.from(lobMap.entries()).map(([lob, items]) => (
            <div key={lob} className="mb-3 ml-4">
              <h4 className="text-sm font-semibold text-ct-text2 mb-1">{lob}</h4>

              <table className="w-full text-xs border border-ct-border rounded-md overflow-hidden">
                <thead>
                  <tr className="bg-ct-surface">
                    <th className="text-left px-2 py-1.5 font-semibold text-ct-text2">País</th>
                    <th className="text-left px-2 py-1.5 font-semibold text-ct-text2">Ciudad</th>
                    <th className="text-right px-2 py-1.5 font-semibold text-ct-text2">Período</th>
                    <th className="text-right px-2 py-1.5 font-semibold text-ct-text2">Proj Trips</th>
                    <th className="text-right px-2 py-1.5 font-semibold text-ct-text2">Real Trips</th>
                    <th className="text-right px-2 py-1.5 font-semibold text-ct-text2">Proj Revenue</th>
                    <th className="text-right px-2 py-1.5 font-semibold text-ct-text2">Real Revenue</th>
                    <th className="text-right px-2 py-1.5 font-semibold text-ct-text2">Exec %</th>
                    <th className="text-center px-2 py-1.5 font-semibold text-ct-text2">Estado</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((r, i) => (
                    <tr key={i} className={`border-t border-ct-border ${i % 2 === 0 ? 'bg-ct-bg' : 'bg-ct-card'}`}>
                      <td className="px-2 py-1 font-medium">{r.country}</td>
                      <td className="px-2 py-1">{r.city}</td>
                      <td className="px-2 py-1 text-right font-mono text-ct-text2">{r.month}</td>
                      <td className="px-2 py-1 text-right">{fmtNum(r.projected_trips)}</td>
                      <td className="px-2 py-1 text-right">{fmtNum(r.real_trips)}</td>
                      <td className="px-2 py-1 text-right">{fmtRevenue(r.projected_revenue)}</td>
                      <td className="px-2 py-1 text-right">{fmtRevenue(r.real_revenue)}</td>
                      <td className="px-2 py-1 text-right font-semibold">{fmtPct(r.execution_pct_trips)}</td>
                      <td className="px-2 py-1 text-center">
                        <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold ${STATUS_COLORS[r.momentum_status] || 'bg-gray-100 text-gray-500'}`}>
                          {r.momentum_status === 'on_track' ? 'On track' :
                           r.momentum_status === 'at_risk' ? 'At risk' :
                           r.momentum_status === 'behind' ? 'Behind' :
                           r.momentum_status === 'no_target' ? 'No target' :
                           r.momentum_status || '—'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
