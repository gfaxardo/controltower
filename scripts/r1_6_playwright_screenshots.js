// LG-INFRA-R1.6 — Human UI Certification Screenshots (fixed selectors)
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const SCREENSHOT_DIR = path.resolve('exports/audits/lima_growth/r1_6_midnight_scheduler_certification');
const BASE_URL = 'http://localhost:5174/lima-growth';

if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function screenshot(page, name) {
  const filepath = path.join(SCREENSHOT_DIR, name);
  await page.screenshot({ path: filepath, fullPage: true });
  console.log(`  [OK] ${name}`);
}

(async () => {
  console.log('LG-INFRA-R1.6 — Playwright UI Certification\n');

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  try {
    // 1. Navigate to Lima Growth
    console.log('Loading Lima Growth dashboard...');
    await page.goto(BASE_URL, { timeout: 60000, waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(8000); // wait for API data to load

    // Today Action Plan (default section)
    console.log('1. Today Action Plan...');
    await screenshot(page, '01_today_action_plan.png');

    // 2. Navigate to Programs
    console.log('2. Programs...');
    await page.click('[data-testid="nav-programs"]');
    await page.waitForTimeout(4000);
    await screenshot(page, '02_programs.png');

    // 3. Navigate to Execution Queue
    console.log('3. Execution Queue...');
    await page.click('[data-testid="nav-execution-queue"]');
    await page.waitForTimeout(4000);
    await screenshot(page, '03_execution_queue.png');

    // 4. Navigate to Intraday Signals
    console.log('4. Intraday Signals...');
    await page.click('[data-testid="nav-intraday-signals"]');
    await page.waitForTimeout(4000);
    await screenshot(page, '04_intraday_signals.png');

    // 5. Navigate to Config
    console.log('5. Config / Governance...');
    await page.click('[data-testid="nav-control-config"]');
    await page.waitForTimeout(4000);
    await screenshot(page, '05_config_governance.png');

    // 6. Back to Today Action Plan for governance header
    console.log('6. Governance header...');
    await page.click('[data-testid="nav-today-action-plan"]');
    await page.waitForTimeout(4000);
    // Scroll to top to capture header
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.waitForTimeout(1000);
    await screenshot(page, '06_governance_header.png');

    console.log('\nAll screenshots captured successfully!');
  } catch (e) {
    console.log(`\nError: ${e.message}`);
    // Take error screenshot anyway
    await screenshot(page, '99_error_state.png');
  } finally {
    await browser.close();
  }

  console.log(`\nScreenshots saved to: ${SCREENSHOT_DIR}`);
})();
