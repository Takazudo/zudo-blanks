/**
 * Offline browser integration checks for the generated PCB art preview.
 * Run after building: node tests/browser.mjs
 * Focused finish/shape-revision checks: node tests/browser.mjs --revision
 * Artifacts: tests/output/browser-report.json and desktop/mobile PNGs.
 */
import assert from 'node:assert/strict';
import { access, mkdir, writeFile, readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { spawnSync } from 'node:child_process';
import { chromium as playwrightChromium } from 'playwright';
import chromium from '@sparticuz/chromium';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const entry = process.env.PCB_PREVIEW_ENTRY || path.join(projectRoot, 'dist', 'index.html');
const outputDir = path.join(projectRoot, 'tests', 'output');
const focusedRevision = process.argv.includes('--revision');
const reportFilename = focusedRevision ? 'revision-report.json' : 'browser-report.json';
let executablePath = process.env.PCB_BROWSER_PATH;
if (!executablePath) {
  try { await access('/tmp/pcb-preview-chromium'); executablePath = '/tmp/pcb-preview-chromium'; } catch {}
}
const expectedDesigns = [
  { id: 'spider-nest', number: '01', count: 8, enig: [1, 3, 5, 7], fill: [3, 5, 7], colors: ['black','white','gold','white','gold','white','gold','red'] },
  { id: 'coral-vault', number: '03', count: 8, enig: [1, 4], fill: [4], colors: ['black','green','purple','gold','red','yellow','red','blue'] },
  { id: 'fault-line', number: '13', count: 9, enig: [1], fill: [], colors: ['black','red','black','red','black','red','black','red','black'] },
  { id: 'kumiko-void', number: '17', count: 9, enig: [1, 4, 7], fill: [], colors: ['black','red','green','black','red','green','black','red','green'] },
  { id: 'woven-maze', number: '18', count: 9, enig: [1], fill: [], colors: ['black','white','black','white','black','white','black','white','black'] },
];
let report = { mode: focusedRevision ? 'focused-revision' : 'full', startedAt: new Date().toISOString(), entry, checks: [], screenshots: [], networkRequests: [], browserErrors: [] };

const resumeAfterDesktop = !focusedRevision && process.argv.includes('--resume-after-desktop');
if (resumeAfterDesktop) {
  report = JSON.parse(await readFile(path.join(outputDir, 'browser-report.json'), 'utf8'));
  delete report.failure;
  delete report.finishedAt;
  report.resumedAt = new Date().toISOString();
}

try { await access(entry); } catch {
  console.error(`Build is required before browser QA: ${entry} does not exist.`);
  process.exit(2);
}
await mkdir(outputDir, { recursive: true });
let browser;
let activePage;
async function launchBrowser() {
  try {
    return await playwrightChromium.launch({
      ...(executablePath ? { executablePath } : {}),
      ...(executablePath === '/tmp/pcb-preview-chromium' ? { args: chromium.args, env: { ...process.env, FONTCONFIG_PATH: '/tmp/fonts' } } : {}),
      headless: true,
    });
  } catch (error) {
    throw new Error('Could not launch Chromium. Run `npx playwright install chromium` or set PCB_BROWSER_PATH to a working browser executable.', { cause: error });
  }
}

function pass(label, details = {}) {
  report.checks.push({ label, passed: true, ...details });
  console.log(`PASS ${label}`);
}

async function context(options) {
  // Serverless Chromium closes its single process with a context; each phase gets a fresh browser.
  if (browser) await browser.close();
  browser = await launchBrowser();
  const ctx = await browser.newContext({ acceptDownloads: true, offline: true, ...options });
  if (focusedRevision) await ctx.addInitScript(() => {
    // Observe the actual texture canvases without changing production code.
    // Disposed textures are resized to 1 px by the viewer and are filtered out.
    globalThis.__QA_TEXTURE_CANVASES__ = [];
    const getContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function (mode, ...args) {
      const context = getContext.call(this, mode, ...args);
      if (mode === '2d' && context && !globalThis.__QA_TEXTURE_CANVASES__.some(item => item.canvas === this)) {
        globalThis.__QA_TEXTURE_CANVASES__.push({ canvas: this, context });
      }
      return context;
    };
  });
  await ctx.route('**/*', async route => {
    if (/^https?:/i.test(route.request().url())) {
      report.networkRequests.push(route.request().url());
      return route.abort('internetdisconnected');
    }
    return route.continue();
  });
  ctx.on('page', page => {
    page.on('pageerror', error => report.browserErrors.push({ type: 'pageerror', message: error.stack || error.message }));
    page.on('console', message => {
      if (message.type() === 'error') report.browserErrors.push({ type: 'console', message: message.text() });
    });
  });
  return ctx;
}

async function settle(page, milliseconds = 180) {
  await page.waitForTimeout(milliseconds);
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function state(page) {
  return page.evaluate(() => globalThis.__PCB_PREVIEW__.getState());
}

async function call(page, method, ...args) {
  await page.evaluate(({ method, args }) => globalThis.__PCB_PREVIEW__[method](...args), { method, args });
  await settle(page);
  return state(page);
}

async function open(page, entryPath = entry) {
  activePage = page;
  await page.goto(pathToFileURL(entryPath).href, { waitUntil: 'load', timeout: 60000 });
  assert.equal(report.browserErrors.length, 0, `Errors during startup: ${JSON.stringify(report.browserErrors)}`);
  await page.waitForFunction(() => globalThis.__PCB_PREVIEW__?.ready, null, { timeout: 60000 });
  await settle(page, 400);
  const canvas = page.locator('canvas').first();
  assert(await canvas.isVisible(), 'The model canvas is visible');
  const rendering = await canvas.evaluate(canvas => {
    const gl = canvas.getContext('webgl2');
    return { width: canvas.width, height: canvas.height, webgl2: !!gl, lost: gl?.isContextLost() ?? true };
  });
  assert(rendering.webgl2 && !rendering.lost, 'WebGL2 context must be live');
  assert(rendering.width > 100 && rendering.height > 100, 'Canvas must have meaningful dimensions');
  return rendering;
}

async function screenshot(page, filename) {
  const destination = path.join(outputDir, filename);
  await page.screenshot({ path: destination, fullPage: false, animations: 'disabled' });
  assert((await stat(destination)).size > 10000, 'Screenshot must contain rendered content');
  report.screenshots.push(filename);
}

async function desktopChecks() {
  const ctx = await context({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  const rendering = await open(page);
  pass('Desktop file:// entry starts with a live WebGL2 model', rendering);
  assert.equal(await page.locator('#design-nav button').count(), 5, 'All five designs are selectable');

  for (let position = 0; position < expectedDesigns.length; position++) {
    const design = expectedDesigns[position];
    await page.locator('#design-nav button').nth(position).click();
    await page.waitForFunction(id => globalThis.__PCB_PREVIEW__.getState().designId === id, design.id);
    let current = await state(page);
    assert.equal(current.layersCount, design.count, `${design.id}: expected PCB layers`);
    assert(current.ready, `${design.id}: state is ready`);
    assert.equal(await page.locator('#layer-list button').count(), design.count, 'Every PCB has an individual UI control');
    await page.locator('#reset').click();
    await settle(page, 350);
    current = await state(page);
    assert.equal(current.visibleCount, design.count);
    assert.equal(current.isolatedLayer, null);
    assert.equal(current.view, 'iso');
    await screenshot(page, `${design.id}-oblique.png`);

    current = await call(page, 'setExplode', 7.5);
    assert.equal(current.explode, 7.5, 'Exploded spacing updates');
    assert.equal(Number(await page.locator('#explode').inputValue()), 7.5, 'Exploded spacing is reflected in the UI');
    current = await call(page, 'setVisibleCount', 2);
    assert.equal(current.visibleCount, 2, 'Partial stack updates');
    assert.equal(current.renderedLayers.length, 2, 'Only the first two PCBs are rendered');
    assert.equal(Number(await page.locator('#visible-layers').inputValue()), 2);
    current = await call(page, 'isolateLayer', design.count - 1);
    assert.equal(current.isolatedLayer, design.count - 1, 'Floor can be isolated');
    assert.equal(current.renderedLayers.length, 1, 'Isolating the floor renders exactly one PCB');
    await page.locator('#show-all').click();
    await settle(page);
    current = await state(page);
    assert.equal(current.isolatedLayer, null, 'Show-all clears isolation');
    assert.equal(current.renderedLayers.length, design.count, 'Show-all restores all PCBs');
    await call(page, 'setExplode', 0);

    for (const view of ['front', 'side', 'back']) {
      await page.locator(`[data-view="${view}"]`).click();
      await settle(page, 250);
      current = await state(page);
      assert.equal(current.view, view, `Camera ${view} control works`);
      assert.equal(await page.locator(`[data-view="${view}"]`).getAttribute('aria-pressed'), 'true');
      if (view === 'front') await screenshot(page, `${design.id}-front.png`);
    }
    await call(page, 'setView', 'iso');
    pass(`${design.id}: ${design.count} PCBs, spacing, partial stack, floor isolation, restore, four camera views`);
  }

  // Exercise every display switch through the real checkbox control.
  for (const [selector, key] of [['#hardware', 'hardware'], ['#rails', 'rails'], ['#artwork', 'artwork'], ['#section', 'section']]) {
    const checkbox = page.locator(selector);
    const original = await checkbox.isChecked();
    await checkbox.setChecked(!original);
    await settle(page);
    assert.equal((await state(page))[key], !original, `${selector} applies its changed value`);
    await checkbox.setChecked(original);
    await settle(page);
    assert.equal((await state(page))[key], original, `${selector} restores its value`);
    pass(`UI switch ${key}: both directions`);
  }

  await page.locator('#reset').click();
  await settle(page);
  const downloadPromise = page.waitForEvent('download', { timeout: 20000 });
  await page.locator('#download-png').click();
  const download = await downloadPromise;
  assert.equal(await download.failure(), null, 'PNG download succeeds');
  assert.match(download.suggestedFilename(), /\.png$/i, 'Download has a PNG filename');
  const pngPath = path.join(outputDir, 'downloaded-preview.png');
  await download.saveAs(pngPath);
  assert((await stat(pngPath)).size > 10000, 'Downloaded PNG contains rendered image data');
  report.download = { filename: download.suggestedFilename(), savedAs: 'downloaded-preview.png', bytes: (await stat(pngPath)).size };
  pass('Current-view PNG download', report.download);
  await ctx.close();
}

async function mobileChecks() {
  const ctx = await context({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
  const page = await ctx.newPage();
  await open(page);
  await screenshot(page, 'mobile-390x844.png');
  const initial = await page.evaluate(() => ({
    width: innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body.scrollWidth,
    scroll: scrollY,
    panelTop: document.querySelector('.controls-panel').getBoundingClientRect().top,
  }));
  assert(initial.documentWidth <= initial.width + 1, 'Mobile document has no horizontal overflow');
  assert(initial.bodyWidth <= initial.width + 1, 'Mobile body has no horizontal overflow');
  assert(initial.panelTop < 844, 'The start of the controls is visible below the model');

  // Native Chromium touch scrolling verifies the page is not trapped by the 3D canvas.
  const cdp = await ctx.newCDPSession(page);
  const swipeStart = Math.min(805, Math.max(740, initial.panelTop + 60));
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: 190, y: swipeStart }] });
  for (let y = swipeStart - 30; y >= swipeStart - 490; y -= 40) {
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: 190, y }] });
    await page.waitForTimeout(35);
  }
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
  await settle(page, 250);
  const afterSwipe = await page.evaluate(() => scrollY);
  assert(afterSwipe > initial.scroll + 50, `Touch swipe must scroll toward controls (${initial.scroll} -> ${afterSwipe})`);

  const front = page.locator('[data-view="front"]');
  await front.scrollIntoViewIfNeeded();
  await front.tap();
  await settle(page);
  assert.equal((await state(page)).view, 'front', 'Mobile camera button responds to touch');
  const floor = page.locator('#layer-list button').last();
  await floor.scrollIntoViewIfNeeded();
  await floor.tap();
  await settle(page);
  assert.equal((await state(page)).isolatedLayer, 7, 'Mobile layer control responds to touch');
  await page.locator('#show-all').tap();
  await settle(page);
  assert.equal((await state(page)).renderedLayers.length, 8, 'Mobile show-all restores the stack');

  for (const selector of ['#explode', '#visible-layers', '#hardware', '#rails', '#artwork', '#section', '#show-all']) {
    const control = page.locator(selector);
    await control.scrollIntoViewIfNeeded();
    const box = await control.boundingBox();
    assert(box && box.width > 0 && box.height > 0, `${selector} has an interactive area`);
    assert(box.x >= -1 && box.x + box.width <= 391, `${selector} fits within the mobile viewport`);
    assert(box.y >= -1 && box.y + box.height <= 845, `${selector} can be scrolled into view`);
  }
  await page.locator('.display-section').scrollIntoViewIfNeeded();
  await screenshot(page, 'mobile-controls-390x844.png');
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'No overflow after interaction');
  pass('Mobile 390×844: no horizontal overflow, native touch scrolling, reachable controls, touch camera/layer actions', { scrollAfterSwipe: afterSwipe });
  await ctx.close();
}

async function captureModelCanvas(page, filename) {
  const png = await page.locator('#preview-canvas').evaluate(canvas => canvas.toDataURL('image/png').split(',')[1]);
  await writeFile(path.join(outputDir, filename), Buffer.from(png, 'base64'));
  report.screenshots.push(filename);
}

async function checkGoldBorderTextures(page, key) {
  const actual = await page.evaluate(() => {
    const state = globalThis.__PCB_PREVIEW__.getState();
    const family = globalThis.PCB_ART_DATA.designs.find(d => d.id === state.designId);
    const design = [family, ...(family.variants || [])].find(d => (d.variantId || null) === state.variantId) || family;
    const spec = globalThis.PCB_ART_DATA.spec;
    const textures = globalThis.__QA_TEXTURE_CANVASES__.filter(({ canvas }) => canvas.width > 100 && canvas.height > 100 && Math.abs(canvas.width / canvas.height - spec.width / spec.height) < 0.002);
    if (textures.length < 2) throw new Error('Actual front color/ORM canvases were not captured');
    const [color, orm] = textures;
    const features = design.layers[0].art.strokes.filter(s => s.purpose === 'top-gold-border').map(stroke => {
      const pts = [...stroke.pts];
      if (pts[0][0] !== pts.at(-1)[0] || pts[0][1] !== pts.at(-1)[1]) pts.push(pts[0]);
      let count = 0, gold = 0, metallic = 0;
      for (let segment = 0; segment < pts.length - 1; segment++) for (const t of [0.25, 0.5, 0.75]) {
        const x = pts[segment][0] * (1 - t) + pts[segment + 1][0] * t;
        const y = pts[segment][1] * (1 - t) + pts[segment + 1][1] * t;
        const pixel = ({ canvas, context }) => context.getImageData(Math.floor(x * canvas.width / spec.width), Math.floor(y * canvas.height / spec.height), 1, 1).data;
        const c = pixel(color), m = pixel(orm);
        count++;
        if (c[0] >= 210 && c[0] <= 224 && c[1] >= 173 && c[1] <= 187 && c[2] >= 86 && c[2] <= 100 && c[3] === 255) gold++;
        if (m[2] >= 250 && m[1] >= 83 && m[1] <= 93 && m[3] === 255) metallic++;
      }
      return { feature: stroke.feature, featureIndex: stroke.featureIndex ?? null, samples: count, goldSamples: gold, metallicSamples: metallic };
    });
    return { metadata: design.topGoldBorders, textureSize: [color.canvas.width, color.canvas.height], features };
  });
  assert.equal(actual.features.length, 9, `${key}: outer frame plus eight hole/slot borders`);
  for (const feature of actual.features) {
    assert(feature.goldSamples / feature.samples > 0.98, `${key}/${feature.feature}: actual color texture lacks gold pixels`);
    assert(feature.metallicSamples / feature.samples > 0.98, `${key}/${feature.feature}: actual ORM texture lacks ENIG pixels`);
  }
  report.goldBorderTextures ??= {};
  report.goldBorderTextures[key] = actual;
  pass(`${key}: all 9 gold borders exist in the actual color and metalness textures`);
}

async function captureTop(page, filename) {
  const before = await state(page);
  await call(page, 'isolateLayer', 0);
  await call(page, 'setView', 'front');
  await page.locator('#hardware').setChecked(false);
  await settle(page);
  await captureModelCanvas(page, filename);
  await page.locator('#hardware').setChecked(before.hardware);
  await call(page, 'isolateLayer', before.isolatedLayer);
  await call(page, 'setView', before.view);
}

async function checkCurrentFinish(page, expected, key = expected.id) {
  const current = await state(page);
  assert.equal(current.designId, expected.id);
  assert.equal(current.layersCount, expected.count);
  assert.equal(current.renderedLayers.length, expected.count);
  const actual = await page.evaluate(id => {
    const family = globalThis.PCB_ART_DATA.designs.find(d => d.id === id);
    const variantId = globalThis.__PCB_PREVIEW__.getState().variantId;
    const d = [family, ...(family.variants || [])].find(v => (v.variantId || null) === variantId) || family;
    return { variantId: d.variantId || null, finishSummary: d.finishSummary,
      layers: d.layers.map((layer, index) => ({ index, colorKey: layer.colorKey, finish: layer.finish,
        finishLabel: layer.finishLabel, surface: layer.surface, strokeCount: layer.art.strokes.length,
        fillCount: layer.art.fills.length, rendered: globalThis.__PCB_PREVIEW__.inspectLayer(index) })) };
  }, expected.id);
  assert.deepEqual(actual.layers.map(layer => layer.colorKey), expected.colors);
  const maskOnly = Array.from({ length: expected.count }, (_, i) => i + 1).filter(n => !expected.enig.includes(n));
  assert.deepEqual(actual.finishSummary.enigLayers, expected.enig);
  assert.deepEqual(actual.finishSummary.maskOnlyLayers, maskOnly);
  assert.equal(actual.finishSummary.enigCount, expected.enig.length);
  assert.equal(actual.finishSummary.maskOnlyCount, maskOnly.length);
  assert.equal(actual.finishSummary.totalLayers, expected.count);
  const buttons = page.locator('#layer-list button');
  assert.equal(await buttons.count(), expected.count);
  for (const layer of actual.layers) {
    const number = layer.index + 1;
    const finish = expected.fill.includes(number) ? 'enig-fill' : expected.enig.includes(number) ? 'enig-art' : 'mask-only';
    assert.equal(layer.finish, finish, `${key} PCB${number}: finish`);
    assert.equal(layer.rendered.finish, finish);
    assert.equal(layer.surface, finish === 'enig-fill' ? 'gold' : 'mask');
    assert.equal(layer.rendered.surface, layer.surface);
    assert(layer.finishLabel?.length > 0);
    assert.equal(await buttons.nth(layer.index).getAttribute('data-finish'), finish);
    assert((await buttons.nth(layer.index).locator('.layer-finish').innerText()).trim().length > 0);
    if (finish === 'mask-only') {
      assert.equal(layer.strokeCount + layer.fillCount, 0);
      assert.equal(layer.rendered.artworkMeshCount + layer.rendered.artworkTextureCount + layer.rendered.artworkVisibleCount, 0);
      assert.equal(layer.rendered.boardMaterialMetalness, 0);
    } else {
      assert(layer.rendered.artworkMeshCount > 0 && layer.rendered.artworkVisibleCount > 0);
      if (['spider-nest', 'kumiko-void'].includes(expected.id)) {
        assert.equal(layer.rendered.strokeJoin, 'miter');
        assert.equal(layer.rendered.strokeCap, 'butt');
      }
    }
  }
  report.finishPolicy[key] = actual;
  pass(`${key}: approved colors and selected-board ENIG in data, UI and rendered meshes/textures`);
}

async function kumikoVariantChecks(page, expected, python) {
  assert.equal((await state(page)).variantId, 'wide', 'Main navigation defaults to wide');
  assert.equal(await page.locator('#variant-options button').count(), 2);
  await call(page, 'setExplode', 2.5);
  await call(page, 'setVisibleCount', 4);
  await call(page, 'isolateLayer', 2);
  for (const [id, value] of [['artwork', false], ['hardware', false], ['rails', true], ['section', true]]) await page.locator(`#${id}`).setChecked(value);
  await settle(page);
  const before = await state(page);
  await page.locator('[data-variant="standard"]').click();
  await settle(page, 300);
  const after = await state(page);
  assert.equal(after.variantId, 'standard');
  for (const key of ['visibleCount','isolatedLayer','explode','view','artwork','hardware','rails','section']) assert.equal(after[key], before[key], `Variant switch preserves ${key}`);
  assert.deepEqual(after.cameraPosition, before.cameraPosition, 'Variant switch preserves exact camera position');
  assert.deepEqual(after.cameraTarget, before.cameraTarget, 'Variant switch preserves camera target');
  await call(page, 'reset');
  await checkCurrentFinish(page, expected, 'kumiko-void:standard');
  await checkGoldBorderTextures(page, 'kumiko-void:standard');
  await captureTop(page, 'kumiko-void-standard-top-render.png');
  await screenshot(page, 'kumiko-void-standard-oblique.png');
  await captureModelCanvas(page, 'kumiko-void-standard-render.png');
  const standardPose = await state(page);
  await page.locator('[data-variant="wide"]').click();
  await settle(page, 300);
  const widePose = await state(page);
  assert.equal(widePose.variantId, 'wide');
  assert.deepEqual(widePose.cameraPosition, standardPose.cameraPosition);
  assert.deepEqual(widePose.cameraTarget, standardPose.cameraTarget);
  await screenshot(page, 'kumiko-void-oblique.png');
  await captureModelCanvas(page, 'kumiko-void-wide-render.png');
  const comparison = spawnSync(python, [path.join(projectRoot, 'tests', 'compose_kumiko.py')], { cwd: projectRoot, encoding: 'utf8' });
  assert.equal(comparison.status, 0, comparison.stderr || comparison.stdout);
  report.screenshots.push('kumiko-void-variants.png');
  report.kumikoComparison = { cameraPosition: widePose.cameraPosition, cameraTarget: widePose.cameraTarget, samePose: true };
  pass('Kumiko variants retain controls and camera; standard/wide comparison uses one identical pose');
  const pending = page.waitForEvent('download', { timeout: 20000 });
  await page.locator('#download-png').click();
  const download = await pending;
  assert.equal(await download.failure(), null);
  assert.match(download.suggestedFilename(), /^kumiko-void-wide-iso\.png$/);
  const destination = path.join(outputDir, 'revision-export.png');
  await download.saveAs(destination);
  const bytes = await readFile(destination);
  assert.equal(bytes.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
  assert(bytes.length > 10000);
  report.download = { filename: download.suggestedFilename(), savedAs: 'revision-export.png', bytes: bytes.length };
  pass('PNG export identifies the selected Kumiko variant', report.download);
  await page.locator('#toast').waitFor({ state: 'hidden', timeout: 5000 });
}

async function revisionChecks() {
  report.revision = 5;
  const python = process.env.PCB_PREVIEW_PYTHON || path.join(projectRoot, '.venv', 'bin', 'python');
  const geometry = spawnSync(python, [path.join(projectRoot, 'tests', 'revision_geometry.py')], { cwd: projectRoot, encoding: 'utf8' });
  assert.equal(geometry.status, 0, `Serialized geometry checks failed: ${geometry.stderr || geometry.error || geometry.stdout}`);
  report.geometry = JSON.parse(await readFile(path.join(outputDir, 'revision-geometry-report.json'), 'utf8'));
  pass('Revision 5 polygons: all 52 Rev4 shapes/drills and lower artwork preserved; all six top gold borders contained');
  const silhouettes = spawnSync(python, [path.join(projectRoot, 'tests', 'compose_openings.py')], { cwd: projectRoot, encoding: 'utf8' });
  assert.equal(silhouettes.status, 0, silhouettes.stderr || silhouettes.stdout);
  report.screenshots.push('pcb-art-openings-before-after.png');
  const ctx = await context({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  pass('Revision-5 offline HTML starts with a live WebGL2 model', await open(page));
  assert.equal(await page.evaluate(() => globalThis.PCB_ART_DATA.revision), 5);
  assert.equal(await page.locator('#design-nav button').count(), 5, 'Variants do not add another design family');
  report.finishPolicy = {};

  for (let position = 0; position < expectedDesigns.length; position++) {
    const expected = expectedDesigns[position];
    await page.locator('#design-nav button').nth(position).click();
    await settle(page, 300);
    assert.equal(await page.locator('#variant-selector').isVisible(), expected.id === 'kumiko-void');
    if (expected.id === 'kumiko-void') assert.equal((await state(page)).variantId, 'wide');
    await checkCurrentFinish(page, expected, expected.id === 'kumiko-void' ? 'kumiko-void:wide' : expected.id);
    await checkGoldBorderTextures(page, expected.id === 'kumiko-void' ? 'kumiko-void:wide' : expected.id);
    await call(page, 'setView', 'iso');
    await screenshot(page, `${expected.id}-oblique.png`);
    await captureModelCanvas(page, `${expected.id}-overview-render.png`);
    if (['spider-nest', 'coral-vault', 'fault-line'].includes(expected.id)) {
      await call(page, 'setView', 'front');
      await screenshot(page, `${expected.id}-front.png`);
    }
    {
      await call(page, 'isolateLayer', 0);
      await call(page, 'setView', 'front');
      await screenshot(page, `${expected.id}-top-pattern.png`);
      await captureTop(page, `${expected.id}-top-render.png`);
      await call(page, 'isolateLayer', null);
      await call(page, 'setView', 'iso');
    }
    if (expected.id === 'kumiko-void') await kumikoVariantChecks(page, expected, python);
  }

  for (let index = 0; index < 8; index++) {
    await call(page, 'isolateLayer', index);
    await call(page, 'setView', 'front');
    await captureModelCanvas(page, `woven-maze-layer-${String(index + 1).padStart(2, '0')}.png`);
  }
  const comparison = spawnSync(python, [path.join(projectRoot, 'tests', 'compose_woven.py')], { cwd: projectRoot, encoding: 'utf8' });
  assert.equal(comparison.status, 0, comparison.stderr || comparison.stdout);
  report.screenshots.push('woven-maze-layers-01-08.png');
  pass('Woven L1-L8 actual captures form a same-physical-scale comparison');
  await call(page, 'isolateLayer', 1);
  const white = await page.evaluate(() => globalThis.__PCB_PREVIEW__.inspectLayer(1));
  assert.equal(white.finish, 'mask-only');
  assert.equal(white.artworkMeshCount + white.artworkTextureCount + white.artworkVisibleCount, 0);
  await screenshot(page, 'woven-maze-white-no-gold.png');
  await page.locator('#show-all').click();
  for (const enabled of [false, true]) {
    await page.locator('#artwork').setChecked(enabled);
    await settle(page);
    const [top, plain] = await page.evaluate(() => [globalThis.__PCB_PREVIEW__.inspectLayer(0), globalThis.__PCB_PREVIEW__.inspectLayer(1)]);
    assert.equal(top.artworkVisibleCount > 0, enabled);
    assert.equal(plain.artworkMeshCount + plain.artworkTextureCount + plain.artworkVisibleCount, 0);
  }
  pass('Woven white stays free of decorative meshes/textures and art toggles only the ENIG board');
  await ctx.close();

  for (const [filename, variant] of [['17-kumiko-void.html','standard'],['17-kumiko-void-wide.html','wide']]) {
    const cold = await context({ viewport: { width: 1440, height: 1000 } });
    const coldPage = await cold.newPage();
    await open(coldPage, path.join(path.dirname(entry), filename));
    assert.equal((await state(coldPage)).variantId, variant, `${filename} initial variant`);
    assert.equal(await coldPage.locator(`[data-variant="${variant}"]`).getAttribute('aria-pressed'), 'true');
    assert.equal(await coldPage.locator('#design-nav button').count(), 5);
    pass(`Standalone initial variant: ${filename} → ${variant}`);
    await cold.close();
  }

  const mobile = await context({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
  const smallPage = await mobile.newPage();
  await open(smallPage);
  await smallPage.locator('[data-design="kumiko-void"]').tap();
  await settle(smallPage, 300);
  assert.equal((await state(smallPage)).variantId, 'wide');
  await smallPage.locator('#variant-selector').scrollIntoViewIfNeeded();
  await smallPage.locator('[data-variant="standard"]').tap();
  await settle(smallPage, 250);
  assert.equal((await state(smallPage)).variantId, 'standard');
  await smallPage.locator('[data-variant="wide"]').tap();
  await settle(smallPage, 250);
  assert.equal((await state(smallPage)).variantId, 'wide');
  const fit = await smallPage.evaluate(() => ({ width: innerWidth, documentWidth: document.documentElement.scrollWidth, bodyWidth: document.body.scrollWidth }));
  assert(fit.documentWidth <= fit.width + 1 && fit.bodyWidth <= fit.width + 1);
  for (const selector of ['#variant-selector', '#finish-summary', '#layer-list', '.display-section']) {
    const control = smallPage.locator(selector);
    await control.scrollIntoViewIfNeeded();
    const box = await control.boundingBox();
    assert(box && box.x >= -1 && box.x + box.width <= 391, `${selector} fits mobile width`);
  }
  await smallPage.locator('#variant-selector').scrollIntoViewIfNeeded();
  await screenshot(smallPage, 'revision-mobile-controls-390x844.png');
  await smallPage.evaluate(() => scrollTo(0, 0));
  await screenshot(smallPage, 'revision-mobile-390x844.png');
  pass('Mobile variant buttons respond to touch; picker, finish labels and controls fit 390px', fit);
  await mobile.close();
}

async function standaloneChecks() {
  for (const design of expectedDesigns) {
    const ctx = await context({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    const file = `${design.number}-${design.id}.html`;
    await open(page, path.join(path.dirname(entry), file));
    const current = await state(page);
    assert.equal(current.designId, design.id, `${file} starts with its own selected design`);
    assert.equal(current.layersCount, design.count);
    assert.equal(current.renderedLayers.length, design.count);
    await screenshot(page, `${design.id}-oblique.png`);
    pass(`Standalone cold start: ${file}`, { designId: current.designId });
    if (design.id === 'spider-nest') {
      const pending = page.waitForEvent('download', { timeout: 20000 });
      await page.locator('#download-png').click();
      const download = await pending;
      assert.equal(await download.failure(), null);
      const pngPath = path.join(outputDir, 'downloaded-preview.png');
      await download.saveAs(pngPath);
      assert((await stat(pngPath)).size > 10000);
      report.download = { filename: download.suggestedFilename(), savedAs: 'downloaded-preview.png', bytes: (await stat(pngPath)).size };
      pass('Final built standalone PNG export', report.download);
    }
    await ctx.close();
  }
}

try {
  if (focusedRevision) {
    await revisionChecks();
  } else {
    if (!resumeAfterDesktop) await desktopChecks();
    await mobileChecks();
    await standaloneChecks();
  }
  assert.equal(report.networkRequests.length, 0, 'Offline HTML must never attempt an HTTP(S) request');
  pass('No HTTP(S) requests while opening and using file:// HTML');
  assert.equal(report.browserErrors.length, 0, `Browser errors: ${JSON.stringify(report.browserErrors)}`);
  pass('No JavaScript exceptions or console errors');
  report.passed = true;
} catch (error) {
  report.passed = false;
  report.failure = error.stack || String(error);
  if (activePage && !activePage.isClosed()) {
    try { await screenshot(activePage, 'failure.png'); } catch {}
  }
  console.error(report.failure);
  process.exitCode = 1;
} finally {
  report.finishedAt = new Date().toISOString();
  report.screenshots = [...new Set(report.screenshots)].filter(name => !report.passed || name !== 'failure.png');
  await writeFile(path.join(outputDir, reportFilename), JSON.stringify(report, null, 2) + '\n');
  await browser?.close();
}
