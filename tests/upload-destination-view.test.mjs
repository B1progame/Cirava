import test from 'node:test';
import assert from 'node:assert/strict';
import { renderUploadDestinationPanel } from '../src/upload-destination-view.js';

test('destination panel gives the folder picker the space previously used by route reassurance', () => {
  const markup = renderUploadDestinationPanel();
  assert.match(markup, /data-cirava-upload-destination/);
  assert.match(markup, /data-cirava-upload-folders/);
  assert.doesNotMatch(markup, /cirava-upload-route|Resumable transfer|If your connection drops/);
});
