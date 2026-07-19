import { chromium } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

const BASE = 'http://localhost:3001';
const OUT = path.join(process.cwd(), 'ui-audit-screenshots');

// Views reachable by clicking the hero cards or nav
const CLICKABLE_VIEWS = [
  { name: '01_home', action: async (page: any) => { /* already on home */ } },
  { name: '02_patient_portal',  action: async (page: any) => page.click('.hero-card.neu:first-of-type') },
  { name: '03_doctor_portal',   action: async (page: any) => page.click('.hero-card.neu:last-of-type') },
  { name: '04_ocr_workbench',   action: async (page: any) => page.evaluate(() => (window as any).__navigate?.('ocr-workbench')) },
  { name: '05_settings',        action: async (page: any) => page.click('button.ghost[title="Settings"]') },
  { name: '06_dashboard',       action: async (page: any) => page.evaluate(() => (window as any).__navigate?.('dashboard')) },
];

async function main() {
  fs.mkdirSync(OUT, { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  const snap = async (name: string) => {
    await page.waitForTimeout(800);
    const fp = path.join(OUT, `${name}.png`);
    await page.screenshot({ path: fp, fullPage: true });
    console.log(`ok ${name}`);
  };

  // ── Home
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await snap('01_home');

  // ── Patient Portal
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.locator('.hero-card').first().click();
  await snap('02_patient_portal');

  // ── Doctor Portal
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.locator('.hero-card').last().click();
  await snap('03_doctor_portal');

  // ── OCR Workbench — click Configure Providers first to expose nav, then navigate
  await page.goto(BASE, { waitUntil: 'networkidle' });
  // expose navigate by injecting through window — not possible in isolated page; use Settings path
  // Instead: click Settings → navigate via topbar
  await page.locator('button[title="Settings"]').click();
  await page.waitForTimeout(500);
  await snap('04_settings');

  // ── Navigate to OCR workbench by injecting state
  await page.goto(BASE, { waitUntil: 'networkidle' });
  // Click patient portal then navigate to OCR via topbar
  await page.locator('.hero-card').last().click();
  await page.waitForTimeout(500);
  // Look for OCR Workbench button in doctor portal sidebar if any
  const ocrBtn = page.locator('button:has-text("OCR"), button:has-text("Workbench"), [data-view="ocr-workbench"]');
  const ocrCount = await ocrBtn.count();
  if (ocrCount > 0) { await ocrBtn.first().click(); }
  await page.waitForTimeout(500);
  await snap('05_doctor_portal_full');

  // ── Dashboard
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.locator('.hero-card').last().click();
  await page.waitForTimeout(500);
  const dbBtn = page.locator('button:has-text("Dashboard")');
  if (await dbBtn.count() > 0) await dbBtn.click();
  await page.waitForTimeout(500);
  await snap('06_dashboard');

  // ── Landing features (bottom section)
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  await snap('07_home_bottom');

  await browser.close();
  console.log(`\nDone. Screenshots in: ${OUT}`);
}

main().catch(e => { console.error(e); process.exit(1); });
