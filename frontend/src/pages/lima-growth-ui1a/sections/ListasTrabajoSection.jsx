import { useState, useEffect, useCallback } from 'react'
import { getExclusiveWorklistRows } from '../../../services/api.js'

const UNIVERSE_SHORT = {
  'RECOVERY_RECENT_INACTIVE_HIGH_VALUE': 'Recovery High',
  'NEW_REACTIVATED_0_14_TO_50': 'New / Reactivated',
  'RAMP_UP_15_45_TO_100W': 'Ramp Up',
  'CONSOLIDATION_46_90_TO_100W': 'Consolidation',
  'ACTIVE_GROWTH_90_PLUS_BAND_UP': 'Active Growth',
  'RECOVERY_RECENT_INACTIVE_LOW_VALUE': 'Recovery Low',
  'PROTECTED_ALREADY_MEETING_GOAL': 'Protected',
  'CEMETERY_LONG_CHURNED': 'Cemetery',
}

const UNIVERSE_ORDER = [
  'RECOVERY_RECENT_INACTIVE_HIGH_VALUE',
  'NEW_REACTIVATED_0_14_TO_50',
  'RAMP_UP_15_45_TO_100W',
  'CONSOLIDATION_46_90_TO_100W',
  'ACTIVE_GROWTH_90_PLUS_BAND_UP',
  'RECOVERY_RECENT_INACTIVE_LOW_VALUE',
]

const PAGE_SIZE = 50

function UniverseBadge({ uni }) {
  const colors = {
    'RECOVERY_RECENT_INACTIVE_HIGH_VALUE': 'bg-red-100 text-red-700',
    'NEW_REACTIVATED_0_14_TO_50': 'bg-yellow-100 text-yellow-700',
    'RAMP_UP_15_45_TO_100W': 'bg-orange-100 text-orange-700',
    'CONSOLIDATION_46_90_TO_100W': 'bg-blue-100 text-blue-700',
    'ACTIVE_GROWTH_90_PLUS_BAND_UP': 'bg-green-100 text-green-700',
    'RECOVERY_RECENT_INACTIVE_LOW_VALUE': 'bg-gray-100 text-gray-600',
  }
  return <span className={`px-1.5 py-0.5 rounded-full text-xs font-medium ${colors[uni] || 'bg-gray-100 text-gray-700'}`}>{UNIVERSE_SHORT[uni] || (uni||'').substring(0,18)}</span>
}

export default function ListasTrabajoSection() {
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [universeFilter, setUniverseFilter] = useState('')
  const [searchTerm, setSearchTerm] = useState('')

  const fetchRows = useCallback(async (newOffset = 0, newUniverse = universeFilter, newSearch = searchTerm) => {
    setLoading(true)
    setError(null)
    try {
      const params = { exportable_only: true, limit: PAGE_SIZE, offset: newOffset }
      if (newUniverse) params.assigned_universe_v1 = newUniverse
      if (newSearch) params.search = newSearch
      const result = await getExclusiveWorklistRows(params)
      setRows(result?.rows || [])
      setTotal(result?.total || 0)
      setOffset(newOffset)
    } catch {
      setError('Failed to load worklist.')
    } finally {
      setLoading(false)
    }
  }, [universeFilter, searchTerm])

  useEffect(() => { fetchRows(0, universeFilter, searchTerm) }, [])

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-gray-800">Listas de Trabajo</h2>

      {/* Priority order hint */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3">
        <p className="text-xs text-blue-700 font-semibold mb-1">Orden sugerido de trabajo</p>
        <div className="flex flex-wrap gap-1 text-xs text-blue-600">
          {UNIVERSE_ORDER.map((u, i) => (
            <span key={u}>{i > 0 && <span className="text-blue-300 mx-1">→</span>}{UNIVERSE_SHORT[u]}</span>
          ))}
        </div>
        <p className="text-[10px] text-blue-400 mt-1">Prioriza valor recuperable, ventanas tempranas y conductores cerca de meta.</p>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-xs text-gray-500 font-medium">Filtro:</span>
        <button onClick={() => { setUniverseFilter(''); fetchRows(0, '', searchTerm) }} className={`px-2 py-1 rounded text-xs ${!universeFilter ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'}`}>Todos</button>
        {UNIVERSE_ORDER.map(u => (
          <button key={u} onClick={() => { setUniverseFilter(u); fetchRows(0, u, searchTerm) }} className={`px-2 py-1 rounded text-xs ${universeFilter === u ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600'}`}>{UNIVERSE_SHORT[u]}</button>
        ))}
        <form onSubmit={e => { e.preventDefault(); fetchRows(0, universeFilter, searchTerm) }} className="flex gap-1 ml-auto">
          <input type="text" value={searchTerm} onChange={e => setSearchTerm(e.target.value)} placeholder="Buscar driver ID..." className="px-2 py-1 border border-gray-300 rounded text-xs w-36" />
          <button type="submit" className="px-2 py-1 bg-blue-600 text-white rounded text-xs">Buscar</button>
        </form>
      </div>

      {error && <div className="bg-red-50 border border-red-200 rounded p-3 text-xs text-red-700">{error}</div>}
      {loading && <div className="text-center py-8 text-sm text-gray-400">Cargando listas...</div>}

      {!loading && !error && rows.length === 0 && (
        <div className="text-center py-12 text-sm text-gray-400">No se encontraron conductores con los filtros seleccionados.</div>
      )}

      {!loading && rows.length > 0 && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="bg-gray-50 text-gray-500 uppercase tracking-wide">
                  <th className="text-left p-2">Driver</th>
                  <th className="text-left p-2">Lista</th>
                  <th className="text-left p-2">Por qué está aquí</th>
                  <th className="text-right p-2">Viajes/sem</th>
                  <th className="text-right p-2">30d</th>
                  <th className="text-right p-2">Días inact.</th>
                  <th className="text-right p-2">Falta</th>
                  <th className="text-center p-2">Acción</th>
                  <th className="text-center p-2">CL</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r.driver_profile_id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="p-2 font-mono text-xs text-gray-700 max-w-[130px] truncate" title={r.driver_profile_id}>
                      {(r.driver_profile_id || '').substring(0, 14)}...
                    </td>
                    <td className="p-2"><UniverseBadge uni={r.assigned_universe_v1} /></td>
                    <td className="p-2 text-gray-600 max-w-[280px]">
                      <span title={r.reason_text}>{(r.reason_text || '—').substring(0, 80)}{(r.reason_text || '').length > 80 ? '…' : ''}</span>
                    </td>
                    <td className="p-2 text-right font-mono">{r.weekly_trips ?? '—'}</td>
                    <td className="p-2 text-right font-mono">{r.activation_window_trips ?? '—'}</td>
                    <td className="p-2 text-right font-mono">{r.inactivity_days ?? '—'}</td>
                    <td className="p-2 text-right font-mono font-bold text-red-600">{r.gap_to_target != null ? r.gap_to_target : '—'}</td>
                    <td className="p-2 text-center"><span className="px-1.5 py-0.5 rounded text-xs bg-purple-100 text-purple-700">{UNIVERSE_SHORT_ACTION[r.recommended_action_category] || r.recommended_action_category || '—'}</span></td>
                    <td className="p-2 text-center">{r.export_to_control_loop ? '✓' : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between text-xs text-gray-500 pt-2">
            <span>{offset + 1}–{Math.min(offset + PAGE_SIZE, total)} de {total.toLocaleString()}</span>
            <div className="flex gap-1">
              <button disabled={offset === 0} onClick={() => fetchRows(Math.max(0, offset - PAGE_SIZE))} className="px-2 py-1 rounded border disabled:opacity-30">Anterior</button>
              <span className="px-2 py-1">{currentPage} / {totalPages || 1}</span>
              <button disabled={offset + PAGE_SIZE >= total} onClick={() => fetchRows(offset + PAGE_SIZE)} className="px-2 py-1 rounded border disabled:opacity-30">Siguiente</button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

const UNIVERSE_SHORT_ACTION = {
  'ONBOARDING_PUSH': 'Onboarding',
  'PRODUCTIVITY_RAMP': 'Ramp Up',
  'CONSOLIDATION_PUSH': 'Consolidar',
  'BAND_GROWTH': 'Subir Banda',
  'HIGH_VALUE_RECOVERY': 'Recuperar Alto',
  'LOW_VALUE_RECOVERY': 'Recuperar Bajo',
}
