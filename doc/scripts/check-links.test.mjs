import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { checkMdxLinks, checkHtmlLinksAndTrailing } from './check-links.js';

test('root-hosted source links resolve but nonexistent targets still fail', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'blanks-links-'));
  try {
    await mkdir(path.join(root, 'content/panels'), { recursive: true });
    await writeFile(path.join(root, 'content/panels/index.mdx'), '# Panels\n');
    await writeFile(path.join(root, 'content/index.mdx'), '[Known](/docs/panels/) [Missing](/docs/absent/)\n');
    const failures = await checkMdxLinks([path.join(root, 'content')], root, null, '/', []);
    assert.deepEqual(failures.map(x => x.href), ['/docs/absent/']);
    const prefixed = await checkMdxLinks([path.join(root, 'content')], root, null, '/prefix/', []);
    assert.equal(prefixed.length, 2);
  } finally { await rm(root, { recursive: true }); }
});

test('viewer state hashes do not suppress ordinary anchor failures', async () => {
  const root = await mkdtemp(path.join(tmpdir(), 'blanks-anchors-'));
  try {
    await mkdir(path.join(root, 'viewers/strip-mine'), { recursive: true });
    await writeFile(path.join(root, 'viewers/strip-mine/index.html'), '<h1>Strip Mine</h1>');
    await writeFile(path.join(root, 'index.html'), '<a href="/viewers/strip-mine/#pattern=5">Selected</a><a href="/viewers/strip-mine/#pattern=11">Invalid</a><a href="/viewers/strip-mine/#missing">Missing</a>');
    const { anchors } = await checkHtmlLinksAndTrailing(root, root, '/', [], false);
    assert.deepEqual(anchors.map(x => x.fragment), ['pattern=11', 'missing']);
  } finally { await rm(root, { recursive: true }); }
});
