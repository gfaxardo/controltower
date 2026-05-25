/**
 * OPERATIONAL MOMENTUM PRIORITY ENGINE
 * 
 * Ranking determinístico de deterioros operacionales.
 * Clasifica entidades (ciudades/líneas) según su riesgo de momentum.
 * 
 * Usa deltas ya computados en la matrix (computeDeltas).
 * NO requiere nuevos endpoints.
 * NO usa IA.
 * 
 * Motor: Control Foundation + Diagnostic Engine Temprano
 */

/* ── RISK LEVELS ── */

export const MOMENTUM_RISK = Object.freeze({
  CRITICAL_DECLINE:  'critical_decline',     // Multiple consecutive declines, severe
  ACCELERATING_DOWN: 'accelerating_down',     // Decline is getting worse
  CONSECUTIVE_DOWN:  'consecutive_down',      // 2+ consecutive declines
  SINGLE_DECLINE:    'single_decline',        // One period decline
  STABLE:            'stable',                // No significant change
  RECOVERING:        'recovering',            // Coming back from decline
  IMPROVING:         'improving',             // Positive momentum
})

const RISK_PRIORITY = Object.freeze({
  [MOMENTUM_RISK.CRITICAL_DECLINE]:  0,
  [MOMENTUM_RISK.ACCELERATING_DOWN]: 1,
  [MOMENTUM_RISK.CONSECUTIVE_DOWN]:  2,
  [MOMENTUM_RISK.SINGLE_DECLINE]:    3,
  [MOMENTUM_RISK.STABLE]:            4,
  [MOMENTUM_RISK.RECOVERING]:        5,
  [MOMENTUM_RISK.IMPROVING]:         6,
})

const RISK_LABEL = Object.freeze({
  [MOMENTUM_RISK.CRITICAL_DECLINE]:  'Critical decline',
  [MOMENTUM_RISK.ACCELERATING_DOWN]: 'Accelerating',
  [MOMENTUM_RISK.CONSECUTIVE_DOWN]:  'Consecutive ↓',
  [MOMENTUM_RISK.SINGLE_DECLINE]:    'Decline',
  [MOMENTUM_RISK.STABLE]:            'Stable',
  [MOMENTUM_RISK.RECOVERING]:        'Recovering',
  [MOMENTUM_RISK.IMPROVING]:         'Improving',
})

/* ── PURE FUNCTIONS ── */

/**
 * Detecta declinios consecutivos en una serie de valores.
 * Retorna cantidad de periodos consecutivos en decline (más recientes hacia atrás).
 */
export function detectConsecutiveDecline(values = [], thresholdPct = 3) {
  if (values.length < 2) return 0

  let count = 0
  // Values are assumed to be in chronological order (oldest first)
  for (let i = values.length - 1; i >= 1; i--) {
    const curr = values[i]
    const prev = values[i - 1]
    if (curr == null || prev == null || prev === 0) break
    const pctChange = ((curr - prev) / Math.abs(prev)) * 100
    if (pctChange < -thresholdPct) {
      count++
    } else {
      break
    }
  }
  return count
}

/**
 * Detecta si el decline se está acelerando
 * (cada periodo cae más que el anterior).
 */
export function detectMomentumAcceleration(values = []) {
  if (values.length < 3) return false

  const changes = []
  for (let i = 1; i < values.length; i++) {
    const curr = values[i]
    const prev = values[i - 1]
    if (curr == null || prev == null || prev === 0) {
      changes.push(0)
    } else {
      changes.push(((curr - prev) / Math.abs(prev)) * 100)
    }
  }

  // Check if changes are getting more negative (steeper decline)
  let negativeCount = 0
  let accelerating = false
  for (let i = 1; i < changes.length; i++) {
    if (changes[i] < 0 && changes[i - 1] < 0 && changes[i] < changes[i - 1]) {
      negativeCount++
      if (negativeCount >= 2) accelerating = true
    }
  }
  return accelerating
}

/**
 * Clasifica el riesgo de momentum basado en deltas recientes.
 * @param {Array} deltas — Array de {value, previous_value, delta_pct} en orden cronológico
 * @param {string} grain — 'daily' | 'weekly' | 'monthly'
 */
export function classifyMomentumRisk(deltas = [], grain = 'daily') {
  if (!deltas || deltas.length === 0) return MOMENTUM_RISK.STABLE

  const values = deltas.map(d => d?.value ?? null)

  const consecutive = detectConsecutiveDecline(values, 3)
  const accelerating = detectMomentumAcceleration(values)

  // Last delta
  const last = deltas[deltas.length - 1]
  const lastPct = last?.delta_pct ?? 0

  const thresholdMap = { daily: 10, weekly: 8, monthly: 5 }
  const severeThreshold = thresholdMap[grain] || 10

  if (consecutive >= 3 && Math.abs(lastPct) > severeThreshold) {
    return MOMENTUM_RISK.CRITICAL_DECLINE
  }
  if (accelerating && lastPct < -5) {
    return MOMENTUM_RISK.ACCELERATING_DOWN
  }
  if (consecutive >= 2) {
    return MOMENTUM_RISK.CONSECUTIVE_DOWN
  }
  if (lastPct < -3) {
    return MOMENTUM_RISK.SINGLE_DECLINE
  }
  if (lastPct > 3) {
    return MOMENTUM_RISK.IMPROVING
  }
  return MOMENTUM_RISK.STABLE
}

/**
 * Construye label descriptivo para una entidad con riesgo de momentum.
 * @param {object} entity — { name, risk, grain, deltas, comparisonType }
 */
export function buildMomentumPriorityLabel(entity = {}) {
  const { name, risk, grain, deltas, comparisonType } = entity
  const last = deltas?.[deltas.length - 1]
  const lastPct = last?.delta_pct ?? 0
  const pctStr = `${lastPct > 0 ? '+' : ''}${lastPct.toFixed(0)}%`
  const consecutive = detectConsecutiveDecline(deltas?.map(d => d?.value) || [])

  if (risk === MOMENTUM_RISK.CRITICAL_DECLINE) {
    return `${name} ↓ ${pctStr} · ${consecutive} periods declining`
  }
  if (risk === MOMENTUM_RISK.ACCELERATING_DOWN) {
    return `${name} ↓ accelerating · ${pctStr}`
  }
  if (risk === MOMENTUM_RISK.CONSECUTIVE_DOWN) {
    return `${name} ↓ ${pctStr} · ${consecutive} consecutive`
  }
  if (risk === MOMENTUM_RISK.SINGLE_DECLINE) {
    return `${name} ↓ ${pctStr}`
  }
  if (risk === MOMENTUM_RISK.IMPROVING) {
    return `${name} ↑ ${pctStr}`
  }
  return `${name} stable`
}

/**
 * Rankea entidades por prioridad de momentum.
 * Retorna array ordenado (más crítico primero).
 */
export function sortMomentumAttention(entities = []) {
  return [...entities].sort((a, b) => {
    const ra = RISK_PRIORITY[a.risk] ?? 99
    const rb = RISK_PRIORITY[b.risk] ?? 99
    if (ra !== rb) return ra - rb

    // Same risk: order by severity of last delta
    const da = a.deltas?.[a.deltas.length - 1]?.delta_pct ?? 0
    const db = b.deltas?.[b.deltas.length - 1]?.delta_pct ?? 0
    return da - db // more negative = higher priority
  })
}

/**
 * Extrae entidades prioritarias desde la matrix canónica (baseMatrix).
 * Trabaja sobre la estructura real: cities Map → lines Map → periods Map.
 * 
 * @param {Map|null} cities — baseMatrix.cities Map
 * @param {Array} allPeriods — baseMatrix.allPeriods (ordenado)
 * @param {string} grain
 * @param {number} maxResults — Max entities to return
 */
export function extractMomentumPriorityFromMatrix(cities = null, allPeriods = [], grain = 'daily', maxResults = 5) {
  if (!cities || !(cities instanceof Map) || cities.size === 0) return []
  if (!allPeriods || allPeriods.length < 2) return []

  const entities = []
  const periodSet = new Set(allPeriods)
  const periodIndex = new Map()
  allPeriods.forEach((pk, i) => periodIndex.set(pk, i))

  for (const [cityKey, cityData] of cities.entries()) {
    const lines = cityData.lines
    if (!(lines instanceof Map) || lines.size === 0) continue

    for (const [lineKey, lineData] of lines.entries()) {
      const periods = lineData.periods
      if (!(periods instanceof Map) || periods.size < 2) continue

      const periodKeys = [...periods.keys()].sort()
      const tripsValues = [] // sequential trips_completed values across allPeriods

      for (const pk of allPeriods) {
        const p = periods.get(pk)
        if (!p?.metrics || p.metrics.trips_completed == null) {
          tripsValues.push(null)
        } else {
          tripsValues.push(Number(p.metrics.trips_completed))
        }
      }

      // Build deltas: sequential delta from previous period
      const deltas = []
      for (let i = 1; i < tripsValues.length; i++) {
        const curr = tripsValues[i]
        const prev = tripsValues[i - 1]
        if (curr == null || prev == null || prev === 0) {
          deltas.push({ value: 0, delta_pct: 0, previous_value: 0 })
        } else {
          const diff = curr - prev
          const pct = (diff / prev) * 100
          deltas.push({ value: diff, delta_pct: pct, previous_value: prev })
        }
      }

      if (deltas.length < 2) continue

      const risk = classifyMomentumRisk(deltas, grain)
      if (risk === MOMENTUM_RISK.STABLE) continue

      const name = lineData.business_slice_name || 'Unknown'
      const label = buildMomentumPriorityLabel({ name, risk, grain, deltas })

      entities.push({
        id: `${cityKey}_${lineKey}`,
        name,
        cityName: cityData.city || cityKey,
        lineName: name,
        risk,
        label,
        deltas,
      })
    }
  }

  return sortMomentumAttention(entities).slice(0, maxResults)
}

export { RISK_PRIORITY, RISK_LABEL }
export default {
  MOMENTUM_RISK,
  detectConsecutiveDecline,
  detectMomentumAcceleration,
  classifyMomentumRisk,
  buildMomentumPriorityLabel,
  sortMomentumAttention,
  extractMomentumPriorityFromMatrix,
}
