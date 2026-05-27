/**
 * OperationalPriorities — FASE H3.5B
 * Execution Intelligence: Movement-first operational prioritization.
 *
 * Convierte driver movement intelligence en prioridades accionables.
 * Deterministic rules. NO AI. NO ML.
 */
import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'

const PRIORITY_COLORS = {
  'P0_CRITICAL': 'bg-red-100 text-red-800 border-red-300',
  'P1_HIGH': 'bg-amber-100 text-amber-800 border-amber-300',
  'P2_MEDIUM': 'bg-blue-100 text-blue-800 border-blue-300',
  'P3_LOW': 'bg-gray-100 text-gray-600 border-gray-300',
  SUCCESS_TRACKING: 'bg-green-100 text-green-800 border-green-300',
  MONITOR: 'bg-slate-100 text-slate-600 border-slate-300',
}

const MOVEMENT_COLORS = {
  DOWNGRADE: 'bg-red-100 text-red-800',
  BECAME_DORMANT: 'bg-red-50 text-red-700',
  CHURNED: 'bg-red-100 text-red-900',
  UPGRADE: 'bg-green-100 text-green-800',
  REACTIVATED: 'bg-emerald-100 text-emerald-700',
  NEW_ACTIVE: 'bg-sky-100 text-sky-700',
  SAME_SEGMENT: 'bg-gray-100 text-gray-600',
}

const READINESS_COLORS = {
  READY: 'bg-emerald-100 text-emerald-700',
  MISSING_PHONE: 'bg-amber-100 text-amber-700',
  CONTACT_LIMIT_REACHED: 'bg-orange-100 text-orange-700',
  ALREADY_IN_CAMPAIGN: 'bg-blue-100 text-blue-700',
  STALE_DATA: 'bg-purple-100 text-purple-700',
  BLOCKED: 'bg-red-100 text-red-700',
}

const PRIORITY_OPTIONS = ['', 'P0_CRITICAL', 'P1_HIGH', 'P2_MEDIUM', 'P3_LOW']
const MOVEMENT_OPTIONS = ['', 'DOWNGRADE', 'BECAME_DORMANT', 'CHURNED', 'UPGRADE', 'REACTIVATED', 'NEW_ACTIVE']

function formatNum (n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('es-ES')
}

function PriorityBadge ({ p }) {
  const c = PRIORITY_COLORS[p] || PRIORITY_COLORS.P3_LOW
  return <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${c}`}>{p}</span>
}

export default function OperationalPriorities () {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filters, setFilters] = useState({
    operational_priority: '',
    movement_type: '',
    campaignable_only: false,
    execution_ready_only: false,
  })

  const loadData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = { limit: 100 }
      if (filters.operational_priority) params.operational_priority = filters.operational_priority
      if (filters.movement_type) params.movement_type = filters.movement_type
      if (filters.campaignable_only) params.campaignable_only = true
      if (filters.execution_ready_only) params.execution_ready_only = true
      const res = await api.get('/drivers/movements/actionable', { params, timeout: 30000 })
      setData(res.data)
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load')
    } finally { setLoading(false) }
  }, [filters])

  useEffect(() => { loadData() }, [loadData])

  return (
    <div className='space-y-4'>
      <div className='bg-ct-card border border-ct-border rounded-xl px-5 py-4'>
        <h2 className='text-lg font-bold text-ct-text'>Operational Priorities</h2>
        <p className='text-xs text-ct-text3 mt-1'>
          Priorización operacional a partir de movimiento de conductores. Reglas determinísticas. Sin IA ni scoring opaco.
        </p>
      </div>

      {/* Filters */}
      <div className='flex flex-wrap gap-3 items-end'>
        <div>
          <label className='block text-[10px] text-ct-text3 mb-1'>Priority</label>
          <select value={filters.operational_priority} onChange={e => setFilters(f => ({ ...f, operational_priority: e.target.value }))}
            className='px-2 py-1 border border-ct-border rounded text-xs'>
            <option value=''>All</option>
            {PRIORITY_OPTIONS.filter(Boolean).map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
        <div>
          <label className='block text-[10px] text-ct-text3 mb-1'>Movement</label>
          <select value={filters.movement_type} onChange={e => setFilters(f => ({ ...f, movement_type: e.target.value }))}
            className='px-2 py-1 border border-ct-border rounded text-xs'>
            <option value=''>All</option>
            {MOVEMENT_OPTIONS.filter(Boolean).map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <label className='flex items-center gap-1 text-[11px] cursor-pointer'>
          <input type='checkbox' checked={filters.campaignable_only} onChange={e => setFilters(f => ({ ...f, campaignable_only: e.target.checked }))} className='rounded' />
          Campaignable only
        </label>
        <label className='flex items-center gap-1 text-[11px] cursor-pointer'>
          <input type='checkbox' checked={filters.execution_ready_only} onChange={e => setFilters(f => ({ ...f, execution_ready_only: e.target.checked }))} className='rounded' />
          Execution ready only
        </label>
        <button type='button' onClick={loadData} disabled={loading}
          className='px-3 py-1 rounded bg-ct-accent text-white text-xs font-medium disabled:opacity-50'>
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>

      {error && <div className='bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-xs text-red-700'>{error}</div>}

      {loading ? (
        <div className='animate-pulse space-y-2'><div className='h-4 bg-gray-100 rounded w-48' /></div>
      ) : data?.status === 'blocked' ? (
        <div className='bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-xs text-red-700'>{data.error}</div>
      ) : (
        <>
          {/* KPI strip */}
          {data?.summary && (
            <div className='grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2'>
              {[
                { label: 'P0 Critical', value: data.summary.p0, color: 'text-red-700' },
                { label: 'P1 High', value: data.summary.p1, color: 'text-amber-700' },
                { label: 'P2 Medium', value: data.summary.p2, color: 'text-blue-700' },
                { label: 'P3 Low', value: data.summary.p3, color: 'text-gray-600' },
                { label: 'Success', value: data.summary.success, color: 'text-green-700' },
                { label: 'Recoverable', value: data.summary.recoverable_high, color: 'text-emerald-700' },
                { label: 'No Phone', value: data.summary.non_campaignable, color: 'text-red-500' },
              ].map(kpi => (
                <div key={kpi.label} className='border border-ct-border rounded-lg px-3 py-2 bg-white/40'>
                  <div className='text-[10px] text-ct-text3 uppercase'>{kpi.label}</div>
                  <div className={`text-sm font-bold ${kpi.color}`}>{kpi.value}</div>
                </div>
              ))}
            </div>
          )}

          {/* Data quality warning */}
          {data?.warnings?.length > 0 && (
            <div className='bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-[11px] text-amber-700'>
              {data.warnings[0]}
            </div>
          )}

          {/* Driver table */}
          <div className='bg-ct-card border border-ct-border rounded-lg overflow-hidden'>
            <div className='px-4 py-2 border-b border-ct-border text-xs text-ct-text2'>
              Period: {data?.period_current} · {data?.total || 0} drivers
            </div>
            {data?.drivers?.length > 0 ? (
              <div className='overflow-x-auto'>
                <table className='w-full text-[11px]'>
                  <thead>
                    <tr className='text-left text-gray-400 border-b border-gray-100'>
                      <th className='py-1.5 pr-1 w-5'></th>
                      <th className='py-1.5 pr-2'>Driver</th>
                      <th className='py-1.5 pr-2'>Movement</th>
                      <th className='py-1.5 pr-2'>From → To</th>
                      <th className='py-1.5 pr-2'>Priority</th>
                      <th className='py-1.5 pr-2'>Reason</th>
                      <th className='py-1.5 pr-2'>Queue Rec</th>
                      <th className='py-1.5 pr-2'>Readiness</th>
                      <th className='py-1.5 pr-2'>Recoverability</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.drivers.map((d, i) => (
                      <tr key={i} className='border-b border-gray-50 hover:bg-gray-50/50'>
                        <td className='py-1.5 pr-1'>
                          {d.phone ? <span className='text-emerald-500 text-[10px]'>&#x2713;</span> : <span className='text-amber-500 text-[10px]'>&#x2717;</span>}
                        </td>
                        <td className='py-1.5 pr-2'>
                          <div className='font-medium text-ct-text truncate max-w-[120px]' title={d.driver_name}>{d.driver_name || d.driver_id?.slice(0, 12)}</div>
                          <div className='text-[9px] text-ct-text3'>{d.city}{d.country ? ' · ' + d.country : ''}</div>
                        </td>
                        <td className='py-1.5 pr-2'>
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium ${MOVEMENT_COLORS[d.movement_type] || 'bg-gray-100'}`}>{d.movement_type}</span>
                        </td>
                        <td className='py-1.5 pr-2 text-ct-text2'>{d.from_segment} → {d.to_segment}</td>
                        <td className='py-1.5 pr-2'><PriorityBadge p={d.operational_priority} /></td>
                        <td className='py-1.5 pr-2 text-ct-text2 truncate max-w-[220px]' title={d.operational_reason}>{d.operational_reason}</td>
                        <td className='py-1.5 pr-2 text-[10px] text-ct-text2'>{d.recommended_queue}</td>
                        <td className='py-1.5 pr-2'>
                          <span className={`px-1 py-0.5 rounded text-[9px] font-medium ${READINESS_COLORS[d.execution_readiness] || 'bg-gray-100'}`}>{d.execution_readiness}</span>
                        </td>
                        <td className='py-1.5 pr-2'>
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-medium ${
                            d.recoverability_band === 'HIGH' ? 'bg-emerald-100 text-emerald-700' :
                            d.recoverability_band === 'MEDIUM' ? 'bg-amber-100 text-amber-700' :
                            d.recoverability_band === 'LOW' ? 'bg-gray-100 text-gray-600' :
                            'bg-gray-100 text-gray-400'
                          }`}>{d.recoverability_band}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className='px-4 py-6 text-center text-xs text-ct-text3'>No drivers match current filters.</div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
