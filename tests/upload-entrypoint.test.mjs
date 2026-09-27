import test from 'node:test';
import assert from 'node:assert/strict';
import { isDriveUploadEntrypoint } from '../src/upload-entrypoint.js';

test('Drive page Upload action is handled by the real upload planner', () => {
  const uploadButton = {
    textContent: ' Upload ',
    matches: (selector) => selector.includes('.page-heading .page-actions button'),
  };
  assert.equal(isDriveUploadEntrypoint(uploadButton), true);
});

test('Drive header tools other than Upload are not intercepted', () => {
  const refreshButton = {
    textContent: 'Refresh',
    matches: (selector) => selector.includes('.page-heading .page-actions button'),
  };
  assert.equal(isDriveUploadEntrypoint(refreshButton), false);
});

test('empty-folder Upload files action opens the same upload planner', () => {
  const emptyFolderUploadButton = {
    textContent: ' Upload files ',
    matches: (selector) => selector.includes('.drive-empty button'),
  };
  assert.equal(isDriveUploadEntrypoint(emptyFolderUploadButton), true);
});
