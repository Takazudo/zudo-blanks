import assert from 'node:assert/strict';
import { test } from 'node:test';
import { classifyPrintableSources, repositoryPrintableFailures } from './check-printable-accessories.mjs';
import { models, printableAccessories } from './stage_viewers.mjs';

const mapped = ['_3dp/blank-module-spacer-m3.3mf'];

test('an unclassified _3dp project fails with its source path', () => {
  const failures = classifyPrintableSources(
    [...mapped, '_3dp/unclassified-spacer.3mf', '_3dp/notes.md'],
    models,
    printableAccessories,
  );
  assert.deepEqual(failures, [
    '_3dp/unclassified-spacer.3mf: supported printable source has no download mapping or reasoned exclusion',
  ]);
});

test('a reasoned exclusion is accepted and an empty reason fails', () => {
  const accepted = classifyPrintableSources(
    ['_3dp/held.stl'],
    {},
    { ...printableAccessories, exclusions: { '_3dp/held.stl': 'Reference mesh kept beside the project; no public copy.' } },
  );
  assert.deepEqual(accepted, []);
  const empty = classifyPrintableSources(
    ['_3dp/held.stl'],
    {},
    { ...printableAccessories, exclusions: { '_3dp/held.stl': '   ' } },
  );
  assert.ok(empty.some(line => line.startsWith('_3dp/held.stl:')));
});

test('supported extensions include 3MF projects and ordinary model files', () => {
  assert.deepEqual(printableAccessories.supportedExtensions, ['.3mf', '.stl', '.step', '.stp', '.fcstd']);
  const failures = classifyPrintableSources(
    ['_3dp/a.3mf', '_3dp/b.stl', '_3dp/c.step', '_3dp/d.stp', '_3dp/e.fcstd'],
    {},
    printableAccessories,
  );
  assert.deepEqual(failures.map(line => line.split(':')[0]), [
    '_3dp/a.3mf', '_3dp/b.stl', '_3dp/c.step', '_3dp/d.stp', '_3dp/e.fcstd',
  ]);
});

test('the committed _3dp accessory is mapped, documented, and byte-identical', async () => {
  assert.equal(models['blank-module-spacer-m3.3mf'], '_3dp/blank-module-spacer-m3.3mf');
  assert.deepEqual(await repositoryPrintableFailures(), []);
});
