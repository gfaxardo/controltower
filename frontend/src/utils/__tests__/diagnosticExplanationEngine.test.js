/**
 * Diagnostic Explanation Engine — Test Cases
 * 
 * Covers: extractDiagnosticFactors, extractDominantDiagnosticFactor,
 * buildDiagnosticExplanation, explainBlockedState, explainCriticalState,
 * explainElevatedState, explainUnknownState, summarizeDiagnosticSignals
 */

import {
  DIAGNOSTIC_FACTOR,
  extractDiagnosticFactors,
  extractDominantDiagnosticFactor,
  buildDiagnosticExplanation,
  explainBlockedState,
  explainCriticalState,
  explainElevatedState,
  explainUnknownState,
  summarizeDiagnosticSignals,
} from '../diagnosticExplanationEngine'

/* ═══════════════════════════════════════════
   CASE 1: Freshness degraded → dominant FRESHNESS_DEGRADED
   ═══════════════════════════════════════════ */
function testFreshnessDegradedFactor() {
  const dominant = extractDominantDiagnosticFactor({ freshness_status: 'critical', lag_days: 5 })
  console.assert(dominant.factor === DIAGNOSTIC_FACTOR.FRESHNESS_DEGRADED,
    `CASE 1 FAIL: expected FRESHNESS_DEGRADED, got ${dominant.factor}`)
  console.assert(dominant.detail.includes('5d'), 'CASE 1 FAIL: detail should include lag')
  return true
}

/* ═══════════════════════════════════════════
   CASE 2: Trust blocked → dominant TRUST_DEGRADED
   ═══════════════════════════════════════════ */
function testTrustDegradedFactor() {
  const dominant = extractDominantDiagnosticFactor({ trust_status: 'blocked' })
  console.assert(dominant.factor === DIAGNOSTIC_FACTOR.TRUST_DEGRADED,
    `CASE 2 FAIL: expected TRUST_DEGRADED, got ${dominant.factor}`)
  return true
}

/* ═══════════════════════════════════════════
   CASE 3: Severe gap → dominant SEVERE_GAP
   ═══════════════════════════════════════════ */
function testSevereGapFactor() {
  const dominant = extractDominantDiagnosticFactor({ gap_revenue_pct: -35 })
  console.assert(dominant.factor === DIAGNOSTIC_FACTOR.SEVERE_GAP,
    `CASE 3 FAIL: expected SEVERE_GAP, got ${dominant.factor}`)
  console.assert(dominant.detail.includes('35'), 'CASE 3 FAIL: detail should include gap value')
  return true
}

/* ═══════════════════════════════════════════
   CASE 4: Unit alert → dominant UNIT_ALERT_TRIGGERED
   ═══════════════════════════════════════════ */
function testUnitAlertFactor() {
  const dominant = extractDominantDiagnosticFactor({ unit_alert: true, gap_revenue_pct: -5 })
  // gap -5% is only warning level, unit_alert should be priority
  console.assert(dominant.factor === DIAGNOSTIC_FACTOR.UNIT_ALERT_TRIGGERED,
    `CASE 4 FAIL: expected UNIT_ALERT_TRIGGERED, got ${dominant.factor}`)
  return true
}

/* ═══════════════════════════════════════════
   CASE 5: Missing plan → dominant MISSING_PLAN
   ═══════════════════════════════════════════ */
function testMissingPlanFactor() {
  const dominant = extractDominantDiagnosticFactor({ comparison_status: 'missing_plan' })
  console.assert(dominant.factor === DIAGNOSTIC_FACTOR.MISSING_PLAN,
    `CASE 5 FAIL: expected MISSING_PLAN, got ${dominant.factor}`)
  return true
}

/* ═══════════════════════════════════════════
   CASE 6: Config incomplete → dominant CONFIG_INCOMPLETE
   ═══════════════════════════════════════════ */
function testConfigIncompleteFactor() {
  const dominant = extractDominantDiagnosticFactor({ has_any_targets: false })
  console.assert(dominant.factor === DIAGNOSTIC_FACTOR.CONFIG_INCOMPLETE,
    `CASE 6 FAIL: expected CONFIG_INCOMPLETE, got ${dominant.factor}`)
  return true
}

/* ═══════════════════════════════════════════
   CASE 7: Data incomplete → dominant DATA_INCOMPLETE
   ═══════════════════════════════════════════ */
function testDataIncompleteFactor() {
  const dominant = extractDominantDiagnosticFactor({ data_complete: false, manual_kpis_pending: 3 })
  console.assert(dominant.factor === DIAGNOSTIC_FACTOR.DATA_INCOMPLETE,
    `CASE 7 FAIL: expected DATA_INCOMPLETE, got ${dominant.factor}`)
  console.assert(dominant.detail.includes('3'), 'CASE 7 FAIL: detail should include pending count')
  return true
}

/* ═══════════════════════════════════════════
   CASE 8: No signals → INSUFFICIENT_SIGNAL
   ═══════════════════════════════════════════ */
function testInsufficientSignalFactor() {
  const dominant = extractDominantDiagnosticFactor({})
  console.assert(dominant.factor === DIAGNOSTIC_FACTOR.INSUFFICIENT_SIGNAL,
    `CASE 8 FAIL: expected INSUFFICIENT_SIGNAL, got ${dominant.factor}`)
  return true
}

/* ═══════════════════════════════════════════
   CASE 9: buildDiagnosticExplanation — structured output
   ═══════════════════════════════════════════ */
function testBuildExplanation() {
  const explanation = buildDiagnosticExplanation({
    gap_revenue_pct: -40,
    gap_trips_pct: -25,
    freshness_status: 'critical',
  })

  console.assert(explanation.dominantFactor != null, 'CASE 9 FAIL: should have dominantFactor')
  console.assert(explanation.severity != null, 'CASE 9 FAIL: should have severity')
  console.assert(explanation.summary != null, 'CASE 9 FAIL: should have summary')

  // Freshness critical → blocked, which is higher priority than severe gap
  console.assert(explanation.dominantFactor.factor === DIAGNOSTIC_FACTOR.FRESHNESS_DEGRADED,
    `CASE 9 FAIL: freshness should dominate, got ${explanation.dominantFactor.factor}`)

  // Should have secondary factors (the gap factors)
  console.assert(explanation.secondaryFactors.length > 0,
    'CASE 9 FAIL: should have secondary factors for the gaps')
  return true
}

/* ═══════════════════════════════════════════
   CASE 10: explainBlockedState — no recommendations
   ═══════════════════════════════════════════ */
function testBlockedStateNoRecommendations() {
  const explanation = explainBlockedState({ freshness_status: 'critical' })
  console.assert(explanation.explanation.includes('Blocked due to'),
    'CASE 10 FAIL: should start with "Blocked due to"')
  console.assert(!explanation.explanation.includes('recommend'),
    'CASE 10 FAIL: should not contain "recommend"')
  console.assert(!explanation.explanation.includes('haz'),
    'CASE 10 FAIL: should not contain "haz"')
  console.assert(!explanation.explanation.includes('acción'),
    'CASE 10 FAIL: should not contain "acción"')
  return true
}

/* ═══════════════════════════════════════════
   CASE 11: explainCriticalState — no recommendations
   ═══════════════════════════════════════════ */
function testCriticalStateNoRecommendations() {
  const explanation = explainCriticalState({ gap_revenue_pct: -40 })
  console.assert(explanation.explanation.includes('Critical due to'),
    'CASE 11 FAIL: should start with "Critical due to"')
  console.assert(!explanation.explanation.includes('recommend'),
    'CASE 11 FAIL: should not contain "recommend"')
  return true
}

/* ═══════════════════════════════════════════
   CASE 12: explainElevatedState
   ═══════════════════════════════════════════ */
function testElevatedState() {
  const explanation = explainElevatedState({ gap_revenue_pct: -20 })
  console.assert(explanation.explanation.includes('Elevated due to'),
    'CASE 12 FAIL: should start with "Elevated due to"')
  return true
}

/* ═══════════════════════════════════════════
   CASE 13: explainUnknownState
   ═══════════════════════════════════════════ */
function testUnknownState() {
  const explanation = explainUnknownState({})
  console.assert(explanation.explanation.includes('Unknown'),
    'CASE 13 FAIL: should include "Unknown"')
  return true
}

/* ═══════════════════════════════════════════
   CASE 14: summarizeDiagnosticSignals — compact format
   ═══════════════════════════════════════════ */
function testSummarizeSignals() {
  const summary = summarizeDiagnosticSignals({
    gap_revenue_pct: -35,
    gap_trips_pct: -20,
    confidence_score: 45,
    trust_status: 'warning',
    freshness_status: 'stale',
  })
  console.assert(summary.includes('revenue: -35'),
    'CASE 14 FAIL: should include revenue gap')
  console.assert(summary.includes('trips: -20'),
    'CASE 14 FAIL: should include trips gap')
  console.assert(summary.includes('conf: 45'),
    'CASE 14 FAIL: should include confidence')
  console.assert(summary.includes('trust: warning'),
    'CASE 14 FAIL: should include trust')
  console.assert(summary.includes('freshness: stale'),
    'CASE 14 FAIL: should include freshness')
  return true
}

/* ═══════════════════════════════════════════
   CASE 15: extractDiagnosticFactors — multiple factors
   ═══════════════════════════════════════════ */
function testMultipleFactors() {
  const factors = extractDiagnosticFactors({
    freshness_status: 'stale',
    confidence_score: 20,
    data_complete: false,
  })
  console.assert(factors.length >= 3,
    `CASE 15 FAIL: should have at least 3 factors, got ${factors.length}`)

  const factorKeys = factors.map(f => f.factor)
  console.assert(factorKeys.includes(DIAGNOSTIC_FACTOR.STALE_DATA),
    'CASE 15 FAIL: should include STALE_DATA')
  console.assert(factorKeys.includes(DIAGNOSTIC_FACTOR.CONFIDENCE_DEGRADED),
    'CASE 15 FAIL: should include CONFIDENCE_DEGRADED')
  console.assert(factorKeys.includes(DIAGNOSTIC_FACTOR.DATA_INCOMPLETE),
    'CASE 15 FAIL: should include DATA_INCOMPLETE')
  return true
}

/* ═══════════════════════════════════════════
   CASE 16: Sustained negative trend
   ═══════════════════════════════════════════ */
function testSustainedNegativeTrend() {
  const dominant = extractDominantDiagnosticFactor({
    weeks_declining_consecutively: 4,
    gap_revenue_pct: -8,
  })
  // 4 weeks declining → SUSTAINED_NEGATIVE (priority 10)
  // gap -8% → elevated (priority 8) → but only checked if no higher match
  console.assert(dominant.factor === DIAGNOSTIC_FACTOR.SUSTAINED_NEGATIVE,
    `CASE 16 FAIL: expected SUSTAINED_NEGATIVE, got ${dominant.factor}`)
  return true
}

/* ═══════════════════════════════════════════
   CASE 17: Prohibited language check — all explanation functions
   ═══════════════════════════════════════════ */
function testNoRecommendationLanguage() {
  const prohibitedWords = ['recommend', 'recomend', 'haz', 'ejecuta', 'llama', 'campaña', 'IA detect', 'sugerimos', 'deberías', 'acción']
  const testCases = [
    { fn: explainBlockedState, input: { freshness_status: 'critical' }, label: 'explainBlockedState' },
    { fn: explainCriticalState, input: { gap_revenue_pct: -40 }, label: 'explainCriticalState' },
    { fn: explainElevatedState, input: { gap_revenue_pct: -20 }, label: 'explainElevatedState' },
    { fn: explainUnknownState, input: {}, label: 'explainUnknownState' },
  ]

  for (const { fn, input, label } of testCases) {
    const result = fn(input)
    const text = (result.explanation || '') + (result.summary || '')
    for (const word of prohibitedWords) {
      if (text.toLowerCase().includes(word.toLowerCase())) {
        console.error(`CASE 17 FAIL: ${label} contains prohibited word "${word}": "${text}"`)
        return false
      }
    }
  }
  return true
}

/* ═══════════════════════════════════════════
   RUN ALL
   ═══════════════════════════════════════════ */
export function runAllExplanationTests() {
  const tests = [
    ['CASE 1: Freshness degraded', testFreshnessDegradedFactor],
    ['CASE 2: Trust degraded', testTrustDegradedFactor],
    ['CASE 3: Severe gap', testSevereGapFactor],
    ['CASE 4: Unit alert', testUnitAlertFactor],
    ['CASE 5: Missing plan', testMissingPlanFactor],
    ['CASE 6: Config incomplete', testConfigIncompleteFactor],
    ['CASE 7: Data incomplete', testDataIncompleteFactor],
    ['CASE 8: Insufficient signal', testInsufficientSignalFactor],
    ['CASE 9: Build explanation', testBuildExplanation],
    ['CASE 10: Blocked (no recs)', testBlockedStateNoRecommendations],
    ['CASE 11: Critical (no recs)', testCriticalStateNoRecommendations],
    ['CASE 12: Elevated state', testElevatedState],
    ['CASE 13: Unknown state', testUnknownState],
    ['CASE 14: Summarize signals', testSummarizeSignals],
    ['CASE 15: Multiple factors', testMultipleFactors],
    ['CASE 16: Sustained trend', testSustainedNegativeTrend],
    ['CASE 17: Prohibited language', testNoRecommendationLanguage],
  ]

  const results = tests.map(([name, fn]) => {
    try {
      const passed = fn()
      return { name, passed, error: null }
    } catch (e) {
      return { name, passed: false, error: e.message }
    }
  })

  const passed = results.filter(r => r.passed).length
  const failed = results.filter(r => !r.passed).length

  console.log(`\n=== EXPLANATION TESTS: ${passed}/${results.length} PASSED, ${failed} FAILED ===`)
  results.filter(r => !r.passed).forEach(r => {
    console.error(`  FAIL: ${r.name}${r.error ? ` — ${r.error}` : ''}`)
  })

  return { passed, failed, total: results.length, results }
}

export default runAllExplanationTests
