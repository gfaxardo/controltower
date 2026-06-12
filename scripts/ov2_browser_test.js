const { chromium } = require('playwright');
const path = require('path');

const SCREENSHOT_DIR = path.join(__dirname, '..', 'docs', 'omnibuilder_v2', 'screenshots');
require('fs').mkdirSync(SCREENSHOT_DIR, { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // 1. V2 Shadow Matrix page
  await page.goto('http://localhost:5174/operacion/omniview-v2-shadow', { waitUntil: 'load', timeout: 60000 });
  await page.waitForTimeout(8000);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'ov2_matrix_day.png'), fullPage: false });
  console.log('1. Matrix page captured');

  // Try multiple selectors for clicking a cell
  const cellSelectors = ['.ov2-matrix-cell', '[data-cell-id]', '.matrix-cell', 'td', '[class*=\"cell\"]'];
  let cell = null;
  for (const sel of cellSelectors) {
    cell = await page.$(sel);
    if (cell) { console.log(`  Found cell with: ${sel}`); break; }
  }
  if (cell) {
    await cell.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'ov2_inspector_open.png'), fullPage: false });
    console.log('2. Inspector captured');
  } else {
    console.log('2. No cell found to click');
  }

  // 3. V1 regression check
    await page.goto('http://localhost:5174/', { waitUntil: 'load', timeout: 60000 });
    await page.waitForTimeout(2000);
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, 'v1_regression_check.png'), fullPage: false });
  console.log('3. V1 captured');

  await browser.close();
  console.log('Done');
})();
