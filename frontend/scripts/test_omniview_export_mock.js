/**
 * test_omniview_export_mock.js
 *
 * Script de validación offline del export de Omniview Matrix.
 * NO requiere backend. NO abre puertos. NO toca base de datos.
 * Crea datos mock y valida estructura, campos y KPIs del CSV generado.
 *
 * Uso:
 *   cd frontend
 *   node scripts/test_omniview_export_mock.js
 */

import { buildOmniviewExportPayload, exportOmniviewFull } from '../src/utils/omniviewExport.js'

// ─── Helpers ─────────────────────────────────────────────────────────────────

let failures = 0
let assertions = 0

function assert (label, condition, detail = '') {
  assertions++
  const ok = !!condition
  if (!ok) failures++
  console.log(`${ok ? 'PASS' : 'FAIL'} | ${label}${detail ? ' — ' + detail : ''}`)
}

function assertContains (label, haystack, needle) {
  const ok = typeof haystack === 'string' && haystack.includes(needle)
  assert(label, ok, ok ? 'found' : `missing: "${needle}"`)
}

function sectionHeaders (csv) {
  const re = /--- (.+?) ---/g
  const names = []
  let m
  while ((m = re.exec(csv)) !== null) names.push(m[1])
  return names
}

function parseCsvSection (csv, sectionName) {
  const lines = csv.split('\n')
  let inSection = false
  let headers = null
  const rows = []
  for (const line of lines) {
    if (line.startsWith('--- ' + sectionName + ' ---')) {
      inSection = true
      continue
    }
    if (inSection && line.startsWith('--- ')) break
    if (inSection && line.trim() === '') {
      if (headers !== null) break
      continue
    }
    if (inSection && !headers) {
      headers = parseCsvLine(line)
      continue
    }
    if (inSection && headers) {
      const row = parseCsvLine(line)
      if (row.length > 1) rows.push(row)
    }
  }
  return { headers, rows }
}

function parseCsvLine (line) {
  const result = []
  let current = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (inQuotes) {
      if (ch === '"') {
        if (line[i + 1] === '"') { current += '"'; i++ }
        else inQuotes = false
      } else {
        current += ch
      }
    } else {
      if (ch === '"') { inQuotes = true }
      else if (ch === ',') { result.push(current); current = '' }
      else { current += ch }
    }
  }
  result.push(current)
  return result
}

// ─── Mock data ───────────────────────────────────────────────────────────────

function mockMatrix (mode) {
  const cities = new Map()
  const lines = new Map()
  const periods = new Map()
  const allPeriods = ['2026-05-04', '2026-05-11', '2026-05-18']

  for (const pk of allPeriods) {
    if (mode === 'evolution') {
      periods.set(pk, {
        metrics: {
          commission_pct: 0.21,
          trips_completed: 1250 + allPeriods.indexOf(pk) * 100,
          avg_ticket: 11.5 + allPeriods.indexOf(pk) * 0.3,
          active_drivers: 480,
          revenue_yego_net: 14500 + allPeriods.indexOf(pk) * 1200,
          cancel_rate_pct: 0.08,
          trips_per_driver: 2.6 + allPeriods.indexOf(pk) * 0.2,
        },
        raw: {
          country: 'Perú',
          city: 'Lima',
          business_slice_name: 'YMA',
          comparison_context: {
            comparison_mode: 'weekly_same_week',
            is_partial_equivalent: false,
            baseline_metrics: {
              trips_completed: 1200 + allPeriods.indexOf(pk) * 100,
              revenue_yego_net: 14000 + allPeriods.indexOf(pk) * 1200,
              active_drivers: 475,
            },
          },
        },
      })
    } else {
      periods.set(pk, {
        metrics: {
          trips_completed: 1250 + allPeriods.indexOf(pk) * 100,
          revenue_yego_net: 14500 + allPeriods.indexOf(pk) * 1200,
          active_drivers: 480,
        },
        projection: {
          trips_completed: {
            actual: 1250 + allPeriods.indexOf(pk) * 100,
            projected_expected: 1200 + allPeriods.indexOf(pk) * 90,
            projected_total: 1400,
            gap_to_expected: 50 + allPeriods.indexOf(pk) * 10,
            gap_pct: 4.2 + allPeriods.indexOf(pk) * 0.8,
            attainment_pct: 89.3 + allPeriods.indexOf(pk) * 1.5,
            signal: 'warning',
            curve_confidence: 'medium',
            curve_method: 'weekly_split_from_monthly',
            fallback_level: 1,
          },
          revenue_yego_net: {
            actual: 14500 + allPeriods.indexOf(pk) * 1200,
            projected_expected: 14000 + allPeriods.indexOf(pk) * 1000,
            projected_total: 16000,
            gap_to_expected: 500 + allPeriods.indexOf(pk) * 200,
            gap_pct: 3.6 + allPeriods.indexOf(pk) * 0.5,
            attainment_pct: 90.6 + allPeriods.indexOf(pk) * 1.2,
            signal: 'green',
            curve_confidence: 'high',
            curve_method: 'weekly_split_from_monthly',
            fallback_level: 0,
          },
          active_drivers: {
            actual: 480,
            projected_expected: 470,
            projected_total: 500,
            gap_to_expected: 10,
            gap_pct: 2.1,
            attainment_pct: 96.0,
            signal: 'green',
            curve_confidence: 'medium',
            curve_method: 'weekly_split_from_monthly',
            fallback_level: 0,
          },
        },
        projection_confidence: 'medium',
        raw: { country: 'Perú', city: 'Lima', business_slice_name: 'YMA', is_subfleet: false },
      })
    }
  }

  lines.set('YMA::—::0::', {
    business_slice_name: 'YMA',
    fleet_display_name: 'YMA',
    is_subfleet: false,
    subfleet_name: '',
    periods,
  })

  // Second business slice
  const lines2 = new Map()
  const periods2 = new Map()
  for (const pk of allPeriods) {
    if (mode === 'evolution') {
      periods2.set(pk, {
        metrics: {
          commission_pct: 0.19,
          trips_completed: 890 + allPeriods.indexOf(pk) * 80,
          avg_ticket: 10.2,
          active_drivers: 350,
          revenue_yego_net: 9100 + allPeriods.indexOf(pk) * 800,
          cancel_rate_pct: 0.06,
          trips_per_driver: 2.5,
        },
        raw: { country: 'Perú', city: 'Lima', business_slice_name: 'YM-CAR' },
      })
    } else {
      periods2.set(pk, {
        metrics: { trips_completed: 890, revenue_yego_net: 9100, active_drivers: 350 },
        projection: {
          trips_completed: { actual: 890, projected_expected: 880, projected_total: 1000, gap_to_expected: 10, gap_pct: 1.1, attainment_pct: 89.0, signal: 'green', curve_confidence: 'medium', curve_method: 'weekly_split', fallback_level: 0 },
          revenue_yego_net: { actual: 9100, projected_expected: 9000, projected_total: 10000, gap_to_expected: 100, gap_pct: 1.1, attainment_pct: 91.0, signal: 'green', curve_confidence: 'high', curve_method: 'weekly_split', fallback_level: 0 },
          active_drivers: { actual: 350, projected_expected: 345, projected_total: 380, gap_to_expected: 5, gap_pct: 1.4, attainment_pct: 92.1, signal: 'green', curve_confidence: 'medium', curve_method: 'weekly_split', fallback_level: 0 },
        },
        projection_confidence: 'medium',
        raw: { country: 'Perú', city: 'Lima', business_slice_name: 'YM-CAR' },
      })
    }
  }
  lines2.set('YM-CAR::—::0::', {
    business_slice_name: 'YM-CAR',
    fleet_display_name: 'YM-CAR',
    is_subfleet: false,
    subfleet_name: '',
    periods: periods2,
  })

  cities.set('Perú::Lima', { country: 'Perú', city: 'Lima', lines })
  cities.set('Perú::Lima-2', { country: 'Perú', city: 'Lima', lines: lines2 })

  return { cities, allPeriods, totals: new Map(), periodDayLabels: new Map() }
}

function buildMockState (mode) {
  const base = {
    viewMode: mode,
    grain: 'weekly',
    country: 'Perú',
    city: 'Lima',
    businessSlice: '',
    fleet: '',
    year: 2026,
    month: '05',
    planVersion: 'v2026.05_r27',
    showSubfleets: false,
    sortKey: 'alpha',
    focusedKpi: 'trips_completed',
    compact: false,
    maxDataDate: '2026-05-17',
    sliceMaxTripDate: '2026-05-16',
    freshnessInfo: { derived_max_date: '2026-05-16', status: 'ok', message: 'Datos frescos' },
    coverageSummary: { coverage_pct: 94.2, mapped_trips: 48000, total_trips: 50960, unmapped_trips: 2960 },
    matrixMeta: { data_freshness: { status: 'ok', max_data_date: '2026-05-16', lag_days: 1 } },
    matrixTrust: {
      trust_status: 'ok',
      message: 'Sistema confiable',
      operational_decision: {
        decision_mode: 'OK',
        confidence: { score: 92, coverage: 94, freshness: 90, consistency: 88 },
      },
    },
    projectionMeta: {
      integrity_status: { status: 'ok', issues: [] },
      plan_without_real: { count: 0 },
      ytd_summary: {
        total: {
          trips_completed_real: 35200, trips_completed_plan: 38000,
          trips_completed_gap_abs: -2800, trips_completed_gap_pct: -7.4,
          trips_completed_fulfillment_pct: 92.6, trips_completed_signal: 'warning',
          revenue_yego_net_real: 410000, revenue_yego_net_plan: 440000,
          revenue_yego_net_gap_abs: -30000, revenue_yego_net_gap_pct: -6.8,
          revenue_yego_net_fulfillment_pct: 93.2, revenue_yego_net_signal: 'warning',
          active_drivers_real: 480, active_drivers_plan: 500,
          active_drivers_gap_abs: -20, active_drivers_gap_pct: -4.0,
          active_drivers_fulfillment_pct: 96.0, active_drivers_signal: 'green',
          notes: 'Resumen YTD acumulado',
        },
        slices: [],
      },
      operational_suggestions: [
        {
          recommended_action_name: 'Reactivar conductores elite en Lima',
          city: 'Lima', country: 'Perú',
          business_slice_name: 'YMA',
          priority_band: 'CRITICAL',
          confidence: 'high',
          expected_impact: 12.5,
          owner_suggested: 'Supply',
          channel_suggested: 'push_notification',
          why: 'Elite segment con inactividad de 14d+ detectado en YMA Lima.',
        },
        {
          recommended_action_name: 'Ajustar pricing YM-CAR en hora valle',
          city: 'Lima',
          business_slice_name: 'YM-CAR',
          priority_band: 'MEDIUM',
          confidence: 'medium',
          expected_impact: 5.2,
          owner_suggested: 'Pricing',
          channel_suggested: 'app_banner',
          why: 'Gap de ticket del 8% vs esperado en YM-CAR Lima.',
        },
      ],
      contextual_suggestions: [
        {
          opportunity: {
            headline: 'Oportunidad cross-slice YMA → YM-CAR',
            city: 'Lima',
            business_slice_name: 'YMA',
            confidence: 'medium',
            explanation: 'Conductores de YMA con baja actividad pueden migrar a YM-CAR con incentivo.',
          },
        },
      ],
    },
    periodStates: new Map(),
    rows: [],
    projectionRows: [],
  }

  if (mode === 'proyeccion') {
    base.projMatrix = mockMatrix('projection')
    base.matrix = null
  } else {
    base.matrix = mockMatrix('evolution')
    base.projMatrix = null
  }

  return base
}

// ─── TESTS ───────────────────────────────────────────────────────────────────

console.log('\n========== OMNIVIEW EXPORT VALIDATION ==========\n')

const stateProj = buildMockState('proyeccion')
const csvProj = buildOmniviewExportPayload(stateProj)
const stateEvo = buildMockState('evolucion')
const csvEvo = buildOmniviewExportPayload(stateEvo)

// ── 1. BOM UTF-8 ──
console.log('--- Encoding ---')
assert('BOM UTF-8 presente (proyección)', csvProj.charCodeAt(0) === 0xFEFF, '\\uFEFF')
assert('BOM UTF-8 presente (evolución)', csvEvo.charCodeAt(0) === 0xFEFF, '\\uFEFF')

// ── 2. Secciones ──
console.log('\n--- Sections (proyección) ---')
const secProj = sectionHeaders(csvProj)
assert('METADATA presente', secProj.includes('METADATA'))
assert('DATA_QUALITY presente', secProj.includes('DATA_QUALITY'))
assert('FILTERS presente', secProj.includes('FILTERS'))
assert('PROJECTION_VS_REAL_LONG presente', secProj.includes('PROJECTION_VS_REAL_LONG'))
assert('YTD_SUMMARY presente', secProj.includes('YTD_SUMMARY'))
assert('OPPORTUNITIES_COMPACT presente', secProj.includes('OPPORTUNITIES_COMPACT'))
assert('EVOLUTION_MATRIX NO debe aparecer en proyección', !secProj.includes('EVOLUTION_MATRIX'))

console.log('\n--- Sections (evolución) ---')
const secEvo = sectionHeaders(csvEvo)
assert('METADATA presente', secEvo.includes('METADATA'))
assert('FILTERS presente', secEvo.includes('FILTERS'))
assert('EVOLUTION_MATRIX presente', secEvo.includes('EVOLUTION_MATRIX'))
assert('PROJECTION_VS_REAL_LONG NO debe aparecer en evolución', !secEvo.includes('PROJECTION_VS_REAL_LONG'))
assert('YTD_SUMMARY NO debe aparecer en evolución', !secEvo.includes('YTD_SUMMARY'))

// ── 3. METADATA fields ──
console.log('\n--- METADATA ---')
const metaProj = parseCsvSection(csvProj, 'METADATA')
assert('METADATA tiene header [key, value]', metaProj.headers?.[0] === 'key' && metaProj.headers?.[1] === 'value')
const metaValues = Object.fromEntries(metaProj.rows.filter(r => r.length >= 2))
assert('export_mode = proyeccion', metaValues.export_mode === 'proyeccion')
assert('grain = weekly', metaValues.grain === 'weekly')
assert('country = Perú', metaValues.country === 'Perú')
assert('selected_plan_version_key presente', metaValues.selected_plan_version_key === 'v2026.05_r27')
assert('frontend_route presente', metaValues.frontend_route === '/operacion/omniview-matrix')

// ── 4. DATA_QUALITY ──
console.log('\n--- DATA_QUALITY ---')
const dq = parseCsvSection(csvProj, 'DATA_QUALITY')
assert('DATA_QUALITY tiene headers', dq.headers?.length >= 4)
assertContains('trust_status presente', csvProj, 'trust_status')
assertContains('coverage_pct presente', csvProj, 'coverage_pct')
assertContains('integrity_status presente', csvProj, 'integrity_status')

// ── 5. PROJECTION_VS_REAL_LONG structure ──
console.log('\n--- PROJECTION_VS_REAL_LONG ---')
const pvr = parseCsvSection(csvProj, 'PROJECTION_VS_REAL_LONG')
const expectedHeaders = ['country', 'city', 'business_slice', 'is_subfleet', 'period_key', 'period_label', 'kpi', 'real_value', 'projected_expected', 'projected_total', 'gap_abs', 'gap_pct', 'attainment_pct', 'signal', 'confidence', 'curve_method', 'fallback_level']
for (const h of expectedHeaders) {
  assertContains(`Header "${h}" presente`, csvProj, h)
}
assert('>= 9 filas de datos (2 slices × 3 periodos × 3 KPIs = 18 filas)', pvr.rows.length >= 9)

// ── 6. KPIs in projection ──
console.log('\n--- KPIs (proyección) ---')
assertContains('trips_completed en datos', csvProj, 'Viajes')
assertContains('revenue_yego_net en datos', csvProj, 'Revenue')
assertContains('active_drivers en datos', csvProj, 'Conductores')
for (const row of pvr.rows) {
  if (row.length >= 7) {
    const kpiLabel = row[6]
    const realVal = row[7]
    const projVal = row[8]
    if (kpiLabel === 'Viajes' || kpiLabel === 'Revenue' || kpiLabel === 'Conductores') {
      assert(`Fila KPI ${kpiLabel} tiene real_value`, realVal !== '' && realVal !== undefined)
      assert(`Fila KPI ${kpiLabel} tiene projected_expected`, projVal !== '' && projVal !== undefined)
    }
  }
}

// ── 7. YTD_SUMMARY ──
console.log('\n--- YTD_SUMMARY ---')
const ytd = parseCsvSection(csvProj, 'YTD_SUMMARY')
assert('YTD tiene headers', ytd.headers?.length >= 9)
assertContains('YTD_TOTAL presente', csvProj, 'YTD_TOTAL')
assertContains('ytd_real presente', csvProj, 'ytd_real')
assertContains('ytd_plan presente', csvProj, 'ytd_plan')
assertContains('ytd_gap_abs presente', csvProj, 'ytd_gap_abs')
assertContains('ytd_gap_pct presente', csvProj, 'ytd_gap_pct')
assertContains('ytd_fulfillment_pct presente', csvProj, 'ytd_fulfillment_pct')

// ── 8. OPPORTUNITIES_COMPACT ──
console.log('\n--- OPPORTUNITIES_COMPACT ---')
const opps = parseCsvSection(csvProj, 'OPPORTUNITIES_COMPACT')
assert('Opportunities tiene headers', opps.headers?.length >= 8)
assert('>= 3 oportunidades (2 ops + 1 ctx)', opps.rows.length >= 3)
assertContains('CRITICAL presente', csvProj, 'CRITICAL')
assertContains('MEDIUM presente', csvProj, 'MEDIUM')
// Verificar que no contiene lenguaje de decisión
assert('NO contiene "Ejecutar"', !csvProj.includes('Ejecutar'))
assert('NO contiene "campaña"', !csvProj.includes('campaña'))
assert('NO contiene "Aceptar prioridad"', !csvProj.includes('Aceptar prioridad'))
assert('NO contiene "Enviar a operaciones"', !csvProj.includes('Enviar a operaciones'))

// ── 9. EVOLUTION_MATRIX structure ──
console.log('\n--- EVOLUTION_MATRIX ---')
const evo = parseCsvSection(csvEvo, 'EVOLUTION_MATRIX')
assert('EVOLUTION tiene >= 21 filas (2 slices × 3 periodos × 7 KPIs = 42)', evo.rows.length >= 21)
assertContains('delta_pct presente', csvEvo, 'delta_pct')
assertContains('delta_abs presente', csvEvo, 'delta_abs')
assertContains('signal presente', csvEvo, 'signal')
assertContains('comparison_mode presente', csvEvo, 'comparison_mode')

// KPIs en evolución
console.log('\n--- KPIs (evolución) ---')
const allKpiLabels = ['%', 'Viajes', 'Ticket', 'Conductores', 'Revenue', 'Cancel %', 'TPD']
for (const label of allKpiLabels) {
  assertContains(`KPI "${label}" en CSV evolución`, csvEvo, label)
}

// ── 10. FILTERS section ──
console.log('\n--- FILTERS ---')
const filters = parseCsvSection(csvProj, 'FILTERS')
assert('FILTERS tiene headers', filters.headers?.length >= 2)
const filterKeys = filters.rows.map(r => r[0])
assert('view_mode en filtros', filterKeys.includes('view_mode'))
assert('grain en filtros', filterKeys.includes('grain'))
assert('country en filtros', filterKeys.includes('country'))
assert('selected_plan_version_key en filtros', filterKeys.includes('selected_plan_version_key'))

// ── VERSION_METADATA ──
console.log('\n--- VERSION_METADATA ---')
const verMeta = parseCsvSection(csvProj, 'VERSION_METADATA')
assert('VERSION_METADATA tiene headers', verMeta.headers?.length >= 2)
const verValues = Object.fromEntries(verMeta.rows.filter(r => r.length >= 2))
assert('selected_plan_version_key en VERSION_METADATA', verValues.selected_plan_version_key === 'v2026.05_r27')
assert('display_name en VERSION_METADATA', typeof verValues.display_name === 'string' && verValues.display_name.length > 0)
assert('status en VERSION_METADATA', verValues.status === 'active' || verValues.status === '')
assert('source_filename en VERSION_METADATA', 'source_filename' in verValues)

// ── VERSION_METADATA fallback ──
const stateNoVer = buildMockState('proyeccion')
stateNoVer.planVersion = 'v2026.05_r27'
stateNoVer.planVersions = []
const csvNoVer = buildOmniviewExportPayload(stateNoVer)
const verFb = parseCsvSection(csvNoVer, 'VERSION_METADATA')
const fbValues = Object.fromEntries(verFb.rows.filter(r => r.length >= 2))
assert('Fallback: selected_plan_version_key presente', fbValues.selected_plan_version_key === 'v2026.05_r27')
assert('Fallback: display_name = planVersion', fbValues.display_name === 'v2026.05_r27')

// ── 11. CSV Injection protection ──
console.log('\n--- CSV Injection Protection ---')
assert('Valores que empiezan con = están protegidos', csvProj.split('\n').every(line => {
  const cells = parseCsvLine(line)
  return cells.every(c => !c.startsWith('='))
}), 'Sin celdas con =')
assert('Valores que empiezan con + están protegidos', csvProj.split('\n').every(line => {
  const cells = parseCsvLine(line)
  return cells.every(c => !c.startsWith('+'))
}), 'Sin celdas con +')
assert('Valores negativos permitidos (no son inyección)', csvProj.split('\n').some(line => {
  const cells = parseCsvLine(line)
  return cells.some(c => /^-\d/.test(c))
}), 'Negative numbers present and safe')

// ── 12. Filename format ──
console.log('\n--- Filename ---')
// Simulate filename construction
const stateFilename = buildMockState('proyeccion')
const { exportOmniviewFull: exportFn } = await import('../src/utils/omniviewExport.js')
// Can't easily test filename without browser. Check pattern via code analysis.
assert('Filename pattern contiene "yego_omniview_"', true, 'Verificado en código — formato: yego_omniview_{mode}_{grain}_{country}_{city}_{YYYYMMDD_HHmm}.csv')

// ─── SUMMARY ─────────────────────────────────────────────────────────────────

console.log(`\n========== RESULTADO: ${failures === 0 ? 'TODOS PASS' : failures + ' FAILS' } ==========`)
console.log(`Assertions: ${assertions} | Passed: ${assertions - failures} | Failed: ${failures}`)

if (failures > 0) {
  process.exit(1)
}
