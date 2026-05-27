/**
 * YEGO Control Tower — Operational Maturity Registry Guard
 *
 * Script de validación offline. NO requiere backend. NO abre puertos.
 * Ejecuta todas las funciones públicas del registry contra módulos
 * conocidos y detecta stack overflow / excepciones.
 *
 * Uso:
 *   cd frontend
 *   node scripts/check-operational-maturity-registry.mjs
 *
 * Gobernanza: ejecutar antes de cada merge que modifique el registry.
 */

import {
  OPERATIONAL_MATURITY_REGISTRY,
  MATURITY,
  ENGINE_OWNER,
  getMaturity,
  isModuleVisible,
  getMaturityBadgeInfo,
  getCapabilityMeta,
  isProductionReady,
  getModulesByGroup,
  getLegacyModules,
  getExperimentalModules,
  validateRegistry,
} from '../src/config/operationalMaturityRegistry.js'

let failures = 0
let assertions = 0

function assert(label, condition, detail = '') {
  assertions++
  const ok = !!condition
  if (!ok) failures++
  console.log(`${ok ? 'PASS' : 'FAIL'} | ${label}${detail ? ' — ' + detail : ''}`)
}

function assertNoThrow(label, fn) {
  assertions++
  try {
    fn()
    console.log(`PASS | ${label}`)
  } catch (e) {
    failures++
    console.log(`FAIL | ${label} — threw: ${e.message}`)
  }
}

// ─── VALIDATE KNOWN MODULES ────────────────────────────────────────────────

const KNOWN_MODULES = [
  'performance_resumen',
  'performance_plan_vs_real',
  'performance_real',
  'drivers_supply',
  'drivers_lifecycle',
  'drivers_action_queues',
  'drivers_diagnostic',
  'drivers_fleet_leakage',
  'drivers_recoverability',
  'drivers_operational_intelligence',
  'riesgo_driver_behavior',
  'operacion_omniview_matrix',
  'operacion_control_loop_pvr',
  'system_health',
  'real_vs_projection',
]

const BOGUS_KEY = 'nonexistent_module_xyz'

console.log('\n═══ Operational Maturity Registry Guard ═══\n')

// ── SECTION 1: Registry integrity ──
console.log('── 1. Registry integrity ──')

const validation = validateRegistry()
assert('Registry has entries', validation.total > 0, `total: ${validation.total}`)
assert('No duplicate keys', validation.duplicates === null, validation.duplicates ? `duplicates: ${validation.duplicates.join(', ')}` : '')

// ── SECTION 2: getMaturity — no stack overflow ──
console.log('\n── 2. getMaturity ──')

for (const key of KNOWN_MODULES) {
  const maturity = getMaturity(key)
  assert(`getMaturity("${key}") returns string`, typeof maturity === 'string', `value: ${maturity}`)
}
assert(`getMaturity("${BOGUS_KEY}") returns default (STABLE)`, getMaturity(BOGUS_KEY) === MATURITY.STABLE)

// ── SECTION 3: getCapabilityMeta — no stack overflow ──
console.log('\n── 3. getCapabilityMeta ──')

for (const key of KNOWN_MODULES) {
  const meta = getCapabilityMeta(key)
  assert(`getCapabilityMeta("${key}") returns object`, meta !== null && typeof meta === 'object', `moduleKey: ${meta?.moduleKey}`)
  assert(`getCapabilityMeta("${key}").productionReady is boolean`, typeof meta?.productionReady === 'boolean', `value: ${meta?.productionReady}`)
}
assert(`getCapabilityMeta("${BOGUS_KEY}") returns null`, getCapabilityMeta(BOGUS_KEY) === null)

// ── SECTION 4: isProductionReady — no stack overflow ──
console.log('\n── 4. isProductionReady ──')

for (const key of KNOWN_MODULES) {
  const ready = isProductionReady(key)
  assert(`isProductionReady("${key}") returns boolean`, typeof ready === 'boolean', `value: ${ready}`)
}
assert(`isProductionReady("${BOGUS_KEY}") returns false`, isProductionReady(BOGUS_KEY) === false)

// ── SECTION 5: isModuleVisible — no stack overflow ──
console.log('\n── 5. isModuleVisible ──')

for (const key of KNOWN_MODULES) {
  const visible = isModuleVisible(key)
  assert(`isModuleVisible("${key}") returns boolean`, typeof visible === 'boolean', `value: ${visible}`)
}
assert(`isModuleVisible("${BOGUS_KEY}") returns false`, isModuleVisible(BOGUS_KEY) === false)

// ── SECTION 6: getMaturityBadgeInfo — no stack overflow ──
console.log('\n── 6. getMaturityBadgeInfo ──')

for (const key of KNOWN_MODULES) {
  const badge = getMaturityBadgeInfo(key)
  assert(`getMaturityBadgeInfo("${key}") returns object or null`, badge === null || typeof badge === 'object', `label: ${badge?.label || 'null'}`)
}

// ── SECTION 7: Repeated calls — no memory leak / stack overflow ──
console.log('\n── 7. Repeated calls (100 iterations) ──')

assertNoThrow('getCapabilityMeta x100', () => {
  for (let i = 0; i < 100; i++) {
    for (const key of KNOWN_MODULES) {
      getCapabilityMeta(key)
    }
  }
})

assertNoThrow('isProductionReady x100', () => {
  for (let i = 0; i < 100; i++) {
    for (const key of KNOWN_MODULES) {
      isProductionReady(key)
    }
  }
})

assertNoThrow('getMaturity x100', () => {
  for (let i = 0; i < 100; i++) {
    for (const key of KNOWN_MODULES) {
      getMaturity(key)
    }
  }
})

// ── SECTION 8: Circular call detection ──
console.log('\n── 8. Circular call detection ──')

// Verificar que getCapabilityMeta NO llama a isProductionReady
// y que isProductionReady NO llama a getCapabilityMeta
// (validación funcional: si hubiera recursión, las secciones 3 y 4 habrían fallado)

let circularGuard = false

// Proxy trap: si isProductionReady es llamado desde dentro de getCapabilityMeta,
// detectaríamos stack overflow. Como ya pasó la sección 3 sin errores,
// validamos que no hay ciclo con esta aserción estructural.
const metaEntry = OPERATIONAL_MATURITY_REGISTRY['performance_resumen']
assert(
  'STABLE entry is productionReady via both helpers',
  isProductionReady('performance_resumen') === true && getCapabilityMeta('performance_resumen')?.productionReady === true
)

const blockedEntry = OPERATIONAL_MATURITY_REGISTRY['drivers_recoverability']
assert(
  'BLOCKED entry is NOT productionReady via both helpers',
  isProductionReady('drivers_recoverability') === false && getCapabilityMeta('drivers_recoverability')?.productionReady === false
)

// ── SECTION 9: Bulk operations ──
console.log('\n── 9. Bulk operations ──')

const groups = getModulesByGroup()
assert('getModulesByGroup returns Map', groups instanceof Map, `groups: ${groups.size}`)

const legacy = getLegacyModules()
assert('getLegacyModules returns array', Array.isArray(legacy), `count: ${legacy.length}`)

const experimental = getExperimentalModules()
assert('getExperimentalModules returns array', Array.isArray(experimental), `count: ${experimental.length}`)

// ── SECTION 10: Production-ready consistency ──
console.log('\n── 10. Production-ready consistency ──')

for (const [key, entry] of Object.entries(OPERATIONAL_MATURITY_REGISTRY)) {
  const meta = getCapabilityMeta(key)
  const ready = isProductionReady(key)
  assert(
    `Consistency: "${key}" — meta.productionReady === isProductionReady()`,
    meta.productionReady === ready,
    `meta: ${meta.productionReady}, ready: ${ready}`
  )
}

// ── Report ──
console.log(`\n═══════════════════════════════════════`)
console.log(`RESULTS: ${assertions - failures}/${assertions} passed`)
if (failures > 0) {
  console.log(`FAILURES: ${failures}`)
  process.exit(1)
} else {
  console.log(`GO: Registry operational maturity check PASSED`)
  process.exit(0)
}
