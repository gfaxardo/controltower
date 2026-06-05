/**
 * projectionClosedPeriodEngine.js
 *
 * Engine de período operativo cerrado para Omniview Vs Proyección.
 *
 * REGLA ABSOLUTA:
 *   El foco dominante es el ÚLTIMO PERIODO OPERATIVO CERRADO,
 *   NO el día calendario actual si éste no tiene data cerrada.
 *
 * OBJETIVO:
 *   - Resolver el anchor period (período al que centrar el viewport)
 *   - Clasificar cada período como closed / partial / future
 *   - Diferenciar "hoy calendario" de "último cierre operativo"
 *
 * Motor: Control Foundation
 */

/**
 * Resolve the operational closed period key and the anchor period.
 *
 * @param {Object} params
 * @param {string[]} params.allPeriods - Todos los period keys del rango actual
 * @param {string} params.grain - 'daily' | 'weekly' | 'monthly'
 * @param {Object|null} params.projectionMeta - Meta de la respuesta de proyección
 * @param {Map|null} [params.periodInfoMap] - Mapa opcional de periodKey → { weekState, comparisonBasis, hasReal }
 * @param {string|null} [params.selectedKpi] - KPI activo seleccionado
 * @param {Object|null} [params.kpiFreshness] - Per-KPI freshness map { kpi: { max_data_date, lag_days, status } }
 * @returns {Object}
 */
export function resolveClosedPeriodAnchor({
  allPeriods,
  grain,
  projectionMeta,
  periodInfoMap = null,
  selectedKpi = null,
  kpiFreshness = null,
}) {
  const now = new Date()
  const todayKey = formatDateKey(now)

  // ── Calendar current period ──
  const calendarCurrentPeriodKey = getCalendarCurrentPeriodKey(grain, now)

  // ── Last data date from freshness (per-KPI override if available) ──
  const globalMaxDataDate = projectionMeta?.data_freshness?.max_data_date || null
  const kpiSpecific = selectedKpi && kpiFreshness?.[selectedKpi]
  const kpiMaxDataDate = kpiSpecific?.max_data_date || null
  const maxDataDate = kpiMaxDataDate || globalMaxDataDate
  const maxDataKey = maxDataDate ? normalizeDateKey(maxDataDate, grain) : null

  // ── Find anchor: last closed/operational period ──
  let operationalClosedPeriodKey = null
  let anchorPeriodKey = null
  let anchorReason = 'calendar_fallback'
  let isCalendarCurrentPartial = false

  if (grain === 'daily') {
    // Daily: anchor = último día con data cerrada (≤ maxDataDate)
    // Si maxDataDate está disponible, buscar ese día o el más cercano atrás
    if (maxDataKey && allPeriods.includes(maxDataKey)) {
      operationalClosedPeriodKey = maxDataKey
      anchorPeriodKey = maxDataKey
      anchorReason = 'freshness_max_data_date'
    } else if (maxDataKey) {
      // maxDataKey not in range — find closest behind
      for (let i = allPeriods.length - 1; i >= 0; i--) {
        if (allPeriods[i] <= maxDataKey) {
          operationalClosedPeriodKey = allPeriods[i]
          anchorPeriodKey = allPeriods[i]
          anchorReason = 'freshness_closest_behind'
          break
        }
      }
    }

    // Fallback: yesterday
    if (!anchorPeriodKey) {
      const yesterday = new Date(now)
      yesterday.setDate(yesterday.getDate() - 1)
      const yesterdayKey = formatDateKey(yesterday)
      if (allPeriods.includes(yesterdayKey)) {
        operationalClosedPeriodKey = yesterdayKey
        anchorPeriodKey = yesterdayKey
        anchorReason = 'yesterday_fallback'
      } else {
        // Last period in range
        operationalClosedPeriodKey = allPeriods[allPeriods.length - 1]
        anchorPeriodKey = allPeriods[allPeriods.length - 1]
        anchorReason = 'last_in_range'
      }
    }

    // Is today partial?
    isCalendarCurrentPartial = todayKey !== maxDataKey &&
      (!allPeriods.includes(todayKey) || todayKey > (maxDataKey || ''))

  } else if (grain === 'weekly') {
    // Weekly: anchor = última semana con week_state="closed"
    if (periodInfoMap) {
      for (let i = allPeriods.length - 1; i >= 0; i--) {
        const info = periodInfoMap.get(allPeriods[i])
        if (info?.weekState === 'closed') {
          operationalClosedPeriodKey = allPeriods[i]
          anchorPeriodKey = allPeriods[i]
          anchorReason = 'last_closed_week'
          break
        }
      }
    }
    // Fallback: penúltima semana
    if (!anchorPeriodKey && allPeriods.length > 1) {
      operationalClosedPeriodKey = allPeriods[allPeriods.length - 2]
      anchorPeriodKey = allPeriods[allPeriods.length - 2]
      anchorReason = 'penultimate_week_fallback'
    } else if (!anchorPeriodKey) {
      operationalClosedPeriodKey = allPeriods[allPeriods.length - 1]
      anchorPeriodKey = allPeriods[allPeriods.length - 1]
      anchorReason = 'last_in_range'
    }

    // Is current week partial?
    const calWeekKey = calendarCurrentPeriodKey
    isCalendarCurrentPartial =
      calWeekKey !== operationalClosedPeriodKey &&
      allPeriods.includes(calWeekKey)

  } else {
    // Monthly: anchor = ultimo mes con comparison_basis="full_month"
    if (periodInfoMap) {
      for (let i = allPeriods.length - 1; i >= 0; i--) {
        const info = periodInfoMap.get(allPeriods[i])
        if (info?.comparisonBasis === 'full_month') {
          operationalClosedPeriodKey = allPeriods[i]
          anchorPeriodKey = allPeriods[i]
          anchorReason = 'last_full_month'
          break
        }
      }
    }
    // P0.6: Fallback reparado — nunca usar penultimate_month_fallback ciego
    if (!anchorPeriodKey) {
      // 1. Buscar el ultimo mes con datos (maxDataKey o el mas reciente <= hoy)
      const searchKey = maxDataKey || calendarCurrentPeriodKey
      for (let i = allPeriods.length - 1; i >= 0; i--) {
        if (allPeriods[i] <= searchKey) {
          operationalClosedPeriodKey = allPeriods[i]
          anchorPeriodKey = allPeriods[i]
          anchorReason = maxDataKey ? 'freshness_closest_behind' : 'calendar_current_or_last_closed'
          break
        }
      }
      // 2. Si no se encontro ninguno (todos futuros), usar el primer periodo
      if (!anchorPeriodKey && allPeriods.length > 0) {
        operationalClosedPeriodKey = allPeriods[0]
        anchorPeriodKey = allPeriods[0]
        anchorReason = 'first_in_range'
      }
    }

    // Is current month partial?
    const calMonthKey = calendarCurrentPeriodKey
    isCalendarCurrentPartial =
      calMonthKey !== operationalClosedPeriodKey &&
      allPeriods.includes(calMonthKey)
  }

  const kpiFreshnessMismatch = kpiMaxDataDate && globalMaxDataDate && kpiMaxDataDate !== globalMaxDataDate
  const kpiNoData = selectedKpi && globalMaxDataDate && !kpiMaxDataDate
  return {
    calendarCurrentPeriodKey,
    operationalClosedPeriodKey,
    anchorPeriodKey,
    anchorReason,
    isCalendarCurrentPartial,
    maxDataDate,
    maxDataKey,
    globalMaxDataDate,
    kpiMaxDataDate,
    kpiFreshnessMismatch,
    kpiNoData,
    selectedKpi,
  }
}

/**
 * Classify a single period as closed, partial, or future.
 *
 * @param {Object} params
 * @param {string} params.periodKey
 * @param {string} params.grain
 * @param {string|null} params.weekState - from backend row.week_state
 * @param {string|null} params.comparisonBasis - from backend row.comparison_basis
 * @param {string|null} params.anchorPeriodKey - the resolved anchor
 * @param {string|null} params.calendarCurrentPeriodKey
 * @returns {'closed'|'partial'|'future'|'past'|'current'}
 */
export function classifyPeriodStatus({
  periodKey,
  grain,
  weekState,
  comparisonBasis,
  anchorPeriodKey,
  calendarCurrentPeriodKey,
}) {
  // Backend says future
  if (weekState === 'future') return 'future'

  // The anchor period = operational focus
  if (periodKey === anchorPeriodKey) return 'current'

  // Calendar current but not anchor = partial
  if (periodKey === calendarCurrentPeriodKey && periodKey !== anchorPeriodKey) {
    return 'partial'
  }

  // Partial comparison basis
  if (comparisonBasis && (
    comparisonBasis.startsWith('partial_') ||
    comparisonBasis.includes('_partial_')
  )) {
    return 'partial'
  }

  // Past (before anchor)
  if (periodKey < (anchorPeriodKey || '')) return 'past'

  // Future (after calendar current)
  if (periodKey > (calendarCurrentPeriodKey || '')) return 'future'

  // Between anchor and calendar current = partial
  if (anchorPeriodKey && calendarCurrentPeriodKey &&
    periodKey > anchorPeriodKey && periodKey < calendarCurrentPeriodKey) {
    return 'partial'
  }

  return 'closed'
}

/**
 * Get visual treatment for a period status.
 */
export function getPeriodVisualClass(status) {
  switch (status) {
    case 'current':
      return {
        border: 'border-l-2 border-r-2 border-emerald-400/60',
        bg: 'bg-gradient-to-b from-emerald-50/40 to-emerald-50/20',
        shadow: 'shadow-[inset_0_0_18px_rgba(16,185,129,0.12),0_0_10px_rgba(16,185,129,0.10)]',
        opacity: 1,
      }
    case 'partial':
      return {
        border: 'border-l border-r border-amber-200/40',
        bg: 'bg-amber-50/15',
        shadow: '',
        opacity: 0.85,
      }
    case 'past':
      return { border: '', bg: '', shadow: '', opacity: null } // computed by aging
    case 'future':
      return {
        border: 'border-r border-gray-100/15',
        bg: 'bg-slate-50/20',
        shadow: '',
        opacity: 0.45,
      }
    case 'closed':
    default:
      return { border: '', bg: '', shadow: '', opacity: 1 }
  }
}

/**
 * Get badge text for a period.
 */
export function getPeriodBadge(status, grain) {
  if (status === 'current') {
    if (grain === 'daily') return 'ÚLTIMO CIERRE'
    if (grain === 'weekly') return 'SEM. CERRADA'
    return 'MES CERRADO'
  }
  if (status === 'partial') {
    if (grain === 'daily') return 'PARCIAL'
    return 'PARCIAL'
  }
  return null
}

/**
 * Get "go to anchor" button label.
 */
export function getAnchorButtonLabel(grain, isCalendarCurrentPartial) {
  if (grain === 'daily') return 'Ir a hoy'
  if (grain === 'weekly') return 'Ir a sem. actual'
  return 'Ir a mes actual'
}

// ── Helpers ──

function formatDateKey(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function getCalendarCurrentPeriodKey(grain, now) {
  if (grain === 'weekly') {
    const day = now.getDay()
    const diff = now.getDate() - day + (day === 0 ? -6 : 1)
    const monday = new Date(now.getFullYear(), now.getMonth(), diff)
    return formatDateKey(monday)
  }
  if (grain === 'monthly') {
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
  }
  return formatDateKey(now)
}

function normalizeDateKey(dateStr, grain) {
  if (!dateStr) return null
  if (grain === 'monthly') {
    return dateStr.slice(0, 7) + '-01'
  }
  return dateStr.slice(0, 10)
}

export default {
  resolveClosedPeriodAnchor,
  classifyPeriodStatus,
  getPeriodVisualClass,
  getPeriodBadge,
  getAnchorButtonLabel,
}
