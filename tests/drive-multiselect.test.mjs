import test from 'node:test';
import assert from 'node:assert/strict';

const { createDriveSelection } = await import('../src/drive-multiselect.js').catch(() => ({}));

test('plain selection replaces the prior item while additive selection toggles items', () => {
  assert.equal(typeof createDriveSelection, 'function');
  const selection = createDriveSelection();
  selection.toggle('a', ['a', 'b', 'c']);
  selection.toggle('b', ['a', 'b', 'c'], { additive: true });
  assert.deepEqual(selection.getSelected(), ['a', 'b']);
  selection.toggle('c', ['a', 'b', 'c']);
  assert.deepEqual(selection.getSelected(), ['c']);
});

test('shift selection selects a visible range from the last anchor', () => {
  const selection = createDriveSelection();
  selection.toggle('a', ['a', 'b', 'c', 'd']);
  selection.toggle('d', ['a', 'b', 'c', 'd'], { range: true });
  assert.deepEqual(selection.getSelected(), ['a', 'b', 'c', 'd']);
  selection.toggle('c', ['a', 'b', 'c', 'd'], { range: true });
  assert.deepEqual(selection.getSelected(), ['a', 'b', 'c']);
});

test('select all, clear, and pruning keep selection synchronized with visible rows', () => {
  const selection = createDriveSelection();
  selection.selectAll(['a', 'b']);
  assert.deepEqual(selection.getSelected(), ['a', 'b']);
  selection.prune(['b', 'c']);
  assert.deepEqual(selection.getSelected(), ['b']);
  selection.clear();
  assert.deepEqual(selection.getSelected(), []);
});

test('selection mode starts off and leaving it clears hidden selections', () => {
  const selection = createDriveSelection();
  assert.equal(selection.isModeEnabled(), false);
  selection.setMode(true);
  selection.toggle('one', ['one', 'two']);
  assert.equal(selection.isModeEnabled(), true);
  assert.deepEqual(selection.getSelected(), ['one']);
  selection.setMode(false);
  assert.equal(selection.isModeEnabled(), false);
  assert.deepEqual(selection.getSelected(), []);
});
