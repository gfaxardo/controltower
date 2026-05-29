/**
 * operationalPriorityEngine.js
 *
 * RC-1 Operational Priority Layer
 *
 * Derives top deteriorations and top opportunities from displayProjMatrix data
 * already loaded in memory. No new API calls. No new data sources.
 *
 * Motor: Control Foundation — Priority Layer
 */

import { PROJECTION_KPIS, computeProjectionDeltas } from '../components/omniview/projectionMatrixUtils.js'
import { buildComparableDelta, resolveSeverityLevel, COMPARABLE_SEVERITY, COMPARABLE_DIRECTION } from './comparableDeltaDisplay.js'
import { MATRIX_KPIS } from '../components/omniview/omniviewMatrixUtils.js'

/**
 * @typedef {Object} OperationalPriority
 * @property {string} id
 * @property {'deterioration'|'improvement'} type
 * @property {string} metric - KPI key
 * @property {string} grain
 * @property {string} country
 * @property {string} city
 * @property {string} slice - business_slice_name
 * @property {string} periodKey
 * @property {string} periodLabel
 * @property {string} comparisonType - 'DoD'|'WoW'|'MoM'
 * @property {number|null} actualValue
 * @property {number|null} previousValue
 * @property {number|null} deltaPct
 * @property {number|null} deltaAbs
 * @property {string} severity - COMPARABLE_SEVERITY
 * @property {string} freshnessStatus
 * @property {number} priorityScore
 * @property {Object} navigation - { cityKey, lineKey, period, kpiKey, lineData, periodDeltas, raw }
 */

/**
 * Compute priority scores for all cells in the projection matrix
 * for the currently focused KPI.
 *
 * @param {Object} projMatrix - from buildProjectionMatrix()
 * @param {string} focusedKpi - selected KPI key
 * @param {string} grain - 'daily'|'weekly'|'monthly'
 * @returns {Object} { deteriorations: OperationalPriority[], improvements: OperationalPriority[] }
 */
export function computeOperationalPriorities(projMatrix, focusedKpi, grain) {
  if (!projMatrix || !PROJECTION_KPIS.includes(focusedKpi) || !projMatrix.cities?.size) {
    return { deteriorations: [], improvements: [] }
  }

  const kpiObj = MATRIX_KPIS.find(k => k.key === focusedKpi) || MATRIX_KPIS[0]
  const { cities, allPeriods } = projMatrix
  const priorities = []

  for (const [cityKey, cityData] of cities) {
    for (const [lineKey, lineData] of cityData.lines) {
      const deltasMap = computeProjectionDeltas(lineData.periods, allPeriods)

      for (const pk of allPeriods) {
        const periodDeltas = deltasMap.get(pk)
        if (!periodDeltas) continue

        const d = periodDeltas[focusedKpi]
        if (!d || !d.isProjection) continue

        // ── Exclude invalid data ──
        if (d.attainment_pct == null && d.value == null) continue
        if (d.week_state === 'future') continue

        // ── Build comparable delta ──
        const comp = buildComparableDelta(d, grain)
        if (!comp.hasComparable) continue

        const deltaPct = comp.pct
        const deltaAbs = comp.abs
        const direction = comp.direction
        const severity = comp.severity

        // ── Previous value from periodPop ──
        const pop = d.periodPop
        const previousValue = pop?.prev_real != null ? Number(pop.prev_real) : null

        // ── Exclude unreliable data ──
        if (deltaPct == null || !Number.isFinite(deltaPct)) continue
        if (!Number.isFinite(deltaAbs)) continue
        if (severity === COMPARABLE_SEVERITY.UNKNOWN) continue
        if (severity === COMPARABLE_SEVERITY.NORMAL && Math.abs(deltaPct) < 3) continue

        // ── Priority Score ──
        const absPct = Math.abs(deltaPct)
        const absScore = absPct * (deltaAbs != null ? Math.log10(Math.abs(deltaAbs) + 1) : 1)
        const priorityScore = Math.round(absScore * 100) / 100

        const periodLabel = allPeriods.length > 0
          ? formatPeriodLabel(pk, grain, d.week_state)
          : pk

        priorities.push({
          id: `${cityKey}::${lineKey}::${pk}::${focusedKpi}`,
          type: direction === COMPARABLE_DIRECTION.DOWN ? 'deterioration' : 'improvement',
          metric: focusedKpi,
          grain,
          country: cityData.country || '—',
          city: cityData.city || '—',
          slice: lineData.business_slice_name || '—',
          periodKey: pk,
          periodLabel,
          comparisonType: comp.label || '—',
          actualValue: d.value,
          previousValue,
          deltaPct,
          deltaAbs,
          severity,
          freshnessStatus: d.signal || 'no_data',
          priorityScore,
          navigation: {
            cityKey,
            lineKey,
            period: pk,
            kpiKey: focusedKpi,
            lineData,
            periodDeltas,
            raw: lineData.periods.get(pk)?.raw,
          },
        })
      }
    }
  }

  // ── Split into deteriorations and improvements ──
  const deteriorations = priorities
    .filter(p => p.type === 'deterioration')
    .sort((a, b) => b.priorityScore - a.priorityScore)

  const improvements = priorities
    .filter(p => p.type === 'improvement')
    .sort((a, b) => b.priorityScore - a.priorityScore)

  return {
    deteriorations: deteriorations.slice(0, 3),
    improvements: improvements.slice(0, 3),
  }
}

/**
 * Format a period key into a human-readable label.
 */
function formatPeriodLabel(pk, grain, weekState) {
  if (!pk) return '—'

  if (grain === 'daily') {
    try {
      const d = new Date(pk + 'T00:00:00')
      if (isNaN(d)) return pk.slice(5)
      const day = d.getDate()
      const months = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
      const weekdays = ['Dom','Lun','Mar','Mié','Jue','Vie','Sáb']
      return `${weekdays[d.getDay()]} ${day} ${months[d.getMonth()]}`
    } catch { return pk.slice(5) }
  }

  if (grain === 'weekly') {
    const suffix = weekState === 'partial' || weekState === 'current' ? ' (parc.)' : ''
    return `sem ${pk.slice(5)}${suffix}`
  }

  if (grain === 'monthly') {
    const months = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
    try {
      const m = parseInt(pk.slice(5, 7), 10)
      return months[m - 1] || pk
    } catch { return pk }
  }

  return pk
}

/**
 * Legacy compatibility: reuses computeAlertsForMatrix fuel level
 * but applies RC-1 scoring for focused priority extraction.
 */
export { computeOperationalPriorities as default }
