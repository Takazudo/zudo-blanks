import assert from 'node:assert/strict';
import { readFile, readdir, stat } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
const dist = path.join(root, 'dist');
const ignored = (await readFile(path.join(dist, '.assetsignore'), 'utf8')).split(/\r?\n/);
const hidden = ['_worker.js', '_zfb_inner.mjs', ...(await readdir(dist)).filter(p => p.endsWith('.wasm'))];
for (const name of hidden) assert(ignored.includes(name), `Missing generated asset exclusion: ${name}`);
async function inspect(dir) {
  for (const item of await readdir(dir, { withFileTypes: true })) {
    const name = path.join(dir, item.name);
    if (item.isDirectory()) await inspect(name);
    else assert((await stat(name)).size <= 25 * 1024 * 1024, `Oversized static file: ${name}`);
  }
}
await inspect(dist);
assert((await readFile(path.join(dist, '404.html'), 'utf8')).includes('Page not found'), 'Styled 404 is required');
const socket = createServer();
await new Promise(resolve => socket.listen(0, '127.0.0.1', resolve));
const port = socket.address().port;
await new Promise(resolve => socket.close(resolve));
const server = spawn(process.execPath, [path.join(root, 'node_modules/wrangler/bin/wrangler.js'), 'dev', '--local', '--ip', '127.0.0.1', '--port', String(port)], { cwd: root, env: { ...process.env, WRANGLER_SEND_METRICS: 'false', CI: 'true' }, stdio: ['ignore', 'pipe', 'pipe'] });
let log = '';
server.stdout.on('data', data => { log += data; });
server.stderr.on('data', data => { log += data; });
const base = `http://127.0.0.1:${port}`;
try {
  let ready = false;
  for (let attempt = 0; attempt < 120; attempt++) {
    if (server.exitCode !== null) throw new Error(log);
    try { await fetch(base); ready = true; break; } catch { await new Promise(resolve => setTimeout(resolve, 500)); }
  }
  assert(ready, `Worker did not start: ${log}`);
  for (const [route, words] of [['/', 'Browse panels'], ['/docs/panels/', 'Plain'], ['/docs/models/', 'Strip Mine'], ['/docs/guides/assembly/stack/', 'spacers'], ['/docs/manufacturing/', 'order'], ['/files/', 'Files'], ['/viewers/pcb-art/?design=kumiko-void&variant=standard', 'geometry'], ['/viewers/strip-mine/', 'Strip Mine']]) {
    const response = await fetch(base + route);
    assert.equal(response.status, 200, route);
    assert((await response.text()).toLowerCase().includes(words.toLowerCase()), `Missing meaningful content: ${route} (${words})`);
    console.log(`PASS page ${route}`);
  }
  const manifest = JSON.parse(await readFile(path.join(root, 'public/viewers/manifest.json')));
  const spacerSource = await readFile(path.join(root, '../_3dp/blank-module-spacer-m3.3mf'));
  const spacerRecord = manifest.files['assets/models/blank-module-spacer-m3.3mf'];
  assert.equal(spacerRecord?.bytes, spacerSource.length, 'M3 spacer manifest size');
  assert.equal(spacerRecord?.sha256, createHash('sha256').update(spacerSource).digest('hex'), 'M3 spacer manifest hash');
  for (const [name, expected] of Object.entries(manifest.files)) {
    const response = await fetch(`${base}/${name}`);
    assert.equal(response.status, 200, name);
    const bytes = Buffer.from(await response.arrayBuffer());
    assert.equal(createHash('sha256').update(bytes).digest('hex'), expected.sha256, `Raw bytes: ${name}`);
    if (/\.(step|stl|FCStd|3mf)$/.test(name)) assert(!response.headers.get('content-type')?.includes('text/html'), `HTML substituted for model: ${name}`);
  }
  for (const route of ['/missing-page-for-verification/', ...hidden.map(name => `/${name}`)]) {
    const response = await fetch(base + route);
    assert.equal(response.status, 404, `Public server module or false 404: ${route}`);
    assert((await response.text()).includes('Page not found'), `Unstyled 404: ${route}`);
  }
  const redirects = (await readFile(path.join(root, 'public/_redirects'), 'utf8')).split('\n').filter(line => line && !line.startsWith('#'));
  for (const line of redirects) {
    const [from, to, status] = line.split(/\s+/);
    if (from.includes('*') || from.includes(':')) continue;
    const response = await fetch(base + from + '?verification=preserved', { redirect: 'manual' });
    assert.equal(response.status, Number(status), `Redirect ${from}`);
    const target = new URL(response.headers.get('location'), base);
    assert.equal(target.pathname, to, `Redirect target ${from}`);
    assert.equal(target.searchParams.get('verification'), 'preserved', `Query lost ${from}`);
  }
  for (const [from, to] of [['/pj/zblanks/assets/models/adapter-3u-to-1u.step','/assets/models/adapter-3u-to-1u.step'], ['/pj/zblanks/files/models/plain-3u-8hp.stl/', '/files/models/plain-3u-8hp.stl/'], ['/pj/zblanks/docs/claude-md/', '/docs/claude-md/']]) {
    const response = await fetch(base + from + '?state=kept', { redirect: 'manual' });
    assert.equal(response.status, 301);
    const location = new URL(response.headers.get('location'), base);
    assert.equal(location.pathname, to);
    assert.equal(location.searchParams.get('state'), 'kept');
  }
  const history = path.join(dist, 'doc-history');
  const established = JSON.parse(await readFile(path.join(history, 'guides/assembly/stack.json')));
  assert(established.entries.length > 1, 'Moved assembly history must retain pre-migration revisions');
  async function historyFiles(dir) { let out = []; for (const entry of await readdir(dir, { withFileTypes: true })) { const name = path.join(dir, entry.name); if (entry.isDirectory()) out.push(...await historyFiles(name)); else if (entry.name.endsWith('.json')) out.push(name); } return out; }
  const jsons = await historyFiles(history);
  assert(jsons.length > 0, 'Generate history with GEN_DOC_HISTORY=1');
  console.log(`PASS raw assets, ${hidden.length} server exclusions, redirects, real 404s, ${jsons.length} history files and static file sizes`);
} catch (error) {
  console.error(log);
  throw error;
} finally {
  server.kill('SIGTERM');
  await new Promise(resolve => { if (server.exitCode !== null) resolve(); else server.once('exit', resolve); });
}
