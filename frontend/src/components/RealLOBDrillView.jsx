/**
 * RealLOBDrillView — Vista drill-down jerárquica (Fase 2C+).
 * Timeline mensual/semanal por país (CO, PE); doble click despliega por LOB o por Park.
 * FASE 2D: clave dimensional con buildDrillKey, reset al cambiar dim, AbortController + guard.
 */
import { useState, useEffect, useCallback, useRef, Fragment } from 'react'
import {
  getRealLobDrillPro,
  getRealLobDrillProChildren,
  getRealDrillSummary,
  getRealDrillByLob,
  getRealDrillByPark,
  getRealLobDrillParks,
  getRealLobComparativesWeekly,
  getRealLobComparativesMonthly,
  getPeriodSemantics,
  getRealMarginQuality
} from '../services/api'
import RealLOBDailyView from './RealLOBDailyView'
import { buildDimKey, buildDrillKey } from '../utils/dimKey'
import { getEstadoConfig, getComparativeClass, GRID_BADGE, GRID_ESTADO, COMPARATIVE_LABELS } from '../constants/gridSemantics'
import { formatRealServiceTypeDisplay } from '../constants/realServiceTypeDisplay'
import DataStateBadge from './DataStateBadge'

const USE_DRILL_PRO = true

const MARGIN_TOOLTIP = 'Margen mostrado en positivo (ABS) para lectura de negocio.'

const MESES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
const SEGMENT_OPTIONS = [
  { value: 'Todos', label: 'Todos' },
  { value: 'B2B', label: 'B2B' },
  { value: 'B2C', label: 'B2C' }
]

function formatPeriod (periodStart, periodType) {
  if (!periodStart) return ''
  const s = String(periodStart)
  if (periodType === 'weekly') {
    return s.length >= 10 ? `Semana ${s}` : s
  }
  const [y, m] = s.slice(0, 7).split('-')
  const monthName = MESES[parseInt(m, 10) - 1] || m
  return `${monthName} ${y}`
}

function formatNumber (n) {
  if (n == null || n === '') return '—'
  const num = Number(n)
  if (Number.isNaN(num)) return '—'
  if (num >= 1e6) return (num / 1e6).toFixed(2) + 'M'
  if (num >= 1e3) return (num / 1e3).toFixed(2) + 'K'
  return num.toLocaleString()
}

function formatMargin (n, trips) {
  if (trips === 0 || n == null || Number.isNaN(Number(n))) return '—'
  return Number(n).toFixed(2)
}

function formatDistanceKm (n, trips) {
  if (trips === 0 || n == null || Number.isNaN(Number(n))) return '—'
  return Number(n).toFixed(2)
}

export default function RealLOBDrillView () {
  const [subView, setSubView] = useState('drill') // 'drill' | 'daily'
  const [periodType, setPeriodType] = useState('monthly')
  const [drillBy, setDrillBy] = useState('lob') // 'lob' | 'park' | 'service_type'
  const [segment, setSegment] = useState('Todos')
  const [parkId, setParkId] = useState('') // '' = todos; si hay valor, timeline y desglose tipo_servicio filtrados por park
  const [parks, setParks] = useState([]) // lista para filtro Park (fuente: drill); siempre poblada, independiente del desglose
  const [countries, setCountries] = useState([]) // [{ country, coverage, kpis, rows }]
  const [meta, setMeta] = useState({ last_period_monthly: null, last_period_weekly: null })
  const [periodSemantics, setPeriodSemantics] = useState(null) // GET /ops/period-semantics (no depende del drill)
  const [lobCoverage, setLobCoverage] = useState(null) // { min_trip_date_loaded, max_trip_date_loaded, recent_days_config }
  const [comparative, setComparative] = useState(null) // WoW o MoM payload
  const [comparativeLoading, setComparativeLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expanded, setExpanded] = useState(new Set())
  const [subrows, setSubrows] = useState({}) // key -> { loading, data, error }
  const [marginQualityAffected, setMarginQualityAffected] = useState({ week: new Set(), month: new Set() })

  const abortControllerRef = useRef(null)
  const summaryAbortRef = useRef(null)
  const activeDimKeyRef = useRef('')

  const limitPeriods = periodType === 'monthly' ? 24 : 26

  const getDimObj = useCallback(() => ({
    drillBy,
    periodType,
    segment,
    parkId
  }), [drillBy, periodType, segment, parkId])

  // Parks para filtro de contexto: misma fuente que el drill (real_drill_dim_fact). No depende del tipo de desglose.
  useEffect(() => {
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/7a567dae-1f05-4a4a-89fa-ed1b37ba03a6',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'9075f8'},body:JSON.stringify({sessionId:'9075f8',location:'RealLOBDrillView.jsx:parks',message:'fetch_start',data:{fetch:'drill/parks'},timestamp:Date.now(),hypothesisId:'H3'})}).catch(()=>{})
    // #endregion
    getRealLobDrillParks()
      .then((res) => {
        // #region agent log
        fetch('http://127.0.0.1:7243/ingest/7a567dae-1f05-4a4a-89fa-ed1b37ba03a6',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'9075f8'},body:JSON.stringify({sessionId:'9075f8',location:'RealLOBDrillView.jsx:parks_then',message:'fetch_ok',data:{fetch:'drill/parks'},timestamp:Date.now(),hypothesisId:'H3'})}).catch(()=>{})
        // #endregion
        setParks(res.parks || [])
      })
      .catch(() => {
        // #region agent log
        fetch('http://127.0.0.1:7243/ingest/7a567dae-1f05-4a4a-89fa-ed1b37ba03a6',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'9075f8'},body:JSON.stringify({sessionId:'9075f8',location:'RealLOBDrillView.jsx:parks_catch',message:'fetch_err',data:{fetch:'drill/parks'},timestamp:Date.now(),hypothesisId:'H3'})}).catch(()=>{})
        // #endregion
        setParks([])
      })
  }, [])

  // Semántica temporal: carga independiente del drill para mostrar siempre "última cerrada / actual abierta"
  useEffect(() => {
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/7a567dae-1f05-4a4a-89fa-ed1b37ba03a6',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'9075f8'},body:JSON.stringify({sessionId:'9075f8',location:'RealLOBDrillView.jsx:periodSemantics',message:'fetch_start',data:{fetch:'period-semantics'},timestamp:Date.now(),hypothesisId:'H3'})}).catch(()=>{})
    // #endregion
    getPeriodSemantics()
      .then((data) => {
        fetch('http://127.0.0.1:7243/ingest/7a567dae-1f05-4a4a-89fa-ed1b37ba03a6',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'9075f8'},body:JSON.stringify({sessionId:'9075f8',location:'RealLOBDrillView.jsx:periodSemantics_then',message:'fetch_ok',data:{fetch:'period-semantics'},timestamp:Date.now(),hypothesisId:'H3'})}).catch(()=>{})
        setPeriodSemantics(data)
      })
      .catch(() => {
        fetch('http://127.0.0.1:7243/ingest/7a567dae-1f05-4a4a-89fa-ed1b37ba03a6',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'9075f8'},body:JSON.stringify({sessionId:'9075f8',location:'RealLOBDrillView.jsx:periodSemantics_catch',message:'fetch_err',data:{fetch:'period-semantics'},timestamp:Date.now(),hypothesisId:'H3'})}).catch(()=>{})
        setPeriodSemantics(null)
      })
  }, [])

  // Periodos con cobertura de margen incompleta (para badge en drill)
  useEffect(() => {
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/7a567dae-1f05-4a4a-89fa-ed1b37ba03a6',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'9075f8'},body:JSON.stringify({sessionId:'9075f8',location:'RealLOBDrillView.jsx:marginQuality',message:'fetch_start',data:{fetch:'real-margin-quality'},timestamp:Date.now(),hypothesisId:'H1'})}).catch(()=>{})
    // #endregion
    getRealMarginQuality({ days_recent: 90 })
      .then((data) => {
        fetch('http://127.0.0.1:7243/ingest/7a567dae-1f05-4a4a-89fa-ed1b37ba03a6',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'9075f8'},body:JSON.stringify({sessionId:'9075f8',location:'RealLOBDrillView.jsx:marginQuality_then',message:'fetch_ok',data:{fetch:'real-margin-quality'},timestamp:Date.now(),hypothesisId:'H1'})}).catch(()=>{})
        setMarginQualityAffected({
          week: new Set((data.affected_week_dates || []).map((d) => String(d).slice(0, 10))),
          month: new Set((data.affected_month_dates || []).map((d) => String(d).slice(0, 10)))
        })
      })
      .catch(() => {
        fetch('http://127.0.0.1:7243/ingest/7a567dae-1f05-4a4a-89fa-ed1b37ba03a6',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'9075f8'},body:JSON.stringify({sessionId:'9075f8',location:'RealLOBDrillView.jsx:marginQuality_catch',message:'fetch_err',data:{fetch:'real-margin-quality'},timestamp:Date.now(),hypothesisId:'H1'})}).catch(()=>{})
        setMarginQualityAffected({ week: new Set(), month: new Set() })
      })
  }, [])

  const resetDrillState = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()
    setExpanded(new Set())
    setSubrows({})
  }, [])

  const loadSummary = useCallback(async () => {
    if (summaryAbortRef.current) summaryAbortRef.current.abort()
    const ac = new AbortController()
    summaryAbortRef.current = ac
    setLoading(true)
    setError(null)
    const t0 = Date.now()
    // #region agent log
    fetch('http://127.0.0.1:7243/ingest/7a567dae-1f05-4a4a-89fa-ed1b37ba03a6',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'9075f8'},body:JSON.stringify({sessionId:'9075f8',location:'RealLOBDrillView.jsx:loadSummary',message:'fetch_start',data:{fetch:'drill_pro'},timestamp:Date.now(),hypothesisId:'H2'})}).catch(()=>{})
    // #endregion
    try {
      if (USE_DRILL_PRO) {
        const res = await getRealLobDrillPro({
          period: periodType === 'monthly' ? 'month' : 'week',
          desglose: drillBy === 'lob' ? 'LOB' : drillBy === 'park' ? 'PARK' : 'SERVICE_TYPE',
          segmento: segment === 'Todos' ? 'all' : segment.toLowerCase(),
          park_id: parkId && parkId.trim() ? parkId.trim() : undefined,
          signal: ac.signal
        })
        setCountries(res.countries || [])
        setMeta(res.meta || {})
        setLobCoverage(res.lob_coverage || null)
      } else {
        const summaryRes = await getRealDrillSummary({
          period_type: periodType,
          segment: segment === 'Todos' ? undefined : segment,
          limit_periods: limitPeriods
        })
        setCountries(summaryRes.countries || [])
        setMeta(summaryRes.meta || {})
        setLobCoverage(null)
      }
    } catch (e) {
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/7a567dae-1f05-4a4a-89fa-ed1b37ba03a6',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'9075f8'},body:JSON.stringify({sessionId:'9075f8',location:'RealLOBDrillView.jsx:loadSummary_catch',message:'fetch_err',data:{err:String(e?.message||e),code:e?.code},timestamp:Date.now(),hypothesisId:'H2'})}).catch(()=>{})
      // #endregion
      if (e?.name === 'CanceledError' || e?.name === 'AbortError' || ac.signal.aborted) return
      let msg = 'Error al cargar timeline'
      if (e?.response?.data?.detail) {
        msg = Array.isArray(e.response.data.detail)
          ? e.response.data.detail.map(d => d.msg || JSON.stringify(d)).join(' ')
          : String(e.response.data.detail)
      } else if (e?.code === 'ECONNABORTED') {
        msg = 'La solicitud tardó demasiado (timeout). El drill puede tardar hasta 5 min; si persiste, revisa el backend (p. ej. espacio en disco: docs/MIGRACION_064_DISKFULL_TROUBLESHOOTING.md).'
      } else if (e?.code === 'ECONNREFUSED' || e?.message?.includes('ECONNREFUSED')) {
        msg = 'No se pudo conectar al backend. Comprueba que uvicorn esté en marcha (puerto 8000).'
      } else if (e?.message) {
        msg = e.message
      }
      setError(msg)
      setCountries([])
    } finally {
      // #region agent log
      fetch('http://127.0.0.1:7243/ingest/7a567dae-1f05-4a4a-89fa-ed1b37ba03a6',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'9075f8'},body:JSON.stringify({sessionId:'9075f8',location:'RealLOBDrillView.jsx:loadSummary_finally',message:'fetch_end',data:{durationMs:Date.now()-t0},timestamp:Date.now(),hypothesisId:'H2'})}).catch(()=>{})
      // #endregion
      setLoading(false)
    }
  }, [periodType, segment, limitPeriods, drillBy, parkId])

  useEffect(() => {
    loadSummary()
  }, [loadSummary])

  // Cargar comparativo WoW o MoM cuando está en drill y cambia el tipo de periodo
  useEffect(() => {
    if (subView !== 'drill') return
    setComparativeLoading(true)
    fetch('http://127.0.0.1:7243/ingest/7a567dae-1f05-4a4a-89fa-ed1b37ba03a6',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'9075f8'},body:JSON.stringify({sessionId:'9075f8',location:'RealLOBDrillView.jsx:comparative',message:'fetch_start',data:{fetch:'comparatives'},timestamp:Date.now(),hypothesisId:'H3'})}).catch(()=>{})
    const fetchComparative = periodType === 'weekly' ? getRealLobComparativesWeekly : getRealLobComparativesMonthly
    fetchComparative()
      .then((data) => {
        fetch('http://127.0.0.1:7243/ingest/7a567dae-1f05-4a4a-89fa-ed1b37ba03a6',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'9075f8'},body:JSON.stringify({sessionId:'9075f8',location:'RealLOBDrillView.jsx:comparative_then',message:'fetch_ok',data:{fetch:'comparatives'},timestamp:Date.now(),hypothesisId:'H3'})}).catch(()=>{})
        setComparative(data); setComparativeLoading(false)
      })
      .catch(() => {
        fetch('http://127.0.0.1:7243/ingest/7a567dae-1f05-4a4a-89fa-ed1b37ba03a6',{method:'POST',headers:{'Content-Type':'application/json','X-Debug-Session-Id':'9075f8'},body:JSON.stringify({sessionId:'9075f8',location:'RealLOBDrillView.jsx:comparative_catch',message:'fetch_err',data:{fetch:'comparatives'},timestamp:Date.now(),hypothesisId:'H3'})}).catch(()=>{})
        setComparative(null); setComparativeLoading(false)
      })
  }, [subView, periodType])

  const normalizePeriodStart = (periodStart) => {
    const s = String(periodStart).trim()
    if (periodType === 'monthly' && s.length === 7) return `${s}-01`
    return s
  }

  const subrowKey = useCallback((country, periodStart) => {
    const norm = normalizePeriodStart(periodStart)
    const dimObj = { ...getDimObj(), country: (country || '').trim() }
    return buildDrillKey(dimObj, norm)
  }, [getDimObj])

  const handleDrillByChange = useCallback((newDrillBy) => {
    if (newDrillBy === drillBy) return
    resetDrillState()
    setDrillBy(newDrillBy)
  }, [drillBy, resetDrillState])

  const handlePeriodTypeChange = useCallback((newPeriodType) => {
    if (newPeriodType === periodType) return
    resetDrillState()
    setPeriodType(newPeriodType)
  }, [periodType, resetDrillState])

  const toggleExpand = useCallback(async (country, periodStart) => {
    const key = subrowKey((country || '').trim(), periodStart)
    if (expanded.has(key)) {
      setExpanded((prev) => {
        const next = new Set(prev)
        next.delete(key)
        return next
      })
      return
    }
    setExpanded((prev) => new Set(prev).add(key))
    if (subrows[key]?.data) return
    if (!abortControllerRef.current) {
      abortControllerRef.current = new AbortController()
    }
    const signal = abortControllerRef.current.signal
    const dimKeyAtRequest = buildDimKey(getDimObj())
    activeDimKeyRef.current = dimKeyAtRequest
    setSubrows((prev) => ({ ...prev, [key]: { loading: true, data: null, error: null } }))
    try {
      if (USE_DRILL_PRO) {
        const res = await getRealLobDrillProChildren({
          country: (country || '').trim(),
          period: periodType === 'monthly' ? 'month' : 'week',
          period_start: normalizePeriodStart(periodStart),
          desglose: drillBy === 'lob' ? 'LOB' : drillBy === 'park' ? 'PARK' : 'SERVICE_TYPE',
          segmento: segment === 'Todos' ? 'all' : segment.toLowerCase(),
          park_id: parkId && parkId.trim() ? parkId.trim() : undefined,
          signal
        })
        if (activeDimKeyRef.current === buildDimKey(getDimObj())) {
          setSubrows((prev) => ({
            ...prev,
            [key]: { loading: false, data: res.data || [], error: null }
          }))
        }
      } else {
        const params = {
          period_type: periodType,
          country: (country || '').trim(),
          period_start: normalizePeriodStart(periodStart),
          segment: segment === 'Todos' ? undefined : segment
        }
        const fetcher = drillBy === 'lob' ? getRealDrillByLob : getRealDrillByPark
        const res = await fetcher(params)
        if (activeDimKeyRef.current === buildDimKey(getDimObj())) {
          setSubrows((prev) => ({
            ...prev,
            [key]: { loading: false, data: res.data || [], error: null }
          }))
        }
      }
    } catch (e) {
      if (e?.name === 'AbortError' || e?.code === 'ERR_CANCELED') return
      if (activeDimKeyRef.current === buildDimKey(getDimObj())) {
        let errMsg = e.message || 'Error al cargar desglose'
        if (e?.code === 'ECONNABORTED' || errMsg.toLowerCase().includes('timeout')) {
          errMsg = 'La consulta tardó demasiado. Prueba sin filtrar por park o otro periodo.'
        } else if (e?.response?.status === 500 && parkId) {
          errMsg = 'Error en el servidor al filtrar por park. Prueba sin park o más tarde.'
        }
        setSubrows((prev) => ({
          ...prev,
          [key]: { loading: false, data: null, error: errMsg }
        }))
      }
    }
  }, [expanded, subrows, periodType, drillBy, segment, parkId, subrowKey, getDimObj])

  const now = new Date()
  const currentMonthStart = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
  const currentWeekStart = (() => {
    const d = new Date(now)
    const day = d.getDay()
    const diff = d.getDate() - day + (day === 0 ? -6 : 1)
    d.setDate(diff)
    return d.toISOString().slice(0, 10)
  })()

  const isPeriodOpen = (periodStart) => {
    const s = String(periodStart).slice(0, 10)
    if (periodType === 'monthly') return s.slice(0, 7) === currentMonthStart.slice(0, 7)
    return s === currentWeekStart
  }

  // countries ya viene ordenado PE, CO desde la API

  // ─── Vista diaria: subtab visible al entrar a Real LOB ─────────────────
  if (subView === 'daily') {
    return (
      <div className="bg-white p-6 rounded-lg shadow-md">
        <div className="flex flex-wrap items-center gap-2 mb-4 border-b border-gray-200 pb-4">
          <h3 className="text-lg font-semibold text-gray-800">Real LOB</h3>
          <DataStateBadge state="canonical" />
          <span className="w-px h-6 bg-gray-300" />
          <button
            type="button"
            onClick={() => setSubView('drill')}
            className={`px-3 py-1.5 rounded text-sm font-medium ${subView !== 'daily' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
          >
            Drill (semanal/mensual)
          </button>
          <button
            type="button"
            onClick={() => setSubView('daily')}
            className={`px-3 py-1.5 rounded text-sm font-medium ${subView === 'daily' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
          >
            Vista diaria
          </button>
        </div>
        <RealLOBDailyView />
      </div>
    )
  }

  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      {/* Fila 1: Título + subtabs Drill | Vista diaria (siempre visibles) */}
      <div className="flex flex-wrap items-center gap-2 mb-4 border-b border-gray-200 pb-4">
        <h3 className="text-lg font-semibold text-gray-800">Real LOB</h3>
        <DataStateBadge state="canonical" />
        <span className="w-px h-6 bg-gray-300" />
        <button
          type="button"
          onClick={() => setSubView('drill')}
          className={`px-3 py-1.5 rounded text-sm font-medium ${subView === 'drill' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
        >
          Drill (semanal/mensual)
        </button>
        <button
          type="button"
          onClick={() => setSubView('daily')}
          className={`px-3 py-1.5 rounded text-sm font-medium ${subView === 'daily' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700 hover:bg-gray-300'}`}
        >
          Vista diaria
        </button>
      </div>
      <div className="flex flex-wrap justify-between items-center gap-4 mb-4">
        <span className="text-sm text-gray-600">Drill por país — Periodo:</span>
        <div className="flex flex-wrap gap-2 items-center">
          <span className="text-sm text-gray-500">Periodo:</span>
          <button
            type="button"
            onClick={() => handlePeriodTypeChange('monthly')}
            className={`px-3 py-1.5 rounded text-sm ${periodType === 'monthly' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            Mensual
          </button>
          <button
            type="button"
            onClick={() => handlePeriodTypeChange('weekly')}
            className={`px-3 py-1.5 rounded text-sm ${periodType === 'weekly' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            Semanal
          </button>
          <span className="w-px h-6 bg-gray-300" />
          <span className="text-sm text-gray-500">Desglose:</span>
          <button
            type="button"
            onClick={() => handleDrillByChange('lob')}
            className={`px-3 py-1.5 rounded text-sm ${drillBy === 'lob' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            LOB
          </button>
          <button
            type="button"
            onClick={() => handleDrillByChange('park')}
            className={`px-3 py-1.5 rounded text-sm ${drillBy === 'park' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            Park
          </button>
          <button
            type="button"
            onClick={() => handleDrillByChange('service_type')}
            className={`px-3 py-1.5 rounded text-sm ${drillBy === 'service_type' ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
          >
            Tipo de servicio
          </button>
          <span className="w-px h-6 bg-gray-300" />
          <span className="text-sm text-gray-500">Park:</span>
          <select
            value={parkId}
            onChange={(e) => {
              const v = e.target.value
              resetDrillState()
              setParkId(v)
            }}
            className="border rounded px-2 py-1.5 text-sm min-w-[200px]"
            title="Filtro de contexto por park; el desglose por tipo de servicio respeta este filtro"
          >
            <option value="">Todos</option>
            {parks.map((p) => {
              const id = p.park_id ?? p.id ?? ''
              const label = p.park_label || (() => {
                const name = p.park_name || p.park_id || p.id || '—'
                const city = (p.city && String(p.city).trim() && String(p.city).toLowerCase() !== 'sin_city') ? p.city : ''
                const country = (p.country && String(p.country).trim()) ? p.country : ''
                if (city && country) return `${name} — ${city} — ${country}`
                if (city) return `${name} — ${city}`
                return name
              })()
              return (
                <option key={id} value={id}>
                  {label}
                </option>
              )
            })}
          </select>
          <span className="w-px h-6 bg-gray-300" />
          <span className="text-sm text-gray-500">Segmento:</span>
          <select
            value={segment}
            onChange={(e) => {
              const v = e.target.value
              resetDrillState()
              setSegment(v)
            }}
            className="border rounded px-2 py-1.5 text-sm"
          >
            {SEGMENT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Semántica temporal: siempre visible (fuente: GET /ops/period-semantics, no depende del drill) */}
      <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-lg text-slate-800 text-sm mb-4">
        <div className="font-semibold text-emerald-900 mb-2">Períodos (semántica cerrada / abierta)</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {periodSemantics ? (
            <>
              <div><strong>Última semana cerrada:</strong> <span className="font-mono">{periodSemantics.last_closed_week_label || '—'}</span></div>
              <div><strong>Semana actual (parcial):</strong> <span className="font-mono">{periodSemantics.current_open_week_label || '—'}</span></div>
              <div><strong>Último mes cerrado:</strong> <span className="font-mono">{periodSemantics.last_closed_month_label || '—'}</span></div>
              <div><strong>Mes actual (parcial):</strong> <span className="font-mono">{periodSemantics.current_open_month_label || '—'}</span></div>
            </>
          ) : (
            <span className="text-gray-500">Cargando semántica temporal…</span>
          )}
        </div>
      </div>
      {meta.hint && (
        <div className="p-4 bg-amber-50 border border-amber-200 rounded text-amber-800 text-sm mb-4">
          {meta.hint}
        </div>
      )}

      {lobCoverage && (lobCoverage.min_trip_date_loaded || lobCoverage.max_trip_date_loaded) && (
        <div className="p-3 bg-slate-50 border border-slate-200 rounded text-slate-700 text-sm mb-4">
          <span className="font-medium">Cobertura actual:</span>{' '}
          {lobCoverage.min_trip_date_loaded && lobCoverage.max_trip_date_loaded
            ? `${lobCoverage.min_trip_date_loaded} — ${lobCoverage.max_trip_date_loaded}`
            : lobCoverage.max_trip_date_loaded
              ? `Último día con data: ${lobCoverage.max_trip_date_loaded}`
              : `Desde: ${lobCoverage.min_trip_date_loaded}`}
          {lobCoverage.recent_days_config != null && (
            <span className="ml-2 text-slate-500">(ventana: {lobCoverage.recent_days_config} días)</span>
          )}
        </div>
      )}

      {/* Comparativo WoW / MoM: siempre visible (cargando, error, sin datos o datos) */}
      <div className="mb-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <div className="text-sm font-semibold text-blue-900 mb-2">
          {COMPARATIVE_LABELS.comparativeTitle(periodType)}
        </div>
        {comparativeLoading && !comparative && (
          <p className="text-sm text-blue-700">Cargando comparativo…</p>
        )}
        {comparative?.error && (
          <p className="text-sm text-amber-700">Error: {comparative.error}</p>
        )}
        {!comparativeLoading && comparative && !comparative.error && (!comparative.by_country || comparative.by_country.length === 0) && (
          <p className="text-sm text-gray-600">Sin datos para períodos cerrados (compruebe que real_rollup_day_fact tenga datos).</p>
        )}
        {comparative && !comparative.error && comparative.by_country?.length > 0 && (
          <div className="flex flex-wrap gap-4">
            {comparative.by_country.map(({ country: c, metrics }) => (
              <div key={c} className="flex flex-wrap gap-3 items-baseline">
                <span className="font-medium text-gray-800 uppercase">{c}</span>
                {metrics && metrics.slice(0, 5).map((m) => (
                  <span key={m.metric} className="text-sm text-gray-700" title={`Actual: ${m.value_current ?? '—'} | Anterior: ${m.value_previous ?? '—'} | Δ: ${m.delta_abs ?? '—'}`}>
                    {m.metric}: {m.delta_pct != null ? `${m.delta_pct > 0 ? '↑' : m.delta_pct < 0 ? '↓' : '→'} ${Number(m.delta_pct).toFixed(1)}%` : '—'}
                  </span>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded text-red-800 text-sm mb-4 flex flex-wrap items-center justify-between gap-2">
          <span>{error}</span>
          <button
            type="button"
            onClick={() => { setError(null); loadSummary(); }}
            className="px-3 py-1.5 bg-red-600 text-white text-sm rounded hover:bg-red-700"
          >
            Reintentar
          </button>
        </div>
      )}

      {loading ? (
        <div className="p-6 space-y-3">
          <div className="animate-pulse space-y-3">
            <div className="h-4 bg-gray-200 rounded w-1/3" />
            <div className="h-32 bg-gray-200 rounded" />
          </div>
          <p className="text-sm text-gray-500">
            Cargando drill… Puede tardar hasta 5 minutos. Si tarda más, revisa la consola del backend.
          </p>
        </div>
      ) : (
        <div className="space-y-6">
          {countries.map(({ country: countryCode, coverage: countryCoverage, kpis, rows }) => {
            const country = (countryCode || '').toUpperCase()
            return (
              <section key={country}>
                {/* Cobertura para este país */}
                {countryCoverage && (countryCoverage.last_trip_date || countryCoverage.last_month_with_data || countryCoverage.last_week_with_data) && (
                  <div className="mb-2 p-3 bg-slate-100 rounded border border-slate-200 text-sm">
                    <span className="font-medium text-slate-600">{country}:</span>{' '}
                    último día con data <span className="font-mono">{countryCoverage.last_trip_date || '—'}</span>
                    {periodType === 'monthly' && (<> · último mes <span className="font-mono">{countryCoverage.last_month_with_data || '—'}</span></>)}
                    {periodType === 'weekly' && (<> · última semana <span className="font-mono">{countryCoverage.last_week_with_data || '—'}</span></>)}
                  </div>
                )}
                {/* KPI bar por país: totales de los periodos listados (no del drill expandido) */}
                {kpis && (
                  <div className="grid grid-cols-2 md:grid-cols-5 lg:grid-cols-6 gap-3 mb-3 p-4 bg-slate-50 rounded-lg border border-slate-200">
                    <div className="col-span-full md:col-span-6 text-xs text-slate-500 mb-1" title="Estas métricas corresponden a la suma de todos los periodos de la tabla inferior">
                      Totales (periodos listados)
                    </div>
                    <div>
                      <div className="text-xs text-slate-500">Total viajes</div>
                      <div className="text-lg font-semibold">{formatNumber(kpis.total_trips)}</div>
                    </div>
                    <div title={MARGIN_TOOLTIP}>
                      <div className="text-xs text-slate-500">Margen total</div>
                      <div className="text-lg font-semibold">{kpis.total_trips ? formatMargin(kpis.margin_total_pos, kpis.total_trips) : '—'}</div>
                    </div>
                    <div title={MARGIN_TOOLTIP}>
                      <div className="text-xs text-slate-500">Margen/trip</div>
                      <div className="text-lg font-semibold">{formatMargin(kpis.margin_unit_pos, kpis.total_trips)}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500">Km prom</div>
                      <div className="text-lg font-semibold">{formatDistanceKm(kpis.km_prom, kpis.total_trips)}</div>
                    </div>
                    {segment === 'Todos' && (kpis.b2b_trips != null || kpis.b2b_pct != null) && (
                      <div>
                        <div className="text-xs text-slate-500">Viajes B2B / %B2B</div>
                        <div className="text-lg font-semibold">
                          {formatNumber(kpis.b2b_trips)}
                          {kpis.b2b_pct != null && ` (${Number(kpis.b2b_pct * 100).toFixed(2)}%)`}
                        </div>
                      </div>
                    )}
                    <div>
                      <div className="text-xs text-slate-500">Activos</div>
                      <div className="text-lg font-semibold">{formatNumber(kpis.active_drivers)}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500">Solo cancelan</div>
                      <div className="text-lg font-semibold">{formatNumber(kpis.cancel_only_drivers)}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500">% Solo cancelan</div>
                      <div className="text-lg font-semibold">{kpis.cancel_only_pct != null ? `${Number(kpis.cancel_only_pct).toFixed(2)}%` : '—'}</div>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500">Último periodo</div>
                      <div className="text-sm font-medium">{kpis.last_period || '—'}</div>
                    </div>
                  </div>
                )}
                {rows.length === 0 ? (
                  <div className="p-4 border border-gray-200 rounded-lg bg-gray-50 text-sm text-gray-500">
                    Sin datos para este país en el rango seleccionado.
                  </div>
                ) : (
                <div className="overflow-x-auto border border-gray-200 rounded-lg">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase w-8" />
                        <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Periodo</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Viajes</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase w-20">{COMPARATIVE_LABELS.deltaPctLabel(periodType)}</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Cancel.</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase w-20">{COMPARATIVE_LABELS.deltaPctLabel(periodType)}</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Activos</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Solo cancelan</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">% Solo cancelan</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase" title={MARGIN_TOOLTIP}>Margen total</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase w-20">{COMPARATIVE_LABELS.deltaPctLabel(periodType)}</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase" title={MARGIN_TOOLTIP}>Margen/trip</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase w-20">{COMPARATIVE_LABELS.deltaPctLabel(periodType)}</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase">Km prom</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase w-20">{COMPARATIVE_LABELS.deltaPctLabel(periodType)}</th>
                        <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase">Segmento / B2B</th>
                        <th className="px-3 py-2 text-right text-xs font-medium text-gray-500 uppercase w-16">{COMPARATIVE_LABELS.ppLabel(periodType)}</th>
                        <th className="px-3 py-2 text-center text-xs font-medium text-gray-500 uppercase">Estado</th>
                      </tr>
                    </thead>
                    {/* Subrow headers: Dimensión | Viajes | Margen total | Margen/trip | Km prom | B2B */}
                    <tbody className="bg-white divide-y divide-gray-200">
                      {rows.map((row) => {
                        const rowId = `${(row.country || countryCode || '').trim()}|${normalizePeriodStart(row.period_start)}`
                        const key = subrowKey((row.country || countryCode || '').trim(), row.period_start)
                        const isExp = expanded.has(key)
                        const sr = subrows[key]
                        const open = isPeriodOpen(row.period_start)
                        const b2bRatio =
                          segment === 'Todos' && row.trips > 0 && row.b2b_trips != null
                            ? (100 * row.b2b_trips / row.trips).toFixed(1)
                            : null
                        const marginTotalPos = row.margin_total_pos != null ? row.margin_total_pos : (row.margin_total != null ? Math.abs(row.margin_total) : null)
                        const marginUnit = row.trips > 0 && (row.margin_unit_pos != null || row.margin_unit_avg != null) ? formatMargin(row.margin_unit_pos ?? row.margin_unit_avg, row.trips) : '—'
                        const distanceKm = row.trips > 0 && (row.km_prom != null || row.distance_km_avg != null || row.distance_total_km != null)
                          ? formatDistanceKm(row.km_prom ?? row.distance_km_avg ?? (row.distance_total_km / row.trips), row.trips)
                          : '—'
                        return (
                          <Fragment key={rowId}>
                            <tr
                              onClick={() => toggleExpand((row.country || countryCode || '').trim(), row.period_start)}
                              className="cursor-pointer hover:bg-slate-50 select-none"
                            >
                              <td className="px-3 py-2 text-sm text-gray-500">
                                {sr?.loading ? (
                                  <span className="animate-pulse">…</span>
                                ) : (
                                  <span className="inline-block w-5 text-center">{isExp ? '▼' : '▶'}</span>
                                )}
                              </td>
                              <td className="px-3 py-2 text-sm font-medium text-gray-900">
                                {formatPeriod(row.period_start, periodType)}
                                {row.is_partial_comparison && (
                                  <span className={`ml-1 inline-flex px-1.5 py-0.5 rounded text-xs font-medium ${GRID_ESTADO.PARCIAL.className}`} title={GRID_ESTADO.PARCIAL.title}>{GRID_ESTADO.PARCIAL.label}</span>
                                )}
                                {(() => {
                                  const norm = normalizePeriodStart(row.period_start)
                                  const normStr = String(norm).slice(0, 10)
                                  const set = periodType === 'monthly' ? marginQualityAffected.month : marginQualityAffected.week
                                  if (set.has(normStr)) {
                                    return (
                                      <span className="ml-1 inline-flex px-1.5 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800 border border-amber-300" title="Este periodo tiene viajes completados sin margen en fuente; el margen mostrado puede ser incompleto.">Cobertura incompleta</span>
                                    )
                                  }
                                  return null
                                })()}
                              </td>
                              <td className="px-3 py-2 text-sm text-right">{formatNumber(row.trips)}</td>
                              <td className={`px-3 py-2 text-sm text-right ${getComparativeClass(row.viajes_trend).bg}`}>
                                {row.viajes_delta_pct != null ? (
                                  <span className={getComparativeClass(row.viajes_trend).text}>
                                    {getComparativeClass(row.viajes_trend).arrow} {Number(row.viajes_delta_pct).toFixed(1)}%
                                  </span>
                                ) : '—'}
                              </td>
                              <td className="px-3 py-2 text-sm text-right">{formatNumber(row.cancelaciones ?? 0)}</td>
                              <td className={`px-3 py-2 text-sm text-right ${getComparativeClass(row.cancelaciones_trend).bg}`}>
                                {row.cancelaciones_delta_pct != null ? (
                                  <span className={getComparativeClass(row.cancelaciones_trend).text}>
                                    {getComparativeClass(row.cancelaciones_trend).arrow} {Number(row.cancelaciones_delta_pct).toFixed(1)}%
                                  </span>
                                ) : '—'}
                              </td>
                              <td className="px-3 py-2 text-sm text-right">{formatNumber(row.active_drivers ?? 0)}</td>
                              <td className="px-3 py-2 text-sm text-right">{formatNumber(row.cancel_only_drivers ?? 0)}</td>
                              <td className="px-3 py-2 text-sm text-right">{row.cancel_only_pct != null ? `${Number(row.cancel_only_pct).toFixed(2)}%` : '—'}</td>
                              <td className="px-3 py-2 text-sm text-right">{row.trips ? formatMargin(marginTotalPos, row.trips) : '—'}</td>
                              <td className={`px-3 py-2 text-sm text-right ${getComparativeClass(row.margen_total_trend).bg}`}>
                                {row.margen_total_delta_pct != null ? (
                                  <span className={getComparativeClass(row.margen_total_trend).text}>
                                    {getComparativeClass(row.margen_total_trend).arrow} {Number(row.margen_total_delta_pct).toFixed(1)}%
                                  </span>
                                ) : '—'}
                              </td>
                              <td className="px-3 py-2 text-sm text-right">{marginUnit}</td>
                              <td className={`px-3 py-2 text-sm text-right ${getComparativeClass(row.margen_trip_trend).bg}`}>
                                {row.margen_trip_delta_pct != null ? (
                                  <span className={getComparativeClass(row.margen_trip_trend).text}>
                                    {getComparativeClass(row.margen_trip_trend).arrow} {Number(row.margen_trip_delta_pct).toFixed(1)}%
                                  </span>
                                ) : '—'}
                              </td>
                              <td className="px-3 py-2 text-sm text-right">{distanceKm}</td>
                              <td className={`px-3 py-2 text-sm text-right ${getComparativeClass(row.km_prom_trend).bg}`}>
                                {row.km_prom_delta_pct != null ? (
                                  <span className={getComparativeClass(row.km_prom_trend).text}>
                                    {getComparativeClass(row.km_prom_trend).arrow} {Number(row.km_prom_delta_pct).toFixed(1)}%
                                  </span>
                                ) : '—'}
                              </td>
                              <td className="px-3 py-2 text-sm text-center">
                                {segment !== 'Todos' ? (
                                  <span className={GRID_BADGE.segment}>{segment}</span>
                                ) : b2bRatio != null ? (
                                  <span className={GRID_BADGE.b2b}>B2B {b2bRatio}%</span>
                                ) : (
                                  '—'
                                )}
                              </td>
                              <td className={`px-3 py-2 text-sm text-right ${getComparativeClass(row.pct_b2b_trend).bg}`}>
                                {row.pct_b2b_delta_pp != null ? (
                                  <span className={getComparativeClass(row.pct_b2b_trend).text}>
                                    {getComparativeClass(row.pct_b2b_trend).arrow} {Number(row.pct_b2b_delta_pp).toFixed(1)} pp
                                  </span>
                                ) : '—'}
                              </td>
                              <td className="px-3 py-2 text-sm text-center">
                                {(() => {
                                  const estado = row.estado || (open ? 'ABIERTO' : 'CERRADO')
                                  const expectedDate = row.expected_last_date ? String(row.expected_last_date).slice(0, 10) : null
                                  const faltaDataTitle = expectedDate
                                    ? `Falta data hasta cierre de ayer (${expectedDate})`
                                    : 'Falta data hasta cierre de ayer'
                                  const { className, label, title } = getEstadoConfig(estado, { faltaDataTitle })
                                  return (
                                    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${className}`} title={title || undefined}>
                                      {label}
                                    </span>
                                  )
                                })()}
                              </td>
                            </tr>
                            {isExp && sr && (
                              <>
                                {sr.loading && (
                                  <tr key={`${rowId}-sub-loading`} className="bg-slate-50">
                                    <td colSpan={18} className="px-4 py-3 text-sm text-gray-500">Cargando…</td>
                                  </tr>
                                )}
                                {sr.error && (
                                  <tr key={`${rowId}-sub-err`} className="bg-slate-50">
                                    <td colSpan={18} className="px-4 py-3 text-sm text-red-600">{sr.error}</td>
                                  </tr>
                                )}
                                {sr.data && sr.data.length > 0 && (() => {
                                  const filteredData = sr.data.filter(
                                    (r) => (r.dimension_key || '').toUpperCase() !== 'LOW_VOLUME' && (r.lob_group || '').toUpperCase() !== 'LOW_VOLUME'
                                  )
                                  return filteredData.length > 0 ? filteredData.map((r, i) => {
                                    const subTrips = r.trips ?? 0
                                    const subMarginTotal = r.margin_total_pos ?? (r.margin_total != null ? Math.abs(r.margin_total) : null)
                                    const subMargin = subTrips > 0 && (r.margin_unit_pos != null || r.margin_unit_avg != null || r.margin_total != null)
                                      ? formatMargin(r.margin_unit_pos ?? r.margin_unit_avg ?? (subMarginTotal != null ? subMarginTotal / subTrips : null), subTrips)
                                      : '—'
                                    const subKm = subTrips > 0 && (r.km_prom != null || r.distance_km_avg != null || r.distance_total_km != null)
                                      ? formatDistanceKm(r.km_prom ?? r.distance_km_avg ?? (r.distance_total_km / subTrips), subTrips)
                                      : '—'
                                    const dimLabel = drillBy === 'lob' ? (r.lob_group ?? '—') : drillBy === 'park' ? (r.park_label ?? r.dimension_key ?? r.park_name_resolved ?? r.park_name ?? '—') : formatRealServiceTypeDisplay(r.service_type ?? r.dimension_key) || '—'
                                    return (
                                      <tr key={`${rowId}-drill-${i}`} className="bg-slate-50">
                                        <td className="px-3 py-2" />
                                        <td className="px-3 py-2 text-sm text-gray-900 pl-6">{dimLabel}</td>
                                        <td className="px-3 py-2 text-sm text-right">{formatNumber(r.trips)}</td>
                                        <td className={`px-3 py-2 text-sm text-right ${getComparativeClass(r.viajes_trend).bg}`}>
                                          {r.viajes_delta_pct != null ? <span className={getComparativeClass(r.viajes_trend).text}>{getComparativeClass(r.viajes_trend).arrow} {Number(r.viajes_delta_pct).toFixed(1)}%</span> : '—'}
                                        </td>
                                        <td className="px-3 py-2 text-sm text-right">{formatNumber(r.cancelaciones ?? 0)}</td>
                                        <td className={`px-3 py-2 text-sm text-right ${(getComparativeClass(r.cancelaciones_trend) || getComparativeClass('flat')).bg}`}>
                                          {r.cancelaciones_delta_pct != null ? <span className={(getComparativeClass(r.cancelaciones_trend) || getComparativeClass('flat')).text}>{getComparativeClass(r.cancelaciones_trend)?.arrow ?? ''} {Number(r.cancelaciones_delta_pct).toFixed(1)}%</span> : '—'}
                                        </td>
                                        <td className="px-3 py-2 text-sm text-right">{formatNumber(r.active_drivers ?? 0)}</td>
                                        <td className="px-3 py-2 text-sm text-right">{formatNumber(r.cancel_only_drivers ?? 0)}</td>
                                        <td className="px-3 py-2 text-sm text-right">{r.cancel_only_pct != null ? `${Number(r.cancel_only_pct).toFixed(2)}%` : '—'}</td>
                                        <td className="px-3 py-2 text-sm text-right">{subTrips ? formatMargin(subMarginTotal, subTrips) : '—'}</td>
                                        <td className={`px-3 py-2 text-sm text-right ${getComparativeClass(r.margen_total_trend).bg}`}>
                                          {r.margen_total_delta_pct != null ? <span className={getComparativeClass(r.margen_total_trend).text}>{getComparativeClass(r.margen_total_trend).arrow} {Number(r.margen_total_delta_pct).toFixed(1)}%</span> : '—'}
                                        </td>
                                        <td className="px-3 py-2 text-sm text-right">{subMargin}</td>
                                        <td className={`px-3 py-2 text-sm text-right ${getComparativeClass(r.margen_trip_trend).bg}`}>
                                          {r.margen_trip_delta_pct != null ? <span className={getComparativeClass(r.margen_trip_trend).text}>{getComparativeClass(r.margen_trip_trend).arrow} {Number(r.margen_trip_delta_pct).toFixed(1)}%</span> : '—'}
                                        </td>
                                        <td className="px-3 py-2 text-sm text-right">{subKm}</td>
                                        <td className={`px-3 py-2 text-sm text-right ${getComparativeClass(r.km_prom_trend).bg}`}>
                                          {r.km_prom_delta_pct != null ? <span className={getComparativeClass(r.km_prom_trend).text}>{getComparativeClass(r.km_prom_trend).arrow} {Number(r.km_prom_delta_pct).toFixed(1)}%</span> : '—'}
                                        </td>
                                        <td className="px-3 py-2 text-sm text-center">
                                          {segment === 'Todos' && (r.b2b_trips != null || r.pct_b2b != null) ? (
                                            <span className={GRID_BADGE.b2b}>
                                              B2B {r.pct_b2b != null ? `${(Number(r.pct_b2b) * 100).toFixed(1)}%` : formatNumber(r.b2b_trips)}
                                            </span>
                                          ) : '—'}
                                        </td>
                                        <td className={`px-3 py-2 text-sm text-right ${getComparativeClass(r.pct_b2b_trend).bg}`}>
                                          {r.pct_b2b_delta_pp != null ? <span className={getComparativeClass(r.pct_b2b_trend).text}>{getComparativeClass(r.pct_b2b_trend).arrow} {Number(r.pct_b2b_delta_pp).toFixed(1)} pp</span> : '—'}
                                        </td>
                                        <td className="px-3 py-2 text-sm text-center">—</td>
                                      </tr>
                                    )
                                  }                                  ) : (
                                    <tr key={`${rowId}-sub-empty`} className="bg-slate-50">
                                      <td colSpan={18} className="px-4 py-3 text-sm text-gray-500">Sin datos para este periodo.</td>
                                    </tr>
                                  )
                                })()}
                                {sr.data && sr.data.length === 0 && (
                                  <tr key={`${rowId}-sub-empty`} className="bg-slate-50">
                                    <td colSpan={18} className="px-4 py-3 text-sm text-gray-500">Sin datos para este periodo.</td>
                                  </tr>
                                )}
                              </>
                            )}
                          </Fragment>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
                )}
              </section>
            )
          })}
        </div>
      )}

      <p className="mt-4 text-xs text-gray-500">
        Clic en una fila para desplegar desglose por {drillBy === 'lob' ? 'LOB' : drillBy === 'park' ? 'Park' : 'Tipo de servicio'}.
        Orden: más reciente → más antiguo; subfilas por viajes descendente.
      </p>
    </div>
  )
}
