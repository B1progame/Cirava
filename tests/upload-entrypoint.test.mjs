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
