/** Deterministic browser-only bundles. Never regenerates native/frozen geometry. */
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../../', import.meta.url));
const preview = path.join(root, 'artwork-resources/pcb-art/preview-source');
const require = createRequire(path.join(preview, 'package.json'));
const { build } = require('esbuild');
const check = process.argv.includes('--check');
const outputs = new Map();
const read = name => readFile(path.join(root, name));
const sha = value => createHash('sha256').update(value).digest('hex');
const back = '<a href="/docs/models/" style="display:inline-block;padding:10px 14px;color:#f0dca3;background:#17191d;border-radius:5px">← 3D &amp; files documentation</a>';

execFileSync(process.execPath, [path.join(preview, 'scripts/build.mjs')], { stdio: 'inherit' });
const pcb = (await readFile(path.join(preview, 'dist/index.html'), 'utf8'))
  .replace('<nav class="design-nav"', `${back}<nav class="design-nav"`)
  .replace(/[ \t]+(?=\r?$)/gm, '');
outputs.set('viewers/pcb-art/index.html', Buffer.from(pcb));
outputs.set('viewers/pcb-art/THIRD_PARTY_NOTICES.txt', await read('artwork-resources/pcb-art/preview-source/THIRD_PARTY_NOTICES.txt'));

let strip = (await read('panels/art-strip-mine/preview/index.html')).toString();
const module = strip.match(/<script type="module">([\s\S]*?)<\/script>/)?.[1];
if (!module) throw new Error('Strip Mine module not found');
const bundled = await build({ stdin: { contents: module, resolveDir: preview, sourcefile: 'strip-mine-viewer.js' }, bundle: true, write: false, minify: true, format: 'iife', target: 'es2020', legalComments: 'eof' });
strip = strip.replace(/<script type="importmap">[\s\S]*?<\/script>\s*/, '')
  .replace(/<script type="module">[\s\S]*?<\/script>/, () => '<script src="viewer.js"></script>')
  .replace('<aside>', `<aside>${back}`);
outputs.set('viewers/strip-mine/index.html', Buffer.from(strip));
outputs.set('viewers/strip-mine/viewer.js', Buffer.from(bundled.outputFiles[0].text));
outputs.set('viewers/strip-mine/geometry.js', await read('panels/art-strip-mine/preview/geometry.js'));
outputs.set('viewers/strip-mine/THREE-LICENSE.txt', await readFile(path.join(preview, 'node_modules/three/LICENSE')));
const models = {
  'adapter-3u-to-1u.step': 'panels/alumi-3u-to-1u-v1/3u-to-1u-v1.step',
  'plain-3u-8hp.stl': 'panels/alumi-blanks-v1-3U-8hp/3d/panel.stl',
  'plain-3u-8hp.FCStd': 'panels/alumi-blanks-v1-3U-8hp/3d/panel.FCStd',
};
for (const [name, source] of Object.entries(models)) outputs.set(`assets/models/${name}`, await read(source));
const manifest = { sources: {
  'pcb-art/geometry.json': sha(await read('artwork-resources/pcb-art/preview-source/assets/geometry.json')),
  'strip-mine/geometry.js': sha(await read('panels/art-strip-mine/preview/geometry.js')),
}, files: Object.fromEntries([...outputs].map(([name, bytes]) => [name, { bytes: bytes.length, sha256: sha(bytes) }])) };
outputs.set('viewers/manifest.json', Buffer.from(JSON.stringify(manifest, null, 2) + '\n'));
for (const [name, bytes] of outputs) {
  if (bytes.length > 25 * 1024 * 1024) throw new Error(`Cloudflare asset limit exceeded: ${name}`);
  const target = path.join(root, 'doc/public', name);
  if (check) {
    const existing = await readFile(target).catch(() => Buffer.alloc(0));
    if (!existing.equals(bytes)) throw new Error(`Generated output drift: ${name}. Run pnpm prepare:viewers.`);
  } else {
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, bytes);
  }
  console.log(`${check ? 'Verified' : 'Staged'} ${name}: ${bytes.length} bytes`);
}
