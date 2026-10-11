/**
 * Restore path continuity after the documented URL migration. zudo-doc remains
 * responsible for generating history and rendering History/Compare. Git's rename
 * heuristic can miss heavily edited moves or follow a duplicate import overlay;
 * the explicit migration map supplies the canonical prior documentation paths.
 * Run --metadata before check/dev/build for the native chrome metadata binding.
 * Run without --metadata after the history-enabled package build for revision
 * JSON continuity. --check verifies either artifact without writing.
 */
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { isDeepStrictEqual } from 'node:util';
import { collectContentFiles, getDocHistoryAsync } from '@takazudo/zudo-doc-history-server/git-history';

const site = fileURLToPath(new URL('../', import.meta.url));
const contentRoot = path.join(site, 'src/content/docs');
const metadataTarget = path.join(site, '.zfb/migrated-doc-history-meta.json');

/** Keep the current page's content when both paths changed in the same commit. */
export function mergeHistoryEntries(current, previous) {
  const entries = new Map();
  for (const entry of [...current, ...previous]) {
    assert.match(entry.hash, /^[a-f0-9]{40}$/, 'Invalid history commit');
    assert(Number.isFinite(Date.parse(entry.date)), `Invalid history date: ${entry.hash}`);
    assert.equal(typeof entry.content, 'string', `Missing history content: ${entry.hash}`);
    assert.equal(typeof entry.author, 'string', `Missing history author: ${entry.hash}`);
    // The package API includes deletion commits with empty content for old paths.
    if (entry.content.trim() && !entries.has(entry.hash)) entries.set(entry.hash, entry);
  }
  return [...entries.values()].sort((a, b) => Date.parse(b.date) - Date.parse(a.date) || a.hash.localeCompare(b.hash));
}

/** The native binding consumes the same metadata schema as the package manifest. */
export function deriveHistoryMetadata(current, previous, currentFile) {
  const entries = mergeHistoryEntries(current, previous);
  assert(entries.length > 0, `No committed metadata history: ${currentFile}`);
  const ext = path.extname(currentFile);
  assert(ext === '.md' || ext === '.mdx', `Unexpected current extension: ${currentFile}`);
  const oldest = entries.at(-1);
  return { author: oldest.author, createdDate: oldest.date, updatedDate: entries[0].date, ext };
}

async function main() {
  assert(process.argv.slice(2).every(arg => ['--check', '--metadata'].includes(arg)),
    'Usage: node scripts/reconcile-history.mjs [--metadata] [--check]');
  const check = process.argv.includes('--check');
  const metadataOnly = process.argv.includes('--metadata');
  const migration = JSON.parse(await readFile(path.join(site, 'data/route-migration.json'), 'utf8'));
  const currentFiles = new Map(collectContentFiles(contentRoot).map(file => [file.slug, file.filePath]));
  const aliases = new Map();
  for (const route of migration.routes) {
    if (route.from === route.to) continue;
    assert.match(route.to, /^\/docs\/.+\/$/, `Unexpected destination: ${route.to}`);
    const slug = route.to.slice('/docs/'.length, -1);
    assert(currentFiles.has(slug), `Missing current document: ${slug}`);
    const oldPath = path.resolve(contentRoot, route.source);
    assert(oldPath.startsWith(contentRoot + path.sep), `Source outside docs: ${route.source}`);
    if (!aliases.has(slug)) aliases.set(slug, []);
    aliases.get(slug).push(oldPath);
  }

  let retained = 0;
  const metadata = {};
  for (const [slug, oldPaths] of aliases) {
    const previous = [];
    // Metadata needs the actual first author/date even after more than the UI's
    // default 50 revisions. This is Git's maximum signed count, not a shallow log.
    const maxEntries = metadataOnly ? 2_147_483_647 : 50;
    for (const oldPath of oldPaths) {
      const history = await getDocHistoryAsync(oldPath, slug, maxEntries);
      const available = history.entries.filter(entry => entry.content.trim());
      assert(available.length > 0, `No original history for ${oldPath}; fetch full Git history`);
      previous.push(...available);
    }
    retained += previous.length;
    if (metadataOnly) {
      const currentFile = currentFiles.get(slug);
      const current = await getDocHistoryAsync(currentFile, slug, maxEntries);
      assert(current.entries.some(entry => entry.content.trim()), `No committed current history: ${slug}`);
      metadata[slug] = deriveHistoryMetadata(current.entries, previous, currentFile);
      continue;
    }
    const target = path.join(site, 'dist/doc-history', slug + '.json');
    const generated = JSON.parse(await readFile(target, 'utf8'));
    assert.equal(generated.slug, slug, `Generated slug mismatch: ${target}`);
    assert(Array.isArray(generated.entries) && generated.entries.some(entry => entry.content.trim()),
      `Missing committed current-page history for ${slug}; build with GEN_DOC_HISTORY=1 first`);
    const entries = mergeHistoryEntries(generated.entries, previous);
    const expected = { ...generated, entries };
    if (check) {
      assert(isDeepStrictEqual(generated.entries, entries), `Missing migrated history for ${slug}; run node scripts/reconcile-history.mjs`);
    } else {
      await writeFile(target, JSON.stringify(expected) + '\n');
    }
    // Validate the emitted artifact, including canonical old-path hashes. Merely
    // counting history JSON files cannot detect lost history across these moves.
    const actual = JSON.parse(await readFile(target, 'utf8'));
    assert(isDeepStrictEqual(actual, expected), `History output mismatch: ${slug}`);
    const hashes = new Set(actual.entries.map(entry => entry.hash));
    assert.equal(hashes.size, actual.entries.length, `Duplicate history commits: ${slug}`);
    for (const entry of previous) assert(hashes.has(entry.hash), `Lost old-path revision ${slug}: ${entry.hash}`);
    for (const entry of generated.entries.filter(entry => entry.content.trim())) {
      assert(isDeepStrictEqual(actual.entries.find(item => item.hash === entry.hash), entry), `Current content overwritten: ${slug}`);
    }
    console.log(`${check ? 'Verified' : 'Reconciled'} history ${slug}: ${actual.entries.length} revisions`);
  }
  if (metadataOnly) {
    if (check) {
      const actual = JSON.parse(await readFile(metadataTarget, 'utf8'));
      assert(isDeepStrictEqual(actual, metadata), 'Migrated history metadata drift; run node scripts/reconcile-history.mjs --metadata');
    } else {
      await mkdir(path.dirname(metadataTarget), { recursive: true });
      await writeFile(metadataTarget, JSON.stringify(metadata, null, 2) + '\n');
    }
    console.log(`${check ? 'Verified' : 'Prepared'} native chrome metadata for ${aliases.size} migrated destinations`);
  }
  console.log(`Migration history passed: ${aliases.size} destinations, ${retained} prior-path revisions represented`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
