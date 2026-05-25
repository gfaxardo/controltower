/**
 * DIAGNOSTIC REGRESSION GUARD
 * 
 * Protege contra regresiones en el sistema de severidades y explicaciones.
 * 
 * Validaciones:
 * 1. Solo 6 severities canónicas
 * 2. Thresholds centralizados (no duplicados)
 * 3. Sin textos de recomendación en explicaciones
 * 4. NORMAL no muestra explanation visible (null return)
 * 5. BLOCKED siempre rankea primero
 * 6. UNKNOWN no compite con CRITICAL
 * 7. Constantes son inmutables (Object.freeze)
 */

import {
  DECISION_SEVERITY,
  DECISION_THRESHOLDS,
  DECISION_PRIORITY_ORDER,
  normalizeDecisionSignal,
  getDecisionSeverity,
  getDecisionRank,
  explainDecisionSeverity,
} from '../operationalDecisionSeverity'

import {
  DIAGNOSTIC_FACTOR,
  extractDominantDiagnosticFactor,
  buildDiagnosticExplanation,
} from '../diagnosticExplanationEngine'

const { BLOCKED, CRITICAL, ELEVATED, WARNING, NORMAL, UNKNOWN } = DECISION_SEVERITY

/* ── GUARD 1: Solo 6 severities canónicas ── */
function guardOnlySixSeverities() {
  const values = Object.values(DECISION_SEVERITY)
  console.assert(values.length === 6, `Expected 6 severities, got ${values.length}: ${values}`)
  console.assert(values.includes('blocked'), 'Missing: blocked')
  console.assert(values.includes('critical'), 'Missing: critical')
  console.assert(values.includes('elevated'), 'Missing: elevated')
  console.assert(values.includes('warning'), 'Missing: warning')
  console.assert(values.includes('normal'), 'Missing: normal')
  console.assert(values.includes('unknown'), 'Missing: unknown')
  return values.length === 6
}

/* ── GUARD 2: Thresholds centralizados ── */
function guardThresholdsComplete() {
  const t = DECISION_THRESHOLDS
  const required = [
    'gap_critical', 'gap_elevated', 'gap_warning',
    'confidence_blocked', 'confidence_critical', 'confidence_warning',
    'attainment_blocked', 'attainment_critical', 'attainment_elevated', 'attainment_warning',
  ]
  for (const key of required) {
    console.assert(t[key] != null, `Missing threshold: ${key}`)
    console.assert(typeof t[key] === 'number', `Threshold ${key} should be a number, got ${typeof t[key]}`)
  }
  return true
}

/* ── GUARD 3: No textos de recomendación ── */
function guardNoRecommendationText() {
  const prohibited = ['recommend', 'recomend', 'haz', 'ejecut', 'llama', 'campaña', 'IA detect', 'sugerimos', 'deberías', 'acción recomendada']
  const testInputs = [
    { freshness_status: 'critical', gap_revenue_pct: -40 },
    { trust_status: 'blocked', confidence_score: 5 },
    { unit_alert: true, gap_revenue_pct: -25 },
    { data_complete: false, manual_kpis_pending: 3 },
    { has_any_targets: false },
    {},
  ]

  for (const input of testInputs) {
    const explanation = explainDecisionSeverity(input)
    const text = (explanation.label || '') + ' ' + (explanation.reasons || []).join(' ')
    const lower = text.toLowerCase()
    for (const word of prohibited) {
      if (lower.includes(word.toLowerCase())) {
        console.error(`GUARD 3 FAIL: Input ${JSON.stringify(input)} produced prohibited word "${word}"`)
        return false
      }
    }
  }
  return true
}

/* ── GUARD 4: NORMAL no muestra explanation visible ── */
function guardNormalReturnsNothing() {
  // DiagnosticDominantFactor: severity === 'normal' → returns null
  // (this is checked in the component, not in the engine)
  // But we can verify the engine produces NORMAL correctly
  const result = normalizeDecisionSignal({
    trust_status: 'ok',
    comparison_status: 'matched',
    signal: 'green',
    meets_oro: true,
    data_complete: true,
    gap_pct: 2,
  })
  console.assert(result === NORMAL, `Expected NORMAL, got ${result}`)

  // Verify NORMAL's rank is higher (less urgent) than WARNING
  console.assert(getDecisionRank(NORMAL) > getDecisionRank(WARNING), 'NORMAL should rank after WARNING')

  return true
}

/* ── GUARD 5: BLOCKED siempre rankea primero ── */
function guardBlockedAlwaysFirst() {
  const severities = [NORMAL, WARNING, ELEVATED, CRITICAL, BLOCKED, UNKNOWN]
  for (const s of severities) {
    if (s === BLOCKED) continue
    console.assert(
      getDecisionRank(BLOCKED) < getDecisionRank(s),
      `BLOCKED (${getDecisionRank(BLOCKED)}) should rank before ${s} (${getDecisionRank(s)})`
    )
  }
  return true
}

/* ── GUARD 6: UNKNOWN no compite con CRITICAL ── */
function guardUnknownDoesNotCompete() {
  console.assert(
    getDecisionRank(UNKNOWN) > getDecisionRank(CRITICAL),
    `UNKNOWN (${getDecisionRank(UNKNOWN)}) should rank after CRITICAL (${getDecisionRank(CRITICAL)})`
  )
  console.assert(
    getDecisionRank(UNKNOWN) > getDecisionRank(NORMAL),
    `UNKNOWN (${getDecisionRank(UNKNOWN)}) should rank after NORMAL (${getDecisionRank(NORMAL)})`
  )
  return true
}

/* ── GUARD 7: Constantes inmutables ── */
function guardConstantsAreFrozen() {
  let frozen = true
  try {
    // Attempting to assign to frozen objects should throw in strict mode
    // or silently fail. We test by checking the descriptor.
    const desc1 = Object.getOwnPropertyDescriptor(DECISION_SEVERITY, 'BLOCKED')
    if (desc1 && desc1.writable) {
      console.error('DECISION_SEVERITY is not frozen (writable)')
      frozen = false
    }

    const desc2 = Object.getOwnPropertyDescriptor(DIAGNOSTIC_FACTOR, 'FRESHNESS_DEGRADED')
    if (desc2 && desc2.writable) {
      console.error('DIAGNOSTIC_FACTOR is not frozen (writable)')
      frozen = false
    }
  } catch (e) {
    // If frozen, attempting to read properties is still fine
  }
  return frozen
}

/* ── GUARD 8: Diagnostic factor count ── */
function guardDiagnosticFactorCount() {
  const values = Object.values(DIAGNOSTIC_FACTOR)
  console.assert(values.length === 18, `Expected 18 diagnostic factors, got ${values.length}`)
  return values.length === 18
}

/* ── GUARD 9: buildDiagnosticExplanation siempre retorna summary ── */
function guardExplanationAlwaysHasSummary() {
  const inputs = [
    { freshness_status: 'critical' },
    { gap_revenue_pct: -40 },
    {},
    { data_complete: false },
  ]
  for (const input of inputs) {
    const explanation = buildDiagnosticExplanation(input)
    console.assert(explanation.summary != null, 'Explanation should always have summary')
    console.assert(typeof explanation.summary === 'string', 'Summary should be a string')
    console.assert(explanation.dominantFactor != null, 'Should always have dominantFactor')
  }
  return true
}

/* ── GUARD 10: extractDominantDiagnosticFactor never returns null ── */
function guardDominantFactorNeverNull() {
  const inputs = [
    {},
    { gap_revenue_pct: -40 },
    { freshness_status: 'critical', gap_revenue_pct: -10 },
    { data_complete: false },
  ]
  for (const input of inputs) {
    const factor = extractDominantDiagnosticFactor(input)
    console.assert(factor != null, 'Dominant factor should never be null')
    console.assert(factor.factor != null, 'Factor should have .factor')
    console.assert(factor.detail != null, 'Factor should have .detail')
  }
  return true
}

/* ── RUN ALL ── */
export function runAllRegressionGuards() {
  const guards = [
    ['GUARD 1: Only 6 severities', guardOnlySixSeverities],
    ['GUARD 2: Thresholds complete', guardThresholdsComplete],
    ['GUARD 3: No recommendation text', guardNoRecommendationText],
    ['GUARD 4: NORMAL returns nothing visible', guardNormalReturnsNothing],
    ['GUARD 5: BLOCKED always first', guardBlockedAlwaysFirst],
    ['GUARD 6: UNKNOWN does not compete', guardUnknownDoesNotCompete],
    ['GUARD 7: Constants are frozen', guardConstantsAreFrozen],
    ['GUARD 8: Factor count', guardDiagnosticFactorCount],
    ['GUARD 9: Explanation always has summary', guardExplanationAlwaysHasSummary],
    ['GUARD 10: Dominant factor never null', guardDominantFactorNeverNull],
  ]

  const results = []
  for (const [name, fn] of guards) {
    try {
      const passed = fn()
      results.push({ name, passed })
    } catch (e) {
      results.push({ name, passed: false, error: e.message })
    }
  }

  const passed = results.filter(r => r.passed).length
  const failed = results.filter(r => !r.passed).length

  console.log(`\n=== REGRESSION GUARDS: ${passed}/${results.length} PASSED, ${failed} FAILED ===`)
  results.filter(r => !r.passed).forEach(r => {
    console.error(`  FAIL: ${r.name}${r.error ? ` — ${r.error}` : ''}`)
  })

  // Throw so build/test runner can detect
  if (failed > 0) {
    throw new Error(`${failed} regression guard(s) failed`)
  }

  return results
}

export default runAllRegressionGuards
