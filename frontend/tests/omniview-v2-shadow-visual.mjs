/**
 * OV2-C.9 — Omniview V2 Shadow Visual Certification Script
 *
 * Uses Playwright library (not @playwright/test) for visual validation.
 * Run with: node frontend/tests/omniview-v2-shadow-visual.mjs
 *
 * Requires: dev server running on localhost:5173
 * Output: backend/exports/audits/omniview_v2_visual/
 */
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUTPUT_DIR = join(__dirname, '..', '..', 'backend', 'exports', 'audits', 'omniview_v2_visual');
const BASE = 'http://localhost:5173';

mkdirSync(OUTPUT_DIR, { recursive: true });

const SCENARIOS = [
  { name: '01_ct_day_default', route: '/operacion/omniview-v2-shadow', wait: 3000 },
  { name: '02_yango_day_shadow', route: '/operacion/omniview-v2-shadow?source=YANGO_API_RAW', wait: 3000 },
  { name: '03_sandbox_ct_day', route: '/operacion/omniview-v2-matrix-sandbox', wait: 2000 },
  { name: '04_sandbox_yango_day', route: '/operacion/omniview-v2-matrix-sandbox', wait: 2000 },
  { name: '05_v1_omniview_matrix', route: '/operacion/omniview-matrix', wait: 4000 },
];

const ASSERTIONS = [
  { selector: '.ov2-command-header', label: 'Command header visible' },
  { selector: '.ov2-source-badge', label: 'Source badge visible' },
  { selector: '.ov2-matrix-shell', label: 'MatrixShell visible' },
  { selector: '.ov2-badge', label: 'Badges visible' },
];

async function capture(page, scenario) {
  await page.goto(BASE + scenario.route, { waitUntil: 'networkidle' });
  await page.waitForTimeout(scenario.wait);

  const path = join(OUTPUT_DIR, `${scenario.name}.png`);
  await page.screenshot({ path, fullPage: true });
  console.log(`  [capture] ${scenario.name} → ${path}`);

  const results = [];
  for (const assert of ASSERTIONS) {
    try {
      await page.waitForSelector(assert.selector, { timeout: 5000 });
      results.push({ check: assert.label, pass: true });
    } catch {
      results.push({ check: assert.label, pass: false });
    }
  }

  // Semantic checks
  const hasCanonical = await page.locator('.ov2-source-badge--canonical').count();
  const hasShadow = await page.locator('.ov2-source-badge--shadow').count();
  const hasActionEngine = await page.locator('text=ACTION_ENGINE').count();
  const hasDecisionEngine = await page.locator('text=DECISION_ENGINE').count();

  results.push({ check: 'Canonical badge present', pass: hasCanonical > 0 });
  results.push({ check: 'Shadow badge present', pass: hasShadow > 0 });
  results.push({ check: 'No ACTION_ENGINE in DOM', pass: hasActionEngine === 0 });
  results.push({ check: 'No DECISION_ENGINE in DOM', pass: hasDecisionEngine === 0 });

  return results;
}

async function main() {
  console.log('[OV2-C.9] Visual Certification');
  console.log(`  Output: ${OUTPUT_DIR}`);
  console.log(`  Scenarios: ${SCENARIOS.length}`);

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  let allPassed = true;
  const allResults = [];

  for (const scenario of SCENARIOS) {
    console.log(`\n[scenario] ${scenario.name}`);
    try {
      const results = await capture(page, scenario);
      allResults.push({ scenario: scenario.name, results });
      const failed = results.filter((r) => !r.pass);
      if (failed.length > 0) {
        console.log(`  FAILED: ${failed.map((f) => f.check).join(', ')}`);
        allPassed = false;
      } else {
        console.log(`  PASS: ${results.length} assertions`);
      }
    } catch (e) {
      console.log(`  ERROR: ${e.message}`);
      allResults.push({ scenario: scenario.name, error: e.message });
      allPassed = false;
    }
  }

  await browser.close();

  // Write report
  const report = [
    '# OV2-C.9 Visual Certification Report',
    '',
    `**Overall:** ${allPassed ? 'PASS' : 'FAIL'}`,
    '',
    '## Results',
    '',
    ...allResults.flatMap((r) => [
      `### ${r.scenario}`,
      r.error ? `ERROR: ${r.error}` : '',
      ...(r.results || []).map((a) => `- ${a.pass ? 'PASS' : 'FAIL'}: ${a.check}`),
      '',
    ]),
  ].join('\n');

  writeFileSync(join(OUTPUT_DIR, 'visual_certification_report.md'), report);
  console.log(`\n[report] ${join(OUTPUT_DIR, 'visual_certification_report.md')}`);
  console.log(`[result] ${allPassed ? 'ALL PASSED' : 'SOME FAILED'}`);

  process.exit(allPassed ? 0 : 1);
}

main();
