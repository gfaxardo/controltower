/**
 * rootCauseEngine.js — FASE 3.2
 *
 * Motor de descomposición determinístico de gaps de proyección.
 * Opera exclusivamente con datos ya disponibles en selection.periodDeltas.
 * Sin llamadas a API, sin ML, sin caja negra.
 *
 * Modelo matemático (multiplicativo, suma exacta):
 *
 * Revenue:  gap = factor_trips + factor_ticket
 *   factor_trips  = (trips_actual - trips_expected) × ticket_expected
 *   factor_ticket = trips_actual × (ticket_actual - ticket_expected)
 *
 * Trips:    gap = factor_drivers + factor_productivity
 *   factor_drivers      = (drivers_actual - drivers_expected) × tpd_expected
 *   factor_productivity = drivers_actual × (tpd_actual - tpd_expected)
 *
 * Drivers:  gap directo (sin sub-descomposición)
 */

const PROJECTION_KPIS = ['trips_completed', 'revenue_yego_net', 'active_drivers']

// ─── Labels por factor ────────────────────────────────────────────────────────

const FACTOR_LABELS = {
  trips:        'Volumen (trips)',
  ticket:       'Ticket promedio',
  drivers:      'Conductores activos',
  productivity: 'Productividad (trips/driver)',
  gap:          'Gap directo',
  residual:     'Residual',
}

// ─── Recomendaciones (reglas simples, determinísticas) ────────────────────────

const RECOMMENDATIONS = {
  trips:        'Revisar asignación de demanda o activación de oferta.',
  ticket:       'Revisar pricing, mix de producto o tarifas por zona.',
  drivers:      'Incrementar activación de conductores / reducir churn.',
  productivity: 'Revisar asignación de viajes por conductor activo.',
  gap:          'Analizar la brecha entre plan y real para este KPI.',
  residual:     'Revisar la composición del gap con datos adicionales.',
}

// ─── Helpers numéricos ────────────────────────────────────────────────────────

function _safe (v) {
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function _pct (impact, gap_total) {
  if (!gap_total || !Number.isFinite(gap_total) || Math.abs(gap_total) < 0.001) return 0
  return Math.round(Math.abs(impact / gap_total) * 1000) / 10
}

function _direction (v) {
  if (v == null) return 'neutral'
  if (v > 0) return 'positive'
  if (v < 0) return 'negative'
  return 'neutral'
}

// ─── Descomposición Revenue ───────────────────────────────────────────────────

function _decomposeRevenue (deltas) {
  const tripsD  = deltas['trips_completed']
  const revD    = deltas['revenue_yego_net']
  const driversD = deltas['active_drivers']

  const trips_actual   = _safe(tripsD?.value)
  const trips_expected = _safe(tripsD?.projected_expected)
  const rev_actual     = _safe(revD?.value)
  const rev_expected   = _safe(revD?.projected_expected)

  // Necesitamos trips_expected > 0 para derivar ticket_expected
  if (trips_actual == null || trips_expected == null || trips_expected === 0 ||
      rev_actual == null || rev_expected == null) {
    return null
  }

  const gap_total = rev_actual - rev_expected

  // Tickets derivados de ratios
  const ticket_expected = rev_expected / trips_expected
  const ticket_actual   = trips_actual > 0 ? rev_actual / trips_actual : ticket_expected

  // Descomposición multiplicativa (Laspeyres-style)
  const factor_trips  = (trips_actual - trips_expected) * ticket_expected
  const factor_ticket = trips_actual * (ticket_actual - ticket_expected)

  // Residual (por aritmética float; debería ser ~0)
  const residual = gap_total - (factor_trips + factor_ticket)
  const hasResidual = Math.abs(residual) > Math.abs(gap_total) * 0.001

  const factors = [
    {
      key: 'trips',
      label: FACTOR_LABELS.trips,
      impact: factor_trips,
      pct: _pct(factor_trips, gap_total),
      direction: _direction(factor_trips),
    },
    {
      key: 'ticket',
      label: FACTOR_LABELS.ticket,
      impact: factor_ticket,
      pct: _pct(factor_ticket, gap_total),
      direction: _direction(factor_ticket),
    },
  ]

  if (hasResidual) {
    factors.push({
      key: 'residual',
      label: FACTOR_LABELS.residual,
      impact: residual,
      pct: _pct(residual, gap_total),
      direction: _direction(residual),
    })
  }

  const main_driver = [...factors].sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact))[0]

  return {
    gap_total,
    is_complete: true,
    kpi_key: 'revenue_yego_net',
    factors,
    main_driver,
    recommendation: RECOMMENDATIONS[main_driver.key] || RECOMMENDATIONS.gap,
    meta: {
      ticket_actual: Math.round(ticket_actual * 100) / 100,
      ticket_expected: Math.round(ticket_expected * 100) / 100,
      trips_actual,
      trips_expected,
    },
  }
}

// ─── Descomposición Trips ─────────────────────────────────────────────────────

function _decomposeTrips (deltas) {
  const tripsD   = deltas['trips_completed']
  const driversD = deltas['active_drivers']

  const trips_actual    = _safe(tripsD?.value)
  const trips_expected  = _safe(tripsD?.projected_expected)
  const drivers_actual  = _safe(driversD?.value)
  const drivers_expected = _safe(driversD?.projected_expected)

  // Necesitamos drivers_expected > 0 para derivar tpd_expected
  if (trips_actual == null || trips_expected == null ||
      drivers_actual == null || drivers_expected == null || drivers_expected === 0) {
    return null
  }

  const gap_total = trips_actual - trips_expected

  // Productividad derivada
  const tpd_expected = trips_expected / drivers_expected
  const tpd_actual   = drivers_actual > 0 ? trips_actual / drivers_actual : tpd_expected

  // Descomposición multiplicativa
  const factor_drivers      = (drivers_actual - drivers_expected) * tpd_expected
  const factor_productivity = drivers_actual * (tpd_actual - tpd_expected)

  // Residual
  const residual = gap_total - (factor_drivers + factor_productivity)
  const hasResidual = Math.abs(residual) > Math.abs(gap_total) * 0.001

  const factors = [
    {
      key: 'drivers',
      label: FACTOR_LABELS.drivers,
      impact: factor_drivers,
      pct: _pct(factor_drivers, gap_total),
      direction: _direction(factor_drivers),
    },
    {
      key: 'productivity',
      label: FACTOR_LABELS.productivity,
      impact: factor_productivity,
      pct: _pct(factor_productivity, gap_total),
      direction: _direction(factor_productivity),
    },
  ]

  if (hasResidual) {
    factors.push({
      key: 'residual',
      label: FACTOR_LABELS.residual,
      impact: residual,
      pct: _pct(residual, gap_total),
      direction: _direction(residual),
    })
  }

  const main_driver = [...factors].sort((a, b) => Math.abs(b.impact) - Math.abs(a.impact))[0]

  return {
    gap_total,
    is_complete: true,
    kpi_key: 'trips_completed',
    factors,
    main_driver,
    recommendation: RECOMMENDATIONS[main_driver.key] || RECOMMENDATIONS.gap,
    meta: {
      tpd_actual: Math.round(tpd_actual * 100) / 100,
      tpd_expected: Math.round(tpd_expected * 100) / 100,
      drivers_actual,
      drivers_expected,
    },
  }
}

// ─── Descomposición Active Drivers ────────────────────────────────────────────

function _decomposeDrivers (deltas) {
  const driversD = deltas['active_drivers']
  const tripsD   = deltas['trips_completed']

  const drivers_actual   = _safe(driversD?.value)
  const drivers_expected = _safe(driversD?.projected_expected)

  if (drivers_actual == null || drivers_expected == null) return null

  const gap_total = drivers_actual - drivers_expected

  // Contexto de productividad (opcional, si hay trips)
  const trips_actual   = _safe(tripsD?.value)
  const trips_expected = _safe(tripsD?.projected_expected)
  const tpd_actual     = drivers_actual > 0 && trips_actual != null ? trips_actual / drivers_actual : null
  const tpd_expected   = drivers_expected > 0 && trips_expected != null ? trips_expected / drivers_expected : null

  const factors = [
    {
      key: 'gap',
      label: FACTOR_LABELS.gap,
      impact: gap_total,
      pct: 100,
      direction: _direction(gap_total),
    },
  ]

  return {
    gap_total,
    is_complete: true,
    kpi_key: 'active_drivers',
    factors,
    main_driver: factors[0],
    recommendation: RECOMMENDATIONS.drivers,
    meta: {
      tpd_actual: tpd_actual != null ? Math.round(tpd_actual * 100) / 100 : null,
      tpd_expected: tpd_expected != null ? Math.round(tpd_expected * 100) / 100 : null,
    },
  }
}

// ─── API pública ──────────────────────────────────────────────────────────────

/**
 * Computa la descomposición de gap para una celda de proyección.
 *
 * @param {string} kpiKey - KPI a analizar ('trips_completed' | 'revenue_yego_net' | 'active_drivers')
 * @param {object} periodDeltas - periodDeltas del período seleccionado (del cellInfo)
 * @returns {{ gap_total, factors, main_driver, recommendation, is_complete, kpi_key, meta }}
 */
export function computeRootCause (kpiKey, periodDeltas) {
  if (!periodDeltas) return _incomplete(kpiKey, 'Sin datos de período')

  // Solo opera en KPIs proyectables
  if (!PROJECTION_KPIS.includes(kpiKey)) {
    return _incomplete(kpiKey, 'KPI no proyectable')
  }

  // Verificar que el KPI objetivo tiene proyección real
  const targetDelta = periodDeltas[kpiKey]
  if (!targetDelta?.isProjection) {
    return _incomplete(kpiKey, 'Sin datos de proyección para este período')
  }

  let result = null

  if (kpiKey === 'revenue_yego_net') {
    result = _decomposeRevenue(periodDeltas)
  } else if (kpiKey === 'trips_completed') {
    result = _decomposeTrips(periodDeltas)
  } else if (kpiKey === 'active_drivers') {
    result = _decomposeDrivers(periodDeltas)
  }

  if (!result) return _incomplete(kpiKey, 'Datos insuficientes para descomponer')

  return result
}

function _incomplete (kpiKey, reason) {
  return {
    gap_total: null,
    is_complete: false,
    kpi_key: kpiKey,
    factors: [],
    main_driver: null,
    recommendation: null,
    meta: {},
    reason,
  }
}

/**
 * Formatea un valor de impacto de forma compacta para mostrar en UI.
 * @param {number} v
 * @param {string} kpiKey
 */
export function fmtImpact (v, kpiKey) {
  if (v == null || !Number.isFinite(v)) return '—'
  const sign = v >= 0 ? '+' : '-'
  const abs = Math.abs(v)
  const isCurrency = kpiKey === 'revenue_yego_net'

  let formatted
  if (abs >= 1000000) {
    formatted = `${(abs / 1000000).toFixed(2)}M`
  } else if (abs >= 1000) {
    formatted = `${(abs / 1000).toFixed(1)}K`
  } else {
    formatted = abs.toFixed(isCurrency ? 2 : 0)
  }

  return `${sign}${formatted}`
}
