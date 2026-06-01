/**
 * BusinessSliceOmniviewMatrix — vista BI premium con Insight & Action Engine.
 */
import { useCallback, useEffect, useMemo, useRef, useState, memo } from 'react'
import {
  getBusinessSliceFilters,
  getBusinessSliceMonthly,
  getBusinessSliceWeekly,
  getBusinessSliceDaily,
  getDataFreshnessGlobal,
  getBusinessSliceCoverageSummary,
  getMatrixOperationalTrust,
  getControlLoopPlanVersions,
  getOmniviewProjection,
  getBusinessSliceRealFreshness,
  getPlanVersions,
  uploadPlanRuta27UI,
  getPlanMappingAudit,
  getServingPlanVersions,
  getOwnershipServingMonthly,
} from '../services/api.js'
import { exportOmniviewFull } from '../utils/omniviewExport.js'
import { centerProjectionViewport, isCurrentPeriodVisible } from '../utils/projectionViewportFocusEngine.js'
import { resolveClosedPeriodAnchor, getAnchorButtonLabel } from '../utils/projectionClosedPeriodEngine.js'
import ProjectionVersionSelector from './projections/ProjectionVersionSelector.jsx'
import {
  buildMatrix,
  computeDeltas as computeDeltasFn,
  computePeriodStates,
  mergePeriodStatesFromMeta,
  computeTemporalVisualTiers,
  periodStateLabel,
  periodElapsedDays,
  periodTotalDays,
  ISO_WEEK_SCOPE_TOOLTIP,
  PERIOD_STATES,
  MATRIX_KPIS,
  fmtValue,
  signalColorForKpi,
  signalArrow,
  fmtDelta,
  loadPersistedState,
  persistState,
  SORT_OPTIONS,
  resolveMainIssueCellTarget,
  findCurrentPeriodIndex,
  getCurrentPeriodKey,
  periodKey,
} from './omniview/omniviewMatrixUtils.js'
import { resolveCurrentPeriodIndex, calculateScrollTarget } from '../utils/currentPeriodFocusEngine.js'
import BusinessSliceOmniviewMatrixTable from './BusinessSliceOmniviewMatrixTable.jsx'
import BusinessSliceOmniviewMatrixHeader, { COL1_W, COL2_W } from './BusinessSliceOmniviewMatrixHeader.jsx'
import { buildProjectionMatrix, PROJECTION_KPIS, fmtAttainment, projectionSignalColor, SIGNAL_DOT } from './omniview/projectionMatrixUtils.js'
import { validateProjectionOmniviewContract, logProjectionYtdPopDebug } from './omniview/projectionContractValidation.js'
import BusinessSliceOmniviewInspector from './BusinessSliceOmniviewInspector.jsx'
import { loadInsightUserPatch, mergeInsightRuntimeConfig } from './omniview/insightUserSettings.js'
import { detectInsights, buildInsightCellMap } from './omniview/insightEngine.js'
import { INSIGHT_CONFIG } from './omniview/insightConfig.js'
import OmniviewPriorityPanel from './OmniviewPriorityPanel.jsx'
import OmniviewProjectionDrill from './OmniviewProjectionDrill.jsx'
import OperationalPriorityLayer from './omniview/priority/OperationalPriorityLayer.jsx'
import OmniviewFreshnessGovernanceCard from './omniview/freshness/OmniviewFreshnessGovernanceCard.jsx'
import BusinessSliceInsightsPanel from './BusinessSliceInsightsPanel.jsx'
import BusinessSliceInsightSettings from './BusinessSliceInsightSettings.jsx'
import MatrixExecutiveBanner from './MatrixExecutiveBanner.jsx'
import FactStatusPanel from './FactStatusPanel.jsx'
import OmniviewDataHelp from './omniview/OmniviewDataHelp.jsx'
import {
  FilterSelect,
  YearSelect,
  MonthSelect,
  normalizeOmniviewYear,
} from './omniview/OmniviewFilterPrimitives.jsx'
import SmartEmptyState from './operational/SmartEmptyState.jsx'
import { OmniviewMatrixSkeleton } from './operational/SkeletonLoader.jsx'
import OperationalStatusBar from './operational/OperationalStatusBar.jsx'
import ActionContext from './operational/ActionContext.jsx'
import OmniviewCommandHeader from './omniview/command/OmniviewCommandHeader.jsx'
import OmniviewMomentumPriorityStrip from './omniview/momentum/OmniviewMomentumPriorityStrip.jsx'
import OwnershipServingView from './ownership/OwnershipServingView.jsx'

const GRAINS = [
  { id: 'monthly', label: 'Mensual' },
  { id: 'weekly', label: 'Semanal' },
  { id: 'daily', label: 'Diario' },
]

const KPI_FOCUS_OPTIONS = [
  { id: 'trips_completed', label: 'Trips', short: 'Viajes' },
  { id: 'revenue_yego_net', label: 'Revenue', short: 'Rev.' },
  { id: 'active_drivers', label: 'Active drivers', short: 'Cond.' },
  { id: 'avg_ticket', label: 'Avg ticket', short: 'Ticket' },
  { id: 'trips_per_driver', label: 'Trips per driver', short: 'TPD' },
]

const btnCls = (active) =>
  `px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
    active ? 'bg-ct-nav text-white shadow-sm' : 'bg-ct-card text-ct-text border border-ct-border hover:border-gray-300 hover:bg-ct-bg'
  }`

const densityCls = (active) =>
  `px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
    active ? 'bg-ct-nav text-white shadow-sm' : 'bg-ct-card text-ct-text2 border border-ct-border hover:border-gray-300 hover:bg-ct-bg'
  }`

const modeCls = (active) =>
  `px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
    active ? 'bg-blue-600 text-white shadow-sm' : 'bg-ct-card text-ct-text2 border border-ct-border hover:border-blue-300 hover:text-blue-600 hover:bg-blue-50'
  }`

const selectCls =
  'uppercase border border-ct-border rounded-md text-sm px-2.5 py-1.5 bg-ct-card focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none text-ct-text tracking-wide'
const miniSelectCls =
  'uppercase border border-ct-border rounded-md text-xs px-2 py-1 bg-ct-card outline-none text-ct-text focus:ring-1 focus:ring-blue-400 tracking-wide'

/** Si true (p. ej. VITE_OMNIVIEW_MATRIX_MANUAL_LOAD en .env.development), no se llama a la API pesada hasta pulsar «Cargar datos». */
const MANUAL_LOAD = import.meta.env.VITE_OMNIVIEW_MATRIX_MANUAL_LOAD === 'true'
/** Tras cargar la matriz: breve pausa antes de coverage-summary (antes 3s; backend devuelve datos en el primer miss con filtros). */
const COVERAGE_FETCH_DELAY_MS = 400

function formatSliceRealLoadedAt (iso) {
  if (!iso || typeof iso !== 'string') return null
  const s = iso.replace('T', ' ').replace(/\.\d+Z?$/, '').replace(/Z$/, '').trim()
  return s.length > 19 ? s.slice(0, 19) : s
}

function toMetricMap (raw) {
  const out = new Map()
  if (!raw || typeof raw !== 'object') return out
  for (const [periodKey, metrics] of Object.entries(raw)) {
    if (!periodKey || !metrics || typeof metrics !== 'object') continue
    out.set(periodKey, metrics)
  }
  return out
}

function filterWeeklyFocus (matrix, grain, weekFocusOnly) {
  if (!weekFocusOnly || grain !== 'weekly' || !matrix?.allPeriods?.length) return matrix
  const currentIdx = findCurrentPeriodIndex(matrix.allPeriods, grain)
  if (currentIdx < 0) return matrix
  const start = Math.max(0, currentIdx - 6)
  const end = Math.min(matrix.allPeriods.length, currentIdx + 7)
  const filteredPeriods = matrix.allPeriods.slice(start, end)
  const filteredTotals = new Map()
  for (const pk of filteredPeriods) {
    if (matrix.totals?.has(pk)) filteredTotals.set(pk, matrix.totals.get(pk))
  }
  const filteredComparisonTotals = matrix.comparisonTotals ? new Map() : undefined
  if (filteredComparisonTotals) {
    for (const pk of filteredPeriods) {
      if (matrix.comparisonTotals.has(pk)) filteredComparisonTotals.set(pk, matrix.comparisonTotals.get(pk))
    }
  }
  const filteredPeriodMeta = matrix.periodMeta ? new Map() : undefined
  if (filteredPeriodMeta) {
    for (const pk of filteredPeriods) {
      if (matrix.periodMeta.has(pk)) filteredPeriodMeta.set(pk, matrix.periodMeta.get(pk))
    }
  }
  return {
    ...matrix,
    allPeriods: filteredPeriods,
    totals: filteredTotals,
    comparisonTotals: filteredComparisonTotals,
    periodMeta: filteredPeriodMeta,
  }
}

/** Extrae un objeto Date desde una period key. Soportes: YYYY-MM-DD, YYYYMMDD, YYYY-MM-DDT*, ISO string, timestamp numérico. Retorna null si no es parseable. */
function parseDateFromPeriodKey (pk) {
  if (!pk || typeof pk !== 'string') return null
  const cleaned = pk.trim()
  // ISO 8601 date-only: YYYY-MM-DD
  if (/^\d{4}-\d{2}-\d{2}$/.test(cleaned)) {
    const [y, m, d] = cleaned.split('-').map(Number)
    const dt = new Date(y, m - 1, d)
    if (!isNaN(dt)) return dt
  }
  // ISO 8601 con hora: YYYY-MM-DDT... o YYYY-MM-DD ...
  if (/^\d{4}-\d{2}-\d{2}[T ]/.test(cleaned)) {
    const dt = new Date(cleaned)
    if (!isNaN(dt)) return dt
  }
  // Compact: YYYYMMDD
  if (/^\d{8}$/.test(cleaned)) {
    const y = Number(cleaned.slice(0, 4))
    const m = Number(cleaned.slice(4, 6))
    const d = Number(cleaned.slice(6, 8))
    const dt = new Date(y, m - 1, d)
    if (!isNaN(dt)) return dt
  }
  return null
}

/** Filtra periodos por día de semana (solo grain=daily). weekdayFocus: 0=DOM, 1=LUN, ..., 6=SÁB, null=todos */
function filterWeekdayFocus (matrix, grain, weekdayFocus) {
  if (weekdayFocus == null || grain !== 'daily' || !matrix?.allPeriods?.length) return matrix
  const filteredPeriods = matrix.allPeriods.filter(pk => {
    const d = parseDateFromPeriodKey(pk)
    if (d == null) return true // keep unknown formats
    return d.getDay() === weekdayFocus
  })
  // DEBUG: log first call this render
  if (typeof window !== 'undefined' && import.meta.env.DEV) {
    const p0 = matrix.allPeriods[0] || ''
    const dp0 = parseDateFromPeriodKey(p0)
    window.__omniviewWeekdayDebug = {
      weekdayFocus,
      totalPeriods: matrix.allPeriods.length,
      filteredCount: filteredPeriods.length,
      firstKey: p0,
      firstKeyDay: dp0 ? ['DOM','LUN','MAR','MIÉ','JUE','VIE','SÁB'][dp0.getDay()] : 'unknown',
    }
  }
  if (filteredPeriods.length === 0) return matrix // never show empty
  const filteredTotals = new Map()
  for (const pk of filteredPeriods) {
    if (matrix.totals?.has(pk)) filteredTotals.set(pk, matrix.totals.get(pk))
  }
  const filteredComparisonTotals = matrix.comparisonTotals ? new Map() : undefined
  if (filteredComparisonTotals) {
    for (const pk of filteredPeriods) {
      if (matrix.comparisonTotals.has(pk)) filteredComparisonTotals.set(pk, matrix.comparisonTotals.get(pk))
    }
  }
  const filteredPeriodMeta = matrix.periodMeta ? new Map() : undefined
  if (filteredPeriodMeta) {
    for (const pk of filteredPeriods) {
      if (matrix.periodMeta.has(pk)) filteredPeriodMeta.set(pk, matrix.periodMeta.get(pk))
    }
  }
  return {
    ...matrix,
    allPeriods: filteredPeriods,
    totals: filteredTotals,
    comparisonTotals: filteredComparisonTotals,
    periodMeta: filteredPeriodMeta,
  }
}

export default function BusinessSliceOmniviewMatrix () {
  const saved = useMemo(() => loadPersistedState(), [])

  const [grain, setGrain] = useState(saved?.grain || 'monthly')
  const [compact, setCompact] = useState(saved?.compact ?? false)
  // FASE 1H.2C — zoom de matriz + focus mode
  const [matrixZoom, setMatrixZoom] = useState(() => {
    try { return Number(localStorage.getItem('ct_matrix_zoom')) || 100 } catch { return 100 }
  })
  const ZOOM_LEVELS = [80, 90, 100, 115, 130]
  const persistZoom = (level) => {
    setMatrixZoom(level)
    try { localStorage.setItem('ct_matrix_zoom', String(level)) } catch {}
  }
  const [focusMode, setFocusMode] = useState(false)
  const [focusTarget, setFocusTarget] = useState(null)
  // FASE 1H.2E — weekly week focus: default ±6 weeks around current
  const [weekFocusOnly, setWeekFocusOnly] = useState(saved?.weekFocusOnly ?? true)
  // FASE 1H.3 — fullscreen de matriz drill
  const [matrixFullscreen, setMatrixFullscreen] = useState(false)
  useEffect(() => {
    if (!focusMode && !matrixFullscreen) return
    const onKey = (e) => {
      if (e.key === 'Escape') {
        if (matrixFullscreen) setMatrixFullscreen(false)
        else if (focusMode) { setFocusMode(false); setFocusTarget(null) }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [focusMode, matrixFullscreen])
  const [insightMode, setInsightMode] = useState(false)
  const [filtersMeta, setFiltersMeta] = useState(null)
  const [country, setCountry] = useState(saved?.country || '')
  const [city, setCity] = useState(saved?.city || '')
  const [businessSlice, setBusinessSlice] = useState(saved?.businessSlice || '')
  const [fleet, setFleet] = useState(saved?.fleet || '')
  const [showSubfleets, setShowSubfleets] = useState(saved?.showSubfleets ?? true)
  const [year, setYear] = useState(() => normalizeOmniviewYear(saved?.year ?? new Date().getFullYear()))
  const [month, setMonth] = useState(saved?.month || '')
  const [sortKey, setSortKey] = useState(saved?.sortKey || 'alpha')
  const [focusedKpi, setFocusedKpi] = useState(saved?.focusedKpi || 'trips_completed')
  const [insightUserPatch, setInsightUserPatch] = useState(() => loadInsightUserPatch() ?? {})
  const [insightSettingsOpen, setInsightSettingsOpen] = useState(false)
  const [factStatusOpen, setFactStatusOpen] = useState(false)
  const prevInsightMode = useRef(insightMode)
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)
  const [selectedCell, setSelectedCell] = useState(null)
  const [selection, setSelection] = useState(null)
  const [selectionHistory, setSelectionHistory] = useState([])

  // Escape key closes inspector/drill globally
  useEffect(() => {
    if (!selection) return
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setSelection(null)
        setSelectedCell(null)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selection])

  const [viewMode, setViewMode] = useState(saved?.viewMode || 'evolucion')
  const [operationalMode, setOperationalMode] = useState('operational')
  const [perspective, setPerspective] = useState('operational') // FASE 1.1 — Perspective Engine
  const [ownershipRows, setOwnershipRows] = useState([])
  const [ownershipByOwner, setOwnershipByOwner] = useState([])
  const [ownershipLoading, setOwnershipLoading] = useState(false)
  const [ownershipError, setOwnershipError] = useState(null)
  const ownershipRequestIdRef = useRef(0)
  const [weekdayFocus, setWeekdayFocus] = useState(null) // null=todos, 0=DOM, 1=LUN, ..., 6=SÁB
  const [planVersion, setPlanVersion] = useState(saved?.planVersion || '')
  const [planVersions, setPlanVersions] = useState([])
  const [servingVersions, setServingVersions] = useState([])
  const servingVersionKeys = useMemo(() => new Set(servingVersions.map((v) => v.plan_version)), [servingVersions])
  const [projectionRows, setProjectionRows] = useState([])
  const [projectionMeta, setProjectionMeta] = useState(null)
  const [projectionResolvedKey, setProjectionResolvedKey] = useState(null)
  const projectionRequestIdRef = useRef(0)
  /** Contrato meta.ytd_summary + filas.period_over_period (anti-regresión). */
  const [projectionContractReport, setProjectionContractReport] = useState(() => ({ ok: true, issues: [] }))

  const [uploadModalOpen, setUploadModalOpen] = useState(false)
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [uploadSuccess, setUploadSuccess] = useState(null)
  const uploadInputRef = useRef(null)

  const isProjectionMode = viewMode === 'proyeccion'

  const needsCountry = (grain === 'weekly' || grain === 'daily') && !isProjectionMode
  const blockedByCountry = needsCountry && !country
  useEffect(() => {
    persistState({ grain, compact, country, city, businessSlice, fleet, showSubfleets, year, month, sortKey, focusedKpi, viewMode, planVersion, weekFocusOnly })
  }, [grain, compact, country, city, businessSlice, fleet, showSubfleets, year, month, sortKey, focusedKpi, viewMode, planVersion, weekFocusOnly])

  const loadPlanVersions = useCallback((autoSelect = false) => {
    Promise.allSettled([
      getPlanVersions(),
      getControlLoopPlanVersions(),
      getServingPlanVersions(),
    ]).then(([r1, r2, r3]) => {
      // Normalizar a { key, label, display_name, ... }
      const normalize = (item) => {
        if (typeof item === 'string') return { key: item, label: item, display_name: item }
        if (item?.plan_version_key) {
          return { key: item.plan_version_key, label: item.display_name || item.plan_version_key, ...item }
        }
        if (item?.plan_version) {
          return { key: item.plan_version, label: item.plan_version, display_name: item.plan_version }
        }
        return null
      }
      const fromPlan = r1.status === 'fulfilled'
        ? (Array.isArray(r1.value) ? r1.value.map(normalize).filter(Boolean) : [])
        : []
      const fromCL = r2.status === 'fulfilled'
        ? (Array.isArray(r2.value) ? r2.value : (r2.value?.data || r2.value?.versions || []))
            .map(normalize).filter(Boolean)
        : []

      const servingList = r3.status === 'fulfilled'
        ? (Array.isArray(r3.value?.versions) ? r3.value.versions : [])
        : []
      setServingVersions(servingList)
      const servingKeys = new Set(servingList.map((v) => v.plan_version))

      // Merge por key unica
      const seen = new Set()
      const merged = []
      for (const v of [...fromPlan, ...fromCL]) {
        if (seen.has(v.key)) continue
        seen.add(v.key)
        v.hasServingFact = servingKeys.has(v.key)
        merged.push(v)
      }
      for (const sv of servingList) {
        if (seen.has(sv.plan_version)) continue
        seen.add(sv.plan_version)
        merged.push({
          key: sv.plan_version, label: sv.plan_version, display_name: sv.plan_version,
          hasServingFact: true, fact_generated_at: sv.fact_generated_at, fact_row_count: sv.row_count,
        })
      }

      setPlanVersions(merged)
      let selectedVersion = planVersion
      if (autoSelect || !selectedVersion) {
        const materialized = merged.find((v) => v.hasServingFact)
        selectedVersion = materialized ? materialized.key : (merged.length > 0 ? merged[0].key : '')
      } else if (servingKeys.size > 0 && !servingKeys.has(selectedVersion)) {
        const materialized = merged.find((v) => v.hasServingFact)
        if (materialized) selectedVersion = materialized.key
      }
      if (selectedVersion) setPlanVersion(selectedVersion)
      setPlanVersions(merged)
      if ((autoSelect || !planVersion) && merged.length > 0) {
        setPlanVersion(merged[0].key)
      }
    })
  }, [planVersion]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (isProjectionMode) {
      loadPlanVersions()
    }
  }, [isProjectionMode]) // eslint-disable-line react-hooks/exhaustive-deps

  // ── FASE 1.1: Ownership Perspective data load ──────────────────────────
  useEffect(() => {
    if (perspective !== 'ownership') {
      setOwnershipRows([])
      setOwnershipByOwner([])
      setOwnershipError(null)
      return
    }
    if (!planVersion) return

    let cancelled = false
    const reqId = ++ownershipRequestIdRef.current

    setOwnershipLoading(true)
    setOwnershipError(null)

    getOwnershipServingMonthly({ plan_version_key: planVersion, limit: 5000 })
      .then((data) => {
        if (cancelled || reqId !== ownershipRequestIdRef.current) return
        setOwnershipRows(data?.rows || [])
        setOwnershipByOwner(data?.by_owner || [])
        setOwnershipLoading(false)
      })
      .catch((err) => {
        if (cancelled || reqId !== ownershipRequestIdRef.current) return
        console.error('Ownership load failed:', err)
        setOwnershipError(err?.response?.data?.detail || err?.message || 'Error desconocido')
        setOwnershipLoading(false)
      })

    return () => { cancelled = true }
  }, [perspective, planVersion])

  const [freshnessInfo, setFreshnessInfo] = useState(null)
  const [sliceMaxTripDate, setSliceMaxTripDate] = useState(null)
  const [sliceRealFreshness, setSliceRealFreshness] = useState(null)
  const [coverageSummary, setCoverageSummary] = useState(null)
  const [matrixMeta, setMatrixMeta] = useState(null)
  const [matrixTrust, setMatrixTrust] = useState(null)
  /** En modo manual, false hasta que el usuario pulse «Cargar datos» (evita consultas pesadas al montar la vista). */
  const [heavyQueriesEnabled, setHeavyQueriesEnabled] = useState(!MANUAL_LOAD)

  const timerRef = useRef(null)
  const effectiveMonth = grain === 'weekly' ? '' : month
  const filterRef = useRef({ grain, country, city, businessSlice, fleet, showSubfleets, year, effectiveMonth, blockedByCountry, isProjectionMode, planVersion })
  filterRef.current = { grain, country, city, businessSlice, fleet, showSubfleets, year, effectiveMonth, blockedByCountry, isProjectionMode, planVersion }

  /**
   * Mapa de tareas activas: { taskKey: 'Etiqueta visible' }.
   * Una tarea aparece mientras su request está en vuelo; desaparece al completarse o cancelarse.
   */
  const [loadingTasks, setLoadingTasks] = useState({})
  const activeTasks = Object.values(loadingTasks).filter(Boolean)
  const projectionRequestKey = useMemo(
    () => JSON.stringify({ grain, country, city, businessSlice, year, month: effectiveMonth, planVersion }),
    [grain, country, city, businessSlice, year, effectiveMonth, planVersion]
  )
  const projectionPending =
    heavyQueriesEnabled &&
    isProjectionMode &&
    !blockedByCountry &&
    !!planVersion &&
    projectionResolvedKey !== projectionRequestKey
  const projectionReady = !loading && !projectionPending
  const projectionIntegrityBroken = projectionMeta?.integrity_status?.status === 'broken'

  const trustAbortRef = useRef(null)
  const freshnessAbortRef = useRef(null)
  const filtersAbortRef = useRef(null)
  const trustStartDelayRef = useRef(null)
  const freshnessDelayRef = useRef(null)

  useEffect(() => {
    const ctrl = new AbortController()
    filtersAbortRef.current = ctrl
    getBusinessSliceFilters({ signal: ctrl.signal })
      .then(setFiltersMeta)
      .catch(() => {})
    return () => ctrl.abort('unmount')
  }, [])

  /** Retraso antes de trust/frescura para que /monthly tome pool y CPU primero (evita el “colgado” al abrir con todo en paralelo). */
  const SECONDARY_TRUST_DELAY_MS = 1500
  const SECONDARY_FRESHNESS_DELAY_MS = 2800

  const trustPollRef = useRef(null)
  useEffect(() => {
    if (!heavyQueriesEnabled) return
    let cancelled = false
    const ctrl = new AbortController()
    trustAbortRef.current = ctrl

    const fetchTrust = () => {
      setLoadingTasks((t) => ({ ...t, trust: 'Trust operativo' }))
      getMatrixOperationalTrust({ signal: ctrl.signal })
        .then((data) => {
          if (cancelled) return
          setMatrixTrust(data)
          // Si el backend todavía está computando, reintentamos en 5s
          if (data?.trust_status === 'loading') {
            trustPollRef.current = setTimeout(fetchTrust, 5000)
          } else {
            setLoadingTasks((t) => { const n = { ...t }; delete n.trust; return n })
          }
        })
        .catch((e) => {
          if (cancelled) return
          if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError' || e?.name === 'AbortError') return
          setMatrixTrust({
            trust_status: 'warning',
            message: 'No se pudo cargar el estado de confianza de la Matrix',
            operational_trust: { status: 'warning', message: 'Error de red' },
            operational_decision: {
              decision_mode: 'CAUTION',
              confidence: { score: 0, coverage: 0, freshness: 0, consistency: 0 },
            },
            trust_recommendations: [],
            trust_history_recent: [],
            global_insights_blocked: false,
            affected_period_keys: { monthly: [], weekly: [], daily: [] },
            executive: {
              status: 'WARNING',
              impact_pct: 0,
              priority_score: 0,
              main_issue: null,
              action: 'Error de red al cargar Data Trust.',
            },
          })
          setLoadingTasks((t) => { const n = { ...t }; delete n.trust; return n })
        })
    }

    trustStartDelayRef.current = setTimeout(() => {
      if (!cancelled) fetchTrust()
    }, SECONDARY_TRUST_DELAY_MS)

    return () => {
      cancelled = true
      clearTimeout(trustStartDelayRef.current)
      ctrl.abort('unmount')
      clearTimeout(trustPollRef.current)
    }
  }, [heavyQueriesEnabled])

  useEffect(() => {
    if (!heavyQueriesEnabled) return
    const ctrl = new AbortController()
    freshnessAbortRef.current = ctrl
    freshnessDelayRef.current = setTimeout(() => {
      setLoadingTasks((t) => ({ ...t, freshness: 'Frescura de datos' }))
      getDataFreshnessGlobal({ group: 'operational' }, { signal: ctrl.signal })
        .then(setFreshnessInfo)
        .catch(() => {})
        .finally(() => setLoadingTasks((t) => { const n = { ...t }; delete n.freshness; return n }))
    }, SECONDARY_FRESHNESS_DELAY_MS)
    return () => {
      clearTimeout(freshnessDelayRef.current)
      ctrl.abort('unmount')
    }
  }, [heavyQueriesEnabled])

  useEffect(() => {
    if (!heavyQueriesEnabled) {
      setSliceRealFreshness(null)
      return
    }
    if (grain !== 'weekly' && grain !== 'daily') {
      setSliceRealFreshness(null)
      return
    }
    const ctrl = new AbortController()
    getBusinessSliceRealFreshness({ signal: ctrl.signal })
      .then(setSliceRealFreshness)
      .catch(() => setSliceRealFreshness(null))
    return () => ctrl.abort('unmount')
  }, [heavyQueriesEnabled, grain])

  const sliceRealFreshnessBanner = useMemo(() => {
    if (!heavyQueriesEnabled || (grain !== 'weekly' && grain !== 'daily') || !sliceRealFreshness) return null
    const st = sliceRealFreshness.status || sliceRealFreshness.overall_status || 'unknown'
    const up = sliceRealFreshness.upstream || {}
    const aggDate = sliceRealFreshness.aggregated?.day_fact?.max_trip_date || sliceRealFreshness.day_fact?.max_trip_date
    const loaded =
      formatSliceRealLoadedAt(sliceRealFreshness.last_refresh_at) ||
      formatSliceRealLoadedAt(sliceRealFreshness.aggregated?.day_fact?.max_loaded_at) ||
      formatSliceRealLoadedAt(sliceRealFreshness.day_fact?.max_loaded_at)
    const border =
      st === 'critical' ? 'border-red-200 bg-red-50 text-red-900'
        : st === 'stale' ? 'border-amber-200 bg-amber-50 text-amber-900'
          : st === 'empty' || st === 'unknown' ? 'border-ct-border bg-ct-surface text-ct-text'
            : 'border-emerald-200 bg-emerald-50 text-emerald-900'
    const emoji = st === 'critical' ? '🔴' : st === 'stale' ? '🟡' : st === 'fresh' ? '🟢' : '🟡'
    let mainLine = ''
    if (st === 'fresh') {
      mainLine = `Datos actualizados hasta: ${aggDate || '—'}${loaded ? ` · ${loaded}` : ''}`
    } else if (st === 'stale') {
      mainLine = `Datos con retraso (última actualización: ${loaded || aggDate || '—'})`
    } else if (st === 'critical') {
      mainLine = 'Datos desactualizados — posible problema de carga'
    } else {
      mainLine = `Estado REAL: ${st}${aggDate ? ` · agregado hasta ${aggDate}` : ''}`
    }
    return (
      <div
        className={`mt-2 rounded-lg border px-3 py-2 text-xs ${border}`}
        role="status"
      >
        <span className="mr-1" aria-hidden>{emoji}</span>
        <span className="font-medium">{mainLine}</span>
        {sliceRealFreshness.lag_days != null && sliceRealFreshness.lag_days > 0 && (
          <span className="ml-1">· lag {sliceRealFreshness.lag_days} día(s)</span>
        )}
        {up.status && up.status !== 'fresh' && (
          <span className="block mt-1 text-ct-text">
            Fuente viajes ({up.source || 'upstream'}): {up.status}
            {up.max_event_date ? ` · max ${up.max_event_date}` : ''}
            {up.error ? ` · ${up.error}` : ''}
          </span>
        )}
      </div>
    )
  }, [heavyQueriesEnabled, grain, sliceRealFreshness])

  const countries = filtersMeta?.countries || []
  const allCities = filtersMeta?.cities || []
  const slices = filtersMeta?.business_slices || []
  const fleets = filtersMeta?.fleets || []

  const cityCountryRef = useRef(new Map())
  useEffect(() => {
    for (const r of rows) {
      if (r.country && r.city) cityCountryRef.current.set(r.city.toLowerCase(), r.country.toLowerCase())
    }
  }, [rows])

  const citiesForCountry = useMemo(() => {
    if (!country) return allCities
    const lc = country.toLowerCase()
    return allCities.filter((c) => { const m = cityCountryRef.current.get(c.toLowerCase()); return !m || m === lc })
  }, [allCities, country])

  useEffect(() => {
    if (country && city) {
      const m = cityCountryRef.current.get(city.toLowerCase())
      if (m && m !== country.toLowerCase()) setCity('')
    }
  }, [country]) // eslint-disable-line react-hooks/exhaustive-deps

  const abortRef = useRef(null)
  const debounceRef = useRef(null)
  /** Evita tratar el primer render con consultas activas como «recién habilitado» (solo transición manual false→true). */
  const wasHeavyEnabledRef = useRef(heavyQueriesEnabled)

  const doLoadProjection = useCallback(async (signal) => {
    const requestKey = JSON.stringify({ grain, country, city, businessSlice, year, month: effectiveMonth, planVersion })
    // Guardrail: semanal/diario requiere país para evitar scope ilimitado
    // (sin país → O(todas_tajadas × semanas × KPIs × SQL) → cuelgue)
    if (blockedByCountry) {
      setProjectionRows([])
      setProjectionMeta(null)
      setProjectionContractReport({ ok: true, issues: [] })
      setErr(null)
      setLoading(false)
      return
    }
    if (!planVersion) {
      setProjectionRows([])
      setProjectionMeta(null)
      setProjectionContractReport({ ok: true, issues: [] })
      setErr(null)
      setLoading(false)
      return
    }
    // Request race protection: discard stale responses
    const thisRequestId = ++projectionRequestIdRef.current
    setLoading(true); setErr(null)
    setLoadingTasks((t) => ({ ...t, matrix: 'Proyección vs Real' }))
    try {
      const params = { plan_version: planVersion, grain }
      if (country) params.country = country
      if (city) params.city = city
      if (businessSlice) params.business_slice = businessSlice
      if (year != null && year !== '') params.year = Number(year)
      if (effectiveMonth) params.month = Number(effectiveMonth)
      const res = await getOmniviewProjection(params, { signal })
      // Discard if a newer request was fired
      if (projectionRequestIdRef.current !== thisRequestId) return
      let data = Array.isArray(res?.data) ? res.data : []
      const pwrRows = res?.meta?.plan_without_real?.rows
      if (
        data.length === 0 &&
        Array.isArray(pwrRows) &&
        pwrRows.length > 0
      ) {
        if (import.meta.env.DEV) {
          console.warn('[omniview projection] data vacío; usando meta.plan_without_real.rows como fallback')
        }
        data = [...pwrRows]
      }
      if (import.meta.env.DEV) {
        const resCountries = [...new Set(data.map(r => r.country).filter(Boolean))]
        const debugOn = typeof window !== 'undefined' && window.location?.search?.includes('debugOmniview=1')
        const peRows = data.filter(r => r.country === 'peru').length
        const coRows = data.filter(r => r.country === 'colombia').length
        console.log('[omniview projection] loaded', {
          requestCountry: country || '(all)',
          responseRows: data.length,
          responseCountries: resCountries,
          peruRows: peRows,
          colombiaRows: coRows,
          grain,
          requestKey,
        })
        if (debugOn) {
          console.group('%c[PIPELINE 1/4] doLoadProjection — request & response', 'color:#6366f1;font-weight:bold')
          console.table({
            selectedCountry: country || '(empty = ALL)',
            blockedByCountry,
            needsCountry,
            grain,
            isProjectionMode,
          })
          console.log('request params:', params)
          console.log('response:', { rows: data.length, countries: resCountries, peru: peRows, colombia: coRows, served_from: res?.meta?.served_from })
          console.groupEnd()
        }
      }
      setProjectionRows(data)
      const pm = { ...(res?.meta ?? {}) }
      if (res?.data_freshness) pm.data_freshness = res.data_freshness
      if (res?.kpi_freshness) pm.kpi_freshness = res.kpi_freshness
      setProjectionMeta(pm)
      setProjectionResolvedKey(requestKey)
      const contract = validateProjectionOmniviewContract(pm, data)
      setProjectionContractReport(contract)
      if (!contract.ok) {
        console.error('[omniview projection] contrato incompleto', contract.issues, {
          filtros: { country, city, businessSlice, grain, year, month: effectiveMonth, planVersion },
        })
      }
      logProjectionYtdPopDebug(pm, data)
      if (pm.integrity_status) {
        if (import.meta.env.DEV) {
          console.log('[projection integrity]', pm.integrity_status)
          if (Array.isArray(pm.integrity_status.issues) && pm.integrity_status.issues.length > 0) {
            console.log('[projection integrity] issues:', pm.integrity_status.issues)
          }
        }
      }
    } catch (e) {
      if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError' || e?.name === 'AbortError') return
      const detail = e?.response?.data?.detail
      setErr((typeof detail === 'string' ? detail : detail?.message) || e.message || 'Error cargando proyección')
      setProjectionRows([])
      setProjectionMeta(null)
      setProjectionContractReport({ ok: true, issues: [] })
      setProjectionResolvedKey(requestKey)
    } finally {
      setLoading(false)
      setLoadingTasks((t) => { const n = { ...t }; delete n.matrix; return n })
    }
  }, [grain, country, city, businessSlice, year, effectiveMonth, planVersion, blockedByCountry])

  // doLoad: ejecuta la carga real de la matriz + lanza coverage-summary DESPUÉS (con retraso).
  const doLoad = useCallback(async (signal) => {
    if (isProjectionMode) {
      return doLoadProjection(signal)
    }
    if (blockedByCountry) {
      setRows([])
      setMatrixMeta(null)
      setSliceMaxTripDate(null)
      setErr(null)
      return
    }
    setLoading(true); setErr(null)
    setLoadingTasks((t) => ({ ...t, matrix: 'Matriz de datos' }))
    try {
      const params = {}
      if (country) params.country = country
      if (city) params.city = city
      if (businessSlice) params.business_slice = businessSlice
      if (year != null && year !== '') params.year = Number(year)
      if (effectiveMonth) params.month = Number(effectiveMonth)
      if (grain === 'monthly' && fleet) params.fleet = fleet
      let res
      if (grain === 'weekly') res = await getBusinessSliceWeekly(params, { signal })
      else if (grain === 'daily') res = await getBusinessSliceDaily(params, { signal })
      else res = await getBusinessSliceMonthly(params, { signal })
      let data = Array.isArray(res?.data) ? res.data : (Array.isArray(res) ? res : [])
      const mm = { ...(res?.meta ?? {}) }
      if (res?.data_freshness) mm.data_freshness = res.data_freshness
      setMatrixMeta(mm)
      setSliceMaxTripDate(res?.meta?.slice_max_trip_date ?? null)
      if (!showSubfleets) data = data.filter((r) => !r.is_subfleet)
      setRows(data)
      setLoadingTasks((t) => { const n = { ...t }; delete n.matrix; return n })
      setLoading(false)

      const coverageParams = {}
      if (country) coverageParams.country = country
      if (city) coverageParams.city = city
      if (year != null && year !== '') coverageParams.year = Number(year)
      if (effectiveMonth) coverageParams.month = Number(effectiveMonth)
      setLoadingTasks((t) => ({ ...t, coverage: 'Cobertura (en espera…)' }))
      await new Promise((resolve) => setTimeout(resolve, COVERAGE_FETCH_DELAY_MS))
      if (signal?.aborted) {
        setLoadingTasks((t) => { const n = { ...t }; delete n.coverage; return n })
        return
      }
      setLoadingTasks((t) => ({ ...t, coverage: 'Cobertura' }))
      getBusinessSliceCoverageSummary(coverageParams, { signal })
        .then(setCoverageSummary)
        .catch(() => setCoverageSummary(null))
        .finally(() => setLoadingTasks((t) => { const n = { ...t }; delete n.coverage; return n }))
    } catch (e) {
      setLoadingTasks((t) => { const n = { ...t }; delete n.matrix; delete n.coverage; return n })
      if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError' || e?.name === 'AbortError') return
      const detail = e?.response?.data?.detail
      const net =
        e?.code === 'ECONNABORTED' || e?.message?.includes?.('timeout')
          ? 'Tiempo de espera agotado: el servidor o la base de datos pueden estar lentos o no disponibles.'
          : null
      setErr(net || (typeof detail === 'string' ? detail : detail?.message) || e.message || 'Error cargando datos')
      setRows([])
      setMatrixMeta(null)
      setSliceMaxTripDate(null)
    } finally {
      setLoading(false)
      setLoadingTasks((t) => { const n = { ...t }; delete n.matrix; return n })
    }
  }, [grain, country, city, businessSlice, fleet, showSubfleets, year, effectiveMonth, blockedByCountry, isProjectionMode, doLoadProjection])

  useEffect(() => {
    if (!heavyQueriesEnabled || !isProjectionMode) return
    if (blockedByCountry || !planVersion) return
    setErr(null)
  }, [heavyQueriesEnabled, isProjectionMode, blockedByCountry, planVersion, grain, country, city, businessSlice, year, effectiveMonth])

  useEffect(() => {
    if (!heavyQueriesEnabled) {
      wasHeavyEnabledRef.current = false
      return
    }
    const justEnabled = !wasHeavyEnabledRef.current
    wasHeavyEnabledRef.current = true

    if (justEnabled) {
      clearTimeout(debounceRef.current)
      abortRef.current?.abort('filter-change')
      abortRef.current = new AbortController()
      doLoad(abortRef.current.signal)
      return () => {
        abortRef.current?.abort('unmount')
      }
    }

    clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      abortRef.current?.abort('filter-change')
      abortRef.current = new AbortController()
      doLoad(abortRef.current.signal)
    }, 600)
    return () => {
      clearTimeout(debounceRef.current)
      abortRef.current?.abort('unmount')
    }
  }, [heavyQueriesEnabled, doLoad])

  // loadData: función pública para refrescos manuales (botones, etc.) sin debounce.
  const loadData = useCallback(() => {
    abortRef.current?.abort('manual-reload')
    abortRef.current = new AbortController()
    doLoad(abortRef.current.signal)
  }, [doLoad])

  /** Cancela TODAS las requests en vuelo (incluido debounce pendiente). */
  const cancelAll = useCallback(() => {
    clearTimeout(debounceRef.current)
    clearTimeout(trustStartDelayRef.current)
    clearTimeout(freshnessDelayRef.current)
    abortRef.current?.abort('user-cancel')
    trustAbortRef.current?.abort('user-cancel')
    freshnessAbortRef.current?.abort('user-cancel')
    filtersAbortRef.current?.abort('user-cancel')
  }, [])

  const projMatrix = useMemo(() => isProjectionMode ? buildProjectionMatrix(projectionRows, grain) : null, [projectionRows, grain, isProjectionMode])

  const periodInfoMap = useMemo(() => {
    if (!isProjectionMode || !projectionRows?.length) return null
    const map = new Map()
    for (const row of projectionRows) {
      const pk = periodKey(row, grain)
      if (!pk) continue
      if (map.has(pk)) continue
      const weekState = row.week_state || null
      const comparisonBasis = row.trips_completed_comparison_basis
        || row.revenue_yego_net_comparison_basis
        || row.active_drivers_comparison_basis
        || row.avg_ticket_comparison_basis
        || row.trips_per_driver_comparison_basis
        || null
      const hasReal = (
        (Number(row.trips_completed) || 0) > 0 ||
        (Number(row.revenue_yego_net) || 0) > 0 ||
        (Number(row.active_drivers) || 0) > 0
      )
      map.set(pk, { weekState, comparisonBasis, hasReal })
    }
    return map
  }, [isProjectionMode, projectionRows, grain])

  useEffect(() => {
    if (!import.meta.env.DEV) return
    const debugOn = typeof window !== 'undefined' && window.location?.search?.includes('debugOmniview=1')
    if (!debugOn || !projMatrix?.cities?.size) return
    const citiesByCountry = new Map()
    for (const [, cityData] of projMatrix.cities) {
      const c = cityData.country || '—'
      citiesByCountry.set(c, (citiesByCountry.get(c) || 0) + 1)
    }
    console.group('%c[PIPELINE 2+3/4] projMatrix → displayProjMatrix', 'color:#10b981;font-weight:bold')
    console.log('stage 2 - buildProjectionMatrix:', {
      totalCities: projMatrix.cities.size,
      citiesByCountry: Object.fromEntries(citiesByCountry),
      allPeriods: projMatrix.allPeriods?.length,
      inputRows: projectionRows?.length,
    })
    const display = filterWeeklyFocus(projMatrix, grain, weekFocusOnly)
    const displayByCountry = new Map()
    for (const [, cityData] of display.cities) {
      const c = cityData.country || '—'
      displayByCountry.set(c, (displayByCountry.get(c) || 0) + 1)
    }
    console.log('stage 3 - displayProjMatrix (after weekFocusOnly):', {
      totalCities: display.cities.size,
      citiesByCountry: Object.fromEntries(displayByCountry),
      allPeriods: display.allPeriods?.length,
      weekFocusOnly,
    })
    console.groupEnd()
  }, [projMatrix, grain, weekFocusOnly, projectionRows])

  /** Vs Proyección: estado vacío tras cargar (país obligatorio W/D, plan sin real, o sin datos). */
  const projectionEmptyKind = useMemo(() => {
    if (!heavyQueriesEnabled || loading || projectionPending || !isProjectionMode || !planVersion || projectionRows.length > 0 || err) {
      return null
    }
    if (blockedByCountry && (grain === 'weekly' || grain === 'daily')) {
      return 'needs_country'
    }
    const pwrN = Number(projectionMeta?.plan_without_real?.count ?? 0)
    const pwrR = projectionMeta?.plan_without_real?.rows
    const hasPwr = pwrN > 0 || (Array.isArray(pwrR) && pwrR.length > 0)
    return hasPwr ? 'plan_without_real' : 'no_data'
  }, [heavyQueriesEnabled, loading, projectionPending, isProjectionMode, planVersion, projectionRows.length, err, projectionMeta, blockedByCountry, grain])

  const baseMatrix = useMemo(() => buildMatrix(rows, grain), [rows, grain])
  const backendTotals = useMemo(() => toMetricMap(matrixMeta?.period_totals), [matrixMeta?.period_totals])
  const backendComparisonTotals = useMemo(
    () => toMetricMap(matrixMeta?.comparison_period_totals),
    [matrixMeta?.comparison_period_totals]
  )
  const backendUnmappedTotals = useMemo(
    () => toMetricMap(matrixMeta?.unmapped_period_totals),
    [matrixMeta?.unmapped_period_totals]
  )
  const matrix = useMemo(() => ({
    ...baseMatrix,
    totals: backendTotals.size > 0 ? backendTotals : baseMatrix.totals,
    comparisonTotals: backendComparisonTotals.size > 0 ? backendComparisonTotals : baseMatrix.comparisonTotals,
  }), [baseMatrix, backendTotals, backendComparisonTotals])

  const displayMatrix = useMemo(() => {
    const m = filterWeeklyFocus(matrix, grain, weekFocusOnly)
    return filterWeekdayFocus(m, grain, weekdayFocus)
  }, [matrix, grain, weekFocusOnly, weekdayFocus])
  const displayProjMatrix = useMemo(() => {
    const m = filterWeeklyFocus(projMatrix, grain, weekFocusOnly)
    return filterWeekdayFocus(m, grain, weekdayFocus)
  }, [projMatrix, grain, weekFocusOnly, weekdayFocus])

  // EXPOSE runtime state for browser debugging: window.__omniviewDebug (DEV only)
  useEffect(() => {
    if (typeof window === 'undefined') return
    if (!import.meta.env.DEV) return
    const citiesByCountry = new Map()
    if (projMatrix?.cities) {
      for (const [, cd] of projMatrix.cities) {
        const c = cd.country || '—'
        citiesByCountry.set(c, (citiesByCountry.get(c) || 0) + 1)
      }
    }
    const dispByCountry = new Map()
    if (displayProjMatrix?.cities) {
      for (const [, cd] of displayProjMatrix.cities) {
        const c = cd.country || '—'
        dispByCountry.set(c, (dispByCountry.get(c) || 0) + 1)
      }
    }
    window.__omniviewDebug = {
      grain,
      countryFilter: country || '(ALL)',
      blockedByCountry,
      needsCountry,
      isProjectionMode,
      projectionRows: projectionRows?.length || 0,
      matrixCountryKeys: Object.fromEntries(citiesByCountry),
      displayCountryKeys: Object.fromEntries(dispByCountry),
      weekFocusOnly,
      allPeriods: projMatrix?.allPeriods?.length || 0,
      displayPeriods: displayProjMatrix?.allPeriods?.length || 0,
      servedFrom: projectionMeta?.served_from,
      factGeneratedAt: projectionMeta?.fact_generated_at,
    }
    const debugOn = typeof window !== 'undefined' && window.location?.search?.includes('debugOmniview=1')
    if (debugOn) {
      const hasBoth = citiesByCountry.has('peru') && citiesByCountry.has('colombia')
      console.group('%c[PIPELINE 4/4] window.__omniviewDebug — RENDER', 'color:#f59e0b;font-weight:bold')
      console.table(window.__omniviewDebug)
      if (hasBoth) {
        console.log('%c✓ Peru + Colombia presentes en matrix', 'color:#10b981')
      } else {
        console.warn('%c✗ SOLO ' + [...citiesByCountry.keys()].join(', ') + ' — falta el otro país', 'color:#ef4444;font-weight:bold')
        console.warn('  posibles causas: bloqueo por blockedByCountry, frontend no recompilado, o request con country=')
      }
      console.groupEnd()
    }
  }, [projMatrix, displayProjMatrix, grain, country, blockedByCountry, needsCountry, isProjectionMode, projectionRows, weekFocusOnly, projectionMeta])
  const execKpis = useMemo(() => {
    const periods = matrix.allPeriods || []
    const currPk = periods.length > 0 ? periods[periods.length - 1] : null
    const currTotals = currPk ? matrix.totals.get(currPk) : null
    const currUnmapped = currPk ? backendUnmappedTotals.get(currPk) : null
    const totalTripsVisible = (Number(currTotals?.trips_completed) || 0) + (Number(currTotals?.trips_cancelled) || 0)
    const unmappedTripsVolume = (Number(currUnmapped?.trips_completed) || 0) + (Number(currUnmapped?.trips_cancelled) || 0)
    return {
      ...(currTotals || {}),
      unmapped_trips_volume: unmappedTripsVolume,
      unmapped_share_of_trips: totalTripsVisible > 0 ? unmappedTripsVolume / totalTripsVisible : 0,
    }
  }, [matrix, backendUnmappedTotals])

  // Freshness para STALE: priorizar capa business_slice (day_fact) alineada a la matriz.
  const maxDataDate = sliceMaxTripDate || freshnessInfo?.derived_max_date || null
  const periodStates = useMemo(
    () => mergePeriodStatesFromMeta(
      computePeriodStates(matrix.allPeriods, grain, maxDataDate),
      matrixMeta?.period_states,
    ),
    [matrix.allPeriods, grain, maxDataDate, matrixMeta]
  )

  const temporalTiers = useMemo(
    () => computeTemporalVisualTiers(matrix.allPeriods, grain, periodStates),
    [matrix.allPeriods, grain, periodStates]
  )

  const bannerContextHints = useMemo(() => {
    const hints = []
    if (matrixMeta?.fact_layer?.status === 'empty') {
      hints.push(
        matrixMeta.fact_layer.message ||
          'Capa operativa (facts) sin datos para este filtro: revisar carga ETL.'
      )
    }
    const lp = matrix.allPeriods.length > 0 ? matrix.allPeriods[matrix.allPeriods.length - 1] : null
    const st = lp ? periodStates?.get(lp) : null
    if (st === PERIOD_STATES.STALE) {
      hints.push('Data desactualizada: el delta no es definitivo')
    }
    if (st === PERIOD_STATES.OPEN || st === PERIOD_STATES.PARTIAL) {
      hints.push(
        st === PERIOD_STATES.PARTIAL
          ? 'Carga incompleta: comparativos preliminares'
          : 'En curso: comparativos preliminares'
      )
    }
    const cp = coverageSummary?.coverage_pct
    if (cp != null && cp < 92) hints.push(`Cobertura mapeada ${cp}%`)
    const um = coverageSummary?.unmapped_trips
    if (um != null && um > 0) hints.push(`Sin mapear ${um.toLocaleString()} viajes`)
    return hints
  }, [matrix.allPeriods, periodStates, coverageSummary, matrixMeta])

  // ─── Insight Engine (memoized) ────────────────────────────────────────────
  const engineConfig = useMemo(
    () => mergeInsightRuntimeConfig(INSIGHT_CONFIG, insightUserPatch),
    [insightUserPatch]
  )
  const trustContext = useMemo(() => {
    if (!matrixTrust?.trust_status) return null
    const decisionMode = matrixTrust.operational_decision?.decision_mode ?? null
    return {
      trust_status: matrixTrust.trust_status,
      decision_mode: decisionMode,
      global_insights_blocked:
        !!matrixTrust.global_insights_blocked || decisionMode === 'BLOCKED',
      matrixTrust,
    }
  }, [matrixTrust])

  const execNavPendingRef = useRef(false)
  const scrollContainerRef = useRef(null)

  const currentPeriodKey = useMemo(
    () => getCurrentPeriodKey(grain),
    [grain]
  )

  // ── CLOSED PERIOD ANCHOR (Proyección) ──
  const closedPeriodAnchor = useMemo(() => {
    if (!isProjectionMode || !displayProjMatrix?.allPeriods?.length) return null
    return resolveClosedPeriodAnchor({
      allPeriods: displayProjMatrix.allPeriods,
      grain,
      projectionMeta,
      periodInfoMap,
      selectedKpi: focusedKpi,
      kpiFreshness: projectionMeta?.kpi_freshness || null,
    })
  }, [isProjectionMode, displayProjMatrix?.allPeriods, grain, projectionMeta, focusedKpi, periodInfoMap])

  const operationalCurrentPeriodKey = useMemo(() => {
    if (isProjectionMode && closedPeriodAnchor?.anchorPeriodKey) {
      return closedPeriodAnchor.anchorPeriodKey
    }
    return currentPeriodKey
  }, [isProjectionMode, closedPeriodAnchor, currentPeriodKey])

  const autoScrollAppliedRef = useRef(false)
  const userHasScrolledRef = useRef(false)
  const scrollRafRef = useRef(null)
  const scrollTimeoutRef = useRef(null)

  const scrollToCurrentPeriod = useCallback(() => {
    const container = scrollContainerRef.current
    if (!container) return
    const allPeriods = isProjectionMode
      ? (displayProjMatrix?.allPeriods || projMatrix?.allPeriods || [])
      : (matrix.allPeriods || [])
    if (!allPeriods.length) return
    // Guard: container must have width and scrollable content
    if (container.clientWidth <= 0) return
    if (container.scrollWidth <= container.clientWidth) return

    const evColW = compact ? 58 : 78
    const projColW = compact ? 78 : 100
    const colW = isProjectionMode ? projColW : evColW
    let effectiveIdx = resolveCurrentPeriodIndex(allPeriods, grain)

    const anchorKey = isProjectionMode ? closedPeriodAnchor?.anchorPeriodKey : null
    if (anchorKey) {
      const anchorIdx = allPeriods.indexOf(anchorKey)
      if (anchorIdx >= 0) effectiveIdx = anchorIdx
    }
    if (effectiveIdx < 0) {
      effectiveIdx = allPeriods.length - 1
    }
    const viewportWidth = container.clientWidth
    const fixedW = COL1_W + COL2_W
    const scrollTo = calculateScrollTarget(effectiveIdx, colW, fixedW, viewportWidth, grain)
    container.scrollTo({ left: scrollTo, behavior: 'smooth' })
  }, [matrix.allPeriods, displayProjMatrix?.allPeriods, projMatrix?.allPeriods, grain, compact, isProjectionMode, closedPeriodAnchor])

  useEffect(() => {
    const hasData = isProjectionMode ? projectionRows.length > 0 : rows.length > 0
    if (loading || blockedByCountry || !hasData) return
    if (!autoScrollAppliedRef.current && !userHasScrolledRef.current) {
      // Double RAF for DOM paint + 150ms timeout fallback for heavy renders
      scrollRafRef.current = requestAnimationFrame(() => {
        scrollRafRef.current = requestAnimationFrame(() => {
          scrollToCurrentPeriod()
          autoScrollAppliedRef.current = true
          // Retry once after paint settles (large tables may need extra time)
          const retryTimer = setTimeout(() => {
            scrollToCurrentPeriod()
          }, 150)
          scrollTimeoutRef.current = retryTimer
        })
      })
      return () => {
        if (scrollRafRef.current) cancelAnimationFrame(scrollRafRef.current)
        if (scrollTimeoutRef.current) clearTimeout(scrollTimeoutRef.current)
      }
    }
    return () => {
      if (scrollRafRef.current) cancelAnimationFrame(scrollRafRef.current)
      if (scrollTimeoutRef.current) clearTimeout(scrollTimeoutRef.current)
    }
  }, [loading, blockedByCountry, rows.length, projectionRows.length, scrollToCurrentPeriod, isProjectionMode])

  useEffect(() => {
    autoScrollAppliedRef.current = false
    userHasScrolledRef.current = false
  }, [grain, viewMode, country, city, year, month, businessSlice])

  // Detect user manual scroll to prevent anchor fights
  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) return
    const onUserScroll = () => {
      if (autoScrollAppliedRef.current) {
        userHasScrolledRef.current = true
      }
    }
    container.addEventListener('wheel', onUserScroll, { passive: true })
    container.addEventListener('touchmove', onUserScroll, { passive: true })
    return () => {
      container.removeEventListener('wheel', onUserScroll)
      container.removeEventListener('touchmove', onUserScroll)
    }
  }, [])

  const executiveForBanner = useMemo(() => {
    if (!matrixTrust) return null
    if (matrixTrust.executive) return matrixTrust.executive
    const ts = matrixTrust.trust_status
    const status = ts === 'ok' ? 'OK' : ts === 'blocked' ? 'BLOCKED' : 'WARNING'
    const im = matrixTrust.impact_summary || {}
    const pi = matrixTrust.primary_issue
    return {
      status,
      impact_pct: Math.max(Number(im.pct_trips_affected) || 0, Number(im.pct_revenue_affected) || 0),
      priority_score: pi?.severity_weight ?? 0,
      main_issue: pi
        ? {
            code: pi.code,
            description: pi.message,
            city: pi.trace?.city ?? null,
            lob: pi.trace?.lob ?? null,
            period: pi.trace?.period ?? null,
            metric: Array.isArray(pi.trace?.metrics) ? pi.trace.metrics[0] : null,
          }
        : null,
      action: pi?.action_engine?.action || matrixTrust.message || '',
    }
  }, [matrixTrust])

  const handleExecutiveBannerActivate = useCallback(() => {
    const mi = executiveForBanner?.main_issue
    if (!mi) return
    execNavPendingRef.current = true
    if (mi.city) setCity(mi.city)
    if (mi.lob) setBusinessSlice(mi.lob)
    if (mi.period && grain === 'monthly') {
      const d = String(mi.period).slice(0, 10)
      const y = parseInt(d.slice(0, 4), 10)
      const mo = parseInt(d.slice(5, 7), 10)
      if (!Number.isNaN(y)) setYear(y)
      if (!Number.isNaN(mo)) setMonth(String(mo))
    }
  }, [executiveForBanner, grain])

  const insights = useMemo(
    () => detectInsights(matrix, grain, engineConfig, periodStates, trustContext),
    [matrix, grain, engineConfig, periodStates, trustContext]
  )
  const insightCellMap = useMemo(
    () => buildInsightCellMap(insights, engineConfig),
    [insights, engineConfig]
  )
  const lineImpactMap = useMemo(() => {
    const m = new Map()
    for (const ins of insights) {
      const k = `${ins.cityKey}::${ins.lineKey}`
      m.set(k, Math.max(m.get(k) ?? 0, ins.impactScore))
    }
    return m
  }, [insights])

  const refreshInsightPatch = useCallback(() => {
    setInsightUserPatch(loadInsightUserPatch() ?? {})
  }, [])

  const refreshMatrixTrust = useCallback(() => {
    getMatrixOperationalTrust()
      .then(setMatrixTrust)
      .catch(() => {})
  }, [])

  const handleUploadSubmit = useCallback(async () => {
    if (!uploadFile) return
    setUploadLoading(true)
    setUploadError(null)
    setUploadSuccess(null)
    try {
      const result = await uploadPlanRuta27UI(uploadFile)
      setUploadSuccess(result)
      setUploadFile(null)
      if (uploadInputRef.current) uploadInputRef.current.value = ''
      loadPlanVersions(true)
      setTimeout(() => {
        setUploadModalOpen(false)
        setUploadSuccess(null)
      }, 2000)
    } catch (e) {
      const detail = e?.response?.data?.detail
      setUploadError(typeof detail === 'string' ? detail : e.message || 'Error al subir el archivo')
    } finally {
      setUploadLoading(false)
    }
  }, [uploadFile, loadPlanVersions])

  const sortSelectOptions = useMemo(() => {
    const impactOpt = SORT_OPTIONS.find((o) => o.id === 'impact_desc')
    const rest = SORT_OPTIONS.filter((o) => o.id !== 'impact_desc')
    if (insightMode) return [impactOpt, ...rest].filter(Boolean)
    return rest
  }, [insightMode])

  useEffect(() => {
    if (insightMode && !prevInsightMode.current && sortKey === 'alpha') {
      setSortKey('impact_desc')
    }
    prevInsightMode.current = insightMode
  }, [insightMode, sortKey])

  useEffect(() => {
    if (!insightMode && sortKey === 'impact_desc') setSortKey('alpha')
  }, [insightMode, sortKey])

  // Find insight for current selection
  const insightForSelection = useMemo(() => {
    if (!selection) return null
    const key = `${selection.cityKey}::${selection.lineKey}::${selection.period}`
    return insights.find((i) => `${i.cityKey}::${i.lineKey}::${i.period}` === key) || null
  }, [selection, insights])

  const handleCellClick = useCallback((cellInfo) => {
    setSelectedCell((prev) => (prev === cellInfo.id ? null : cellInfo.id))
    setSelection((prev) => {
      const next = prev?.id === cellInfo.id ? null : cellInfo
      if (next && prev && prev.id !== next.id) {
        setSelectionHistory(h => {
          const filtered = h.filter(s => s.id !== next.id)
          return [...filtered.slice(-9), prev]
        })
      }
      return next
    })
  }, [])

  useEffect(() => {
    if (!execNavPendingRef.current || loading || blockedByCountry || rows.length === 0) return
    const mi = executiveForBanner?.main_issue
    const resolved = mi && resolveMainIssueCellTarget(matrix, grain, mi, periodStates)
    if (resolved?.cellInfo) {
      handleCellClick(resolved.cellInfo)
      requestAnimationFrame(() => {
        const id = resolved.cellInfo.id
        const el = typeof CSS !== 'undefined' && CSS.escape
          ? document.querySelector(`[data-matrix-cell-id="${CSS.escape(id)}"]`)
          : document.querySelector(`[data-matrix-cell-id="${id.replace(/"/g, '')}"]`)
        el?.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' })
      })
    }
    execNavPendingRef.current = false
  }, [rows, matrix, loading, blockedByCountry, executiveForBanner, grain, periodStates, handleCellClick])

  const handleInsightClick = useCallback((insight) => {
    const lineData = matrix.cities.get(insight.cityKey)?.lines
    let foundLine = null, foundLineKey = null
    if (lineData) {
      for (const [lk, ld] of lineData) {
        if (ld.business_slice_name === insight.business_slice) { foundLine = ld; foundLineKey = lk; break }
      }
    }
    if (!foundLine) return
    const periodDeltas = {}
    const rawDeltas = computeDeltasFn(foundLine.periods, matrix.allPeriods, periodStates)
    const pd = rawDeltas.get(insight.period)
    if (pd) Object.assign(periodDeltas, pd)

    const cellId = `${insight.cityKey}::${foundLineKey}::${insight.period}::${insight.metric}`
    setSelectedCell(cellId)
    setSelection({
      id: cellId,
      cityKey: insight.cityKey,
      lineKey: foundLineKey,
      period: insight.period,
      kpiKey: insight.metric,
      lineData: foundLine,
      periodDeltas,
      raw: foundLine.periods.get(insight.period)?.raw,
    })
  }, [matrix, periodStates])

  const handleExport = useCallback(() => {
    exportOmniviewFull({
      viewMode, grain, country, city, businessSlice, fleet, year, month,
      planVersion, planVersions, showSubfleets, sortKey, focusedKpi, compact,
      matrix, projMatrix, projectionRows, projectionMeta,
      freshnessInfo, coverageSummary, matrixMeta, matrixTrust,
      sliceMaxTripDate, maxDataDate,
      periodStates, rows,
    })
  }, [viewMode, grain, country, city, businessSlice, fleet, year, month,
    planVersion, planVersions, showSubfleets, sortKey, focusedKpi, compact,
    matrix, projMatrix, projectionRows, projectionMeta,
    freshnessInfo, coverageSummary, matrixMeta, matrixTrust,
    sliceMaxTripDate, maxDataDate, periodStates, rows])

  return (
    <div className="relative" data-omniview-matrix-root style={{ width: '100vw', left: '50%', right: '50%', marginLeft: '-50vw', marginRight: '-50vw' }}>
      {/* ═══ OMNIVIEW SHELL — single operational surface ═══ */}
      <div className="mx-3 sm:mx-4 rounded-lg border border-ct-border bg-ct-surface overflow-hidden shadow-[0_1px_3px_rgba(0,0,0,0.04)] divide-y divide-ct-border/40">
        {/* ═══ COMMAND HEADER ═══ */}
        <OmniviewCommandHeader
          viewMode={viewMode}
          grain={grain}
          year={year}
          month={month}
          freshnessInfo={freshnessInfo}
          coverageSummary={coverageSummary}
          matrixTrust={matrixTrust}
          matrixMeta={matrixMeta}
          rows={rows}
          compact={compact}
          operationalMode={operationalMode}
          onOperationalModeChange={setOperationalMode}
        >
          {heavyQueriesEnabled && (
            <MatrixExecutiveBanner
              executive={executiveForBanner}
              decisionMode={matrixTrust?.operational_decision?.decision_mode}
              confidence={matrixTrust?.operational_decision?.confidence}
              recommendations={matrixTrust?.trust_recommendations}
              loading={!matrixTrust || matrixTrust?.trust_status === 'loading'}
              actionable={!blockedByCountry && rows.length > 0 && !loading}
              onActivate={handleExecutiveBannerActivate}
              contextHints={bannerContextHints}
            />
          )}
        </OmniviewCommandHeader>

        {/* Momentum Priority Strip — surfaces deteriorations (both modes) */}
        <div className="divide-y-0">
          <OmniviewMomentumPriorityStrip cities={isProjectionMode ? projMatrix?.cities ?? null : baseMatrix?.cities ?? null} allPeriods={isProjectionMode ? projMatrix?.allPeriods ?? [] : baseMatrix?.allPeriods ?? []} grain={grain} maxItems={5} />
        </div>

        {/* Controls — unified inside shell */}
        <div className="overflow-hidden">
          <div className="flex flex-wrap items-end gap-x-2 gap-y-1 px-3 py-1">
            {/* Grano temporal */}
            <div className="flex flex-col gap-1">
              <span className="text-2xs font-semibold text-ct-text3 uppercase tracking-wider">Grano</span>
              <div className="flex gap-1">
                {GRAINS.map((g) => (
                  <button key={g.id} type="button" className={`${btnCls(grain === g.id)} uppercase tracking-wide`} onClick={() => setGrain(g.id)}>{g.label}</button>
                ))}
              </div>
            </div>

            {/* Separador vertical */}
            <div className="hidden sm:block self-stretch w-px bg-gray-100 mx-1" />

            {/* Filtros dimensionales */}
            <FilterSelect label="País" value={country} onChange={setCountry} options={countries} placeholder="Todos los países" required={needsCountry} />
            <FilterSelect label="Ciudad" value={city} onChange={setCity} options={citiesForCountry} placeholder="Todas las ciudades" />
            <FilterSelect label="Tajada" value={businessSlice} onChange={setBusinessSlice} options={slices} placeholder="Todas las tajadas" />
            {grain === 'monthly' && <FilterSelect label="Flota" value={fleet} onChange={setFleet} options={fleets} placeholder="Todas las flotas" />}

            {/* Separador vertical */}
            <div className="hidden sm:block self-stretch w-px bg-gray-100 mx-1" />

            {/* Periodo */}
            <YearSelect value={year} onChange={setYear} />

            {(grain === 'monthly' || grain === 'daily') && (
              <MonthSelect value={month} onChange={setMonth} />
            )}
            {grain === 'weekly' && (
              <div className="flex flex-col gap-1 self-end pb-1">
                <span className="text-[10px] font-semibold text-ct-text3 uppercase tracking-wider">Scope semanal</span>
                <span
                  className="inline-flex items-center rounded-md border border-blue-200 bg-blue-50 px-2.5 py-1.5 text-xs font-medium text-blue-700"
                  title={ISO_WEEK_SCOPE_TOOLTIP}
                >
                  Semanas ISO (pueden cruzar meses)
                </span>
              </div>
            )}
            {grain === 'weekly' && (
              <label className="flex items-center gap-1.5 text-xs text-ct-text2 cursor-pointer select-none self-end pb-1.5 uppercase tracking-wide">
                <input type="checkbox" checked={!weekFocusOnly} onChange={(e) => setWeekFocusOnly(!e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 h-3.5 w-3.5" />
                Año completo
              </label>
            )}

            <label className="flex items-center gap-1.5 text-xs text-ct-text2 cursor-pointer select-none self-end pb-1.5 uppercase tracking-wide">
              <input type="checkbox" checked={showSubfleets} onChange={(e) => setShowSubfleets(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 h-3.5 w-3.5" />
              Subflotas
            </label>

            <button type="button" onClick={() => {
              setCountry(''); setCity(''); setBusinessSlice(''); setFleet('')
              setYear(normalizeOmniviewYear(new Date().getFullYear())); setMonth('')
              setSortKey('alpha'); setFocusedKpi('trips_completed')
            }}
              className="self-end pb-1.5 px-2 py-0.5 rounded text-[10px] text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
              title="Restablecer filtros">
              Reset
            </button>

            {/* Weekday Focus — solo visible en grain daily */}
            {grain === 'daily' && (
              <div className="flex flex-col gap-1 self-end">
                <span className="text-2xs font-semibold text-ct-text3 uppercase tracking-wider">
                  {weekdayFocus != null
                    ? `Comparando ${['DOM','LUN','MAR','MIÉ','JUE','VIE','SÁB'][weekdayFocus]} vs ${['DOM','LUN','MAR','MIÉ','JUE','VIE','SÁB'][weekdayFocus]}`
                    : 'Todos los días'}
                  <span className="text-ct-text3/50 font-normal ml-1 lowercase">{weekdayFocus != null ? `· ${displayMatrix?.allPeriods?.length || 0} semanas` : ''}</span>
                </span>
                <div className="flex gap-0.5">
                  {['DOM','LUN','MAR','MIÉ','JUE','VIE','SÁB'].map((label, idx) => {
                    const isActive = weekdayFocus === idx
                    return (
                      <button
                        key={label}
                        type="button"
                        onClick={() => setWeekdayFocus(isActive ? null : idx)}
                        className={`px-2.5 py-1 rounded-md text-xs font-bold transition-all ${
                          isActive
                            ? 'bg-blue-600 text-white shadow-[0_0_12px_rgba(59,130,246,0.35)] ring-1 ring-blue-400/50 scale-110'
                            : 'text-ct-text3 hover:text-ct-text hover:bg-ct-border/50'
                        }`}
                        title={isActive ? `Mostrar todos los días` : `Ver solo ${label} — comparar ${label} contra ${label}`}
                      >
                        {label}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}
          </div>

          <div className="px-3 py-1 border-t border-ct-border bg-ct-surface/40">
            {!focusMode && <OmniviewDataHelp />}
          </div>

          {/* Fila 2: Controles de visualización + KPI selector compacto */}
          <div className="px-3 py-1.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 bg-ct-bg/60">
            {/* Modo Evolución / Vs Proyección */}
            <div className="flex items-center gap-1">
              <span className="text-[10px] font-medium text-ct-text3 mr-1">Modo</span>
              <div className="flex gap-0.5">
                <button type="button" className={btnCls(viewMode === 'evolucion')} onClick={() => setViewMode('evolucion')}>Evolución</button>
                <button type="button" className={btnCls(viewMode === 'proyeccion')} onClick={() => setViewMode('proyeccion')}>Vs Proyección</button>
              </div>
            </div>

            {/* FASE 1.1 — Perspective Selector (solo en modo Proyección) */}
            {isProjectionMode && (
              <>
                <div className="w-px h-4 bg-gray-200 hidden sm:block" />
                <div className="flex items-center gap-1">
                  <span className="text-[11px] font-medium text-ct-text3 mr-1">Perspectiva</span>
                  <div className="flex gap-1">
                    <button
                      type="button"
                      className={btnCls(perspective === 'operational')}
                      onClick={() => setPerspective('operational')}
                    >
                      Operational
                    </button>
                    <button
                      type="button"
                      className={btnCls(perspective === 'ownership')}
                      onClick={() => setPerspective('ownership')}
                    >
                      Ownership
                    </button>
                  </div>
                </div>
              </>
            )}
            {/* ── KPI selector compacto (inline) ── */}
            <div className="w-px h-4 bg-gray-200 hidden sm:block" />
            <div className="flex items-center gap-1">
              <span className="text-[10px] font-medium text-ct-text3 mr-1">KPI</span>
              <div className="flex gap-0.5">
                {KPI_FOCUS_OPTIONS.map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    onClick={() => setFocusedKpi(option.id)}
                    className={btnCls(focusedKpi === option.id)}
                    title={option.label}
                  >
                    {option.short || option.label}
                  </button>
                ))}
              </div>
            </div>

            {isProjectionMode && (
              <>
                <div className="w-px h-4 bg-gray-200 hidden sm:block" />
                <div className="flex items-center gap-1.5">
                  <ProjectionVersionSelector
                    versions={planVersions}
                    selectedVersionKey={planVersion}
                    onChange={(key) => setPlanVersion(key)}
                    onRenameSuccess={() => loadPlanVersions()}
                    servingVersionKeys={servingVersionKeys}
                  />
                  <button
                    type="button"
                    onClick={() => { setUploadModalOpen(true); setUploadError(null); setUploadSuccess(null) }}
                    className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                    title="Subir archivo de proyección"
                  >
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                    </svg>
                    Subir
                  </button>
                </div>
              </>
            )}

            <div className="w-px h-4 bg-gray-200 hidden sm:block" />

            {/* Modo Data / Insight */}
            {!isProjectionMode && (
            <div className="flex items-center gap-1">
              <span className="text-[11px] font-medium text-ct-text3 mr-1">Vista</span>
              <div className="flex gap-1">
                <button type="button" className={modeCls(!insightMode)} onClick={() => setInsightMode(false)}>Data</button>
                <button type="button" className={modeCls(insightMode)} onClick={() => setInsightMode(true)}>
                  Insight
                  {insights.length > 0 && (
                    <span className="ml-1.5 px-1.5 py-px rounded-full text-[9px] font-bold bg-red-500 text-white">{insights.length}</span>
                  )}
                </button>
              </div>
            </div>
            )}

            <div className="w-px h-4 bg-gray-200 hidden sm:block" />

            {/* Orden */}
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] font-medium text-ct-text3">Orden</span>
              <select className={miniSelectCls} value={sortKey} onChange={(e) => setSortKey(e.target.value)}>
                {sortSelectOptions.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
              </select>
            </div>

            <div className="w-px h-4 bg-gray-200 hidden sm:block" />

            {/* Densidad */}
            <div className="flex items-center gap-1">
              <span className="text-[11px] font-medium text-ct-text3 mr-1">Densidad</span>
              <div className="flex gap-1">
                <button type="button" className={densityCls(!compact)} onClick={() => setCompact(false)}>Cómodo</button>
                <button type="button" className={densityCls(compact)} onClick={() => setCompact(true)}>Compacto</button>
              </div>
            </div>

            <div className="w-px h-4 bg-gray-200 hidden sm:block" />

            {/* Zoom de matriz — FASE 1H.2C */}
            <div className="flex items-center gap-1">
              <span className="text-[11px] font-medium text-ct-text3 mr-1">Zoom</span>
              <div className="flex gap-0.5">
                <button type="button" onClick={() => { const idx = ZOOM_LEVELS.indexOf(matrixZoom); if (idx > 0) persistZoom(ZOOM_LEVELS[idx - 1]) }}
                  className="px-1.5 py-1 rounded-l-md text-xs font-medium text-ct-text2 bg-ct-card border border-ct-border hover:border-gray-300 hover:bg-ct-bg transition-colors"
                  title="Reducir zoom" disabled={matrixZoom <= ZOOM_LEVELS[0]}>−</button>
                <button type="button" onClick={() => persistZoom(100)}
                  className="px-2 py-1 text-[11px] font-semibold text-ct-text2 bg-ct-card border-y border-ct-border hover:bg-ct-bg transition-colors"
                  title="Reset zoom 100%">{matrixZoom}%</button>
                <button type="button" onClick={() => { const idx = ZOOM_LEVELS.indexOf(matrixZoom); if (idx < ZOOM_LEVELS.length - 1) persistZoom(ZOOM_LEVELS[idx + 1]) }}
                  className="px-1.5 py-1 rounded-r-md text-xs font-medium text-ct-text2 bg-ct-card border border-ct-border hover:border-gray-300 hover:bg-ct-bg transition-colors"
                  title="Aumentar zoom" disabled={matrixZoom >= ZOOM_LEVELS[ZOOM_LEVELS.length - 1]}>+</button>
              </div>
            </div>

            <div className="w-px h-4 bg-gray-200 hidden sm:block" />

            {/* Focus Mode — FASE 1H.2C */}
            <button type="button" onClick={() => setFocusMode((f) => !f)}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-all ${
                focusMode ? 'bg-blue-600 text-white shadow-sm' : 'text-ct-text2 bg-ct-card border border-ct-border hover:border-blue-300 hover:text-blue-600'
              }`}
              title={focusMode ? 'Salir de modo foco (Esc)' : 'Enfocar matriz — oculta elementos no esenciales'}>
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 001.934 12c1.293 4.338 5.31 7.68 10.066 7.68.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.32c4.756 0 8.773 3.342 10.065 7.68a10.462 10.462 0 01-1.8 3.064M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              {focusMode ? 'Salir foco' : 'Enfocar'}
            </button>

            <div className="ml-auto flex items-center gap-2">
              {!focusMode && (
              <button type="button"
                onClick={() => setFactStatusOpen((o) => !o)}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-all border ${factStatusOpen ? 'bg-slate-800 text-white border-slate-800' : 'text-ct-text2 bg-ct-card border-ct-border hover:border-gray-300 hover:bg-ct-bg'}`}
                title="Ver estado de materialización de FACT tables">
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 7v10c0 2 1 3 3 3h10c2 0 3-1 3-3V7M4 7c0-2 1-3 3-3h10c2 0 3 1 3 3M4 7h16" />
                </svg>
                FACT tables
              </button>
              )}
              {(rows.length > 0 || (isProjectionMode && projectionRows.length > 0)) && (
                <>
                  <div className="w-px h-4 bg-gray-200" />
                  <button type="button" onClick={handleExport}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-ct-text2 bg-ct-card border border-ct-border hover:border-gray-300 hover:bg-ct-bg transition-all"
                    title="Descargar Omniview Matrix (CSV)">
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5m0 0l5-5m-5 5V3" />
                    </svg>
                    Descargar
                  </button>
                  <button type="button" onClick={() => { userHasScrolledRef.current = false; scrollToCurrentPeriod() }}
                    className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium text-blue-700 bg-blue-50 border border-blue-200 hover:bg-blue-100 hover:border-blue-300 transition-all"
                    title={isProjectionMode && closedPeriodAnchor ? getAnchorButtonLabel(grain, closedPeriodAnchor.isCalendarCurrentPartial) : grain === 'daily' ? 'Ir a hoy' : grain === 'weekly' ? 'Ir a semana actual' : 'Ir a mes actual'}>
                    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {isProjectionMode && closedPeriodAnchor ? getAnchorButtonLabel(grain, closedPeriodAnchor.isCalendarCurrentPartial) : grain === 'daily' ? 'Ir a hoy' : grain === 'weekly' ? 'Ir a sem. actual' : 'Ir a mes actual'}
                  </button>
                </>
              )}
            </div>
          </div>

          {blockedByCountry && heavyQueriesEnabled && (
            <div className="px-4 py-2 text-xs text-amber-800 bg-amber-50 border-t border-amber-100 font-medium flex items-center gap-2">
              <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z" />
              </svg>
              {isProjectionMode ? (
                <>Selecciona un <strong className="mx-0.5">país</strong> para derivar la proyección semanal o diaria desde el plan mensual.</>
              ) : (
                <>Selecciona un <strong className="mx-0.5">país</strong> para habilitar el análisis semanal o diario.</>
              )}
            </div>
          )}

          {factStatusOpen && (
            <div className="mt-3">
              <FactStatusPanel onClose={() => setFactStatusOpen(false)} />
            </div>
          )}

          {MANUAL_LOAD && !heavyQueriesEnabled && (
            <div className="mt-3 rounded-lg border border-ct-border bg-gradient-to-br from-slate-50 to-white px-6 py-6 flex flex-col items-center gap-4 text-center shadow-sm">
              <div className="w-10 h-10 rounded-full bg-ct-surface flex items-center justify-center">
                <svg className="w-5 h-5 text-ct-text2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5M9 11.25v1.5M12 9v3.75m3-6v6" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-semibold text-ct-text">Omniview Matrix — carga diferida</p>
                <p className="mt-1 text-xs text-ct-text2 max-w-sm">
                  No se ejecutan consultas a la base de datos hasta que pulses el botón. Ajusta los filtros y carga cuando estés listo.
                </p>
                {blockedByCountry && (
                  <p className="mt-2 text-xs font-medium text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-1">
                    Selecciona un país para habilitar el grano semanal o diario.
                  </p>
                )}
              </div>
              <button
                type="button"
                disabled={blockedByCountry}
                onClick={() => setHeavyQueriesEnabled(true)}
                className="px-6 py-2 rounded-lg text-sm font-semibold bg-ct-nav text-white hover:bg-slate-700 transition-colors shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Cargar datos
              </button>
            </div>
          )}
        </div>

        {/* ── Barra de actividad: muestra qué requests están en vuelo + botón Detener ── */}
        {activeTasks.length > 0 && (
          <div className="mt-2 flex items-center gap-2.5 px-3 py-1.5 rounded-lg border border-blue-100 bg-blue-50 text-xs text-blue-700">
            <span className="inline-block w-3 h-3 border-[1.5px] border-blue-300 border-t-blue-600 rounded-full animate-spin flex-shrink-0" />
            <span className="flex-1 min-w-0 truncate font-medium">
              {activeTasks.join(' · ')}
            </span>
            <button
              type="button"
              onClick={cancelAll}
              className="flex-shrink-0 px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-100 hover:bg-red-100 hover:text-red-700 text-blue-700 border border-blue-200 hover:border-red-200 transition-colors"
              title="Cancelar todas las consultas en vuelo"
            >
              Detener
            </button>
          </div>
        )}

        {!focusMode && heavyQueriesEnabled && !blockedByCountry && !isProjectionMode && (
          <OperationalStatusBar
            grain={grain} periodStates={periodStates} allPeriods={matrix.allPeriods}
            freshnessInfo={freshnessInfo} sliceMaxTripDate={sliceMaxTripDate}
            coverageSummary={coverageSummary} matrixMeta={matrixMeta}
            matrixTrust={matrixTrust} execKpis={execKpis}
            compact={compact}
          />
        )}
        {sliceRealFreshnessBanner}

        {/* ── Capa de integridad (Vs Proyección) — FASE 3.7 ───── */}
        {!focusMode && heavyQueriesEnabled && isProjectionMode && projectionReady && projectionMeta?.integrity_status && (
          <ProjectionIntegrityBanner integrity={projectionMeta.integrity_status} compact={compact} />
        )}

        {/* ── YTD resumido (Vs Proyección) — FASE 3.5 ─────────── */}
        {!focusMode && heavyQueriesEnabled && isProjectionMode && projectionReady && !projectionContractReport.ok && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-2.5 text-xs text-amber-950 shadow-sm">
            <span className="font-semibold">Datos de proyección incompletos. </span>
            <span>{projectionContractReport.issues.map((it) => it.message).join(' · ')}</span>
            <span className="text-amber-800/90"> Revisa la consola para detalle.</span>
          </div>
        )}

        {!focusMode && heavyQueriesEnabled && isProjectionMode && projectionMeta?.ytd_summary && !projectionMeta.ytd_summary.error && (
          <ProjectionYtdSummaryBar ytd={projectionMeta.ytd_summary} grain={grain} compact={compact} />
        )}

        {!focusMode && heavyQueriesEnabled && isProjectionMode && Array.isArray(projectionMeta?.ytd_alerts) && projectionMeta.ytd_alerts.length > 0 && !projectionIntegrityBroken && (
          <ProjectionYtdAlertsBlock alerts={projectionMeta.ytd_alerts} compact={compact} />
        )}

        {!focusMode && heavyQueriesEnabled && isProjectionMode && projectionReady && projectionMeta && (
          <OperationalOpportunitiesSummary projectionMeta={projectionMeta} compact={compact} />
        )}

        {/* ── Freshness Governance (CF-H1D) ──────────────────── */}
        {!focusMode && heavyQueriesEnabled && isProjectionMode && (
          <OmniviewFreshnessGovernanceCard compact={compact} />
        )}

        {/* ── Context bar (Vs Proyección) ─────────────────────── */}
        {!focusMode && heavyQueriesEnabled && isProjectionMode && (
          <ProjectionContextBar
            grain={grain} projMatrix={projMatrix} projectionMeta={projectionMeta}
            planVersion={planVersion} compact={compact}
            focusedKpi={focusedKpi} closedPeriodAnchor={closedPeriodAnchor}
          />
        )}

        {/* ── Operational Priority Layer (RC-1) ───────────────── */}
        {!focusMode && heavyQueriesEnabled && isProjectionMode && projectionReady && (
          <OperationalPriorityLayer
            projMatrix={displayProjMatrix}
            focusedKpi={focusedKpi}
            grain={grain}
            compact={compact}
            onCellNavigate={(cellId, nav) => {
              setSelectedCell(cellId)
              setSelection({
                id: cellId,
                cityKey: nav.cityKey,
                lineKey: nav.lineKey,
                period: nav.period,
                kpiKey: nav.kpiKey,
                lineData: nav.lineData,
                periodDeltas: nav.periodDeltas,
                raw: nav.raw,
              })
            }}
          />
        )}

        {/* ── Badge de filas no mapeadas (interactivo) ───────────────────── */}
        {!focusMode && heavyQueriesEnabled && projectionReady && isProjectionMode && projectionMeta?.unresolved?.count > 0 && (
          <UnmappedBadge
            count={projectionMeta.unresolved.count}
            rows={projectionMeta.unresolved.rows}
            planVersion={planVersion}
          />
        )}

        {/* ── KPI focus mode ── merged into controls row (inline) ── */}

        {/* ── Insights Panel (additive, between focus and Matrix) ── */}
        {!focusMode && heavyQueriesEnabled && !blockedByCountry && !isProjectionMode && insights.length > 0 && (
          <BusinessSliceInsightsPanel
            insights={insights}
            onInsightClick={handleInsightClick}
            compact={compact}
            transparency={engineConfig.transparency}
            defaultTopN={engineConfig.panelTopN ?? 10}
            onOpenSettings={() => setInsightSettingsOpen(true)}
            onUserPatchPersist={refreshInsightPatch}
          />
        )}

        <BusinessSliceInsightSettings
          open={insightSettingsOpen}
          onClose={() => setInsightSettingsOpen(false)}
          userPatch={insightUserPatch}
          onSaved={refreshInsightPatch}
        />

        {err && heavyQueriesEnabled && !blockedByCountry && (
          <SmartEmptyState
            kind="loading_failed"
            title="Error al cargar datos"
            message={String(err)}
            actionLabel="Reintentar"
            onAction={loadData}
          />
        )}

        {loading && heavyQueriesEnabled && (
          <OmniviewMatrixSkeleton rows={compact ? 12 : 8} />
        )}

        {/* ── Action Context (contexto operacional al seleccionar) — FASE 1H.3 ── */}
        {!focusMode && selection && heavyQueriesEnabled && !loading && !blockedByCountry && (
          <ActionContext
            selection={selection}
            grain={grain}
            onFilter={(type, value) => {
              if (type === 'city') setCity(value)
              else if (type === 'country') setCountry(value)
              else if (type === 'slice') setBusinessSlice(value)
            }}
          />
        )}

        {/* ── Matrix + Inspector (Evolución) — FASE 1H.3 fullscreen ── */}
        {heavyQueriesEnabled && !loading && !blockedByCountry && !isProjectionMode && rows.length > 0 && (
          matrixFullscreen ? (
            <div className="fixed inset-0 z-[100] bg-white overflow-y-auto" role="dialog" aria-modal="true" aria-label="Omniview Matrix — pantalla completa">
              <div className="max-w-full mx-auto p-3 sm:p-4">
                <div className="flex items-center justify-between mb-2 px-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Omniview Matrix · {grain === 'monthly' ? 'Mensual' : grain === 'weekly' ? 'Semanal' : 'Diario'}</span>
                    {selection && <span className="text-[10px] text-blue-600">· Celda seleccionada</span>}
                  </div>
                  <button type="button" onClick={() => setMatrixFullscreen(false)}
                    className="text-gray-400 hover:text-gray-700 text-sm font-medium flex items-center gap-1">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 0v12" />
                    </svg>
                    Salir (Esc)
                  </button>
                </div>
                <div className="flex gap-3 items-start">
                  <div className="flex-1 min-w-0">
                    <BusinessSliceOmniviewMatrixTable
                      matrix={displayMatrix} grain={grain} compact={compact} sortKey={sortKey}
                      onCellClick={handleCellClick} selectedCell={selectedCell}
                      insightCellMap={insightCellMap} insightMode={insightMode}
                      lineImpactMap={lineImpactMap} periodStates={periodStates}
                      temporalTiers={temporalTiers}
                      matrixTrust={matrixTrust}
                      focusedKpi={focusedKpi}
                      currentPeriodKey={operationalCurrentPeriodKey}
                      calendarCurrentPeriodKey={isProjectionMode ? currentPeriodKey : undefined}
                      scrollContainerRef={scrollContainerRef}
                      isFullscreen={true}
                    />
                  </div>
                  <BusinessSliceOmniviewInspector
                    selection={selection} grain={grain} compact={compact}
                    onClose={() => { setSelection(null); setSelectedCell(null); setSelectionHistory([]) }}
                    insightForSelection={insightForSelection}
                    insightTransparency={engineConfig.transparency}
                    periodStates={periodStates} coverageSummary={coverageSummary}
                    matrixTrust={matrixTrust}
                    matrixMeta={matrixMeta}
                    onTrustStateRefresh={refreshMatrixTrust}
                    selectionHistory={selectionHistory}
                    onGoBack={(prev) => { setSelection(prev); setSelectedCell(prev.id); setSelectionHistory(h => h.filter(s => s.id !== prev.id)) }}
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className={`flex gap-3 items-start transition-opacity duration-200 ${focusMode ? 'opacity-95' : ''}`}>
              <div className="flex-1 min-w-0" style={matrixZoom !== 100 ? { transform: `scale(${matrixZoom / 100})`, transformOrigin: 'top left', width: `${(100 / matrixZoom) * 100}%` } : undefined}>
                {!focusMode && (
                  <div className="flex items-center gap-2 mb-1.5">
                    <button type="button" onClick={() => setMatrixFullscreen(true)}
                      className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                      title="Pantalla completa (Esc para salir)">
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                      </svg>
                      Pantalla completa
                    </button>
                  </div>
                )}
                <BusinessSliceOmniviewMatrixTable
                  matrix={displayMatrix} grain={grain} compact={compact} sortKey={sortKey}
                  onCellClick={handleCellClick} selectedCell={selectedCell}
                  insightCellMap={insightCellMap} insightMode={insightMode}
                  lineImpactMap={lineImpactMap} periodStates={periodStates}
                  temporalTiers={temporalTiers}
                  matrixTrust={matrixTrust}
                  focusedKpi={focusedKpi}
                  currentPeriodKey={operationalCurrentPeriodKey}
                      calendarCurrentPeriodKey={isProjectionMode ? currentPeriodKey : undefined}
                  scrollContainerRef={scrollContainerRef}
                />
              </div>
              {!focusMode && (
                <BusinessSliceOmniviewInspector
                  selection={selection} grain={grain} compact={compact}
                  onClose={() => { setSelection(null); setSelectedCell(null); setSelectionHistory([]) }}
                  insightForSelection={insightForSelection}
                  insightTransparency={engineConfig.transparency}
                  periodStates={periodStates} coverageSummary={coverageSummary}
                  matrixTrust={matrixTrust}
                  matrixMeta={matrixMeta}
                  onTrustStateRefresh={refreshMatrixTrust}
                  selectionHistory={selectionHistory}
                  onGoBack={(prev) => { setSelection(prev); setSelectedCell(prev.id); setSelectionHistory(h => h.filter(s => s.id !== prev.id)) }}
                />
              )}
            </div>
          )
        )}

        {/* ── Empty state Evolution — FASE 1H.3 ── */}
        {heavyQueriesEnabled && !loading && !blockedByCountry && !isProjectionMode && rows.length === 0 && !err && (
          <SmartEmptyState
            kind="empty_result"
            title="Sin datos disponibles"
            message="No se encontraron datos para los filtros y grano seleccionados."
            actionHint="Prueba cambiando el grano a mensual, o ajusta los filtros de país/ciudad/tajada."
          />
        )}

        {/* ── Prioridades del periodo (Vs Proyección) — FASE 3.3 ───── */}
        {!focusMode && heavyQueriesEnabled && projectionReady && isProjectionMode && perspective === 'operational' && projMatrix && projectionRows.length > 0 && !projectionIntegrityBroken && (
          <OmniviewPriorityPanel
            projMatrix={projMatrix}
            focusedKpi={focusedKpi}
            grain={grain}
            compact={compact}
            onCellNavigate={handleCellClick}
          />
        )}

        {/* ── FASE 1.1: Ownership Perspective View ────────────────────── */}
        {heavyQueriesEnabled && isProjectionMode && perspective === 'ownership' && planVersion && (
          <div className="px-4 py-4">
            <OwnershipServingView
              rows={ownershipRows}
              byOwner={ownershipByOwner}
              loading={ownershipLoading}
              error={ownershipError}
            />
          </div>
        )}

        {/* ── Matrix + Drill (Vs Proyección) — FASE 1H.3 fullscreen ── */}
        {heavyQueriesEnabled && projectionReady && isProjectionMode && perspective === 'operational' && projMatrix && projectionRows.length > 0 && (
          matrixFullscreen ? (
            <div className="fixed inset-0 z-[100] bg-white overflow-y-auto" role="dialog" aria-modal="true" aria-label="Omniview Proyección — pantalla completa">
              <div className="max-w-full mx-auto p-3 sm:p-4">
                <div className="flex items-center justify-between mb-2 px-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Vs Proyección · {grain === 'monthly' ? 'Mensual' : grain === 'weekly' ? 'Semanal' : 'Diario'}</span>
                    {selection && <span className="text-[10px] text-blue-600">· Celda seleccionada</span>}
                  </div>
                  <button type="button" onClick={() => setMatrixFullscreen(false)}
                    className="text-gray-400 hover:text-gray-700 text-sm font-medium flex items-center gap-1">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 0v12" />
                    </svg>
                    Salir (Esc)
                  </button>
                </div>
                <div className="flex gap-3 items-start">
                  <div className="flex-1 min-w-0">
                    {projectionIntegrityBroken && (
                      <div className="mb-2 rounded-md border border-red-200 bg-red-50/80 px-3 py-2 text-[11px] text-red-900" role="note">
                        <strong>Integridad rota:</strong> puedes revisar la tabla como referencia, pero no tomes decisiones con alertas o prioridades automáticas hasta que el estado vuelva a confiable.
                      </div>
                    )}
                    <BusinessSliceOmniviewMatrixTable
                      matrix={displayProjMatrix} grain={grain} compact={compact} sortKey={sortKey}
                      onCellClick={handleCellClick} selectedCell={selectedCell}
                      periodStates={periodStates}
                      temporalTiers={temporalTiers}
                      focusedKpi={focusedKpi}
                      mode="projection"
                      projectionAuthoritativeYtd={projectionMeta?.authoritative_ytd}
                      projectionIntegrityBroken={projectionIntegrityBroken}
                      currentPeriodKey={operationalCurrentPeriodKey}
                      calendarCurrentPeriodKey={isProjectionMode ? currentPeriodKey : undefined}
                      scrollContainerRef={scrollContainerRef}
                      isFullscreen={true}
                    />
                  </div>
                  <OmniviewProjectionDrill
                    selection={selection} grain={grain} compact={compact}
                    onClose={() => { setSelection(null); setSelectedCell(null) }}
                    projectionMeta={projectionMeta}
                    planVersion={planVersion}
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className={`flex gap-3 items-start transition-opacity duration-200 ${focusMode ? 'opacity-95' : ''}`}>
              <div className="flex-1 min-w-0" style={matrixZoom !== 100 ? { transform: `scale(${matrixZoom / 100})`, transformOrigin: 'top left', width: `${(100 / matrixZoom) * 100}%` } : undefined}>
                {!focusMode && (
                  <div className="flex items-center gap-2 mb-1.5">
                    <button type="button" onClick={() => setMatrixFullscreen(true)}
                      className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                      title="Pantalla completa (Esc para salir)">
                      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                      </svg>
                      Pantalla completa
                    </button>
                  </div>
                )}
                {projectionIntegrityBroken && (
                  <div className="mb-2 rounded-md border border-red-200 bg-red-50/80 px-3 py-2 text-[11px] text-red-900" role="note">
                    <strong>Integridad rota:</strong> puedes revisar la tabla como referencia, pero no tomes decisiones con alertas o prioridades automáticas hasta que el estado vuelva a confiable.
                  </div>
                )}
                <BusinessSliceOmniviewMatrixTable
                  matrix={displayProjMatrix} grain={grain} compact={compact} sortKey={sortKey}
                  onCellClick={handleCellClick} selectedCell={selectedCell}
                  periodStates={periodStates}
                  temporalTiers={temporalTiers}
                  focusedKpi={focusedKpi}
                  mode="projection"
                  projectionAuthoritativeYtd={projectionMeta?.authoritative_ytd}
                  projectionIntegrityBroken={projectionIntegrityBroken}
                  currentPeriodKey={operationalCurrentPeriodKey}
                  calendarCurrentPeriodKey={isProjectionMode ? currentPeriodKey : undefined}
                  scrollContainerRef={scrollContainerRef}
                />
              </div>
              {!focusMode && (
                <OmniviewProjectionDrill
                  selection={selection} grain={grain} compact={compact}
                  onClose={() => { setSelection(null); setSelectedCell(null) }}
                  projectionMeta={projectionMeta}
                  planVersion={planVersion}
                />
              )}
            </div>
          )
        )}

        {/* ── Plan sin ejecución real (sección QA) ───────────────── */}
        {!focusMode && heavyQueriesEnabled && projectionReady && isProjectionMode && projectionMeta?.plan_without_real?.count > 0 && (
          <PlanWithoutRealSection
            rows={projectionMeta.plan_without_real.rows}
            count={projectionMeta.plan_without_real.count}
            grain={grain}
            planVersion={planVersion}
          />
        )}

        {/* ── Estadísticas de reconciliación ─────────────────────── */}
        {!focusMode && heavyQueriesEnabled && projectionReady && isProjectionMode && projectionMeta?.reconciliation && (
          <ReconciliationSummaryBar reconciliation={projectionMeta.reconciliation} />
        )}

        {/* ── Sin proyección cargada — FASE 1H.3 SmartEmptyState ── */}
        {heavyQueriesEnabled && projectionReady && isProjectionMode && planVersions.length === 0 && (
          <SmartEmptyState
            kind="not_configured"
            title="No hay proyección cargada"
            message="Para activar la comparación Plan vs Real, sube un archivo de proyección en formato Ruta 27 (CSV o Excel)."
          >
            <button
              type="button"
              onClick={() => { setUploadModalOpen(true); setUploadError(null); setUploadSuccess(null) }}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-colors shadow-sm"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
              Subir archivo de proyección
            </button>
          </SmartEmptyState>
        )}
        {heavyQueriesEnabled && projectionReady && isProjectionMode && planVersions.length > 0 && !planVersion && (
          <SmartEmptyState
            kind="needs_filter"
            title="Selecciona una versión de plan"
            message="Para ver la comparación Plan vs Real, selecciona una versión de proyección en el selector de arriba."
          />
        )}
        {projectionEmptyKind === 'needs_country' && (
          <SmartEmptyState
            kind="needs_filter"
            title="Selecciona un país"
            message="Para semanal o diario en Vs Proyección hace falta país: la meta se deriva del plan mensual y el real se filtra por país."
          />
        )}
        {projectionEmptyKind === 'plan_without_real' && (
          <SmartEmptyState
            kind="empty_result"
            title="Hay proyección cargada pero no hay ejecución asociada"
            message={(grain === 'weekly' || grain === 'daily')
              ? 'Proyección derivada desde el plan mensual, sin ejecución real aún para estos filtros. Revisa reconciliación y el panel "Plan sin ejecución".'
              : 'El backend reporta plan sin filas reales coincidentes para estos filtros. Revisa reconciliación y el panel "Plan sin ejecución" abajo, o los logs del servidor.'}
          />
        )}
        {projectionEmptyKind === 'no_data' && (
          <SmartEmptyState
            kind="no_data"
            title="Sin datos de proyección"
            message="No hay datos de proyección para la versión seleccionada con los filtros actuales."
          />
        )}
      </div>

      {/* ── Modal subida de proyección ──────────────────────────── */}
      {uploadModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="w-full max-w-md bg-ct-card rounded-2xl shadow-2xl border border-ct-border overflow-hidden">
            {/* Header */}
            <div className="px-6 py-4 border-b border-ct-border flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center">
                  <svg className="w-4 h-4 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                </div>
                <div>
                  <p className="text-sm font-semibold text-ct-text">Subir archivo de proyección</p>
                  <p className="text-[11px] text-ct-text2">Formato Ruta 27 · CSV o Excel</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => { setUploadModalOpen(false); setUploadFile(null); setUploadError(null); setUploadSuccess(null) }}
                className="text-ct-text3 hover:text-ct-text transition-colors p-1 rounded"
                disabled={uploadLoading}
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Body */}
            <div className="px-6 py-5 space-y-4">
              {/* Zona de selección de archivo */}
              <div
                className="border-2 border-dashed border-ct-border rounded-lg p-6 text-center cursor-pointer hover:border-blue-300 hover:bg-blue-50/30 transition-colors group"
                onClick={() => uploadInputRef.current?.click()}
              >
                <svg className="w-8 h-8 text-ct-text3 group-hover:text-blue-400 mx-auto mb-2 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m6.75 12H9m1.5-12H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
                {uploadFile ? (
                  <div>
                    <p className="text-sm font-semibold text-blue-700">{uploadFile.name}</p>
                    <p className="text-[11px] text-ct-text3 mt-0.5">{(uploadFile.size / 1024).toFixed(1)} KB · Haz clic para cambiar</p>
                  </div>
                ) : (
                  <div>
                    <p className="text-sm text-ct-text2 font-medium">Haz clic para seleccionar archivo</p>
                    <p className="text-[11px] text-ct-text3 mt-0.5">CSV o Excel (.xlsx) · Formato Ruta 27</p>
                  </div>
                )}
                <input
                  ref={uploadInputRef}
                  type="file"
                  className="hidden"
                  accept=".csv,.xlsx,.xls"
                  onChange={(e) => { setUploadFile(e.target.files?.[0] || null); setUploadError(null) }}
                />
              </div>

              {/* Formatos aceptados */}
              <div className="bg-ct-bg rounded-lg px-3 py-2.5 space-y-2.5">
                <p className="text-[10px] font-semibold text-ct-text2 uppercase tracking-wide">Formatos aceptados</p>
                <div className="space-y-1.5">
                  <div className="flex items-start gap-2">
                    <span className="mt-0.5 flex-shrink-0 w-4 h-4 rounded bg-blue-100 text-blue-700 text-[9px] font-bold flex items-center justify-center">1</span>
                    <div>
                      <p className="text-[10px] font-semibold text-ct-text">Plantilla Control Tower (Excel multi-hoja)</p>
                      <p className="text-[10px] text-ct-text2 leading-relaxed">
                        Hojas: <span className="font-mono">TRIPS · REVENUE · DRIVERS</span><br />
                        Columnas fijas: <span className="font-mono">country, city, linea_negocio</span><br />
                        Columnas de meses: <span className="font-mono">2026-01, 2026-02…</span>
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-2">
                    <span className="mt-0.5 flex-shrink-0 w-4 h-4 rounded bg-gray-200 text-ct-text text-[9px] font-bold flex items-center justify-center">2</span>
                    <div>
                      <p className="text-[10px] font-semibold text-ct-text">Formato long/tabular Ruta 27 (CSV o Excel)</p>
                      <p className="text-[10px] text-ct-text2 font-mono leading-relaxed">
                        country, city, lob_base, segment,<br />
                        year, month, trips_plan,<br />
                        active_drivers_plan, avg_ticket_plan
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Error */}
              {uploadError && (
                <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-lg px-3 py-2.5">
                  <svg className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                  </svg>
                  <p className="text-xs text-red-700">{uploadError}</p>
                </div>
              )}

              {/* Éxito */}
              {uploadSuccess && (
                <div className="bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2.5 space-y-1">
                  <div className="flex items-start gap-2">
                    <svg className="w-4 h-4 text-emerald-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-semibold text-emerald-800">{uploadSuccess.plan_version}</p>
                      <p className="text-[11px] text-emerald-600">
                        {uploadSuccess.rows_inserted?.toLocaleString()} registros cargados
                        {uploadSuccess.format_detected === 'plantilla_control_tower' && (
                          <span className="ml-1.5 px-1 py-px bg-emerald-100 rounded text-[9px] font-semibold">Plantilla CT</span>
                        )}
                      </p>
                    </div>
                  </div>
                  {uploadSuccess.warnings?.length > 0 && (
                    <div className="pl-6 space-y-0.5">
                      {uploadSuccess.warnings.map((w, i) => (
                        <p key={i} className="text-[10px] text-amber-700">{w}</p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-ct-border space-y-2">
              {uploadLoading && (
                <div className="flex items-center gap-2 text-[11px] text-blue-700 bg-blue-50 border border-blue-100 rounded-lg px-3 py-2">
                  <span className="inline-block w-3 h-3 border-[1.5px] border-blue-300 border-t-blue-600 rounded-full animate-spin flex-shrink-0" />
                  <span>Procesando archivo e insertando datos en la base de datos. Esto puede tardar hasta 2 minutos con conexión remota. No cierres esta ventana.</span>
                </div>
              )}
              <div className="flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => { setUploadModalOpen(false); setUploadFile(null); setUploadError(null); setUploadSuccess(null) }}
                  disabled={uploadLoading}
                  className="px-4 py-2 rounded-lg text-sm font-medium text-ct-text bg-gray-100 hover:bg-gray-200 transition-colors disabled:opacity-50"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleUploadSubmit}
                  disabled={!uploadFile || uploadLoading || !!uploadSuccess}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {uploadLoading ? (
                    <>
                      <span className="inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Procesando…
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                      </svg>
                      Subir proyección
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function OperationalOpportunitiesSummary ({ projectionMeta, compact }) {
  const py = compact ? 'py-1.5' : 'py-2'
  const opsSuggestions = Array.isArray(projectionMeta?.operational_suggestions) ? projectionMeta.operational_suggestions : []
  const ctxSuggestions = Array.isArray(projectionMeta?.contextual_suggestions) ? projectionMeta.contextual_suggestions : []
  const decisions = Array.isArray(projectionMeta?.decision_recommendations) ? projectionMeta.decision_recommendations : []
  const globalQueue = Array.isArray(projectionMeta?.global_strategic_queue) ? projectionMeta.global_strategic_queue : []

  const totalOpportunities = opsSuggestions.length + ctxSuggestions.length
  const byType = {
    operacionales: opsSuggestions.length,
    contextuales: ctxSuggestions.length,
  }

  const topProblems = [
    ...opsSuggestions.slice(0, 2).map((s) => ({ type: 'operacional', item: s })),
    ...ctxSuggestions.slice(0, 1).map((s) => ({ type: 'contextual', item: s })),
  ].slice(0, 3)

  if (totalOpportunities === 0) return null

  return (
    <div className={`rounded-lg border border-ct-border bg-ct-card shadow-sm px-4 ${py}`}>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-ct-text2">
            Oportunidades operativas
          </span>
          <span className="ml-2 text-[11px] text-ct-text">
            <strong>{totalOpportunities}</strong> detectadas
            {byType.operacionales > 0 && <span className="text-ct-text2"> · {byType.operacionales} operacionales</span>}
            {byType.contextuales > 0 && <span className="text-ct-text2"> · {byType.contextuales} contextuales</span>}
          </span>
        </div>
        <a
          href="/operacion/oportunidades"
          className="text-[11px] font-semibold text-blue-600 hover:text-blue-800 whitespace-nowrap"
        >
          Ir a Oportunidades Operativas →
        </a>
      </div>

      {topProblems.length > 0 && (
        <div className="mt-2 space-y-1">
          {topProblems.map((tp, i) => {
            const s = tp.item
            const headline = s?.recommended_action_name || s?.opportunity?.headline || `Oportunidad ${i + 1}`
            const city = s?.city || s?.country || ''
            const slice = s?.business_slice_name || s?.lob || ''
            return (
              <div key={i} className="flex items-center gap-2 text-[10px] text-ct-text">
                <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                  i === 0 ? 'bg-amber-500' : i === 1 ? 'bg-blue-500' : 'bg-slate-400'
                }`} />
                <span className="font-medium truncate max-w-[16rem]">{headline}</span>
                {(city || slice) && (
                  <span className="text-ct-text3 truncate hidden sm:inline">
                    {[city, slice].filter(Boolean).join(' · ')}
                  </span>
                )}
                <button
                  type="button"
                  className="ml-auto text-[10px] text-blue-600 hover:underline flex-shrink-0"
                  onClick={() => {
                    const evt = new CustomEvent('omniview:navigate-opportunity', { detail: { type: tp.type, index: i } })
                    window.dispatchEvent(evt)
                  }}
                >
                  Ver diagnóstico
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function OperationalContextBar ({ grain, periodStates, allPeriods, comparisonMeta, freshnessInfo, sliceMaxTripDate, coverageSummary, compact, matrixMeta, execKpis }) {
  const df = matrixMeta?.data_freshness
  const lagStr = df?.lag_days != null && df?.status !== 'broken' ? String(df.lag_days) : '—'
  const dataFreshnessLine = df?.max_data_date
    ? `Data al ${df.max_data_date} (lag: ${lagStr} días)`
    : `Data al — (lag: ${lagStr} días)`
  const dataFreshnessCls = df?.status === 'ok' ? 'text-emerald-800 font-semibold'
    : df?.status === 'warning' ? 'text-amber-800 font-semibold'
    : df?.status === 'stale' ? 'text-red-800 font-semibold'
    : 'text-ct-text font-semibold'
  const hasPartial = [...(periodStates?.values() || [])].some(
    (s) => s === PERIOD_STATES.PARTIAL || s === PERIOD_STATES.CURRENT_DAY || s === PERIOD_STATES.OPEN
  )
  const hasStale = [...(periodStates?.values() || [])].some((s) => s === PERIOD_STATES.STALE)
  const lastPeriod = allPeriods.length > 0 ? allPeriods[allPeriods.length - 1] : null
  const lastState = lastPeriod ? periodStates?.get(lastPeriod) : null
  const lastMeta = lastPeriod ? comparisonMeta?.get(lastPeriod) : null

  let compLabel = grain === 'weekly' ? 'Comparativo WoW cerrado'
    : grain === 'daily' ? 'Comparativo diario · mismo día semana anterior'
      : 'Comparativo MoM cerrado'
  if (lastMeta?.comparison_mode === 'weekly_partial_equivalent') {
    compLabel = 'Comparativo semanal parcial equivalente'
  } else if (lastMeta?.comparison_mode === 'monthly_partial_equivalent') {
    compLabel = 'Comparativo mensual parcial equivalente'
  } else if (lastMeta?.comparison_mode === 'daily_same_weekday') {
    compLabel = 'Comparativo diario · mismo día de semana'
  } else if (hasPartial) {
    compLabel = grain === 'weekly' ? 'Comparativo semanal · parcial vs cerrado'
      : grain === 'daily' ? 'Comparativo diario · mismo día semana anterior'
        : 'Comparativo mensual · parcial vs cerrado'
  }

  const elapsed = lastPeriod && (lastState === PERIOD_STATES.PARTIAL || lastState === PERIOD_STATES.CURRENT_DAY || lastState === PERIOD_STATES.OPEN)
    ? periodElapsedDays(lastPeriod, grain) : null
  const total = lastPeriod && elapsed ? periodTotalDays(lastPeriod, grain) : null

  const cov = coverageSummary
  const py = compact ? 'py-1' : 'py-1.5'

  return (
    <div className={`rounded-lg border border-ct-border bg-ct-surface shadow-sm px-4 ${py} flex flex-wrap items-center gap-x-4 gap-y-1`}>
      <span className="text-[10px] font-bold text-ct-text2 uppercase tracking-wider">Contexto</span>

      <span
        className={`text-[11px] ${dataFreshnessCls}`}
        title={df?.last_update_at ? `Última carga en facts: ${df.last_update_at}` : undefined}
      >
        {dataFreshnessLine}
        {df?.status && (
          <span className="ml-1.5 text-[9px] font-bold uppercase text-ct-text2">[{df.status}]</span>
        )}
      </span>

      <span className="text-[10px] text-ct-text">
        {compLabel}
      </span>

      {lastMeta?.is_partial_equivalent && (
        <span className="text-[10px] text-blue-700">
          {lastMeta.current_range_start} → {lastMeta.current_cutoff_date} vs {lastMeta.previous_equivalent_range_start} → {lastMeta.previous_equivalent_cutoff_date}
        </span>
      )}

      {lastMeta?.comparison_mode === 'daily_same_weekday' && (
        <span className="text-[10px] text-blue-700">
          Base operativa: mismo día de semana anterior
          {lastMeta.is_preliminary && <span className="text-amber-700 ml-1">(día actual en curso)</span>}
        </span>
      )}

      {hasPartial && elapsed != null && total != null && (
        <span className="inline-flex items-center gap-1 text-[10px] text-blue-700 font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-blue-500 inline-block" />
          Avance {elapsed}/{total} días
        </span>
      )}

      {hasStale && (
        <span className="inline-flex items-center gap-1 text-[10px] text-amber-700 font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500 inline-block" />
          Periodo stale detectado
        </span>
      )}

      {freshnessInfo && !df?.max_data_date && (
        <span
          className="text-[10px] text-ct-text2"
          title={sliceMaxTripDate ? `Business slice day_fact: ${sliceMaxTripDate}. ${freshnessInfo.message || ''}` : freshnessInfo.message}>
          Trust API: {sliceMaxTripDate || freshnessInfo.derived_max_date || '—'}
        </span>
      )}

      {cov && (cov.total_trips_real_raw ?? cov.total_trips) > 0 && (
        <span className="text-[10px] text-ct-text ml-auto flex items-center gap-2">
          <span title="Mapped / universo RAW (public.trips_unified)">
            Cobertura: <strong className={cov.coverage_pct >= 95 ? 'text-emerald-700' : cov.coverage_pct >= 80 ? 'text-amber-700' : 'text-red-700'}>{cov.coverage_pct}%</strong>
            <span className="text-ct-text3 font-normal"> RAW {(cov.total_trips_real_raw ?? cov.total_trips).toLocaleString()}</span>
          </span>
          {cov.unmapped_trips > 0 && (
            <span className="text-ct-text3">Sin mapear: {cov.unmapped_trips.toLocaleString()}</span>
          )}
          {cov.identity_check_ok === false && (
            <span className="text-amber-700" title="RAW vs resolved o conteos por estado">⚠ identidad</span>
          )}
        </span>
      )}

      {execKpis?.unmapped_trips_volume > 0 && (
        <span className="text-[10px] text-amber-800" title="Volumen en bucket UNMAPPED (calidad de mapeo, no LOB)">
          Sin mapear en vista: {execKpis.unmapped_trips_volume.toLocaleString()} viajes
          {execKpis.unmapped_share_of_trips != null && (
            <span className="text-ct-text2"> ({(execKpis.unmapped_share_of_trips * 100).toFixed(1)}% del volumen mostrado)</span>
          )}
        </span>
      )}

      {matrixMeta?.period_states?.length > 0 && (
        <span className="text-[10px] text-ct-text2 hidden lg:inline" title="State Engine: max por período en day_fact (no solo global)">
          Estados: backend · máx global {matrixMeta.slice_max_trip_date || '—'} · por período ✓
        </span>
      )}
    </div>
  )
}

function ProjectionIntegrityBanner ({ integrity, compact }) {
  if (!integrity) return null
  const py = compact ? 'py-1.5' : 'py-2.5'
  const base = `rounded-lg border shadow-sm px-4 ${py}`
  const st = integrity.status
  if (st === 'ok') {
    return (
      <div className={`${base} border-emerald-200 bg-emerald-50/95 text-emerald-950`} role="status">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px]">
          <span aria-hidden>🟢</span>
          <span className="font-bold">Sistema confiable</span>
          {integrity.checked_at && (
            <span className="text-emerald-900/75 tabular-nums text-[10px]">
              · verificado {integrity.checked_at}
            </span>
          )}
        </div>
      </div>
    )
  }
  if (st === 'warning') {
    return (
      <div className={`${base} border-amber-300 bg-amber-50 text-amber-950`} role="alert">
        <div className="flex flex-wrap items-start gap-2 text-[11px]">
          <span aria-hidden className="mt-0.5 flex-shrink-0">🟡</span>
          <div className="min-w-0 flex-1">
            <span className="font-bold">Datos parciales</span>
            {Array.isArray(integrity.issues) && integrity.issues.length > 0 && (
              <ul className="mt-1.5 list-disc list-inside text-[10px] text-amber-950 space-y-0.5">
                {integrity.issues.slice(0, 6).map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    )
  }
  return (
    <div className={`${base} border-red-400 bg-red-50 text-red-950`} role="alert">
      <div className="flex flex-wrap items-start gap-2 text-[11px]">
        <span aria-hidden className="mt-0.5 flex-shrink-0">🔴</span>
        <div className="min-w-0 flex-1">
          <span className="font-bold">Datos incompletos — no tomar decisiones</span>
          {Array.isArray(integrity.issues) && integrity.issues.length > 0 && (
            <ul className="mt-1.5 list-disc list-inside text-[10px] text-red-900 space-y-0.5">
              {integrity.issues.slice(0, 8).map((t, i) => (
                <li key={i}>{t}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}

const DRIVER_LABEL_ES = {
  volume: 'Volumen',
  productivity: 'Productividad',
  ticket: 'Ticket',
}

const SEGMENT_LABEL_ES = {
  low_activity_0_5_7d: '0–5 viajes / sem ISO',
  dormant_14d: 'Sin viaje 14d+',
  dormant_30d: 'Sin viaje 30d+',
  elite_degraded: 'Elite / alto valor en deterioro',
  onboarding_pending_first_trip: 'Onboarding pend. 1.er viaje',
  casual_low_engagement: 'Casual / PT bajo engagement',
  // compat legado FASE 4.2 previa
  '0_5_trips_last_7d': '0–5 viajes / sem ISO',
  pending_first_trip: 'Pendientes 1.er viaje'
}

function ProjectionContextualOperationalSuggestionsBlock ({ projectionMeta, compact }) {
  const py = compact ? 'py-1.5' : 'py-2'
  const items = Array.isArray(projectionMeta?.contextual_suggestions)
    ? projectionMeta.contextual_suggestions
    : []
  const integrityBroken = projectionMeta?.integrity_status?.status === 'broken'
  const chk = projectionMeta?.integrity_status?.checks || {}
  const ctxChk = chk.contextual_suggestions
  const auditSeg = chk.segment_registry
  const auditRec = chk.recovery_auditability
  const auditPool = chk.operational_pool_quality
  const top = items.slice(0, 3)

  const confidenceLabel = (v) => {
    const m = { high: 'Alta', medium: 'Media', low: 'Baja' }
    return m[v] || v || '—'
  }

  const fmtCtxLine = (c) => {
    if (!c || typeof c !== 'object') return null
    if (c.opportunity?.headline) {
      const comp = Array.isArray(c.opportunity.comparable_slice_labels) ? c.opportunity.comparable_slice_labels : []
      const compHint = comp.length ? ` · vs ${comp.slice(0, 2).join(', ')}` : ''
      return `${c.opportunity.headline}${compHint}`
    }
    const parts = []
    if (c.current_driver_productivity != null && c.expected_driver_productivity != null) {
      parts.push(`TPD ${Number(c.current_driver_productivity).toFixed(1)} vs esp. ${Number(c.expected_driver_productivity).toFixed(1)}`)
    }
    if (c.pending_first_trip_registrations != null) {
      parts.push(`Pend. 1.er viaje: ${Number(c.pending_first_trip_registrations).toLocaleString()}`)
    }
    if (c.estimated_supply_gap_drivers != null) {
      parts.push(`Gap supply (drv): ${Number(c.estimated_supply_gap_drivers).toFixed(0)}`)
    }
    if (c.avg_ticket_real_ytd != null && c.avg_ticket_expected_ytd != null) {
      parts.push(`Ticket ø R ${Number(c.avg_ticket_real_ytd).toFixed(2)} / E ${Number(c.avg_ticket_expected_ytd).toFixed(2)}`)
    }
    return parts.length ? parts.join(' · ') : null
  }

  if (integrityBroken) {
    return (
      <div className={`rounded-lg border border-ct-border bg-ct-card shadow-sm px-4 ${py}`}>
        <p className="text-[10px] font-bold uppercase tracking-wider text-ct-text mb-1">
          Sugerencias operativas contextualizadas
        </p>
        <p className="text-[11px] text-rose-800" role="status">
          Contextualización desactivada por integridad rota
        </p>
      </div>
    )
  }

  if (!items.length) return null

  return (
    <div className={`rounded-lg border border-violet-100 bg-violet-50/40 shadow-sm px-4 ${py}`}>
      <p className="text-[10px] font-bold uppercase tracking-wider text-violet-800 mb-2">
        Sugerencias operativas contextualizadas
      </p>
      {(ctxChk === 'partial' || auditSeg === 'partial' || auditRec === 'partial' || auditPool === 'partial') && (
        <div className="mb-2 rounded border border-amber-200 bg-amber-50 px-2 py-1 text-[9px] text-amber-950" role="status">
          Contexto auditado parcialmente (segmentos / recovery / pool). Revisa expansiones por tarjeta.
        </div>
      )}
      <ul className="space-y-2">
        {top.map((s) => {
          const pool = s.operational_pool || {}
          const segs = Array.isArray(pool.segments) ? pool.segments : []
          const rec = s.estimated_recovery || {}
          const ctx = s.operational_context || {}
          const ctxLine = fmtCtxLine(ctx)
          const reasoning = s.contextual_reasoning || {}
          const tc = Number(pool.total_candidates)
          const rc = pool.reachable_candidates != null ? Number(pool.reachable_candidates) : null
          const reachPct = rc != null && tc > 0 ? (100 * rc / tc).toFixed(1) : null
          const levBd = s.operational_leverage_breakdown || {}
          return (
            <li
              key={s.suggestion_id}
              className="rounded-md border border-violet-100 bg-ct-card/90 p-2.5 text-[11px] text-ct-text shadow-sm"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-1 mb-1">
                <span className="font-semibold text-ct-text">{s.entity}</span>
                <span className="text-[9px] text-violet-800 font-semibold tabular-nums">
                  Apalancamiento {s.operational_leverage_score ?? '—'}/100
                </span>
              </div>
              <p className="font-semibold text-violet-900 text-[11px] leading-snug mb-1">
                {s.recommended_action_name || s.action_type}
              </p>
              <div className="text-[10px] text-ct-text mb-1">
                <span className="text-ct-text3">Pool</span>{' '}
                <strong className="tabular-nums">{pool.total_candidates != null ? Number(pool.total_candidates).toLocaleString() : '—'}</strong>
                {reachPct != null && (
                  <span className="text-ct-text2 ml-1 tabular-nums">
                    · alcanzable ~{reachPct}%
                  </span>
                )}
                {pool.pool_method && (
                  <span className="text-ct-text3 ml-1">({pool.pool_method})</span>
                )}
              </div>
              {segs.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-1.5">
                  {segs.slice(0, 3).map((seg, i) => (
                    <span
                      key={`${s.suggestion_id}-seg-${i}`}
                      className="rounded bg-ct-surface px-1.5 py-px text-[9px] text-ct-text"
                    >
                      {SEGMENT_LABEL_ES[seg.segment_id] || SEGMENT_LABEL_ES[seg.segment] || seg.segment_id || seg.segment}:{' '}
                      <span className="font-bold tabular-nums">{seg.drivers != null ? seg.drivers : '—'}</span>
                    </span>
                  ))}
                </div>
              )}
              <p className="text-[10px] text-ct-text mb-1">
                <span className="text-ct-text3">Recup. est.</span>{' '}
                {rec.potential_trips_recovered_weekly != null
                  ? (
                    <span>
                      ~<strong className="tabular-nums">{Number(rec.potential_trips_recovered_weekly).toLocaleString()}</strong> trips/sem
                    </span>
                    )
                  : '—'}
                {rec.potential_gap_recovery_pct != null && (
                  <span className="text-ct-text2 tabular-nums">{` · ~${Number(rec.potential_gap_recovery_pct).toFixed(1)}% gap (orden magnitud)`}</span>
                )}
              </p>
              {rec.recovery_method && (
                <p className="text-[9px] text-violet-900/90 mb-1 font-medium">
                  Método: <span className="font-mono">{rec.recovery_method}</span>
                </p>
              )}
              {reasoning.main_problem_detected && (
                <p className="text-[9px] text-ct-text leading-snug mb-1.5 line-clamp-3" title={reasoning.main_problem_detected}>
                  <span className="text-ct-text3">Razonamiento</span> {reasoning.main_problem_detected}
                </p>
              )}
              {ctxLine && (
                <p className="text-[9px] text-ct-text leading-snug mb-1.5 line-clamp-2" title={ctxLine}>
                  <span className="text-ct-text3">Contexto</span> {ctxLine}
                </p>
              )}
              {Array.isArray(s.suggested_operational_focus) && s.suggested_operational_focus.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-1.5">
                  {s.suggested_operational_focus.slice(0, 4).map((f, fi) => (
                    <span
                      key={`${s.suggestion_id}-f-${fi}`}
                      className="rounded border border-ct-border/80 bg-ct-surface/90 px-1.5 py-px text-[8px] text-ct-text"
                    >
                      {f}
                    </span>
                  ))}
                </div>
              )}
              <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-[9px] text-ct-text mb-1.5">
                <span><span className="text-ct-text3">Prioridad</span> {s.priority_score ?? '—'}</span>
                <span><span className="text-ct-text3">Confianza</span> {confidenceLabel(s.confidence)}</span>
              </div>
              <details className="group mt-1 border-t border-ct-border pt-1.5 text-[9px] text-ct-text">
                <summary className="cursor-pointer list-none text-violet-800 font-semibold marker:content-none flex items-center gap-1">
                  <span aria-hidden>▸</span>
                  <span className="group-open:hidden">Cómo se estimó</span>
                  <span className="hidden group-open:inline">▼ Cómo se estimó</span>
                </summary>
                <div className="mt-1 space-y-1 pl-3 border-l border-violet-100">
                  {rec.confidence_reason && (
                    <p><span className="text-ct-text3">Confianza (por qué):</span> {rec.confidence_reason}</p>
                  )}
                  {rec.sample_size != null && (
                    <p className="tabular-nums"><span className="text-ct-text3">sample_size:</span> {rec.sample_size}</p>
                  )}
                  {rec.historical_reference_window && (
                    <p><span className="text-ct-text3">Ventana referencia:</span> {rec.historical_reference_window}</p>
                  )}
                  {Array.isArray(rec.assumptions_used) && rec.assumptions_used.length > 0 && (
                    <div>
                      <span className="text-ct-text3">Supuestos</span>
                      <ul className="list-disc list-inside text-[8px] space-y-0.5 mt-0.5">
                        {rec.assumptions_used.slice(0, 8).map((a, i) => (
                          <li key={i}>{typeof a === 'string' ? a : JSON.stringify(a)}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {Object.keys(levBd).length > 0 && (
                    <p className="text-[8px] text-ct-text2 leading-relaxed font-mono break-all">
                      leverage_breakdown: {JSON.stringify(levBd)}
                    </p>
                  )}
                  {reasoning.why_this_action && (
                    <p><span className="text-ct-text3">Por qué esta acción:</span> {reasoning.why_this_action}</p>
                  )}
                </div>
              </details>
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  disabled
                  className="cursor-not-allowed rounded border border-ct-border bg-ct-surface px-2 py-1 text-[9px] font-medium text-ct-text3"
                >
                  Ver detalle
                </button>
                <button
                  type="button"
                  disabled
                  className="cursor-not-allowed rounded border border-ct-border bg-ct-surface px-2 py-1 text-[9px] font-medium text-ct-text3"
                >
                  {s.next_step_preview?.entity_type === 'drivers'
                    ? 'Ver conductores afectados'
                    : s.next_step_preview?.entity_type === 'analysis'
                      ? 'Ver análisis de ticket'
                      : 'Ver slices comparables'}
                </button>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function ProjectionDecisionRecommendationsBlock ({ projectionMeta, compact }) {
  const py = compact ? 'py-1.5' : 'py-2'
  const items = Array.isArray(projectionMeta?.decision_recommendations)
    ? projectionMeta.decision_recommendations
    : []
  const integrityBroken = projectionMeta?.integrity_status?.status === 'broken'
  const chk = projectionMeta?.integrity_status?.checks || {}
  const decisionChk = chk.decision_policy_engine
  const ctxCount = Array.isArray(projectionMeta?.contextual_suggestions)
    ? projectionMeta.contextual_suggestions.length
    : 0

  const statusBadge = (st) => {
    if (st === 'recommended') {
      return (
        <span className="rounded bg-emerald-100 px-1.5 py-px text-[9px] font-bold uppercase text-emerald-950">
          Recomendada
        </span>
      )
    }
    if (st === 'alternative') {
      return (
        <span className="rounded bg-amber-100 px-1.5 py-px text-[9px] font-bold uppercase text-amber-950">
          Alternativa
        </span>
      )
    }
    return (
      <span className="rounded bg-ct-surface px-1.5 py-px text-[9px] font-bold uppercase text-ct-text">
        No recomendada
      </span>
    )
  }

  const confidenceLabel = (v) => {
    const m = { high: 'Alta', medium: 'Media', low: 'Baja' }
    return m[v] || v || '—'
  }

  if (integrityBroken) {
    return (
      <div className={`rounded-lg border border-ct-border bg-ct-card shadow-sm px-4 ${py}`}>
        <p className="text-[10px] font-bold uppercase tracking-wider text-ct-text mb-1">
          Recomendaciones priorizadas
        </p>
        <p className="text-[11px] text-rose-800" role="status">
          Motor de decisión inactivo por integridad rota
        </p>
      </div>
    )
  }

  if (!items.length) {
    if (ctxCount > 0 && decisionChk === 'missing') {
      return (
        <div className={`rounded-lg border border-amber-200 bg-amber-50/60 shadow-sm px-4 ${py}`}>
          <p className="text-[10px] font-bold uppercase tracking-wider text-amber-900 mb-1">
            Recomendaciones priorizadas
          </p>
          <p className="text-[11px] text-amber-950" role="status">
            Sin priorización disponible para este contexto (revisa integridad contextual o política decision_policy_engine).
          </p>
        </div>
      )
    }
    return null
  }

  const top = items.slice(0, 6)

  return (
    <div className={`rounded-lg border border-teal-100 bg-teal-50/35 shadow-sm px-4 ${py}`}>
      <p className="text-[10px] font-bold uppercase tracking-wider text-teal-900 mb-2">
        Recomendaciones priorizadas
      </p>
      {(decisionChk === 'partial' || projectionMeta?.integrity_status?.status === 'warning') && (
        <div className="mb-2 rounded border border-amber-200 bg-amber-50 px-2 py-1 text-[9px] text-amber-950" role="status">
          Priorización con señales parciales (confianza baja u otro chequeo incompleto). Usa como orden sugerido, no como automatismo.
        </div>
      )}
      <p className="text-[9px] text-teal-950/85 mb-2 leading-snug" role="note">
        Decision Engine informativo — ejecución no habilitada. No hay campañas, tareas ni APIs externas; la UI sólo muestra el orden sugerido del backend.
      </p>
      <ul className="space-y-2">
        {top.map((r) => {
          const act = r.recommended_action || {}
          const reasoning = r.decision_reasoning || {}
          const factors = r.decision_factors || {}
          const cons = r.decision_constraints || {}
          const alts = Array.isArray(r.alternatives) ? r.alternatives : []
          return (
            <li
              key={r.recommendation_id || `${r.entity}-${act.action_type}`}
              className="rounded-md border border-teal-100 bg-ct-card/90 p-2.5 text-[11px] text-ct-text shadow-sm"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-1 mb-1">
                <span className="font-semibold text-ct-text">{r.entity}</span>
                {statusBadge(r.decision_status)}
              </div>
              <p className="font-semibold text-teal-950 text-[11px] leading-snug mb-1">
                {act.action_name || act.action_type}
              </p>
              <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-ct-text mb-1">
                <span>
                  <span className="text-ct-text3">Score decisión</span>{' '}
                  <strong className="tabular-nums">{r.decision_score != null ? Number(r.decision_score).toFixed(1) : '—'}</strong>/100
                </span>
                <span>
                  <span className="text-ct-text3">Confianza datos</span> {confidenceLabel(cons.data_confidence)}
                </span>
                {cons.execution_enabled === false && (
                  <span className="text-ct-text2">Ejecución: desactivada</span>
                )}
              </div>
              {reasoning.why_selected && (
                <p className="text-[10px] text-ct-text leading-snug mb-1 line-clamp-3" title={reasoning.why_selected}>
                  <span className="text-ct-text3">Razón principal</span> {reasoning.why_selected}
                </p>
              )}
              {reasoning.expected_operational_benefit && (
                <p className="text-[9px] text-ct-text leading-snug mb-1 line-clamp-2">
                  <span className="text-ct-text3">Beneficio esperado</span> {reasoning.expected_operational_benefit}
                </p>
              )}
              {Array.isArray(reasoning.main_tradeoffs) && reasoning.main_tradeoffs.length > 0 && (
                <div className="text-[9px] text-ct-text mb-1">
                  <span className="text-ct-text3">Tradeoffs</span>{' '}
                  <span className="leading-snug">{reasoning.main_tradeoffs.slice(0, 3).join(' · ')}</span>
                </div>
              )}
              {alts.length > 0 && (
                <div className="flex flex-wrap gap-1 mb-1.5 text-[9px]">
                  <span className="text-ct-text3 w-full">Alternativas</span>
                  {alts.slice(0, 4).map((a, ai) => (
                    <span
                      key={`${r.recommendation_id}-alt-${ai}`}
                      className={`rounded px-1.5 py-px font-medium tabular-nums ${
                        a.decision_status === 'alternative'
                          ? 'border border-amber-200 bg-amber-50 text-amber-950'
                          : 'border border-ct-border bg-ct-surface text-ct-text'
                      }`}
                      title={a.action_name ? `${a.action_name} (${a.decision_status})` : a.decision_status}
                    >
                      {a.action_name || a.action_type}
                      {' '}
                      <span className="opacity-90">({a.decision_score != null ? Number(a.decision_score).toFixed(1) : '—'})</span>
                    </span>
                  ))}
                </div>
              )}
              <details className="group mt-1 border-t border-ct-border pt-1.5 text-[9px] text-ct-text">
                <summary className="cursor-pointer list-none text-teal-900 font-semibold marker:content-none flex items-center gap-1">
                  <span aria-hidden>▸</span>
                  <span className="group-open:hidden">Trazabilidad y desglose</span>
                  <span className="hidden group-open:inline">▼ Trazabilidad</span>
                </summary>
                <div className="mt-1 space-y-1 pl-3 border-l border-teal-100">
                  {r.policy_trace && (
                    <>
                      <p className="font-mono text-[8px] break-all">
                        policy: {r.policy_trace.policy_version} · {r.policy_trace.policy_type}
                      </p>
                      {Array.isArray(r.policy_trace.inputs_used) && r.policy_trace.inputs_used.length > 0 && (
                        <ul className="list-disc list-inside text-[8px] space-y-0.5">
                          {r.policy_trace.inputs_used.slice(0, 12).map((u, i) => (
                            <li key={i}>{typeof u === 'string' ? u : JSON.stringify(u)}</li>
                          ))}
                        </ul>
                      )}
                      {r.policy_trace.decision_score_breakdown && (
                        <p className="tabular-nums text-[8px]">
                          breakdown:{' '}
                          {JSON.stringify(r.policy_trace.decision_score_breakdown)}
                        </p>
                      )}
                    </>
                  )}
                  {Object.keys(factors).length > 0 && (
                    <p className="text-[8px] font-mono break-all leading-relaxed">
                      factores ponderados (impacto / vel. / simpl. compl. / conf. / efic. costo):{' '}
                      {JSON.stringify(factors)}
                    </p>
                  )}
                  {Array.isArray(reasoning.why_not_other_actions) && reasoning.why_not_other_actions.length > 0 && (
                    <div>
                      <span className="text-ct-text3">Por qué no otras acciones</span>
                      <ul className="list-disc list-inside text-[8px] space-y-0.5 mt-0.5">
                        {reasoning.why_not_other_actions.slice(0, 6).map((w, wi) => (
                          <li key={wi}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {alts.length > 0 && (
                    <div className="mt-1.5">
                      <span className="text-ct-text3">Lista completa de alternativas</span>
                      <ul className="mt-0.5 max-h-28 overflow-y-auto list-disc list-inside text-[8px] text-ct-text space-y-0.5 pr-1">
                        {alts.map((a, ai) => (
                          <li key={`${r.recommendation_id}-alta-${ai}`} className="tabular-nums">
                            <span className="font-medium text-ct-text">{a.action_name || a.action_type}</span>
                            {' '}
                            · score {a.decision_score != null ? Number(a.decision_score).toFixed(1) : '—'}
                            {' '}
                            · {a.decision_status === 'alternative' ? 'alternativa' : 'no recomendada'}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </details>
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                <button
                  type="button"
                  disabled
                  className="cursor-not-allowed rounded border border-ct-border bg-ct-surface px-2 py-1 text-[9px] font-medium text-ct-text3"
                >
                  Aceptar orden sugerido
                </button>
                <button
                  type="button"
                  disabled
                  className="cursor-not-allowed rounded border border-ct-border bg-ct-surface px-2 py-1 text-[9px] font-medium text-ct-text3"
                >
                  Enviar a operaciones
                </button>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

const PORTFOLIO_ROLE_LABEL_ES = {
  quick_win: 'Quick win',
  growth: 'Growth',
  structural: 'Estructural',
  defensive: 'Defensiva',
}

const PORTFOLIO_ROLE_BADGE = {
  quick_win: 'border-emerald-200 bg-emerald-50 text-emerald-900',
  growth: 'border-sky-200 bg-sky-50 text-sky-900',
  structural: 'border-violet-200 bg-violet-50 text-violet-900',
  defensive: 'border-amber-200 bg-amber-50 text-amber-900',
}

const OPERATIONAL_LOAD_LABEL_ES = {
  low: 'Carga baja',
  medium: 'Carga media',
  high: 'Carga alta',
}

function ProjectionGlobalStrategicQueueBlock ({ projectionMeta, compact }) {
  const py = compact ? 'py-1.5' : 'py-2'
  const queue = Array.isArray(projectionMeta?.global_decision_queue)
    ? projectionMeta.global_decision_queue
    : []
  const integrityBroken = projectionMeta?.integrity_status?.status === 'broken'
  const chk = projectionMeta?.integrity_status?.checks || {}
  const globalChk = chk.global_decision_engine
  const recoCount = Array.isArray(projectionMeta?.decision_recommendations)
    ? projectionMeta.decision_recommendations.length
    : 0

  const confidenceLabel = (v) => {
    const m = { high: 'Alta', medium: 'Media', low: 'Baja' }
    return m[v] || v || '—'
  }

  const entityLabel = (e) => {
    if (!e) return '—'
    if (e.label) return e.label
    const parts = [e.country, e.city, e.lob].filter(Boolean)
    if (e.segment) parts.push(`· ${e.segment}`)
    return parts.join(' · ') || '—'
  }

  if (integrityBroken) {
    return (
      <div className={`rounded-lg border border-ct-border bg-ct-card shadow-sm px-4 ${py}`}>
        <p className="text-[10px] font-bold uppercase tracking-wider text-ct-text mb-1">
          Prioridades estratégicas globales
        </p>
        <p className="text-[11px] text-rose-800" role="status">
          Layer global desactivado por integridad rota
        </p>
      </div>
    )
  }

  if (!queue.length) {
    if (recoCount > 0 && globalChk === 'missing') {
      return (
        <div className={`rounded-lg border border-amber-200 bg-amber-50/60 shadow-sm px-4 ${py}`}>
          <p className="text-[10px] font-bold uppercase tracking-wider text-amber-900 mb-1">
            Prioridades estratégicas globales
          </p>
          <p className="text-[11px] text-amber-950" role="status">
            Sin priorización global disponible (revisa integridad o el chequeo global_decision_engine).
          </p>
        </div>
      )
    }
    return null
  }

  const top = queue.slice(0, 8)
  const saturationSummary = top[0]?.global_policy_trace?.saturation_summary
  const hasSaturation =
    saturationSummary &&
    ((Array.isArray(saturationSummary.saturated_actions) && saturationSummary.saturated_actions.length > 0) ||
      (Array.isArray(saturationSummary.saturated_teams) && saturationSummary.saturated_teams.length > 0))

  return (
    <div className={`rounded-lg border border-indigo-100 bg-indigo-50/40 shadow-sm px-4 ${py}`}>
      <p className="text-[10px] font-bold uppercase tracking-wider text-indigo-900 mb-2">
        Prioridades estratégicas globales
      </p>
      {(globalChk === 'partial' || projectionMeta?.integrity_status?.status === 'warning') && (
        <div className="mb-2 rounded border border-amber-200 bg-amber-50 px-2 py-1 text-[9px] text-amber-950" role="status">
          Priorización global con señales parciales (confianza baja, saturación o inputs incompletos). Usar como orden sugerido, no como ejecución.
        </div>
      )}
      {hasSaturation && (
        <div className="mb-2 rounded border border-orange-200 bg-orange-50 px-2 py-1 text-[9px] text-orange-950" role="alert">
          Saturación detectada en cola:{' '}
          {Array.isArray(saturationSummary.saturated_actions) && saturationSummary.saturated_actions.length > 0 && (
            <span>
              acciones [{saturationSummary.saturated_actions.join(', ')}]
            </span>
          )}
          {Array.isArray(saturationSummary.saturated_teams) && saturationSummary.saturated_teams.length > 0 && (
            <span>
              {' '}equipos [{saturationSummary.saturated_teams.join(', ')}]
            </span>
          )}
          . Validar capacidad antes de cualquier ejecución manual.
        </div>
      )}
      <p className="text-[9px] text-indigo-950/85 mb-2 leading-snug" role="note">
        Global Decision Layer informativa — ejecución no habilitada. No hay automatización, campañas ni APIs externas; la UI sólo muestra el orden sugerido por el backend.
      </p>
      <ul className="space-y-2">
        {top.map((g) => {
          const ent = g.entity || {}
          const sel = g.selected_decision || {}
          const reasoning = g.global_decision_reasoning || {}
          const dims = g.priority_dimensions || {}
          const risks = g.decision_risks || {}
          const rp = g.resource_profile || {}
          const role = g.portfolio_role || {}
          const cons = g.decision_constraints || {}
          const trace = g.global_policy_trace || {}
          const breakdown = trace.score_breakdown || {}
          const teams = Array.isArray(rp.required_team_type) ? rp.required_team_type : []
          const roleClass = PORTFOLIO_ROLE_BADGE[role.role_type] || 'border-ct-border bg-ct-surface text-ct-text'
          return (
            <li
              key={g.global_recommendation_id || `${g.global_priority_rank}-${ent.label}`}
              className="rounded-md border border-indigo-100 bg-ct-card/95 p-2.5 text-[11px] text-ct-text shadow-sm"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-1 mb-1">
                <div className="flex items-baseline gap-2 min-w-0">
                  <span className="rounded bg-indigo-100 px-1.5 py-px text-[9px] font-bold text-indigo-950 tabular-nums">
                    #{g.global_priority_rank}
                  </span>
                  <span className="font-semibold text-ct-text truncate">
                    {entityLabel(ent)}
                  </span>
                </div>
                <span className={`rounded border px-1.5 py-px text-[9px] font-bold uppercase tracking-wide ${roleClass}`}>
                  {PORTFOLIO_ROLE_LABEL_ES[role.role_type] || role.role_type || '—'}
                </span>
              </div>
              <p className="font-semibold text-indigo-950 text-[11px] leading-snug mb-1">
                {sel.action_name || sel.action_type}
              </p>
              <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[10px] text-ct-text mb-1">
                <span>
                  <span className="text-ct-text3">Score global</span>{' '}
                  <strong className="tabular-nums">{g.global_decision_score != null ? Number(g.global_decision_score).toFixed(1) : '—'}</strong>/100
                </span>
                <span>
                  <span className="text-ct-text3">Confianza datos</span>{' '}
                  {confidenceLabel(cons.data_confidence)}
                </span>
                <span>
                  <span className="text-ct-text3">Carga</span>{' '}
                  {OPERATIONAL_LOAD_LABEL_ES[rp.estimated_operational_load] || rp.estimated_operational_load || '—'}
                </span>
                {cons.execution_enabled === false && (
                  <span className="text-ct-text2">Ejecución: desactivada</span>
                )}
              </div>
              {reasoning.why_prioritized_globally && (
                <p className="text-[10px] text-ct-text leading-snug mb-1 line-clamp-3" title={reasoning.why_prioritized_globally}>
                  <span className="text-ct-text3">Por qué priorizado</span> {reasoning.why_prioritized_globally}
                </p>
              )}
              {reasoning.expected_business_impact && (
                <p className="text-[9px] text-ct-text leading-snug mb-1 line-clamp-2">
                  <span className="text-ct-text3">Impacto esperado</span> {reasoning.expected_business_impact}
                </p>
              )}
              {reasoning.strategic_relevance && (
                <p className="text-[9px] text-ct-text leading-snug mb-1 line-clamp-2">
                  <span className="text-ct-text3">Relevancia estratégica</span> {reasoning.strategic_relevance}
                </p>
              )}
              {(teams.length > 0 || risks.operational_saturation_risk) && (
                <div className="flex flex-wrap items-center gap-1 mb-1.5">
                  {teams.slice(0, 4).map((t, ti) => (
                    <span
                      key={`${g.global_recommendation_id}-team-${ti}`}
                      className="rounded border border-ct-border bg-ct-surface/90 px-1.5 py-px text-[8px] text-ct-text"
                    >
                      {t}
                    </span>
                  ))}
                  {risks.operational_saturation_risk && /Saturaci\u00f3n V1/i.test(String(risks.operational_saturation_risk)) && (
                    <span className="rounded border border-orange-200 bg-orange-50 px-1.5 py-px text-[8px] text-orange-900">
                      saturación
                    </span>
                  )}
                </div>
              )}
              <details className="group mt-1 border-t border-ct-border pt-1.5 text-[9px] text-ct-text">
                <summary className="cursor-pointer list-none text-indigo-900 font-semibold marker:content-none flex items-center gap-1">
                  <span aria-hidden>▸</span>
                  <span className="group-open:hidden">Detalles, riesgos y trazabilidad</span>
                  <span className="hidden group-open:inline">▼ Detalles</span>
                </summary>
                <div className="mt-1 space-y-1 pl-3 border-l border-indigo-100">
                  {(reasoning.urgency_reasoning || reasoning.execution_feasibility) && (
                    <>
                      {reasoning.urgency_reasoning && (
                        <p><span className="text-ct-text3">Urgencia</span> {reasoning.urgency_reasoning}</p>
                      )}
                      {reasoning.execution_feasibility && (
                        <p><span className="text-ct-text3">Viabilidad ejecución</span> {reasoning.execution_feasibility}</p>
                      )}
                    </>
                  )}
                  {Object.keys(dims).length > 0 && (
                    <p className="text-[8px] font-mono break-all leading-relaxed">
                      dimensiones (local / impacto / urgencia / alcance / viabilidad / estratégico):{' '}
                      {JSON.stringify(dims)}
                    </p>
                  )}
                  {Object.keys(breakdown).length > 0 && (
                    <p className="text-[8px] font-mono break-all leading-relaxed">
                      breakdown: {JSON.stringify(breakdown)}
                    </p>
                  )}
                  {(risks.operational_saturation_risk || risks.execution_complexity_risk || risks.confidence_risk) && (
                    <div>
                      <span className="text-ct-text3">Riesgos</span>
                      <ul className="list-disc list-inside text-[8px] space-y-0.5 mt-0.5">
                        {risks.operational_saturation_risk && (
                          <li>{risks.operational_saturation_risk}</li>
                        )}
                        {risks.execution_complexity_risk && (
                          <li>{risks.execution_complexity_risk}</li>
                        )}
                        {risks.confidence_risk && (
                          <li>{risks.confidence_risk}</li>
                        )}
                      </ul>
                    </div>
                  )}
                  {Array.isArray(rp.required_team_type) && rp.required_team_type.length > 0 && (
                    <p className="text-[8px]">
                      <span className="text-ct-text3">Equipos sugeridos:</span> {rp.required_team_type.join(', ')}
                    </p>
                  )}
                  {role.role_type && (
                    <p className="text-[8px]">
                      <span className="text-ct-text3">Rol portfolio:</span> {PORTFOLIO_ROLE_LABEL_ES[role.role_type] || role.role_type}
                      {role.portfolio_balance_weight != null && (
                        <span className="ml-1 tabular-nums">
                          · balance {Number(role.portfolio_balance_weight).toFixed(0)}/100
                        </span>
                      )}
                    </p>
                  )}
                  {trace.policy_version && (
                    <p className="font-mono text-[8px] break-all">
                      policy: {trace.policy_version} · {trace.policy_type}
                    </p>
                  )}
                  {Array.isArray(trace.inputs_used) && trace.inputs_used.length > 0 && (
                    <ul className="list-disc list-inside text-[8px] space-y-0.5">
                      {trace.inputs_used.slice(0, 14).map((u, i) => (
                        <li key={i}>{typeof u === 'string' ? u : JSON.stringify(u)}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </details>
              <div className="flex flex-wrap gap-1.5 mt-1.5">
                <button
                  type="button"
                  disabled
                  className="cursor-not-allowed rounded border border-ct-border bg-ct-surface px-2 py-1 text-[9px] font-medium text-ct-text3"
                >
                  Aceptar prioridad global
                </button>
                <button
                  type="button"
                  disabled
                  className="cursor-not-allowed rounded border border-ct-border bg-ct-surface px-2 py-1 text-[9px] font-medium text-ct-text3"
                >
                  Enviar a planeación
                </button>
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function ProjectionOperationalSuggestionsBlock ({ projectionMeta, compact }) {
  const py = compact ? 'py-1.5' : 'py-2'
  const suggestions = Array.isArray(projectionMeta?.suggestions) ? projectionMeta.suggestions : []
  const st = projectionMeta?.suggestions_status
  const integrityBroken = projectionMeta?.integrity_status?.status === 'broken'
  const disabled = integrityBroken || st?.status === 'disabled'

  const impactLabel = (v) => {
    const m = {
      medium_high: 'Medio-alto',
      high: 'Alto',
      medium: 'Medio',
      low: 'Bajo',
      preventive: 'Preventivo'
    }
    return m[v] || v || '—'
  }
  const confidenceLabel = (v) => {
    const m = { high: 'Alta', medium: 'Media', low: 'Baja' }
    return m[v] || v || '—'
  }

  const top = suggestions.slice(0, 5)

  return (
    <div className={`rounded-lg border border-ct-border bg-ct-card shadow-sm px-4 ${py}`}>
      <p className="text-[10px] font-bold uppercase tracking-wider text-ct-text mb-2">
        Sugerencias operativas
      </p>

      {disabled && (
        <p className="text-[11px] text-rose-800 font-medium mb-2" role="status">
          Sugerencias desactivadas por integridad rota
        </p>
      )}

      {!disabled && st?.status === 'partial' && st?.reason === 'integrity_warning' && (
        <div
          className="mb-2 rounded border border-amber-200 bg-amber-50 px-2 py-1.5 text-[10px] text-amber-950"
          role="status"
        >
          Sugerencias generadas con confianza parcial
        </div>
      )}

      {!disabled && st?.status === 'empty' && (
        <p className="text-[11px] text-ct-text2" role="status">
          {st.reason === 'no_ytd_alerts' && 'Sin sugerencias en esta vista (no hay alertas YTD).'}
          {st.reason === 'no_suggestions' && 'Sin sugerencias en esta vista (no se derivaron acciones desde las alertas).'}
          {st.reason === 'suggestion_engine_error' && 'Sin sugerencias en esta vista (error al generar sugerencias).'}
          {(!st.reason || !['no_ytd_alerts', 'no_suggestions', 'suggestion_engine_error'].includes(st.reason)) && (
            'Sin sugerencias en esta vista.'
          )}
        </p>
      )}

      {!disabled && top.length > 0 && (
        <ul className="grid gap-2 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
          {top.map((s) => (
            <li
              key={s.suggestion_id}
              className="rounded-md border border-ct-border bg-ct-surface/80 p-2.5 text-[11px] text-ct-text shadow-sm"
            >
              <div className="flex flex-wrap items-start justify-between gap-1 mb-1">
                <span className="font-semibold text-ct-text leading-snug min-w-0">{s.entity}</span>
                <span
                  className={`flex-shrink-0 text-[9px] font-bold uppercase px-1 rounded ${
                    s.level === 'critical'
                      ? 'bg-rose-100 text-rose-900'
                      : s.level === 'warning'
                        ? 'bg-amber-100 text-amber-900'
                        : 'bg-emerald-100 text-emerald-900'
                  }`}
                >
                  {s.level === 'critical' ? 'crítico' : s.level === 'warning' ? 'alerta' : 'oportunidad'}
                </span>
              </div>
              <p className="font-semibold text-indigo-900 text-[11px] leading-snug mb-1">
                {s.recommended_action_name}
              </p>
              <p className="text-[10px] text-ct-text leading-snug mb-1.5 line-clamp-3" title={s.why}>
                {s.why}
              </p>
              <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-[9px] text-ct-text mb-2">
                <span>
                  <span className="text-ct-text3">Owner</span> {s.owner_suggested}
                </span>
                <span>
                  <span className="text-ct-text3">Canal</span> {s.channel_suggested}
                </span>
                <span>
                  <span className="text-ct-text3">Impacto</span> {impactLabel(s.expected_impact)}
                </span>
                <span className="tabular-nums">
                  <span className="text-ct-text3">Prioridad</span> {s.priority_score ?? '—'}
                </span>
                <span>
                  <span className="text-ct-text3">Confianza</span> {confidenceLabel(s.confidence)}
                </span>
              </div>
              <button
                type="button"
                disabled
                className="w-full cursor-not-allowed rounded border border-ct-border bg-ct-surface px-2 py-1 text-[9px] font-semibold text-ct-text2"
                title="La ejecución de acciones no está habilitada en esta fase"
              >
                Ejecución no habilitada
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function ProjectionYtdAlertsBlock ({ alerts, compact }) {
  const py = compact ? 'py-1.5' : 'py-2'
  if (!alerts?.length) return null
  const firstOpp = alerts.findIndex((a) => a.level === 'opportunity')
  const problemRows = firstOpp === -1 ? alerts : alerts.slice(0, firstOpp)
  const oppRows = firstOpp === -1 ? [] : alerts.slice(firstOpp)
  const topProblems = problemRows.slice(0, 3)
  const topOpps = oppRows.slice(0, 3)
  if (topProblems.length === 0 && topOpps.length === 0) return null

  return (
    <div className={`rounded-lg border border-ct-border bg-ct-card shadow-sm px-4 ${py}`}>
      <p className="text-[10px] font-bold uppercase tracking-wider text-ct-text mb-2">Top problemas del negocio</p>
      <div className={`grid gap-3 ${compact ? 'grid-cols-1' : 'md:grid-cols-2'}`}>
        <div>
          <p className="text-[9px] font-semibold text-rose-800 mb-1.5">Top 3 críticos / alerta</p>
          {topProblems.length === 0
            ? <p className="text-[11px] text-ct-text3">Sin alertas en esta vista.</p>
            : (
              <ol className="space-y-1.5 list-decimal list-inside text-[11px] text-ct-text">
                {topProblems.map((a, i) => (
                  <li key={`p-${i}-${a.entity}`} className="leading-snug">
                    <span className="font-semibold">{a.entity}</span>
                    <span className={`ml-1 px-1 rounded text-[9px] font-bold ${a.level === 'critical' ? 'bg-rose-100 text-rose-900' : 'bg-amber-100 text-amber-900'}`}>
                      {a.level === 'critical' ? 'CRÍTICO' : 'ALERTA'}
                    </span>
                    <span className="text-ct-text tabular-nums">{` · gap ${a.gap_trips != null ? `${Number(a.gap_trips) >= 0 ? '+' : ''}${Number(a.gap_trips).toLocaleString()} trips` : '—'}`}</span>
                    {a.gap_pct != null && (
                      <span className="text-ct-text2 tabular-nums">{` (${Number(a.gap_pct) >= 0 ? '+' : ''}${Number(a.gap_pct).toFixed(1)}%)`}</span>
                    )}
                    <span className="text-ct-text2">{` · driver: ${DRIVER_LABEL_ES[a.principal_driver] || a.principal_driver || '—'}`}</span>
                  </li>
                ))}
              </ol>
              )}
        </div>
        <div>
          <p className="text-[9px] font-semibold text-emerald-800 mb-1.5">Top 3 oportunidades</p>
          {topOpps.length === 0
            ? <p className="text-[11px] text-ct-text3">Sin oportunidades destacadas.</p>
            : (
              <ol className="space-y-1.5 list-decimal list-inside text-[11px] text-ct-text">
                {topOpps.map((a, i) => (
                  <li key={`o-${i}-${a.entity}`} className="leading-snug">
                    <span className="font-semibold">{a.entity}</span>
                    <span className="ml-1 px-1 rounded text-[9px] font-bold bg-emerald-100 text-emerald-900">OPORTUNIDAD</span>
                    <span className="text-ct-text tabular-nums">{` · gap ${a.gap_trips != null ? `${Number(a.gap_trips) >= 0 ? '+' : ''}${Number(a.gap_trips).toLocaleString()} trips` : '—'}`}</span>
                    {a.gap_pct != null && (
                      <span className="text-ct-text2 tabular-nums">{` (${Number(a.gap_pct) >= 0 ? '+' : ''}${Number(a.gap_pct).toFixed(1)}%)`}</span>
                    )}
                    <span className="text-ct-text2">{` · driver: ${DRIVER_LABEL_ES[a.principal_driver] || a.principal_driver || '—'}`}</span>
                  </li>
                ))}
              </ol>
              )}
        </div>
      </div>
    </div>
  )
}

function ProjectionYtdSummaryBar ({ ytd, grain, compact }) {
  const py = compact ? 'py-1.5' : 'py-2'
  if (!ytd) return null
  const att = ytd.ytd_attainment_pct
  const signal = att == null ? 'no_data' : att >= 100 ? 'green' : att >= 90 ? 'warning' : 'danger'
  const dot = SIGNAL_DOT[signal] || SIGNAL_DOT.no_data
  const attColor = projectionSignalColor(signal)
  const gapT = ytd.ytd_gap_trips

  const pacing = ytd.pacing_vs_expected
  const pacingCls = pacing === 'ahead'
    ? 'bg-emerald-100 text-emerald-900 border-emerald-200'
    : pacing === 'behind'
      ? 'bg-red-100 text-red-900 border-red-200'
      : pacing === 'on_track'
        ? 'bg-ct-surface text-ct-text border-ct-border'
        : 'bg-ct-surface text-ct-text2 border-ct-border'
  const pacingLabel = pacing === 'ahead' ? 'Adelantado'
    : pacing === 'behind' ? 'Atrasado'
      : pacing === 'on_track' ? 'En ritmo'
      : '—'

  const trend = ytd.ytd_trend
  const trendArrow = trend === 'improving' ? '↑' : trend === 'deteriorating' ? '↓' : '→'
  const trendLabel = trend === 'improving' ? 'Mejora'
    : trend === 'deteriorating' ? 'Deterioro'
      : trend === 'flat' ? 'Plano'
      : '—'

  const ddr = ytd.ytd_avg_active_drivers_real
  const prod = ytd.driver_productivity_ytd_real

  return (
    <div className={`rounded-lg border border-indigo-100 bg-indigo-50/80 shadow-sm px-4 ${py}`}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-[10px] font-bold text-indigo-700 uppercase tracking-wider">YTD {ytd.year}</span>
        <span
          className="text-[9px] font-bold uppercase tracking-wide px-1.5 py-px rounded border border-emerald-500/60 bg-emerald-100 text-emerald-900"
          title="Resumen YTD presente en meta y renderizado en UI"
        >
          YTD activo
        </span>
        <span className="text-[10px] text-indigo-600/90">hasta <strong>{ytd.through_period}</strong> · grano <strong className="uppercase">{grain}</strong></span>
        {pacing && (
          <span className={`text-[9px] font-bold px-1.5 py-px rounded border ${pacingCls}`} title="Pacing vs plan esperado YTD (trips): &gt;103% adelantado, 97–103% en ritmo, &lt;97% atrasado">
            Pacing: {pacingLabel}
          </span>
        )}
        {trend && (
          <span className="text-[9px] font-semibold text-ct-text" title="Tendencia reciente (hasta 3 períodos, cumplimiento agregado)">
            Tendencia: <span className="tabular-nums text-[11px]">{trendArrow}</span> {trendLabel}
          </span>
        )}
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-ct-text">
        <span>
          <span className="text-ct-text2">Real trips</span>{' '}
          <strong>{ytd.ytd_real_trips != null ? Number(ytd.ytd_real_trips).toLocaleString() : '—'}</strong>
        </span>
        <span>
          <span className="text-ct-text2">Plan esp.</span>{' '}
          <strong>{ytd.ytd_plan_expected_trips != null ? Number(ytd.ytd_plan_expected_trips).toLocaleString() : '—'}</strong>
        </span>
        <span>
          <span className="text-ct-text2">Gap</span>{' '}
          <strong>{gapT != null ? `${gapT >= 0 ? '+' : ''}${Number(gapT).toLocaleString()}` : '—'}</strong>
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="text-ct-text2">Cump.</span>
          <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
          <strong style={{ color: attColor }}>{att != null ? fmtAttainment(att) : '—'}</strong>
        </span>
        {ddr != null && (
          <span title="Promedio ponderado por trips del período (no suma de drivers únicos)">
            <span className="text-ct-text2">Drv.ø</span>{' '}
            <strong className="tabular-nums">{Number(ddr).toFixed(1)}</strong>
          </span>
        )}
        {prod != null && (
          <span title="Productividad YTD: trips / drivers ponderados">
            <span className="text-ct-text2">TPD</span>{' '}
            <strong className="tabular-nums">{Number(prod).toFixed(2)}</strong>
          </span>
        )}
        {ytd.ytd_real_revenue != null && (
          <span className="text-ct-text">
            <span className="text-ct-text2">Rev.R</span>{' '}
            <strong>{Number(ytd.ytd_real_revenue).toLocaleString()}</strong>
            {ytd.ytd_plan_expected_revenue != null && (
              <span className="text-ct-text3 font-normal">{` / esp. ${Number(ytd.ytd_plan_expected_revenue).toLocaleString()}`}</span>
            )}
          </span>
        )}
      </div>
      {ytd.active_drivers_note && (
        <p className="mt-1 text-[9px] text-ct-text2 leading-snug max-w-4xl">{ytd.active_drivers_note}</p>
      )}
    </div>
  )
}

function ProjectionContextBar ({ grain, projMatrix, projectionMeta, planVersion, compact, focusedKpi, closedPeriodAnchor }) {
  const py = compact ? 'py-1' : 'py-1.5'
  const allPeriods = projMatrix?.allPeriods || []
  const totals = projMatrix?.totals
  const lastPk = allPeriods.length > 0 ? allPeriods[allPeriods.length - 1] : null
  const lastTotals = lastPk ? totals?.get(lastPk) : null

  const df = projectionMeta?.data_freshness
  const lagStrP = df?.lag_days != null && df?.status !== 'broken' ? String(df.lag_days) : '—'
  const dataFreshnessLineP = df?.max_data_date
    ? `Data al ${df.max_data_date} (lag: ${lagStrP} días)`
    : `Data al — (lag: ${lagStrP} días)`
  const dataFreshnessClsP = df?.status === 'ok' ? 'text-emerald-800 font-semibold'
    : df?.status === 'warning' ? 'text-amber-800 font-semibold'
    : df?.status === 'stale' ? 'text-red-800 font-semibold'
    : 'text-ct-text font-semibold'

  const kpiFresh = projectionMeta?.kpi_freshness
  const kpiMaxDate = focusedKpi && kpiFresh?.[focusedKpi]?.max_data_date
  const hasFreshnessMismatch = kpiMaxDate && df?.max_data_date && kpiMaxDate !== df.max_data_date
  const hasKpiNoData = focusedKpi && df?.max_data_date && !kpiMaxDate

  const curveSummary = projectionMeta?.curve_summary || {}

  const KPI_LABELS = { trips_completed: 'Trips', revenue_yego_net: 'Revenue', active_drivers: 'Drivers' }

  const methodsStr = curveSummary.by_method
    ? Object.entries(curveSummary.by_method).map(([m, c]) => `${m}: ${c}`).join(', ')
    : ''

  const avgConf = curveSummary.avg_confidence
  const confBadgeCls = avgConf === 'high' ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
    : avgConf === 'medium' ? 'bg-amber-100 text-amber-800 border-amber-200'
    : avgConf ? 'bg-red-100 text-red-800 border-red-200'
    : ''
  const confLabel = avgConf === 'high' ? 'Alta confianza'
    : avgConf === 'medium' ? 'Media'
    : avgConf === 'low' ? 'Baja'
    : avgConf === 'fallback' ? 'Fallback'
    : null

  return (
    <div className={`rounded-lg border border-ct-border bg-ct-surface shadow-sm px-4 ${py} flex flex-wrap items-center gap-x-4 gap-y-1`}>
      <span className="text-[10px] font-bold text-ct-text2 uppercase tracking-wider">Proyección</span>

      <span
        className={`text-[11px] ${dataFreshnessClsP}`}
        title={df?.last_update_at ? `Última carga en facts: ${df.last_update_at}` : undefined}
      >
        {dataFreshnessLineP}
        {df?.status && (
          <span className="ml-1.5 text-[9px] font-bold uppercase text-ct-text2">[{df.status}]</span>
        )}
      </span>

      {hasFreshnessMismatch && (
        <span
          className="text-[10px] text-amber-700 font-medium border border-amber-200 bg-amber-50 rounded px-1.5 py-0.5"
          title={`Freshness global: ${df.max_data_date} | ${focusedKpi}: ${kpiMaxDate}`}
        >
          {focusedKpi === 'active_drivers' ? 'Conductores' : focusedKpi} actualizado al {kpiMaxDate}
        </span>
      )}

      {hasKpiNoData && (
        <span
          className="text-[10px] text-red-700 font-medium border border-red-200 bg-red-50 rounded px-1.5 py-0.5"
          title={`Sin data real para ${focusedKpi}. Freshness global (trips): ${df.max_data_date}`}
        >
          Sin data real para {focusedKpi === 'active_drivers' ? 'conductores' : focusedKpi}
        </span>
      )}

      <span className="text-[10px] text-ct-text">
        Plan: <strong>{planVersion || '—'}</strong>
      </span>

      {projectionMeta?.plan_loaded_at && (
        <span className="text-[10px] text-ct-text2">
          Cargado: {projectionMeta.plan_loaded_at}
        </span>
      )}

      <span className="text-[10px] text-ct-text">
        Grano: <strong className="uppercase">{grain}</strong>
      </span>

      <div className="w-px h-3 bg-gray-200 hidden sm:block" />

      {PROJECTION_KPIS.map(kpi => {
        const plan = lastTotals?.[`${kpi}_projected_total`]
        const real = lastTotals?.[kpi]
        const expected = lastTotals?.[`${kpi}_projected_expected`]
        const attainment = lastTotals?.[`${kpi}_attainment_pct`]
        const signal = lastTotals?.[`${kpi}_signal`] || 'no_data'
        const gap = lastTotals?.[`${kpi}_gap_to_expected`]
        const dot = SIGNAL_DOT[signal] || SIGNAL_DOT.no_data
        const attColor = projectionSignalColor(signal)
        const label = KPI_LABELS[kpi] || kpi

        if (plan == null && real == null) return null

        return (
          <span key={kpi} className="inline-flex items-center gap-1.5 text-[10px] text-ct-text">
            <strong className="text-ct-text">{label}:</strong>
            {plan != null && <span>P {Number(plan).toLocaleString()}</span>}
            {real != null && <span>R {Number(real).toLocaleString()}</span>}
            {attainment != null && (
              <span className="inline-flex items-center gap-0.5">
                <span className={`w-1.5 h-1.5 rounded-full ${dot} inline-block`} />
                <span style={{ color: attColor }} className="font-semibold">{fmtAttainment(attainment)}</span>
              </span>
            )}
            {gap != null && <span className="text-ct-text3">Gap {gap >= 0 ? '+' : ''}{Number(gap).toLocaleString()}</span>}
          </span>
        )
      })}

      {confLabel && (
        <span className={`ml-auto inline-block px-1.5 py-px rounded text-[9px] font-semibold border ${confBadgeCls}`} title={methodsStr || undefined}>
          {confLabel}
          {curveSummary.total_combinations ? ` · ${curveSummary.total_combinations} comb.` : ''}
        </span>
      )}
    </div>
  )
}

// ─── Barra de reconciliación ──────────────────────────────────────────────────
function ReconciliationSummaryBar ({ reconciliation }) {
  const {
    matched = 0,
    missing_plan = 0,
    plan_without_real: pwr = 0,
    unresolved_plan = 0,
    total_real_rows = 0,
    total_display_rows = null,
  } = reconciliation
  const chips = [
    { label: 'Con plan', value: matched, color: 'text-emerald-700 bg-emerald-50 border-emerald-200', title: 'Filas con real y plan matched' },
    { label: 'Sin proyección', value: missing_plan, color: 'text-ct-text2 bg-ct-surface border-ct-border', title: 'Real existe, sin plan correspondiente' },
    { label: 'Plan sin real', value: pwr, color: 'text-amber-600 bg-amber-50 border-amber-200', title: 'Plan resuelto, sin ejecución visible' },
    { label: 'Sin mapear', value: unresolved_plan, color: 'text-red-600 bg-red-50 border-red-200', title: 'Plan no resuelto a tajada canónica' },
  ]
  return (
    <div className="flex items-center gap-3 flex-wrap px-1">
      <span className="text-[10px] font-semibold text-ct-text3 uppercase tracking-wide">Reconciliación:</span>
      {chips.map(c => (
        <span key={c.label} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${c.color}`} title={c.title}>
          {c.label} <span className="font-bold">{c.value}</span>
        </span>
      ))}
      <span className="text-[10px] text-ct-text3">
        ({total_real_rows} filas reales base
        {total_display_rows != null ? ` · ${total_display_rows} filas en respuesta` : ''})
      </span>
    </div>
  )
}

// ─── Sección "Plan sin ejecución real" ────────────────────────────────────────
function PlanWithoutRealSection ({ rows = [], count, grain, planVersion }) {
  const [open, setOpen] = useState(false)

  // Agrupar por (country, city, business_slice_name)
  const groups = {}
  for (const r of rows) {
    const k = `${r.country}::${r.city}::${r.business_slice_name}`
    if (!groups[k]) {
      groups[k] = {
        country: r.country, city: r.city,
        business_slice_name: r.business_slice_name,
        periods: [],
      }
    }
    const period = r.month || r.week_start || r.trip_date || '—'
    groups[k].periods.push(period)
  }
  const groupList = Object.values(groups).sort((a, b) => {
    const co = (a.country || '').localeCompare(b.country || '')
    if (co !== 0) return co
    return (a.city || '').localeCompare(b.city || '')
  })

  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50/50 shadow-sm overflow-hidden">
      <div className="px-4 py-2.5 flex items-center gap-2.5">
        <div className="w-2 h-2 rounded-full bg-blue-400 flex-shrink-0" />
        <div className="flex-1">
          <p className="text-xs font-bold text-blue-800">
            {count} fila{count !== 1 ? 's' : ''} con plan pero sin ejecución real
          </p>
          <p className="text-[11px] text-blue-600 mt-0.5">
            Estas tajadas tienen plan resuelto pero no hay ejecución real cargada para ese período.
            No aparecen en la matriz principal; se muestran aquí para auditoría.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setOpen(o => !o)}
          className="flex-shrink-0 px-2.5 py-1 rounded text-[11px] font-semibold border border-blue-200 bg-ct-card text-blue-600 hover:bg-blue-100 transition-colors"
        >
          {open ? 'Cerrar' : `Ver ${groupList.length} tajadas`}
        </button>
      </div>

      {open && (
        <div className="border-t border-blue-100 bg-ct-card px-4 py-3">
          <div className="overflow-x-auto rounded border border-ct-border">
            <table className="text-[10px] w-full border-collapse">
              <thead>
                <tr className="bg-ct-surface text-ct-text2 uppercase tracking-wide">
                  <th className="px-2 py-1 text-left font-semibold border-b border-ct-border">País</th>
                  <th className="px-2 py-1 text-left font-semibold border-b border-ct-border">Ciudad</th>
                  <th className="px-2 py-1 text-left font-semibold border-b border-ct-border">Tajada</th>
                  <th className="px-2 py-1 text-left font-semibold border-b border-ct-border">Períodos sin real</th>
                </tr>
              </thead>
              <tbody>
                {groupList.map((g, i) => (
                  <tr key={i} className={i % 2 === 1 ? 'bg-blue-50/20' : ''}>
                    <td className="px-2 py-1 border-b border-gray-50 font-mono text-ct-text">{g.country}</td>
                    <td className="px-2 py-1 border-b border-gray-50 font-mono text-ct-text">{g.city}</td>
                    <td className="px-2 py-1 border-b border-gray-50 font-medium text-blue-700">{g.business_slice_name}</td>
                    <td className="px-2 py-1 border-b border-gray-50 text-ct-text3">{g.periods.sort().join(', ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[10px] text-ct-text3 mt-2">
            Auditoría completa: <code className="bg-ct-bg px-1 rounded">GET /plan/reconciliation-audit?plan_version={planVersion}</code>
          </p>
        </div>
      )}
    </div>
  )
}

// ─── Badge interactivo de filas no mapeadas ───────────────────────────────────
function UnmappedBadge ({ count, rows = [], planVersion }) {
  const [open, setOpen] = useState(false)
  const [auditData, setAuditData] = useState(null)
  const [auditLoading, setAuditLoading] = useState(false)
  const [auditErr, setAuditErr] = useState(null)

  const handleOpenAudit = async () => {
    setOpen(true)
    if (auditData || auditLoading) return
    setAuditLoading(true)
    setAuditErr(null)
    try {
      const data = await getPlanMappingAudit(planVersion)
      setAuditData(data)
    } catch (e) {
      setAuditErr('No se pudo cargar el detalle de auditoría.')
    } finally {
      setAuditLoading(false)
    }
  }

  const alertLevel = auditData?.alert_level
  const coveragePct = auditData?.coverage_pct

  return (
    <div className="rounded-lg border border-amber-300 bg-amber-50 shadow-sm overflow-hidden">
      {/* ── Cabecera del badge ─────────────────────────────── */}
      <div className="px-4 py-2.5 flex items-start gap-2.5">
        <svg className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z" />
        </svg>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-xs font-bold text-amber-900">
              ⚠ {count} fila{count !== 1 ? 's' : ''} del plan no mapeada{count !== 1 ? 's' : ''} a tajada canónica
            </p>
            {coveragePct != null && (
              <span className={`text-[10px] px-1.5 py-px rounded font-semibold ${
                alertLevel === 'critical' ? 'bg-red-100 text-red-700'
                  : alertLevel === 'warning' ? 'bg-amber-200 text-amber-800'
                  : 'bg-green-100 text-green-700'
              }`}>
                Cobertura: {coveragePct.toFixed(1)}%
              </span>
            )}
          </div>
          <p className="text-[11px] text-amber-700 mt-0.5">
            Estas filas <strong>no aparecen en la matriz</strong>. Verificar raw_city / raw_lob o agregar alias.
          </p>
          <div className="mt-1 flex flex-wrap gap-x-2 gap-y-0.5">
            {rows.slice(0, 6).map((r, i) => (
              <span key={i} className="text-[10px] font-mono text-amber-800 bg-amber-100 px-1 rounded">
                {r.raw_city}/{r.raw_lob}
              </span>
            ))}
            {count > 6 && <span className="text-[10px] text-amber-500">…y {count - 6} más</span>}
          </div>
        </div>
        <button
          type="button"
          onClick={open ? () => setOpen(false) : handleOpenAudit}
          className="flex-shrink-0 px-2.5 py-1 rounded text-[11px] font-semibold border border-amber-300 bg-ct-card text-amber-700 hover:bg-amber-100 transition-colors"
        >
          {open ? 'Cerrar' : 'Ver detalle'}
        </button>
      </div>

      {/* ── Panel de detalle expandible ──────────────────── */}
      {open && (
        <div className="border-t border-amber-200 bg-ct-card px-4 py-3">
          {auditLoading && (
            <div className="flex items-center gap-2 text-xs text-ct-text2 py-2">
              <span className="w-3.5 h-3.5 border-2 border-ct-border border-t-amber-500 rounded-full animate-spin" />
              Cargando auditoría completa…
            </div>
          )}
          {auditErr && <p className="text-xs text-red-600">{auditErr}</p>}
          {auditData && !auditLoading && (
            <div className="space-y-3">
              {/* Resumen */}
              <div className="flex flex-wrap gap-4 text-xs">
                <span><span className="text-ct-text3">Total plan:</span> <strong>{auditData.total_rows}</strong></span>
                <span><span className="text-ct-text3">Resueltos:</span> <strong className="text-emerald-700">{auditData.resolved}</strong></span>
                <span><span className="text-ct-text3">Sin mapear:</span> <strong className="text-red-600">{auditData.unresolved}</strong></span>
                <span><span className="text-ct-text3">Cobertura:</span> <strong className={alertLevel === 'critical' ? 'text-red-600' : alertLevel === 'warning' ? 'text-amber-600' : 'text-emerald-700'}>{auditData.coverage_pct?.toFixed(1)}%</strong></span>
                <span><span className="text-ct-text3">Aliases conocidos:</span> <strong>{auditData.alias_map_size}</strong></span>
              </div>
              {/* Tabla de no mapeados */}
              {auditData.unresolved_items?.length > 0 && (
                <div className="overflow-x-auto rounded border border-ct-border">
                  <table className="text-[10px] w-full border-collapse">
                    <thead>
                      <tr className="bg-ct-surface text-ct-text2 uppercase tracking-wide">
                        <th className="px-2 py-1 text-left font-semibold border-b border-ct-border">País</th>
                        <th className="px-2 py-1 text-left font-semibold border-b border-ct-border">Ciudad</th>
                        <th className="px-2 py-1 text-left font-semibold border-b border-ct-border">raw_lob</th>
                        <th className="px-2 py-1 text-left font-semibold border-b border-ct-border">Alias resuelto</th>
                        <th className="px-2 py-1 text-left font-semibold border-b border-ct-border">Motivo</th>
                        <th className="px-2 py-1 text-left font-semibold border-b border-ct-border">Periodo</th>
                      </tr>
                    </thead>
                    <tbody>
                      {auditData.unresolved_items.map((item, i) => (
                        <tr key={i} className={i % 2 === 1 ? 'bg-red-50/30' : ''}>
                          <td className="px-2 py-1 border-b border-gray-50 font-mono">{item.raw_country}</td>
                          <td className="px-2 py-1 border-b border-gray-50 font-mono">{item.raw_city}</td>
                          <td className="px-2 py-1 border-b border-gray-50 font-mono text-red-700">{item.raw_lob}</td>
                          <td className="px-2 py-1 border-b border-gray-50 text-ct-text3">{item.canonical_lob_base || '—'}</td>
                          <td className="px-2 py-1 border-b border-gray-50 text-amber-700 max-w-xs truncate" title={item.resolution_note}>{item.resolution_note}</td>
                          <td className="px-2 py-1 border-b border-gray-50 text-ct-text2">{item.period}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <p className="text-[10px] text-ct-text3">
                Endpoint: <code className="bg-ct-bg px-1 rounded">GET /plan/mapping-audit?plan_version={planVersion}</code>
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
