/** Built Cloudflare Worker browser checks. Dependencies come from the existing PCB preview toolchain. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
const require = createRequire(new URL('../../artwork-resources/pcb-art/preview-source/package.json', import.meta.url));
const { chromium: pw } = require('playwright');
const chromiumModule = require('@sparticuz/chromium');
const chromium = chromiumModule.default || chromiumModule;
const base = process.env.BROWSER_BASE || 'http://127.0.0.1:8787';
const out = process.env.BROWSER_OUTPUT || '/tmp/blanks-browser';
const report = { base, checks: [], errors: [], screenshots: [], startedAt: new Date().toISOString() };
await mkdir(out, { recursive: true });
let browser, page;
async function fresh(options = {}) {
  await browser?.close();
  browser = await pw.launch({ executablePath: await chromium.executablePath(), args: chromium.args, headless: true });
  const ctx = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 1000 }, ...options });
  page = await ctx.newPage();
  page.on('pageerror', e => report.errors.push({ type: 'pageerror', url: page.url(), error: e.message }));
  page.on('requestfailed', r => { const error = r.failure()?.errorText; /* A subsequent navigation can cancel its replaced document request; asset and fetch cancellations still fail. */ if (error === 'net::ERR_ABORTED' && r.isNavigationRequest()) { (report.intentionalCancellations ||= []).push({ url: r.url(), error }); return; } report.errors.push({ type: 'requestfailed', url: r.url(), error }); });
  return page;
}
async function open(url) { const response = await page.goto(base + url, { waitUntil: 'networkidle', timeout: 60000 }); assert.equal(response.status(), 200, url); }
async function shot(name) { await page.screenshot({ path: `${out}/${name}.png`, fullPage: false }); report.screenshots.push(name + '.png'); }
async function check(name, fn) { try { await fn(); report.checks.push({ name, passed: true }); console.log('PASS ' + name); } catch (e) { report.checks.push({ name, passed: false, error: e.stack }); console.error('FAIL ' + name + ': ' + e.message); try { await shot('failure-' + report.checks.length); } catch {} } }
async function fits() { assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'horizontal overflow'); }
async function readyPCB() { await page.waitForFunction(() => globalThis.__PCB_PREVIEW__?.ready, null, { timeout: 60000 }); const rendering = await page.locator('#preview-canvas').evaluate(canvas => { const gl = canvas.getContext('webgl2'); return { live: !!gl && !gl.isContextLost(), width: canvas.width, height: canvas.height }; }); assert(rendering.live && rendering.width > 100 && rendering.height > 100, 'live WebGL2 canvas'); }
async function state() { return page.evaluate(() => globalThis.__PCB_PREVIEW__.getState()); }
async function range(selector, value) { await page.locator(selector).evaluate((el, value) => { el.value = value; el.dispatchEvent(new Event('input', { bubbles: true })); }, value); }
async function settle() { await page.waitForTimeout(250); }
try {
  for (const mobile of [false, true]) for (const colorScheme of ['light', 'dark']) await check(`${mobile ? 'mobile' : 'desktop'} ${colorScheme}: homepage and five sections`, async () => {
    await fresh({ viewport: mobile ? { width: 390, height: 844 } : { width: 1440, height: 1000 }, isMobile: mobile, hasTouch: mobile, colorScheme });
    await open('/'); await fits(); await shot(`${mobile ? 'mobile' : 'desktop'}-${colorScheme}-home`);
    for (const section of ['panels', 'models', 'manufacturing', 'guides', 'overview']) { await open(`/docs/${section}/`); assert(await page.locator('h1').count() > 0); await fits(); }
    await shot(`${mobile ? 'mobile' : 'desktop'}-${colorScheme}-about`);
  });
  await check('search finds Kumiko and navigates', async () => {
    await fresh(); await open('/'); await page.locator('[data-open-search]').first().click();
    await page.locator('[data-search-input]').fill('Kumiko');
    const result = page.locator('[data-search-dialog] a[href*="kumiko"]').first(); await result.waitFor(); await result.click();
    await page.waitForURL('**/docs/**kumiko**'); await page.waitForFunction(() => /Kumiko/i.test(document.querySelector('h1')?.textContent || '')); assert.match(await page.locator('h1').innerText(), /Kumiko/i);
  });
  await check('native Sidebar focus, broaden, restore preserve URL, article scroll and TOC', async () => {
    await fresh(); await open('/docs/panels/art/kumiko-void/');
    await page.evaluate(() => window.scrollTo(0, 400)); await settle();
    const before = await page.evaluate(() => ({ url: location.href, y: scrollY, toc: [...document.querySelectorAll('[data-zd-toc] a')].map(a => a.getAttribute('href')) }));
    const focus = page.locator('[data-sidebar-focus][aria-label="Show only this branch: Artwork families"]:visible').first(); await focus.waitFor(); await focus.click(); await settle();
    await page.locator('[data-sidebar-broaden]:visible').first().click(); await settle();
    // Broadening this branch reaches the page's baseline tree, so focus it again to exercise Restore.
    await page.locator('[data-sidebar-focus][aria-label="Show only this branch: Artwork families"]:visible').first().click(); await settle();
    await page.locator('[data-sidebar-restore]:visible').first().click(); await settle();
    const after = await page.evaluate(() => ({ url: location.href, y: scrollY, toc: [...document.querySelectorAll('[data-zd-toc] a')].map(a => a.getAttribute('href')) }));
    assert.deepEqual(after, before); await shot('sidebar-restored');
  });
  await check('dynamic navigation transitions retain search and sidebar', async () => {
    await fresh(); await open('/docs/panels/');
    await page.evaluate(() => { globalThis.__QA_DOCUMENT_SENTINEL = 'retained'; });
    await page.locator('a[href="/docs/models/"]').first().click(); await page.waitForURL('**/docs/models/'); await settle();
    assert.equal(await page.evaluate(() => globalThis.__QA_DOCUMENT_SENTINEL), 'retained');
    assert(await page.locator('[data-open-search]').first().isVisible()); assert(await page.locator('[data-sidebar-broaden]').count() > 0);
  });
  await check('History and Compare on moved established page', async () => {
    await fresh(); await open(process.env.BROWSER_HISTORY_PAGE || '/docs/guides/assembly/stack/');
    await page.getByRole('button', { name: 'View document history' }).click();
    await page.getByRole('button', { name: 'Compare', exact: true }).waitFor({ timeout: 20000 });
    await page.getByRole('button', { name: 'Compare', exact: true }).click();
    await page.getByRole('heading', { name: 'Diff', exact: true }).waitFor(); await shot('history-compare');
    assert(!/Failed to load/i.test(await page.locator('body').innerText()));
  });
  await check('models gallery starts no WebGL contexts and art embeds are lazy', async () => {
    await fresh(); await page.addInitScript(() => { globalThis.__QA_WEBGL = 0; const get = HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext = function(type, ...args) { if (/webgl/.test(type)) globalThis.__QA_WEBGL++; return get.call(this, type, ...args); }; });
    await open('/docs/models/'); await shot('models-gallery'); assert.equal(await page.locator('iframe, canvas').count(), 0); assert.equal(await page.evaluate(() => globalThis.__QA_WEBGL), 0);
    for (const design of ['spider-nest', 'coral-vault', 'fault-line', 'kumiko-void', 'woven-maze', 'strip-mine']) { await open(`/docs/panels/art/${design}/`); const iframe = page.locator('iframe'); assert.equal(await iframe.count(), 1); assert.equal(await iframe.getAttribute('loading'), 'lazy'); }
  });
  await check('PCB viewer all selections, Kumiko variants, controls, query/hash reload and PNG export', async () => {
    await fresh(); await open('/viewers/pcb-art/?design=kumiko-void&variant=standard'); await readyPCB(); assert.equal((await state()).variantId, 'standard');
    for (const id of ['spider-nest', 'coral-vault', 'fault-line', 'kumiko-void', 'woven-maze']) {
      await page.locator(`[data-design="${id}"]`).click(); await settle(); assert.equal((await state()).designId, id); assert((await state()).ready); console.log('PCB selection ' + id);
      assert.equal(await page.locator('#layer-list button').count(), (await state()).layersCount);
    }
    await page.locator('[data-design="kumiko-void"]').click(); await settle();
    for (const variant of ['standard', 'wide']) { await page.locator(`[data-variant="${variant}"]`).click(); await settle(); assert.equal((await state()).variantId, variant); await page.reload({ waitUntil: 'networkidle', timeout: 60000 }); await readyPCB(); assert.equal((await state()).variantId, variant); }
    for (const view of ['front', 'side', 'back', 'iso']) { await page.locator(`[data-view="${view}"]`).click(); await settle(); assert.equal((await state()).view, view); }
    await range('#explode', '5'); assert.equal((await state()).explode, 5);
    await range('#visible-layers', '3'); assert.equal((await state()).visibleCount, 3);
    await page.locator('#layer-list button').last().click(); await settle(); assert.equal((await state()).renderedLayers.length, 1); await page.locator('#show-all').click();
    for (const selector of ['#hardware', '#rails', '#artwork', '#section']) { await page.locator(selector).setChecked(false); await page.locator(selector).setChecked(true); }
    await page.locator('#reset').click(); await settle(); await shot('pcb-viewer-wide');
    const pending = page.waitForEvent('download'); await page.locator('#download-png').click(); const download = await pending; assert.equal(await download.failure(), null); assert.match(download.suggestedFilename(), /kumiko-void-wide.*\.png$/); await download.saveAs(`${out}/viewer-export.png`); assert.equal((await readFile(`${out}/viewer-export.png`)).subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
  });
  await check('Strip Mine all patterns, selected Strata/blobs, controls and hash reload', async () => {
    await fresh(); await open('/viewers/strip-mine/#pattern=5'); await page.waitForFunction(() => !!window.__checks); assert.match(await page.locator('#variant-name').innerText(), /5\. .*Strata/i);
    const count = await page.locator('#variants button').count(); for (let i = 0; i < count; i++) { await page.locator('#variants button').nth(i).click(); assert.equal(new URL(page.url()).hash, `#pattern=${i + 1}`); assert.equal(await page.locator('#variants button').nth(i).getAttribute('aria-pressed'), 'true'); }
    await page.locator('#variants button').nth(4).click(); await page.reload({ waitUntil: 'networkidle', timeout: 60000 }); await page.waitForFunction(() => !!window.__checks); assert.match(await page.locator('#variant-name').innerText(), /Strata/i);
    for (const view of ['front', 'side', 'back', 'low', 'iso']) await page.locator(`[data-view="${view}"]`).click();
    for (const [selector, value] of [['#gap', '5'], ['#layers', '3']]) { await range(selector, value); }
    for (const selector of ['#bldg', '#hw', '#rails', '#section']) { await page.locator(selector).setChecked(false); await page.locator(selector).setChecked(true); }
    assert(await page.locator('canvas').isVisible()); await shot('strip-mine-pattern5');
  });
  await check('mobile viewers fit and touch controls work', async () => {
    for (const viewer of ['pcb-art', 'strip-mine']) { await fresh({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true }); await open(`/viewers/${viewer}/`); if (viewer === 'pcb-art') await readyPCB(); else await page.waitForFunction(() => !!window.__checks); await fits(); const button = page.locator('[data-view="front"]'); await button.scrollIntoViewIfNeeded(); await button.tap(); await fits(); await shot(`mobile-${viewer}`); }
  });
  await check('mechanical downloads retain native format signatures', async () => {
    await fresh(); for (const [file, signature] of [['adapter-3u-to-1u.step', 'ISO-10303-21'], ['plain-3u-8hp.FCStd', 'PK']]) { const response = await page.request.get(base + '/assets/models/' + file); assert.equal(response.status(), 200); assert((await response.body()).subarray(0, 100).toString().includes(signature)); } const stl = await page.request.get(base + '/assets/models/plain-3u-8hp.stl'); assert.equal(stl.status(), 200); assert((await stl.body()).length > 100); }
  );
} finally { await browser?.close(); report.finishedAt = new Date().toISOString(); report.passed = report.checks.every(c => c.passed) && report.errors.length === 0; await writeFile(`${out}/report.json`, JSON.stringify(report, null, 2) + '\n'); }
if (!report.passed) process.exitCode = 1;
