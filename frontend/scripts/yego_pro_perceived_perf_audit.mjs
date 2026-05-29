/**
 * Yego Pro Profitability — User Perceived Performance Audit (Playwright)
 * Mide timeline visual real sin modificar código.
 *
 * Usage: npx playwright test frontend/scripts/yego_pro_profitability_perceived_perf.spec.mjs
 *    or: node frontend/scripts/yego_pro_profitability_perceived_perf_audit.mjs
 */
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SCREENSHOT_DIR = join(__dirname, '..', '..', 'screenshots', 'yego-pro-profitability');
const REPORT_DIR = join(__dirname, '..', '..', 'reports');
const URL = 'http://localhost:5173/fleet-project/yego-pro/profitability';
const SNAPSHOT_TIMES = [0, 1, 2, 3, 5, 8, 10, 15];
const MAX_WAIT = 30000;

mkdirSync(SCREENSHOT_DIR, { recursive: true });
mkdirSync(REPORT_DIR, { recursive: true });

async function main() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();

  const timeline = [];
  const kpiSelectors = [
    { name: 'spinner', selector: 'text=Cargando diagnóstico ejecutivo' },
    { name: 'spinner_alt', selector: 'text=Cargando diagnostico ejecutivo' },
    { name: 'any_spinner', selector: '.animate-spin' },
    { name: 'kpi_profit', selector: 'text=Utilidad neta semanal' },
    { name: 'kpi_revenue', selector: 'text=Revenue semanal' },
    { name: 'kpi_margin', selector: 'text=Margen %' },
    { name: 'table_drivers', selector: 'text=Conductores: contribucion al resultado' },
    { name: 'table_vehicles', selector: 'text=TOP VEHICULOS EN PERDIDA' },
    { name: 'waterfall', selector: 'text=Donde se va el dinero' },
    { name: 'utilization', selector: 'text=Utilizacion' },
    { name: 'findings', selector: 'text=Hallazgos observados' },
    { name: 'quality_section', selector: 'text=Confianza de datos' },
  ];

  console.log('=== YEGO PRO PROFITABILITY — PERCEIVED PERFORMANCE AUDIT ===\n');
  console.log(`URL: ${URL}\n`);

  // Collect console logs
  const consoleLogs = [];
  page.on('console', msg => {
    if (msg.type() === 'log' || msg.type() === 'debug' || msg.type() === 'error') {
      consoleLogs.push({ type: msg.type(), text: msg.text(), time: Date.now() });
    }
  });

  // Track network
  const networkLog = [];
  page.on('response', response => {
    const url = response.url();
    if (url.includes('profitability')) {
      networkLog.push({
        url: url.split('/').pop()?.split('?')[0],
        status: response.status(),
        duration: 0,
        time: Date.now(),
      });
    }
  });

  const t0 = Date.now();

  // Navigate
  console.log('T0: Navigation start');
  await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: MAX_WAIT });
  const tNav = Date.now() - t0;
  timeline.push({ label: 'T0_navigation_complete', ms: tNav });
  console.log(`  Navigation complete: ${tNav}ms`);

  // Take screenshots at intervals
  for (const sec of SNAPSHOT_TIMES) {
    if (sec > 0) {
      const elapsed = Date.now() - t0;
      const delay = sec * 1000 - elapsed;
      if (delay > 0) await page.waitForTimeout(delay);
    }
    const actualMs = Date.now() - t0;
    const filename = `overview_t${String(sec).padStart(2, '0')}s.png`;
    await page.screenshot({
      path: join(SCREENSHOT_DIR, filename),
      fullPage: false,
    });
    console.log(`  Screenshot t=${sec}s (actual ${actualMs}ms): ${filename}`);
  }

  // Detect transitions
  let spinnerGoneTime = null;
  let firstKpiTime = null;
  let firstTableTime = null;
  let usableTime = null;
  let fullyLoadedTime = null;
  let kpiCount = 0;
  let tableCount = 0;

  const pollInterval = 250;
  const startPoll = Date.now();

  while (Date.now() - startPoll < MAX_WAIT) {
    const elapsed = Date.now() - t0;
    let spinnerVisible = false;
    let hasKpi = false;
    let hasTable = false;

    try {
      spinnerVisible = await page.locator('.animate-spin').first().isVisible({ timeout: 500 }).catch(() => false);
    } catch { spinnerVisible = false; }

    try {
      // Check for KPI text
      const kpiElements = await page.locator('text=Utilidad neta semanal, text=Revenue semanal').count();
      hasKpi = kpiElements > 0;
    } catch { hasKpi = false; }

    try {
      const tableElements = await page.locator('text=Conductores: contribucion, text=TOP VEHICULOS EN PERDIDA, text=Donde se va el dinero').count();
      hasTable = tableElements > 0;
    } catch { hasTable = false; }

    if (spinnerGoneTime === null && !spinnerVisible && hasKpi) {
      spinnerGoneTime = elapsed;
      timeline.push({ label: 'T1_spinner_disappears', ms: elapsed });
      console.log(`  T1 Spinner gone: ${elapsed}ms`);
    }

    if (firstKpiTime === null && hasKpi) {
      firstKpiTime = elapsed;
      timeline.push({ label: 'T2_first_KPI_visible', ms: elapsed });
      console.log(`  T2 First KPI visible: ${elapsed}ms`);
      kpiCount++;
    }

    if (firstTableTime === null && hasTable) {
      firstTableTime = elapsed;
      timeline.push({ label: 'T3_first_table_visible', ms: elapsed });
      console.log(`  T3 First table visible: ${elapsed}ms`);
      tableCount++;
    }

    if (usableTime === null && hasKpi && hasTable && kpiCount > 1) {
      usableTime = elapsed;
      timeline.push({ label: 'T4_dashboard_usable', ms: elapsed });
      console.log(`  T4 Dashboard usable: ${elapsed}ms`);
    }

    if (!spinnerVisible && hasKpi && hasTable && elapsed > 5000) {
      if (fullyLoadedTime === null) {
        // Check if most sections are loaded
        const sectionCount = await page.locator('text=Utilizacion, text=Confianza de datos, text=Hallazgos, text=Diagnostico dia/noche').count();
        if (sectionCount >= 2) {
          fullyLoadedTime = elapsed;
          timeline.push({ label: 'T5_dashboard_fully_loaded', ms: elapsed });
          console.log(`  T5 Dashboard fully loaded: ${elapsed}ms`);
          break;
        }
      }
    }

    await page.waitForTimeout(pollInterval);
  }

  // Final screenshot
  await page.screenshot({
    path: join(SCREENSHOT_DIR, 'final_state.png'),
    fullPage: true,
  });

  // Collect diag state from window
  let diagState = null;
  try {
    diagState = await page.evaluate(() => {
      if (window.__profitabilityState) {
        return {
          anyLoading: window.__profitabilityState.anyLoading,
          hasAnyData: window.__profitabilityState.hasAnyData,
          allDone: window.__profitabilityState.allDone,
          loadingKeys: window.__profitabilityState.loadingKeys,
          dataKeys: window.__profitabilityState.dataKeys,
          errorKeys: window.__profitabilityState.errorKeys,
        };
      }
      return null;
    });
  } catch { }

  // Report
  const report = {
    url: URL,
    timestamp: new Date().toISOString(),
    timeline,
    diagState,
    consoleLogs: consoleLogs.filter(l => l.text.includes('[DIAG]') || l.text.includes('PROFITABILITY VERSION')),
    networkLog,
    summary: {
      T0_navigation_complete_ms: tNav,
      T1_spinner_disappears_ms: spinnerGoneTime,
      T2_first_KPI_visible_ms: firstKpiTime,
      T3_first_table_visible_ms: firstTableTime,
      T4_dashboard_usable_ms: usableTime,
      T5_dashboard_fully_loaded_ms: fullyLoadedTime,
    },
    total_wait_ms: Date.now() - t0,
  };

  const reportPath = join(REPORT_DIR, 'yego_pro_perceived_performance.json');
  writeFileSync(reportPath, JSON.stringify(report, null, 2));

  console.log('\n=== TIMELINE ===');
  for (const t of timeline) {
    const sec = (t.ms / 1000).toFixed(1);
    console.log(`  ${sec}s — ${t.label}`);
  }

  console.log('\n=== SUMMARY ===');
  console.log(`  T0 (navigation):  ${tNav}ms`);
  console.log(`  T1 (spinner off): ${spinnerGoneTime ?? 'NOT DETECTED'}ms`);
  console.log(`  T2 (first KPI):   ${firstKpiTime ?? 'NOT DETECTED'}ms`);
  console.log(`  T3 (first table): ${firstTableTime ?? 'NOT DETECTED'}ms`);
  console.log(`  T4 (usable):      ${usableTime ?? 'NOT DETECTED'}ms`);
  console.log(`  T5 (fully loaded):${fullyLoadedTime ?? 'NOT DETECTED'}ms`);
  console.log(`  Total: ${Date.now() - t0}ms`);

  if (diagState) {
    console.log('\n=== REACT STATE ===');
    console.log(`  anyLoading: ${diagState.anyLoading}`);
    console.log(`  hasAnyData: ${diagState.hasAnyData}`);
    console.log(`  allDone: ${diagState.allDone}`);
    console.log(`  loadingKeys: ${diagState.loadingKeys?.join(', ') || 'none'}`);
    console.log(`  dataKeys: ${diagState.dataKeys?.join(', ') || 'none'}`);
    console.log(`  errorKeys: ${diagState.errorKeys?.join(', ') || 'none'}`);
  }

  console.log(`\nReport: ${reportPath}`);
  console.log(`Screenshots: ${SCREENSHOT_DIR}`);

  await browser.close();
}

main().catch(err => {
  console.error('Audit failed:', err);
  process.exit(1);
});
