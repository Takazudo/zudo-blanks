import assert from 'node:assert/strict';
import test from 'node:test';
import { deriveHistoryMetadata, mergeHistoryEntries } from './reconcile-history.mjs';

const revision = (digit, date, content, author = 'Author') => ({
  hash: digit.repeat(40), date, content, author, message: 'Document change',
});
const current = revision('a', '2026-10-11T00:00:00Z', 'Moved current document', 'Current author');
const previous = revision('b', '2025-09-01T00:00:00Z', 'Original document', 'Original author');

test('migration keeps current content when both paths changed in one commit', () => {
  const oldAtMove = { ...current, content: 'Old path content' };
  assert.deepEqual(mergeHistoryEntries([current], [oldAtMove, previous]), [current, previous]);
});

test('deleted old path cannot become a blank newest revision', () => {
  const deletion = revision('c', '2026-10-12T00:00:00Z', '');
  const whitespace = revision('d', '2026-10-13T00:00:00Z', ' \n');
  assert.deepEqual(mergeHistoryEntries([current], [deletion, whitespace, previous]), [current, previous]);
});

test('overlapping rename-follow history is deduplicated and reconciliation is idempotent', () => {
  const merged = mergeHistoryEntries([current, previous], [previous]);
  assert.deepEqual(merged, [current, previous]);
  assert.deepEqual(mergeHistoryEntries(merged, [previous]), merged);
});

test('metadata retains original author and creation date with current update and extension', () => {
  const oldAtMove = { ...current, content: '' };
  assert.deepEqual(deriveHistoryMetadata([current], [oldAtMove, previous], '/docs/new.mdx'), {
    author: 'Original author', createdDate: previous.date, updatedDate: current.date, ext: '.mdx',
  });
  assert.equal(deriveHistoryMetadata([current], [previous], '/docs/new.md').ext, '.md');
});

test('dates compare as timestamps across timezone offsets', () => {
  const older = revision('c', '2026-10-11T01:00:00+09:00', 'Older by eight hours');
  assert.deepEqual(mergeHistoryEntries([older], [current]), [current, older]);
});

test('missing or malformed provenance fails instead of inventing metadata', () => {
  assert.throws(() => deriveHistoryMetadata([], [], '/docs/new.mdx'), /No committed/);
  assert.throws(() => mergeHistoryEntries([{ ...current, date: 'not a date' }], []), /Invalid history date/);
  assert.throws(() => mergeHistoryEntries([{ ...current, hash: '../bad' }], []), /Invalid history commit/);
  assert.throws(() => deriveHistoryMetadata([current], [], '/docs/new.html'), /Unexpected current extension/);
});
