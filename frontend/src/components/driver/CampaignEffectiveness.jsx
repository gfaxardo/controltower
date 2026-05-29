/**
 * CampaignEffectiveness — FASE H3.4
 * Execution & Campaign Layer: Campaign Effectiveness Analytics
 *
 * Mide efectividad real de campañas ejecutadas vía CRM.
 * "Observed lift" — NO afirmar causalidad.
 *
 * NO IA. NO predicción. NO recomendaciones automáticas.
 */
import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'

const WINDOWS = [1, 3, 7, 14, 30]
const GROUP_OPTIONS = [
  { value: '', label: 'No grouping' },
  { value: 'owner', label: 'Owner' },
  { value: 'queue_type', label: 'Queue Type' },
  { value: 'lifecycle_stage', label: 'Lifecycle Stage' },
  { value: 'priority', label: 'Priority' },
  { value: 'city', label: 'City' },
  { value: 'country', label: 'Country' },
]

function formatNum (n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('es-ES')
}

function formatPct (n) {
  if (n == null) return '—'
  return (Number(n) * 100).toFixed(1) + '%'
}

export default function CampaignEffectiveness () {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [selectedCampaign, setSelectedCampaign] = useState('')
  const [windowDays, setWindowDays] = useState(7)
  const [groupBy, setGroupBy] = useState('')
  const [effectiveness, setEffectiveness] = useState(null)
  const [effLoading, setEffLoading] = useState(false)
  const [effError, setEffError] = useState(null)

  const loadSummary = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get('/drivers/campaigns/effectiveness-summary', { timeout: 15000 })
      setSummary(res.data)
    } catch { /* ignore */ } finally { setLoading(false) }
  }, [])

  useEffect(() => { loadSummary() }, [loadSummary])

  const loadEffectiveness = useCallback(async (id) => {
    if (!id) return
    setEffLoading(true)
    setEffError(null)
    try {
      const params = { window_days: windowDays, include_members: false }
      if (groupBy) params.group_by = groupBy
      const res = await api.get(`/drivers/campaigns/${id}/effectiveness`, { params, timeout: 30000 })
      setEffectiveness(res.data)
    } catch (err) {
      setEffError(err?.response?.data?.detail || err?.message || 'Failed to load')
    } finally { setEffLoading(false) }
  }, [windowDays, groupBy])

  const handleSelect = (id) => {
    setSelectedCampaign(id)
    loadEffectiveness(id)
  }

  return (
    <div className='space-y-4'>
      {/* Header + disclaimer */}
      <div className='bg-ct-card border border-ct-border rounded-xl px-5 py-4'>
        <h2 className='text-lg font-bold text-ct-text'>Resultado Observado de Campañas</h2>
        <p className='text-xs text-ct-text3 mt-1'>
          Mide actividad real post-campaña. Resultados expresados como "cambio observado". NO afirmar causalidad.
        </p>
      </div>

      <div className='bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-[11px] text-amber-800'>
        <strong>IMPORTANTE:</strong> Las métricas muestran correlación observada, no causalidad. Una reactivación post-campaña no prueba que la campaña causó la reactivación. Interpretar con contexto operacional.
      </div>

      {loading ? (
        <div className='animate-pulse space-y-2'><div className='h-4 bg-gray-100 rounded w-48' /><div className='h-3 bg-gray-50 rounded w-3/4' /></div>
      ) : (
        <>
          {/* Campaign list */}
          <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
            <h3 className='text-sm font-semibold text-ct-text mb-2'>Campaigns ({summary?.campaigns?.length || 0})</h3>
            <div className='overflow-x-auto'>
              <table className='w-full text-xs'>
                <thead>
                  <tr className='text-left text-gray-400 border-b'>
                    <th className='py-1.5 pr-2'>Campaign</th>
                    <th className='py-1.5 pr-2'>Type</th>
                    <th className='py-1.5 pr-2 text-right'>Conductores</th>
                    <th className='py-1.5 pr-2 text-right'>Contactados</th>
                    <th className='py-1.5 pr-2 text-right'>Recuperados</th>
                    <th className='py-1.5 pr-2 text-right'>Tel. malo</th>
                    <th className='py-1.5 pr-2'>Status</th>
                    <th className='py-1.5 pr-2'>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {summary?.campaigns?.map(c => (
                    <tr key={c.campaign_id} className={`border-b border-gray-50 ${selectedCampaign === c.campaign_id ? 'bg-blue-50' : 'hover:bg-gray-50/50'}`}>
                      <td className='py-1.5 pr-2 font-medium text-ct-text truncate max-w-[180px]'>{c.campaign_name || '(Sin nombre)'}</td>
                      <td className='py-1.5 pr-2 text-ct-text2'>{c.campaign_type}</td>
                      <td className='py-1.5 pr-2 text-right'>{c.target_count}</td>
                      <td className='py-1.5 pr-2 text-right text-emerald-600'>{c.contacted}</td>
                      <td className='py-1.5 pr-2 text-right text-green-600'>{c.recovered}</td>
                      <td className='py-1.5 pr-2 text-right text-red-500'>{c.bad_phone}</td>
                      <td className='py-1.5 pr-2'>{c.campaign_status}</td>
                      <td className='py-1.5 pr-2'>
                        <button type='button' onClick={() => handleSelect(c.campaign_id)}
                          className='px-2 py-0.5 rounded bg-blue-500 text-white text-[10px] font-medium hover:bg-blue-600'>
                          Analyze
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!summary?.campaigns?.length && (
                <div className='py-8 text-center text-xs text-ct-text3'>No campaigns yet. Create one in Campaign Intelligence.</div>
              )}
            </div>
          </div>

          {/* Effectiveness detail */}
          {selectedCampaign && (
            <div className='space-y-4'>
              {/* Controls */}
              <div className='flex flex-wrap gap-3 items-end'>
                <div>
                  <label className='block text-[10px] text-ct-text3 mb-1'>Window</label>
                  <div className='flex gap-1'>
                    {WINDOWS.map(w => (
                      <button key={w} type='button' onClick={() => setWindowDays(w)}
                        className={`px-2 py-1 rounded text-[10px] font-medium ${windowDays === w ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
                        D+{w}
                      </button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className='block text-[10px] text-ct-text3 mb-1'>Group By</label>
                  <select value={groupBy} onChange={e => setGroupBy(e.target.value)}
                    className='px-2 py-1 border border-ct-border rounded text-[10px]'>
                    {GROUP_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
                <button type='button' onClick={() => loadEffectiveness(selectedCampaign)} disabled={effLoading}
                  className='px-3 py-1 rounded bg-ct-accent text-white text-xs font-medium disabled:opacity-50'>
                  {effLoading ? 'Loading...' : 'Refresh'}
                </button>
              </div>

              {effError && (
                <div className='bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-xs text-red-700'>{effError}</div>
              )}

              {effLoading ? (
                <div className='animate-pulse space-y-2'><div className='h-4 bg-gray-100 rounded w-64' /><div className='h-3 bg-gray-50 rounded w-3/4' /></div>
              ) : effectiveness?.status === 'error' ? (
                <div className='bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-xs text-red-700'>{effectiveness.error}</div>
              ) : effectiveness?.summary ? (
                <>
                  {/* KPI strip */}
                  <div className='grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-2'>
                    {[
                      { label: `Ventana D+${windowDays}`, value: `${effectiveness.days_since_campaign}d transcurridos`, color: '' },
                      { label: 'Conductores', value: effectiveness.summary.target_count, color: '' },
                      { label: 'Contactados', value: effectiveness.summary.contacted_count, color: 'text-emerald-700' },
                      { label: 'Reactivados', value: effectiveness.summary.reactivated_count, color: 'text-green-700' },
                      { label: 'Tasa reactivación', value: formatPct(effectiveness.summary.reactivation_rate), color: 'text-green-700' },
                      { label: 'Cambio viajes', value: (effectiveness.summary.observed_trip_delta >= 0 ? '+' : '') + formatNum(effectiveness.summary.observed_trip_delta), color: effectiveness.summary.observed_trip_delta >= 0 ? 'text-emerald-700' : 'text-red-600' },
                    ].map(kpi => (
                      <div key={kpi.label} className='border border-ct-border rounded-lg px-3 py-2'>
                        <div className='text-[10px] text-ct-text3 uppercase'>{kpi.label}</div>
                        <div className={`text-sm font-bold ${kpi.color || 'text-ct-text'}`}>{kpi.value}</div>
                      </div>
                    ))}
                  </div>

                  {/* Before / After comparison */}
                  <div className='grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs'>
                    <div className='border border-ct-border rounded-lg px-3 py-2'>
                      <div className='text-[10px] text-ct-text3'>Viajes antes</div>
                      <div className='font-bold text-ct-text'>{formatNum(effectiveness.summary.trips_before_window)}</div>
                    </div>
                    <div className='border border-ct-border rounded-lg px-3 py-2'>
                      <div className='text-[10px] text-ct-text3'>Viajes después</div>
                      <div className='font-bold text-ct-text'>{formatNum(effectiveness.summary.trips_after_window)}</div>
                    </div>
                    <div className='border border-ct-border rounded-lg px-3 py-2'>
                      <div className='text-[10px] text-ct-text3'>Días hasta primer viaje</div>
                      <div className='font-bold text-ct-text'>{effectiveness.summary.avg_days_to_first_trip_after ?? '—'}</div>
                    </div>
                  </div>

                  {/* Warnings */}
                  {effectiveness.warnings?.length > 0 && (
                    <div className='bg-amber-50 border border-amber-200 rounded-lg px-4 py-3'>
                      <div className='text-xs font-semibold text-amber-800 mb-1'>Data pendiente de refresco</div>
                      {effectiveness.warnings.map((w, i) => (
                        <div key={i} className='text-[11px] text-amber-700'>{w}</div>
                      ))}
                    </div>
                  )}

                  {/* Segments / Group By */}
                  {effectiveness.segments?.length > 0 && (
                    <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
                      <h3 className='text-sm font-semibold text-ct-text mb-2'>By {groupBy || 'Segment'}</h3>
                      <div className='overflow-x-auto'>
                        <table className='w-full text-[11px]'>
                          <thead><tr className='text-left text-gray-400 border-b'>
                            <th className='py-1 pr-2'>Group</th>
                            <th className='py-1 pr-2 text-right'>Total</th>
                            <th className='py-1 pr-2 text-right'>Contacted</th>
                            <th className='py-1 pr-2 text-right'>Re-activated</th>
                            <th className='py-1 pr-2 text-right'>Rate</th>
                            <th className='py-1 pr-2 text-right'>Trip Δ</th>
                            <th className='py-1 pr-2 text-right'>Avg Days</th>
                          </tr></thead>
                          <tbody>
                            {effectiveness.segments.map((s, i) => (
                              <tr key={i} className='border-b border-gray-50'>
                                <td className='py-1 pr-2 font-medium text-ct-text'>{s.key}</td>
                                <td className='py-1 pr-2 text-right'>{s.total}</td>
                                <td className='py-1 pr-2 text-right text-emerald-600'>{s.contacted_count}</td>
                                <td className='py-1 pr-2 text-right text-green-600'>{s.reactivated_count}</td>
                                <td className='py-1 pr-2 text-right'>{formatPct(s.reactivation_rate)}</td>
                                <td className={`py-1 pr-2 text-right ${s.trip_delta >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>{s.trip_delta >= 0 ? '+' : ''}{s.trip_delta}</td>
                                <td className='py-1 pr-2 text-right'>{s.avg_days_to_first_trip ?? '—'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className='bg-gray-50 rounded-lg p-6 text-center text-xs text-gray-500'>
                  Select a campaign and click Analyze to view effectiveness.
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
