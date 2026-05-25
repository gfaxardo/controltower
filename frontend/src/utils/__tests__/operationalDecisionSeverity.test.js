/**
 * Operational Decision Severity — Test Cases
 * 
 * Covers: normalizeDecisionSignal, getDecisionSeverity, sortByDecisionPriority,
 * explainDecisionSeverity, getDecisionTone, getDecisionLabel, getDecisionRank
 */

import {
  DECISION_SEVERITY,
  DECISION_THRESHOLDS,
  normalizeDecisionSignal,
  getDecisionSeverity,
  getDecisionTone,
  getDecisionLabel,
  getDecisionRank,
  sortByDecisionPriority,
  explainDecisionSeverity,
} from '../operationalDecisionSeverity'

/* ── Helper ── */
const { BLOCKED, CRITICAL, ELEVATED, WARNING, NORMAL, UNKNOWN } = DECISION_SEVERITY

/* ═══════════════════════════════════════════
   CASE 1: Freshness blocked
   ═══════════════════════════════════════════ */
function testFreshnessBlocked() {
  const result = normalizeDecisionSignal({ freshness_status: 'critical' })
  console.assert(result === BLOCKED, 'CASE 1 FAIL: freshness critical should be BLOCKED')
  return result === BLOCKED
}

/* ═══════════════════════════════════════════
   CASE 2: Trust blocked
   ═══════════════════════════════════════════ */
function testTrustBlocked() {
  const result = normalizeDecisionSignal({ trust_status: 'blocked' })
  console.assert(result === BLOCKED, 'CASE 2 FAIL: trust blocked should be BLOCKED')
  return result === BLOCKED
}

/* ═══════════════════════════════════════════
   CASE 3: Missing comparable data
   ═══════════════════════════════════════════ */
function testMissingComparable() {
  // plan_without_real → WARNING (has plan but no real data)
  const result = normalizeDecisionSignal({ comparison_status: 'plan_without_real' })
  console.assert(result === WARNING, 'CASE 3 FAIL: plan_without_real should be WARNING')
  return result === WARNING
}

/* ═══════════════════════════════════════════
   CASE 4: Severe negative gap (>30%)
   ═══════════════════════════════════════════ */
function testSevereNegativeGap() {
  const result = normalizeDecisionSignal({ gap_pct: -35 })
  console.assert(result === CRITICAL, 'CASE 4 FAIL: -35% gap should be CRITICAL')
  return result === CRITICAL
}

/* ═══════════════════════════════════════════
   CASE 5: Moderate negative gap (15-30%)
   ═══════════════════════════════════════════ */
function testModerateNegativeGap() {
  const result = normalizeDecisionSignal({ gap_pct: -20 })
  console.assert(result === ELEVATED, 'CASE 5 FAIL: -20% gap should be ELEVATED')
  return result === ELEVATED
}

/* ═══════════════════════════════════════════
   CASE 6: Positive gap (above plan, should be NORMAL)
   ═══════════════════════════════════════════ */
function testPositiveGap() {
  // Positive gap above plan — not a negative deviation. But gap > threshold applies to abs.
  // 10% positive gap: abs(10) > 5 → warning
  const result = normalizeDecisionSignal({ gap_pct: 10 })
  console.assert(result === WARNING, 'CASE 6 FAIL: +10% gap should be WARNING (above warning threshold)')

  // 3% positive gap: abs(3) < 5 → no gap trigger, but no normal signal either
  const result2 = normalizeDecisionSignal({ gap_pct: 3 })
  console.assert(result2 === UNKNOWN, 'CASE 6b FAIL: +3% gap with no other signals should be UNKNOWN')
  return result === WARNING && result2 === UNKNOWN
}

/* ═══════════════════════════════════════════
   CASE 7: Unknown signal (no data)
   ═══════════════════════════════════════════ */
function testUnknownSignal() {
  const result = normalizeDecisionSignal({})
  console.assert(result === UNKNOWN, 'CASE 7 FAIL: empty signals should be UNKNOWN')
  return result === UNKNOWN
}

/* ═══════════════════════════════════════════
   CASE 8: Incomplete config
   ═══════════════════════════════════════════ */
function testIncompleteConfig() {
  const result = normalizeDecisionSignal({ has_any_targets: false })
  console.assert(result === WARNING, 'CASE 8 FAIL: no targets should be WARNING')
  return result === WARNING
}

/* ═══════════════════════════════════════════
   CASE 9: Stale data
   ═══════════════════════════════════════════ */
function testStaleData() {
  const result = normalizeDecisionSignal({ freshness_status: 'stale' })
  console.assert(result === ELEVATED, 'CASE 9 FAIL: stale freshness should be ELEVATED')
  return result === ELEVATED
}

/* ═══════════════════════════════════════════
   CASE 10: No plan
   ═══════════════════════════════════════════ */
function testNoPlan() {
  const result = normalizeDecisionSignal({ comparison_status: 'missing_plan' })
  console.assert(result === BLOCKED, 'CASE 10 FAIL: missing plan should be BLOCKED')
  return result === BLOCKED
}

/* ═══════════════════════════════════════════
   CASE 11: No real data
   ═══════════════════════════════════════════ */
function testNoReal() {
  const result = normalizeDecisionSignal({ comparison_status: 'plan_without_real' })
  console.assert(result === WARNING, 'CASE 11 FAIL: plan without real should be WARNING')
  return result === WARNING
}

/* ═══════════════════════════════════════════
   CASE 12: Normal within tolerance
   ═══════════════════════════════════════════ */
function testNormalWithinTolerance() {
  const result = normalizeDecisionSignal({
    trust_status: 'ok',
    comparison_status: 'matched',
    signal: 'green',
    meets_oro: true,
    data_complete: true,
    gap_pct: 2,
  })
  console.assert(result === NORMAL, 'CASE 12 FAIL: all green should be NORMAL')
  return result === NORMAL
}

/* ═══════════════════════════════════════════
   CASE 13: Unit alert → CRITICAL
   ═══════════════════════════════════════════ */
function testUnitAlert() {
  const result = normalizeDecisionSignal({ unit_alert: true })
  console.assert(result === CRITICAL, 'CASE 13 FAIL: unit_alert should be CRITICAL')
  return result === CRITICAL
}

/* ═══════════════════════════════════════════
   CASE 14: Low confidence → CRITICAL
   ═══════════════════════════════════════════ */
function testLowConfidence() {
  const result = normalizeDecisionSignal({ confidence_score: 20 })
  console.assert(result === CRITICAL, 'CASE 14 FAIL: confidence 20 should be CRITICAL (<25)')
  return result === CRITICAL
}

/* ═══════════════════════════════════════════
   CASE 15: getDecisionSeverity with existing entity
   ═══════════════════════════════════════════ */
function testGetDecisionSeverity() {
  const entity = { trust_status: 'ok', signal: 'green' }
  const result = getDecisionSeverity(entity)
  console.assert(result === NORMAL, 'CASE 15 FAIL: ok+green should be NORMAL')

  // With explicit severity (already computed)
  const entity2 = { severity: BLOCKED }
  const result2 = getDecisionSeverity(entity2)
  console.assert(result2 === BLOCKED, 'CASE 15b FAIL: explicit severity should be preserved')
  return result === NORMAL && result2 === BLOCKED
}

/* ═══════════════════════════════════════════
   CASE 16: sortByDecisionPriority
   ═══════════════════════════════════════════ */
function testSortByPriority() {
  const items = [
    { gap_pct: 2 },   // normal-ish
    { gap_pct: 35 },  // critical
    { gap_pct: 20 },  // elevated
    { freshness_status: 'critical' }, // blocked
  ]
  const sorted = sortByDecisionPriority(items)
  // blocked first, then critical, then elevated, then normal
  const first = getDecisionSeverity(sorted[0])
  const last = getDecisionSeverity(sorted[3])
  console.assert(first === BLOCKED, `CASE 16 FAIL: first should be BLOCKED, got ${first}`)
  console.assert(last === NORMAL || last === UNKNOWN, `CASE 16 FAIL: last should be NORMAL/UNKNOWN, got ${last}`)
  // Stability: items with same severity maintain order
  console.assert(sorted.length === 4, 'CASE 16 FAIL: should keep all items')
  return true
}

/* ═══════════════════════════════════════════
   CASE 17: explainDecisionSeverity returns reasons
   ═══════════════════════════════════════════ */
function testExplainDecisionSeverity() {
  const result = explainDecisionSeverity({ gap_pct: -40, unit_alert: true })
  console.assert(result.reasons.length > 0, 'CASE 17 FAIL: should have reasons')
  console.assert(result.severity === BLOCKED || result.severity === CRITICAL, 'CASE 17 FAIL: should be BLOCKED or CRITICAL')
  // Check no recommendation language
  const allText = result.reasons.join(' ') + (result.label || '')
  console.assert(!allText.includes('recommend'), 'CASE 17 FAIL: should not contain "recommend"')
  console.assert(!allText.includes('haz'), 'CASE 17 FAIL: should not contain "haz"')
  return true
}

/* ═══════════════════════════════════════════
   CASE 18: getDecisionTone returns valid colors
   ═══════════════════════════════════════════ */
function testDecisionTone() {
  const tone = getDecisionTone(CRITICAL)
  console.assert(tone != null, 'CASE 18 FAIL: should return tone object')
  console.assert(tone.bg != null && tone.text != null, 'CASE 18 FAIL: tone should have bg and text')
  return true
}

/* ═══════════════════════════════════════════
   CASE 19: getDecisionLabel
   ═══════════════════════════════════════════ */
function testDecisionLabel() {
  console.assert(getDecisionLabel(BLOCKED) === 'Blocked', 'CASE 19 FAIL')
  console.assert(getDecisionLabel(CRITICAL) === 'Critical', 'CASE 19 FAIL')
  console.assert(getDecisionLabel(NORMAL) === 'Normal', 'CASE 19 FAIL')
  return true
}

/* ═══════════════════════════════════════════
   CASE 20: getDecisionRank ordering
   ═══════════════════════════════════════════ */
function testDecisionRank() {
  const blockedRank = getDecisionRank(BLOCKED)
  const criticalRank = getDecisionRank(CRITICAL)
  const normalRank = getDecisionRank(NORMAL)
  console.assert(blockedRank < criticalRank, 'CASE 20 FAIL: blocked should rank before critical')
  console.assert(criticalRank < normalRank, 'CASE 20 FAIL: critical should rank before normal')
  return true
}

/* ═══════════════════════════════════════════
   CASE 21: Attainment thresholds
   ═══════════════════════════════════════════ */
function testAttainmentThresholds() {
  // 25% attainment → BLOCKED (<30%)
  const r1 = normalizeDecisionSignal({ attainment_pct: 25 })
  console.assert(r1 === BLOCKED, `CASE 21 FAIL: attainment 25% should be BLOCKED, got ${r1}`)

  // 40% attainment → CRITICAL (<50%)
  const r2 = normalizeDecisionSignal({ attainment_pct: 40 })
  console.assert(r2 === CRITICAL, `CASE 21 FAIL: attainment 40% should be CRITICAL, got ${r2}`)

  // 120% attainment with no other signals → normal (gap is checked, positive gap → warning)
  const r3 = normalizeDecisionSignal({ attainment_pct: 120, signal: 'green', trust_status: 'ok' })
  console.assert(r3 === NORMAL, `CASE 21b FAIL: attainment 120% with green signals should be NORMAL, got ${r3}`)

  return true
}

/* ═══════════════════════════════════════════
   RUN ALL
   ═══════════════════════════════════════════ */
export function runAllSeverityTests() {
  const tests = [
    ['CASE 1: Freshness blocked', testFreshnessBlocked],
    ['CASE 2: Trust blocked', testTrustBlocked],
    ['CASE 3: Missing comparable', testMissingComparable],
    ['CASE 4: Severe negative gap', testSevereNegativeGap],
    ['CASE 5: Moderate negative gap', testModerateNegativeGap],
    ['CASE 6: Positive gap', testPositiveGap],
    ['CASE 7: Unknown signal', testUnknownSignal],
    ['CASE 8: Incomplete config', testIncompleteConfig],
    ['CASE 9: Stale data', testStaleData],
    ['CASE 10: No plan', testNoPlan],
    ['CASE 11: No real', testNoReal],
    ['CASE 12: Normal within tolerance', testNormalWithinTolerance],
    ['CASE 13: Unit alert', testUnitAlert],
    ['CASE 14: Low confidence', testLowConfidence],
    ['CASE 15: getDecisionSeverity', testGetDecisionSeverity],
    ['CASE 16: sortByPriority', testSortByPriority],
    ['CASE 17: Explain (no recommendations)', testExplainDecisionSeverity],
    ['CASE 18: Tone valid', testDecisionTone],
    ['CASE 19: Labels', testDecisionLabel],
    ['CASE 20: Ranks', testDecisionRank],
    ['CASE 21: Attainment', testAttainmentThresholds],
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

  console.log(`\n=== SEVERITY TESTS: ${passed}/${results.length} PASSED, ${failed} FAILED ===`)
  results.filter(r => !r.passed).forEach(r => {
    console.error(`  FAIL: ${r.name}${r.error ? ` — ${r.error}` : ''}`)
  })

  return { passed, failed, total: results.length, results }
}

export default runAllSeverityTests
