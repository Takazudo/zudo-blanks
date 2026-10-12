/** Coverage for printable accessory sources under `_3dp/`. Separate from the panel inventory. */
import { createHash } from 'node:crypto';
import { readdir, readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { models, printableAccessories } from './stage_viewers.mjs';

const repoRoot = fileURLToPath(new URL('../../', import.meta.url));

function normalize(file) {
  return file.split(path.sep).join('/');
}

export function classifyPrintableSources(files, modelMap = models, policy = printableAccessories) {
  const prefix = `${policy.directory.replace(/\/$/, '')}/`;
  const extensions = new Set(policy.supportedExtensions.map(ext => ext.toLowerCase()));
  const listed = new Set(files.map(normalize));
  const published = new Map();
  const failures = [];
  for (const [name, source] of Object.entries(modelMap)) {
    const normalized = normalize(source);
    if (!normalized.startsWith(prefix)) continue;
    published.set(normalized, name);
  }
  for (const file of [...listed].sort()) {
    if (!file.startsWith(prefix)) continue;
    const ext = path.posix.extname(file).toLowerCase();
    if (!extensions.has(ext)) continue;
    const reason = policy.exclusions[file];
    if (published.has(file)) {
      if (reason !== undefined) failures.push(`${file}: published download and exclusion both set`);
      continue;
    }
    if (typeof reason === 'string' && reason.trim()) continue;
    failures.push(`${file}: supported printable source has no download mapping or reasoned exclusion`);
  }
  for (const [source, name] of published) {
    if (!listed.has(source)) failures.push(`${source}: download ${name} has no source file`);
  }
  for (const [source, reason] of Object.entries(policy.exclusions)) {
    const normalized = normalize(source);
    if (typeof reason !== 'string' || !reason.trim()) failures.push(`${normalized}: exclusion needs a reason`);
    const ext = path.posix.extname(normalized).toLowerCase();
    if (!normalized.startsWith(prefix) || !extensions.has(ext)) {
      failures.push(`${normalized}: exclusion is outside supported ${policy.directory} printable sources`);
    }
  }
  return failures;
}

async function walk(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) files.push(...await walk(full));
    else if (entry.isFile()) files.push(full);
  }
  return files;
}

export async function repositoryPrintableFailures(root = repoRoot) {
  const directory = path.join(root, printableAccessories.directory);
  const files = (await walk(directory)).map(file => path.relative(root, file));
  const failures = classifyPrintableSources(files, models, printableAccessories);
  const modelsPage = await readFile(path.join(root, 'doc/src/content/docs/models/index.mdx'), 'utf8');
  const stackPage = await readFile(path.join(root, 'doc/src/content/docs/guides/assembly/stack.mdx'), 'utf8');
  const manifest = JSON.parse(await readFile(path.join(root, 'doc/public/viewers/manifest.json'), 'utf8'));
  if (!modelsPage.includes('id="m3-spacer"')) failures.push('doc/src/content/docs/models/index.mdx: missing stable #m3-spacer anchor');
  if (!stackPage.includes('/docs/models/#m3-spacer')) failures.push('doc/src/content/docs/guides/assembly/stack.mdx: missing M3 spacer link');
  for (const [name, source] of Object.entries(models)) {
    if (!normalize(source).startsWith(`${printableAccessories.directory}/`)) continue;
    const publicPath = `assets/models/${name}`;
    const href = `/${publicPath}`;
    if (!modelsPage.includes(href)) failures.push(`doc/src/content/docs/models/index.mdx: missing download ${href}`);
    if (!modelsPage.includes(normalize(source))) failures.push(`doc/src/content/docs/models/index.mdx: missing repository source ${normalize(source)}`);
    const sourceBytes = await readFile(path.join(root, source));
    const stagedBytes = await readFile(path.join(root, 'doc/public', publicPath)).catch(() => Buffer.alloc(0));
    if (!stagedBytes.equals(sourceBytes)) failures.push(`${publicPath}: staged bytes differ from ${normalize(source)}`);
    const recorded = manifest.files?.[publicPath];
    const sha256 = createHash('sha256').update(sourceBytes).digest('hex');
    if (!recorded || recorded.bytes !== sourceBytes.length || recorded.sha256 !== sha256) {
      failures.push(`${publicPath}: output manifest does not record the repository original`);
    }
  }
  for (const fact of ['7 mm outside diameter', '3.3 mm inside diameter', '3 mm high', '476 copies', 'Textured PEI Plate', 'Bambu Lab P1S']) {
    if (!modelsPage.includes(fact)) failures.push(`doc/src/content/docs/models/index.mdx: missing accessory fact "${fact}"`);
  }
  return failures;
}

const invokedDirectly = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (invokedDirectly) {
  const failures = await repositoryPrintableFailures();
  if (failures.length > 0) {
    for (const failure of failures) console.error(failure);
    process.exit(1);
  }
  console.log(`Verified ${printableAccessories.directory}/ printable sources, staged bytes, and M3 spacer documentation`);
}
