/**
 * DriverStrategyView — FASE H3.5
 * Role: Strategy — "¿Qué segmentos, campañas y cohorts funcionan?"
 *
 * Campaign effectiveness, lifecycle trends, behavioral previews,
 * segments by city/fleet/park, recovery opportunities.
 *
 * NO recomendaciones automáticas. "Observed lift."
 */
import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'
import DriverLifecycleSummary from './DriverLifecycleSummary.jsx'
import DriverDataFoundation from './DriverDataFoundation.jsx'

function formatNum (n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('es-ES')
}

function formatPct (n) {
  if (n == null) return '—'
  return (Number(n) * 100).toFixed(1) + '%'
}

export default function DriverStrategyView () {
  const [effSummary, setEffSummary] = useState(null)
  const [campaigns, setCampaigns] = useState([])
  const [loading, setLoading] = useState(true)

  const [error, setError] = useState(null)

  const loadAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [esRes, cRes] = await Promise.all([
        api.get('/drivers/campaigns/effectiveness-summary', { timeout: 15000 }),
        api.get('/drivers/campaigns', { params: { limit: 10 }, timeout: 15000 }),
      ])
      setEffSummary(esRes.data)
      setCampaigns(cRes.data?.campaigns || [])
    } catch (err) {
      setError(err.code === 'ECONNABORTED' ? 'Timeout al cargar datos de estrategia' : (err.message || 'Error al cargar vista estrategia'))
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { loadAll() }, [loadAll])

  return (
    <div className='space-y-4'>
      <div className='bg-ct-card border border-ct-border rounded-xl px-5 py-4'>
        <div className='flex items-baseline gap-2'>
          <h2 className='text-lg font-bold text-ct-text'>Strategy View</h2>
          <span className='text-xs text-ct-text3'>Growth & Analytics</span>
        </div>
        <p className='text-xs text-ct-text3 mt-1'>Analiza efectividad de campañas, tendencias de lifecycle y patrones de comportamiento.</p>
      </div>

      {/* Disclaimer */}
      <div className='bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-[11px] text-amber-800'>
        <strong>Observed lift, not causal.</strong> Los datos muestran correlación, no causalidad. No tomar decisiones de inversión solo con estas métricas.
      </div>

      {error && (
        <div className='border border-red-200 rounded-lg p-3 bg-red-50/50'>
          <div className='flex items-start justify-between gap-2'>
            <div>
              <span className='text-[11px] text-red-700 font-medium'>Error t\u00e9cnico</span>
              <div className='text-[10px] text-red-600 mt-0.5'>{error}</div>
              <div className='text-[10px] text-gray-500 mt-1'>Remediaci\u00f3n: Verificar conectividad con backend y que los endpoints de lifecycle/campaigns est\u00e9n operativos.</div>
            </div>
            <button type='button' onClick={loadAll} className='flex-shrink-0 px-2.5 py-1 text-[10px] font-medium rounded border border-gray-300 bg-white text-gray-600 hover:bg-gray-50'>Reintentar</button>
          </div>
        </div>
      )}

      {loading ? (
        <div className='animate-pulse space-y-2'><div className='h-4 bg-gray-100 rounded w-48' /></div>
      ) : (
        <>
          {/* Effectiveness Overview */}
          {effSummary?.overview && (
            <div className='space-y-2'>
              <h3 className='text-sm font-semibold text-ct-text'>Effectiveness Overview</h3>
              <div className='grid grid-cols-2 sm:grid-cols-4 gap-2'>
                {[
                  { label: 'Campaigns Measured', value: effSummary.overview.campaigns_with_effectiveness },
                  { label: 'With Reactivations', value: effSummary.overview.campaigns_with_reactivations, color: 'text-emerald-700' },
                  { label: 'Total Re-activated', value: effSummary.overview.total_reactivated, color: 'text-green-700' },
                  { label: 'Overall Rate', value: formatPct(effSummary.overview.overall_reactivation_rate), color: 'text-green-700' },
                  { label: 'Trip Delta', value: (effSummary.overview.total_trips_delta >= 0 ? '+' : '') + formatNum(effSummary.overview.total_trips_delta), color: 'text-emerald-700' },
                  { label: 'Avg Days to 1st Trip', value: effSummary.overview.avg_days_to_first_trip || '—' },
                ].map(kpi => (
                  <div key={kpi.label} className='border border-ct-border rounded-lg px-3 py-2 bg-white/40'>
                    <div className='text-[10px] text-ct-text3 uppercase'>{kpi.label}</div>
                    <div className={`text-sm font-bold ${kpi.color || 'text-ct-text'}`}>{kpi.value}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Lifecycle snapshot */}
          <DriverDataFoundation />
          <DriverLifecycleSummary />

          {/* Campaigns overview */}
          <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
            <h3 className='text-sm font-semibold text-ct-text mb-2'>Recent Campaigns ({campaigns.length})</h3>
            {campaigns.length === 0 ? (
              <div className='text-xs text-ct-text3'>No campaigns yet. Create one in Campaign Intelligence.</div>
            ) : (
              <div className='overflow-x-auto'>
                <table className='w-full text-xs'>
                  <thead><tr className='text-left text-gray-400 border-b'><th className='py-1.5 pr-2'>Campaign</th><th className='py-1.5 pr-2'>Type</th><th className='py-1.5 pr-2 text-right'>Members</th><th className='py-1.5 pr-2 text-right'>Phone</th><th className='py-1.5 pr-2'>Status</th><th className='py-1.5 pr-2'>CRM Sync</th></tr></thead>
                  <tbody>
                    {campaigns.map(c => (
                      <tr key={c.campaign_id} className='border-b border-gray-50'>
                        <td className='py-1.5 pr-2 font-medium text-ct-text truncate max-w-[200px]'>{c.campaign_name || '(Sin nombre)'}</td>
                        <td className='py-1.5 pr-2 text-ct-text2'>{c.campaign_type}</td>
                        <td className='py-1.5 pr-2 text-right'>{formatNum(c.target_count)}</td>
                        <td className='py-1.5 pr-2 text-right text-emerald-600'>{formatNum(c.with_phone_count)}</td>
                        <td className='py-1.5 pr-2'>{c.campaign_status}</td>
                        <td className='py-1.5 pr-2'>{c.crm_sync_status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Guidance */}
          <div className='bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-xs text-blue-800'>
            <strong>Next steps:</strong> Open Campaign Effectiveness to drill into specific campaigns. Use Campaign Intelligence to define new cohorts.
          </div>
        </>
      )}
    </div>
  )
}
