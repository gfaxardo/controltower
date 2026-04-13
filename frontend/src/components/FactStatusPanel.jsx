/**
 * FactStatusPanel — Vista simple de qué meses están materializados
 * y selector directo para lanzar el backfill.
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { getFactStatus, getBackfillProgress, startBackfill, cancelBackfill } from '../services/api.js'

const POLL_PROG_MS   = 3_000   // progreso (barato, solo lee un dict en mem)
const POLL_STATUS_MS = 20_000  // fact-status (golpea la BD, solo cada 20s)

function ProgressBar ({ value, max, color = 'bg-blue-500', indeterminate = false }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0
  return (
    <div className="h-1.5 w-full rounded-full bg-gray-200 overflow-hidden">
      {indeterminate
        ? <div className="h-full w-1/3 bg-blue-400 rounded-full animate-[slide_1.4s_ease-in-out_infinite]"
            style={{ animation: 'indeterminate 1.4s ease-in-out infinite' }} />
        : <div className={`h-full ${color} transition-all duration-500`} style={{ width: `${pct}%` }} />
      }
    </div>
  )
}

function useElapsed (startedAt) {
  const [secs, setSecs] = useState(0)
  useEffect(() => {
    if (!startedAt) { setSecs(0); return }
    const base = new Date(startedAt).getTime()
    const tick = () => setSecs(Math.floor((Date.now() - base) / 1000))
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [startedAt])
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

// Genera lista de "YYYY-MM" desde 2025-01 hasta mes actual
function allMonths () {
  const list = []
  const end = new Date()
  let y = 2025, m = 1
  while (y < end.getFullYear() || (y === end.getFullYear() && m <= end.getMonth() + 1)) {
    list.push(`${y}-${String(m).padStart(2, '0')}`)
    m++; if (m > 12) { m = 1; y++ }
  }
  return list
}

const MONTH_LABELS = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']

export default function FactStatusPanel ({ onClose }) {
  const [status,   setStatus]   = useState(null)   // /fact-status
  const [prog,     setProg]     = useState(null)   // /backfill-progress
  const [selected, setSelected] = useState(new Set()) // meses seleccionados
  const [withWeek, setWithWeek] = useState(true)
  const [loading,  setLoading]  = useState(false)
  const [err,      setErr]      = useState(null)
  const [lastUpd,  setLastUpd]  = useState(null)
  const abortRef = useRef(null)

  const isRunning = prog?.running === true
  const isDone    = ['done','error','cancelled'].includes(prog?.phase)

  const fetchStatus = useCallback(async () => {
    const ctrl = new AbortController()
    abortRef.current = ctrl
    try {
      const s = await getFactStatus({ signal: ctrl.signal })
      setStatus(s)
      setLastUpd(new Date())
    } catch (e) {
      if (e?.name === 'AbortError' || e?.name === 'CanceledError') return
    }
  }, [])

  const fetchProg = useCallback(async () => {
    try {
      const p = await getBackfillProgress({})
      setProg(p)
    } catch (_) {}
  }, [])

  const fetchAll = useCallback(async () => {
    await Promise.all([fetchStatus(), fetchProg()])
  }, [fetchStatus, fetchProg])

  useEffect(() => {
    fetchAll()

    // Progreso: barato, cada 3s
    const progId = setInterval(async () => {
      await fetchProg()
    }, POLL_PROG_MS)

    // Estado de tablas: consulta la BD, cada 20s
    const statusId = setInterval(fetchStatus, POLL_STATUS_MS)

    return () => {
      clearInterval(progId)
      clearInterval(statusId)
      abortRef.current?.abort()
    }
  }, [fetchAll, fetchStatus, fetchProg])

  // Mapa rápido: "2025-01" → { month: bool, day: bool, week: bool }
  const matMap = {}
  ;(status?.months || []).forEach(r => {
    const k = (r.period || '').slice(0, 7)
    matMap[k] = { month: r.month_trips > 0, day: r.day_trips > 0, week: r.week_trips > 0 }
  })

  const months = allMonths()

  // Agrupados por año para la grilla
  const byYear = {}
  months.forEach(ym => {
    const yr = ym.slice(0, 4)
    if (!byYear[yr]) byYear[yr] = []
    byYear[yr].push(ym)
  })

  const toggleMonth = (ym) => {
    if (isRunning) return
    setSelected(prev => {
      const next = new Set(prev)
      next.has(ym) ? next.delete(ym) : next.add(ym)
      return next
    })
  }

  const selectMissing = () => {
    const missing = months.filter(ym => !matMap[ym]?.day)
    setSelected(new Set(missing))
  }

  const clearSelection = () => setSelected(new Set())

  const handleRun = async () => {
    if (!selected.size || isRunning) return
    const sorted = [...selected].sort()
    setErr(null)
    setLoading(true)
    try {
      await startBackfill({ from_date: sorted[0], to_date: sorted[sorted.length - 1], with_week: withWeek })
      setSelected(new Set())
      await fetchAll()
    } catch (e) {
      setErr(e?.response?.data?.detail || e?.message || 'Error al iniciar')
    } finally {
      setLoading(false)
    }
  }

  const handleCancel = async () => {
    await cancelBackfill()
    setTimeout(fetchAll, 600)
  }

  // Estado del progreso en texto
  const failedCount = prog?.failed_months?.length || 0
  const phaseLabel = (() => {
    const p = prog?.phase
    if (p === 'done' && failedCount > 0) return 'Terminado con errores'
    return {
      materializing_enriched: 'Escaneando viajes del período…',
      inserting_month_fact:   'Insertando month_fact…',
      inserting_chunks:       `Insertando chunk ${prog?.current_chunk_idx}/${prog?.total_chunks}`,
      week_rollup:            'Calculando semanas…',
      done:                   '¡Completado!',
      error:                  'Error',
      cancelled:              'Cancelado',
    }[p] || 'Iniciando…'
  })()

  const phaseDesc = {
    materializing_enriched: 'La fase más larga (~5-7 min por mes). Lee y clasifica millones de viajes.',
    inserting_month_fact:   'Agrupando viajes en month_fact para mantener consistencia con day_fact.',
    inserting_chunks:       prog?.current_chunk_label ? `País / ciudad: ${prog.current_chunk_label}` : '',
    week_rollup:            'Agrupando días en semanas…',
  }[prog?.phase] || ''

  const elapsed = useElapsed(prog?.started_at)

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-lg overflow-hidden text-sm w-full">

      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-slate-800 text-white">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 7v10c0 2 1 3 3 3h10c2 0 3-1 3-3V7M4 7c0-2 1-3 3-3h10c2 0 3 1 3 3M4 7h16" />
          </svg>
          <span className="font-semibold text-[13px]">Materialización FACT tables</span>
          {isRunning && <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />}
        </div>
        {onClose && (
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-white transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      <div className="p-4 space-y-4">

        {/* ── Grilla de meses ──────────────────────────────────────────────── */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">
              Estado por mes
            </span>
            <div className="flex items-center gap-3 text-[10px] text-gray-400">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-emerald-500" />day OK</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-amber-400" />solo month</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-gray-200" />vacío</span>
            </div>
          </div>

          {Object.entries(byYear).map(([yr, yms]) => (
            <div key={yr} className="mb-3">
              <div className="text-[10px] font-bold text-gray-400 mb-1.5">{yr}</div>
              <div className="grid grid-cols-6 gap-1.5">
                {yms.map(ym => {
                  const m   = matMap[ym]
                  const hasDay   = m?.day
                  const hasMonth = m?.month
                  const isSel    = selected.has(ym)
                  const mo = parseInt(ym.slice(5)) - 1

                  const bgColor = isSel
                    ? 'bg-blue-600 text-white border-blue-600'
                    : hasDay
                      ? 'bg-emerald-500 text-white border-emerald-500'
                      : hasMonth
                        ? 'bg-amber-400 text-white border-amber-400'
                        : 'bg-gray-100 text-gray-400 border-gray-200'

                  return (
                    <button
                      key={ym}
                      type="button"
                      onClick={() => toggleMonth(ym)}
                      disabled={isRunning}
                      title={`${ym} — ${hasDay ? 'day_fact ✓' : hasMonth ? 'solo month_fact' : 'sin datos'}`}
                      className={`rounded-md border text-[11px] font-semibold py-1.5 text-center transition-all cursor-pointer
                        disabled:cursor-default ${bgColor}
                        ${!isRunning && !hasDay ? 'hover:border-blue-400 hover:bg-blue-50 hover:text-blue-700' : ''}
                        ${!isRunning && hasDay && !isSel ? 'hover:opacity-80' : ''}
                        ${isSel ? 'ring-2 ring-blue-400 ring-offset-1' : ''}
                      `}
                    >
                      {MONTH_LABELS[mo]}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </div>

        {/* ── Progreso si hay backfill activo ──────────────────────────────── */}
        {(isRunning || (isDone && prog?.phase === 'done')) && (
          <div className={`rounded-lg border px-3 py-3 space-y-2 ${
            prog?.phase === 'done'
              ? (failedCount > 0 ? 'border-red-200 bg-red-50' : 'border-emerald-200 bg-emerald-50')
              : 'border-blue-100 bg-blue-50'
          }`}>
            {/* Fila superior: ícono + label + tiempo */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {isRunning && <span className="w-3 h-3 border-2 border-blue-300 border-t-blue-600 rounded-full animate-spin flex-shrink-0" />}
                {prog?.phase === 'done' && failedCount === 0 && (
                  <svg className="w-4 h-4 text-emerald-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"/>
                  </svg>
                )}
                {prog?.phase === 'done' && failedCount > 0 && (
                  <span className="text-red-600 text-sm flex-shrink-0" aria-hidden>✕</span>
                )}
                <span className={`text-xs font-semibold ${
                  prog?.phase === 'done'
                    ? (failedCount > 0 ? 'text-red-800' : 'text-emerald-700')
                    : 'text-blue-800'
                }`}>
                  {phaseLabel}
                </span>
              </div>
              <span className="text-[11px] font-mono text-gray-500 tabular-nums">{elapsed}</span>
            </div>

            {/* Descripción de la fase actual */}
            {phaseDesc && isRunning && (
              <p className="text-[10px] text-blue-600 pl-5 leading-relaxed">{phaseDesc}</p>
            )}

            {/* Barra global de meses */}
            <div>
              <div className="flex justify-between text-[10px] text-gray-400 mb-0.5">
                <span>Mes {prog?.done_months}/{prog?.total_months}</span>
                <span>{Math.round(((prog?.done_months || 0) / Math.max(prog?.total_months || 1, 1)) * 100)}%</span>
              </div>
              <ProgressBar
                value={prog?.done_months}
                max={prog?.total_months}
                color={prog?.phase === 'done' ? (failedCount > 0 ? 'bg-red-400' : 'bg-emerald-500') : 'bg-slate-600'}
              />
            </div>

            {/* Barra indeterminada mientras escanea o inserta month_fact */}
            {isRunning && (prog?.phase === 'materializing_enriched' || prog?.phase === 'inserting_month_fact') && (
              <div className="overflow-hidden h-1 rounded-full bg-blue-100">
                <div className="h-full bg-blue-400 rounded-full w-1/3"
                  style={{ animation: 'indeterminate-slide 1.6s ease-in-out infinite' }} />
              </div>
            )}

            {/* Barra de chunks cuando ya está insertando */}
            {isRunning && prog?.phase === 'inserting_chunks' && prog?.total_chunks > 0 && (
              <div>
                <div className="flex justify-between text-[10px] text-blue-500 mb-0.5">
                  <span className="font-mono truncate max-w-[70%]">{prog.current_chunk_label || '…'}</span>
                  <span>{prog.current_chunk_idx}/{prog.total_chunks}</span>
                </div>
                <ProgressBar value={prog?.current_chunk_idx} max={prog?.total_chunks} color="bg-blue-400" />
              </div>
            )}

            {prog?.phase === 'done' && failedCount > 0 && prog?.last_month_error && (
              <p className="text-[10px] text-red-700 bg-red-100/80 border border-red-200 rounded px-2 py-1.5 font-mono break-all max-h-28 overflow-y-auto">
                {prog.last_month_error}
              </p>
            )}
            {prog?.phase === 'done' && failedCount > 0 && (prog?.failed_months?.length || 0) > 0 && (
              <p className="text-[10px] text-red-800">
                Meses con fallo: <strong>{(prog.failed_months || []).join(', ')}</strong>
                {' '}(sesión terminada, revisá logs del backend)
              </p>
            )}
            {/* Pie: contadores + cancelar */}
            <div className="flex items-center justify-between text-[10px] text-gray-500 pt-0.5">
              <span>
                {(prog?.day_inserted_total || 0).toLocaleString()} filas day
                {typeof prog?.week_inserted_total === 'number' && prog.week_inserted_total > 0
                  ? ` · ${prog.week_inserted_total.toLocaleString()} week`
                  : ''}
                {' · '}
                {(prog?.completed_months?.length || 0) - (prog?.empty_source_months?.length || 0)} meses con datos
                {(prog?.empty_source_months?.length || 0) > 0 && (
                  <> · {prog.empty_source_months.length} sin viajes (fuente vacía)</>
                )}
                {failedCount > 0 && <> · <span className="text-red-600 font-semibold">{failedCount} fallidos</span></>}
              </span>
              {isRunning && (
                <button type="button" onClick={handleCancel}
                  className="text-red-500 hover:text-red-700 underline">
                  Cancelar
                </button>
              )}
            </div>
          </div>
        )}

        {/* ── Panel de acción ──────────────────────────────────────────────── */}
        {!isRunning && (
          <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-3 space-y-3">
            {/* Accesos rápidos */}
            <div className="flex flex-wrap gap-1.5">
              <button type="button" onClick={selectMissing}
                className="px-2.5 py-1 text-[11px] rounded-full border border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100 transition-colors font-medium">
                Seleccionar sin day_fact
              </button>
              <button type="button"
                onClick={() => setSelected(new Set(months.filter(m => m.startsWith('2026'))))}
                className="px-2.5 py-1 text-[11px] rounded-full border border-gray-200 bg-white text-gray-600 hover:border-gray-400 transition-colors">
                Todo 2026
              </button>
              <button type="button"
                onClick={() => setSelected(new Set(months.filter(m => m.startsWith('2025'))))}
                className="px-2.5 py-1 text-[11px] rounded-full border border-gray-200 bg-white text-gray-600 hover:border-gray-400 transition-colors">
                Todo 2025
              </button>
              {selected.size > 0 && (
                <button type="button" onClick={clearSelection}
                  className="px-2.5 py-1 text-[11px] rounded-full border border-gray-200 text-gray-400 hover:text-gray-600 transition-colors">
                  Limpiar
                </button>
              )}
            </div>

            {/* Checkbox week */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={withWeek} onChange={e => setWithWeek(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
              <span className="text-xs text-gray-600">
                Incluir <code className="text-[11px] bg-gray-200 px-1 rounded">week_fact</code>
              </span>
            </label>

            {err && (
              <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-2 py-1.5">{err}</div>
            )}

            {/* Botón principal */}
            <button type="button" onClick={handleRun}
              disabled={selected.size === 0 || loading}
              className="w-full py-2.5 rounded-lg font-semibold text-sm bg-slate-800 text-white hover:bg-slate-700 transition-colors shadow-sm disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2">
              {loading
                ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />Iniciando…</>
                : selected.size === 0
                  ? 'Seleccioná meses para materializar'
                  : <>
                      <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd"/>
                      </svg>
                      Materializar {selected.size} mes{selected.size !== 1 ? 'es' : ''}
                    </>
              }
            </button>

            {selected.size > 0 && (
              <p className="text-[10px] text-gray-400 text-center">
                {[...selected].sort().join(' · ')}
              </p>
            )}
          </div>
        )}

      </div>
    </div>
  )
}
