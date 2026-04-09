/**
 * insightEngine.js — Insight & Action Engine para Omniview Matrix.
 * Toda calibración numérica y reglas base viven en INSIGHT_CONFIG (insightConfig.js).
 * Opcional: mergeInsightRuntimeConfig + patch de usuario (insightUserSettings.js).
 *
 * Period State awareness: si el periodo está abierto pero el delta ya usa
 * partial-equivalent real, el insight puede mantenerse normal. Solo se degrada
 * cuando sigue siendo parcial-vs-completo o CURRENT_DAY sin corte intradía equivalente.
 */

import { computeDeltas, periodLabel, PERIOD_STATES, resolveCellTrustVisual } from './omniviewMatrixUtils.js'
import { INSIGHT_CONFIG } from './insightConfig.js'

// ─── Resolución de config por métrica + grano ───────────────────────────────

export function getMetricDefinition (config, grain, metricKey) {
  const base = config.metrics?.[metricKey]
  if (!base) return null
  const ov = config.grainOverrides?.[grain]?.metrics?.[metricKey]
  return ov ? { ...base, ...ov } : { ...base }
}

function severityRank (config, s) {
  return config.severityRank?.[s] ?? 0
}

// ─── Severidad (100% driven por config + multiplicador de grano) ─────────────

export function evaluateMetricThresholds (cfg, delta, grainMultiplier) {
  if (!cfg || !delta) return null
  if (cfg.direction === 'up_is_bad') {
    const critPp = cfg.criticalPp != null ? cfg.criticalPp * grainMultiplier : null
    const warnPp = cfg.warningPp != null ? cfg.warningPp * grainMultiplier : null
    if (critPp != null && delta.delta_abs_pp != null && delta.delta_abs_pp >= critPp) return 'critical'
    if (warnPp != null && delta.delta_abs_pp != null && delta.delta_abs_pp >= warnPp) return 'warning'
    const critPct = cfg.criticalPct != null ? cfg.criticalPct * grainMultiplier : null
    const warnPct = cfg.warningPct != null ? cfg.warningPct * grainMultiplier : null
    if (critPct != null && delta.delta_pct != null && delta.delta_pct >= critPct) return 'critical'
    if (warnPct != null && delta.delta_pct != null && delta.delta_pct >= warnPct) return 'warning'
  } else {
    const critPct = cfg.criticalPct != null ? cfg.criticalPct * grainMultiplier : null
    const warnPct = cfg.warningPct != null ? cfg.warningPct * grainMultiplier : null
    if (critPct != null && delta.delta_pct != null && delta.delta_pct <= critPct) return 'critical'
    if (warnPct != null && delta.delta_pct != null && delta.delta_pct <= warnPct) return 'warning'
    const critPp = cfg.criticalPp != null ? cfg.criticalPp * grainMultiplier : null
    const warnPp = cfg.warningPp != null ? cfg.warningPp * grainMultiplier : null
    if (critPp != null && delta.delta_abs_pp != null && delta.delta_abs_pp <= -critPp) return 'critical'
    if (warnPp != null && delta.delta_abs_pp != null && delta.delta_abs_pp <= -warnPp) return 'warning'
  }
  return null
}

// ─── Impact score ────────────────────────────────────────────────────────────

export function calculateImpactScore (periodDeltas, config = INSIGHT_CONFIG) {
  const weights = config.impactWeights || {}
  let score = 0
  for (const [metric, weight] of Object.entries(weights)) {
    const d = periodDeltas?.[metric]
    if (d?.delta_pct != null) {
      score += Math.abs(d.delta_pct) * weight * Math.abs(Number(d.value) || 1)
    }
  }
  return score
}

// ─── Root cause ──────────────────────────────────────────────────────────────

export function explainInsight (triggerMetric, periodDeltas, config = INSIGHT_CONFIG) {
  const th = config.rootCauseThresholds || {}
  const drivers = periodDeltas?.active_drivers
  const ticket = periodDeltas?.avg_ticket
  const trips = periodDeltas?.trips_completed
  const cancel = periodDeltas?.cancel_rate_pct
  const rev = periodDeltas?.revenue_yego_net

  const flags = {
    driversDrop: drivers?.delta_pct != null && drivers.delta_pct <= th.drivers_drop_pct,
    ticketDrop: ticket?.delta_pct != null && ticket.delta_pct <= th.ticket_drop_pct,
    tripsDrop: trips?.delta_pct != null && trips.delta_pct <= th.trips_drop_pct,
    cancelUp: cancel?.delta_abs_pp != null && cancel.delta_abs_pp > th.cancel_up_pp,
  }

  let causeId = 'combined'
  const rules = config.rootCauseRules || []
  for (const rule of rules) {
    if (rule.match(flags, triggerMetric)) {
      causeId = rule.id
      break
    }
  }

  const causeCfg = config.causes?.[causeId] || config.causes?.combined

  return {
    causeId,
    cause: causeCfg?.label ?? '—',
    drivers_delta_pct: drivers?.delta_pct ?? null,
    ticket_delta_pct: ticket?.delta_pct ?? null,
    trips_delta_pct: trips?.delta_pct ?? null,
    cancel_delta_pp: cancel?.delta_abs_pp ?? null,
    revenue_delta_pct: rev?.delta_pct ?? null,
  }
}

/** Acción sugerida para una causa (desde config.causes). */
export function suggestActions (causeId, config = INSIGHT_CONFIG) {
  const causeCfg = config.causes?.[causeId]
  if (!causeCfg) return config.defaultAction || { action: '—', priority: 'low' }
  return { action: causeCfg.action, priority: causeCfg.priority }
}

/** Alias retrocompatible. */
export const suggestAction = suggestActions

// ─── Agrupación anti-spam: una alerta prioritaria por ciudad+línea+periodo ───

function groupInsightsByRowPeriod (rawInsights, config) {
  const groups = new Map()
  for (const ins of rawInsights) {
    const k = `${ins.cityKey}::${ins.lineKey}::${ins.period}`
    if (!groups.has(k)) groups.set(k, [])
    groups.get(k).push(ins)
  }

  const out = []
  for (const arr of groups.values()) {
    arr.sort((a, b) =>
      severityRank(config, b.severity) - severityRank(config, a.severity)
      || b.impactScore - a.impactScore
    )
    const primary = arr[0]
    const secondary = arr.slice(1)
    const maxImpact = Math.max(...arr.map((x) => x.impactScore))
    const rowKey = `${primary.cityKey}::${primary.lineKey}::${primary.period}`

    out.push({
      ...primary,
      id: `insight-row-${rowKey}`,
      impactScore: maxImpact,
      groupedCount: arr.length,
      secondarySignals: secondary.map((s) => ({
        metric: s.metric,
        metricLabel: s.metricLabel,
        severity: s.severity,
        delta_pct: s.delta_pct,
        delta_abs_pp: s.delta_abs_pp,
      })),
    })
  }

  return out.sort((a, b) => b.impactScore - a.impactScore)
}

// ─── Period state helpers for insight engine ─────────────────────────────────

function _isPartialPeriod (state) {
  return (
    state === PERIOD_STATES.PARTIAL ||
    state === PERIOD_STATES.CURRENT_DAY ||
    state === PERIOD_STATES.OPEN
  )
}

function _downgradeSeverity (severity) {
  if (severity === 'critical') return 'warning'
  return severity
}

// ─── Detección principal ─────────────────────────────────────────────────────

export function detectInsights (matrix, grain, config = INSIGHT_CONFIG, periodStates = null, trustContext = null) {
  const { cities, allPeriods } = matrix
  if (allPeriods.length < 2) return []
  if (trustContext?.global_insights_blocked) return []
  const dm =
    trustContext?.decision_mode ||
    trustContext?.matrixTrust?.operational_decision?.decision_mode ||
    null
  if (dm === 'BLOCKED') return []

  const mt = trustContext?.matrixTrust
  const baseMult = config.grainThresholdMultipliers?.[grain] ?? 1
  const userSens = config.userSensitivityMultiplier ?? 1
  const grainMult = baseMult * userSens
  const partialMultiplier = config.partialPeriodThresholdMultiplier ?? 1.5

  const raw = []
  let idCounter = 0

  for (const [cityKey, cityData] of cities) {
    for (const [lineKey, lineData] of cityData.lines) {
      if (lineData.business_slice_name === 'UNMAPPED' || cityData.city === 'UNMAPPED') continue

      const deltas = computeDeltas(lineData.periods, allPeriods, periodStates)

      for (const pk of allPeriods) {
        const periodDeltas = deltas.get(pk)
        if (!periodDeltas) continue

        const pState = periodStates?.get(pk)
        const isPartial = _isPartialPeriod(pState)
        const isStale = pState === PERIOD_STATES.STALE

        for (const metricKey of Object.keys(config.metrics || {})) {
          const cfg = getMetricDefinition(config, grain, metricKey)
          const d = periodDeltas[metricKey]
          if (!d || d.value == null || !cfg) continue

          const hasTrustworthyEquivalent = !!(d.is_equivalent_comparison && !d.is_preliminary)
          const shouldDowngrade = (isPartial && !hasTrustworthyEquivalent) || isStale
          const effectiveMult = shouldDowngrade ? grainMult * partialMultiplier : grainMult

          let severity = evaluateMetricThresholds(cfg, d, effectiveMult)
          if (!severity) continue

          const cellTrust = mt
            ? resolveCellTrustVisual(mt, grain, cityData.city, lineData.business_slice_name, pk, metricKey)
            : null
          if (cellTrust === 'blocked') continue

          if (shouldDowngrade) severity = _downgradeSeverity(severity)
          const matrixCaution =
            dm === 'CAUTION' ||
            trustContext?.trust_status === 'warning'
          const trustDegraded =
            cellTrust === 'warning' ||
            (!cellTrust && matrixCaution)
          if (trustDegraded) {
            if (severity === 'critical') severity = 'warning'
            else if (severity === 'warning') severity = 'warning'
          }

          let impactScore = calculateImpactScore(periodDeltas, config)
          if (trustDegraded) impactScore *= 0.5
          const explanation = explainInsight(metricKey, periodDeltas, config)
          const action = suggestActions(explanation.causeId, config)

          raw.push({
            id: `insight-raw-${idCounter++}`,
            cityKey,
            lineKey,
            city: cityData.city,
            country: cityData.country,
            business_slice: lineData.business_slice_name,
            fleet: lineData.fleet_display_name,
            period: pk,
            periodLabel: periodLabel(pk, grain),
            severity,
            metric: metricKey,
            metricLabel: cfg.label,
            delta_pct: d.delta_pct,
            delta_abs: d.delta_abs,
            delta_abs_pp: d.delta_abs_pp,
            current: d.value,
            previous: d.previous,
            impactScore,
            explanation,
            action,
            preliminary: shouldDowngrade || !!d.is_preliminary,
            comparisonMode: d.comparison_mode ?? null,
            isEquivalentComparison: !!d.is_equivalent_comparison,
          })
        }
      }
    }
  }

  return groupInsightsByRowPeriod(raw, config)
}

// ─── Mapa de celdas para resaltado ───────────────────────────────────────────

export function buildInsightCellMap (insights, config = INSIGHT_CONFIG) {
  const rank = (s) => severityRank(config, s)
  const map = new Map()
  const applySeverity = (cityKey, lineKey, period, metric, sev) => {
    const cellKey = `${cityKey}::${lineKey}::${period}::${metric}`
    const existing = map.get(cellKey)
    if (!existing || rank(sev) > rank(existing)) map.set(cellKey, sev)
    const rowKey = `${cityKey}::${lineKey}::${period}`
    if (!map.has(rowKey) || rank(sev) > rank(map.get(rowKey))) map.set(rowKey, sev)
  }

  for (const ins of insights) {
    applySeverity(ins.cityKey, ins.lineKey, ins.period, ins.metric, ins.severity)
    for (const s of ins.secondarySignals || []) {
      applySeverity(ins.cityKey, ins.lineKey, ins.period, s.metric, s.severity)
    }
  }
  return map
}
