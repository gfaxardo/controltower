import { useState, useEffect, useCallback } from 'react'
import { getExclusiveWorklistRows } from '../../../services/api.js'

const UNIVERSE_ORDER = [
  'RECOVERY_RECENT_INACTIVE_HIGH_VALUE',
  'NEW_REACTIVATED_0_14_TO_50',
  'RAMP_UP_15_45_TO_100W',
  'CONSOLIDATION_46_90_TO_100W',
  'ACTIVE_GROWTH_90_PLUS_BAND_UP',
  'RECOVERY_RECENT_INACTIVE_LOW_VALUE',
]

const PAGE_SIZE = 50

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
      setError('Failed to load worklist. Check backend Growth.')
    } finally {
      setLoading(false)
    }
  }, [universeFilter, searchTerm])

  useEffect(() => { fetchRows(0, universeFilter, searchTerm) }, [])

  const handleFilter = (uni) => {
    setUniverseFilter(uni)
    setOffset(0)
    fetchRows(0, uni, searchTerm)
  }

  const handleSearch = (e) => {
    e.preventDefault()
    fetchRows(0, universeFilter, searchTerm)
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1

  const badgeColor = (uni) => {
    if (uni === 'RECOVERY_RECENT_INACTIVE_HIGH_VALUE') return 'bg-red-100 text-red-700'
    if (uni === 'NEW_REACTIVATED_0_14_TO_50') return 'bg-yellow-100 text-yellow-700'
    if (uni?.includes('RAMP')) return 'bg-orange-100 text-orange-700'
    if (uni?.includes('CONSOLIDATION')) return 'bg-blue-100 text-blue-700'
    if (uni?.includes('ACTIVE_GROWTH')) return 'bg-green-100 text-green-700'
    if (uni?.includes('RECOVERY') && uni?.includes('LOW')) return 'bg-gray-100 text-gray-600'
    return 'bg-gray-100 text-gray-700'
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-gray-800">Listas de Trabajo</h2>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center">
        <span className="text-xs text-gray-500 font-medium">Universo:</span>
        <button onClick={() => handleFilter('')} className={`px-2 py-1 rounded text-xs ${!universeFilter ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>All</button>
        {UNIVERSE_ORDER.map(u => (
          <button key={u} onClick={() => handleFilter(u)} className={`px-2 py-1 rounded text-xs truncate max-w-[160px] ${universeFilter === u ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>{u.substring(0,25).replace(/_/g,' ')}</button>
        ))}
        <form onSubmit={handleSearch} className="flex gap-1 ml-auto">
          <input type="text" value={searchTerm} onChange={e => setSearchTerm(e.target.value)} placeholder="Search driver ID..." className="px-2 py-1 border border-gray-300 rounded text-xs w-40" />
          <button type="submit" className="px-2 py-1 bg-blue-600 text-white rounded text-xs">Search</button>
        </form>
      </div>

      {/* Error */}
      {error && <div className="bg-red-50 border border-red-200 rounded p-3 text-xs text-red-700">{error}</div>}

      {/* Loading */}
      {loading && <div className="text-center py-8 text-sm text-gray-400">Loading worklists...</div>}

      {/* Table */}
      {!loading && !error && rows.length === 0 && (
        <div className="text-center py-8 text-sm text-gray-400">No drivers found for the selected filters.</div>
      )}

      {!loading && rows.length > 0 && (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="bg-gray-50 text-gray-500 uppercase tracking-wide">
                  <th className="text-left p-2">Driver</th>
                  <th className="text-left p-2">Universe</th>
                  <th className="text-left p-2">Reason</th>
                  <th className="text-right p-2">Weekly</th>
                  <th className="text-right p-2">30d Trips</th>
                  <th className="text-right p-2">Inact. Days</th>
                  <th className="text-right p-2">Gap</th>
                  <th className="text-center p-2">Action</th>
                  <th className="text-center p-2">CL</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r.driver_profile_id} className="border-t border-gray-100 hover:bg-gray-50">
                    <td className="p-2 font-mono text-xs text-gray-700 max-w-[140px] truncate" title={r.driver_profile_id}>{r.driver_profile_id?.substring(0,16)}...</td>
                    <td className="p-2"><span className={`px-1.5 py-0.5 rounded-full text-xs ${badgeColor(r.assigned_universe_v1)}`}>{(r.assigned_universe_v1||'').substring(0,20).replace(/_/g,' ')}</span></td>
                    <td className="p-2 text-gray-600 max-w-[240px] truncate" title={r.reason_text}>{r.reason_text?.substring(0,60)}{r.reason_text?.length > 60 ? '...' : ''}</td>
                    <td className="p-2 text-right font-mono">{r.weekly_trips ?? '—'}</td>
                    <td className="p-2 text-right font-mono">{r.activation_window_trips ?? '—'}</td>
                    <td className="p-2 text-right font-mono">{r.inactivity_days ?? '—'}</td>
                    <td className="p-2 text-right font-mono font-bold text-red-600">{(r.gap_to_target != null) ? r.gap_to_target : '—'}</td>
                    <td className="p-2 text-center"><span className="px-1.5 py-0.5 rounded text-xs bg-purple-100 text-purple-700">{r.recommended_action_category || '—'}</span></td>
                    <td className="p-2 text-center">{r.export_to_control_loop ? <span className="text-green-500 font-bold">✓</span> : <span className="text-gray-300">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between text-xs text-gray-500 pt-2">
            <span>Showing {offset + 1}-{Math.min(offset + PAGE_SIZE, total)} of {total}</span>
            <div className="flex gap-1">
              <button disabled={offset === 0} onClick={() => fetchRows(Math.max(0, offset - PAGE_SIZE))} className="px-2 py-1 rounded border disabled:opacity-30">Prev</button>
              <span className="px-2 py-1">{currentPage} / {totalPages || 1}</span>
              <button disabled={offset + PAGE_SIZE >= total} onClick={() => fetchRows(offset + PAGE_SIZE)} className="px-2 py-1 rounded border disabled:opacity-30">Next</button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
