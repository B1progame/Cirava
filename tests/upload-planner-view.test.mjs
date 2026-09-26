import test from 'node:test';
import assert from 'node:assert/strict';
import { getUploadSelectionView } from '../src/upload-planner-view.js';

test('empty upload selection gives a real next-step prompt', () => {
  assert.deepEqual(getUploadSelectionView([], undefined, false), {
    kind: 'empty',
    title: 'Choose files or a folder',
    detail: 'Nothing starts until you hold Start upload.',
    fileNames: [],
    fileCount: 0,
    totalSize: 'No files selected',
  });
});

test('selected files show their names, count, and total size instead of only a generic count', () => {
  assert.deepEqual(getUploadSelectionView(
    ['C:/work/one.zip', 'C:/work/two.mov'],
    { files: 2, folders: 0, bytes: 5 * 1024 ** 3 },
    false,
  ), {
    kind: 'files',
    title: '2 files selected',
    detail: '5.0 GB total',
    fileNames: ['one.zip', 'two.mov'],
    fileCount: 2,
    totalSize: '5.0 GB',
  });
});

test('Cobalt test selection is identified as a sparse test upload', () => {
  assert.equal(getUploadSelectionView([], undefined, true).kind, 'test');
  assert.equal(getUploadSelectionView([], undefined, true).title, 'Cobalt launch kit');
  assert.equal(getUploadSelectionView([], undefined, true).detail, '20 GB upload · uses your Drive storage quota');
});
