import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'

const GROUP_LABELS = {
  ready_for_crm: 'Listas para CRM',
  in_execution: 'En ejecución',
  waiting_outcomes: 'Esperando resultados',
  follow_up_needed: 'Seguimiento pendiente',
  waiting_measurement: 'Esperando medición',
  measured: 'Medidas',
  needs_review: 'Necesitan revisión',
}

const GROUP_COLORS = {
  ready_for_crm: 'border-blue-200 bg-blue-50',
  in_execution: 'border-amber-200 bg-amber-50',
  waiting_outcomes: 'border-purple-200 bg-purple-50',
  follow_up_needed: 'border-orange-200 bg-orange-50',
  waiting_measurement: 'border-gray-200 bg-gray-50',
  measured: 'border-emerald-200 bg-emerald-50',
  needs_review: 'border-red-200 bg-red-50',
}

const GROUP_HEADER_COLORS = {
  ready_for_crm: 'text-blue-800',
  in_execution: 'text-amber-800',
  waiting_outcomes: 'text-purple-800',
  follow_up_needed: 'text-orange-800',
  waiting_measurement: 'text-gray-700',
  measured: 'text-emerald-800',
  needs_review: 'text-red-800',
}

export default function CampaignOperatingBoard ({ onSelectCampaign }) {
  const [board, setBoard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showTechnical, setShowTechnical] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/drivers/campaigns/operating-board', { timeout: 20000 })
      setBoard(res.data)
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Error cargando board')
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) return (
    <div className='animate-pulse space-y-3'>
      <div className='h-5 bg-gray-100 rounded w-48' />
      <div className='h-32 bg-gray-50 rounded' />
    </div>
  )

  if (error) return (
    <div className='bg-red-50 border border-red-200 rounded-lg p-4 text-xs text-red-700'>
      {error}
      <button type='button' onClick={load} className='ml-2 underline'>Reintentar</button>
    </div>
  )

  const groups = board?.groups || {}
  const counts = board?.group_counts || {}
  const totalActive = board?.total_active_campaigns || 0

  return (
    <div className='space-y-4'>
      <div className='bg-ct-card border border-ct-border rounded-xl px-5 py-4'>
        <div className='flex items-center justify-between'>
          <div>
            <h2 className='text-lg font-bold text-ct-text'>Campaign Operating Board</h2>
            <p className='text-xs text-ct-text3 mt-1'>
              Campañas agrupadas por etapa del loop operativo. {totalActive} campañas activas.
            </p>
          </div>
          <button type='button' onClick={load}
            className='px-3 py-1.5 rounded bg-ct-accent text-white text-xs font-medium hover:opacity-90'>
            Actualizar
          </button>
        </div>
      </div>

      <div className='grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2'>
        {Object.entries(GROUP_LABELS).map(([key, label]) => (
          <div key={key} className={`rounded-lg border px-3 py-2 ${GROUP_COLORS[key]}`}>
            <div className='text-[10px] text-ct-text3 uppercase truncate'>{label}</div>
            <div className={`text-lg font-bold ${GROUP_HEADER_COLORS[key]}`}>{counts[key] || 0}</div>
          </div>
        ))}
      </div>

      {Object.entries(GROUP_LABELS).map(([key, label]) => {
        const items = groups[key] || []
        if (items.length === 0) return null
        return (
          <div key={key} className={`rounded-lg border p-4 ${GROUP_COLORS[key]}`}>
            <h3 className={`text-sm font-semibold mb-3 ${GROUP_HEADER_COLORS[key]}`}>
              {label} ({items.length})
            </h3>
            <div className='space-y-2'>
              {items.map(c => (
                <div key={c.campaign_id}
                  className='bg-white/80 rounded-lg border border-white/50 px-4 py-3 flex items-center justify-between cursor-pointer hover:shadow-sm transition-shadow'
                  onClick={() => onSelectCampaign?.(c.campaign_id)}>
                  <div className='min-w-0 flex-1'>
                    <div className='text-xs font-medium text-ct-text truncate'>{c.campaign_name || '(Sin nombre)'}</div>
                    <div className='text-[10px] text-ct-text3 mt-0.5'>
                      {c.campaign_type} · {c.target_count} conductores · {c.country || 'Global'}{c.city ? ` / ${c.city}` : ''}
                    </div>
                  </div>
                  <div className='text-right ml-3 flex-shrink-0'>
                    <div className='text-[10px] font-medium text-ct-text2'>{c.next_action?.label}</div>
                    {c.next_action?.urgency === 'high' && (
                      <span className='text-[9px] px-1.5 py-0.5 rounded bg-red-100 text-red-700 font-medium'>Urgente</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )
      })}

      {totalActive === 0 && (
        <div className='py-8 text-center text-xs text-ct-text3'>
          No hay campañas activas. Crea una desde Campaign Builder.
        </div>
      )}

      <div className='text-right'>
        <button type='button' onClick={() => setShowTechnical(!showTechnical)}
          className='text-[10px] text-ct-text3 hover:text-ct-text underline'>
          {showTechnical ? 'Ocultar detalle técnico' : 'Ver detalle técnico'}
        </button>
      </div>
      {showTechnical && (
        <div className='bg-gray-50 border border-gray-200 rounded-lg p-3 text-[10px] text-gray-600'>
          <div>Endpoint: <code>/drivers/campaigns/operating-board</code></div>
          <div>Loop statuses: DETECTED → PRIORITIZED → CAMPAIGN_DRAFT → READY_FOR_CRM → SENT_TO_CRM → IN_EXECUTION → OUTCOMES_RECEIVED → FOLLOW_UP_PENDING → MEASURED → CLOSED</div>
          <div>Total campañas: {totalActive} | Última carga: {new Date().toLocaleTimeString()}</div>
        </div>
      )}
    </div>
  )
}
