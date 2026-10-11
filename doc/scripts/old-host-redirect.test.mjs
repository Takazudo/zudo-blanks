import assert from 'node:assert/strict';
import { test } from 'node:test';
import { redirectOldDocs } from './old-host-redirect.mjs';

test('old-host migration preserves route and selection without claiming unrelated traffic', () => {
  const response = redirectOldDocs(new Request('https://takazudomodular.com/pj/zblanks/assets/pcb-art/previews/index.html?design=kumiko-void'));
  assert.equal(response.status, 301);
  assert.equal(response.headers.get('location'), 'https://zudo-blanks.zudolab.dev/pj/zblanks/assets/pcb-art/previews/index.html?design=kumiko-void');
  for (const url of ['https://takazudomodular.com/pj/zblanks-other/', 'https://example.com/pj/zblanks/', 'https://takazudomodular.com/']) assert.equal(redirectOldDocs(new Request(url)), null);
});
