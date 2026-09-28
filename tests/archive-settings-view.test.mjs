import test from 'node:test';
import assert from 'node:assert/strict';
import { renderArchiveCompressionSetting } from '../src/archive-settings-view.js';

test('7-Zip setting explains its private install location and has a clear accessible enable control', () => {
  const markup = renderArchiveCompressionSetting();
  assert.match(markup, /7-Zip archive compression/);
  assert.match(markup, /own app folder/);
  assert.match(markup, /type="checkbox"[^>]*data-cirava-archive-enabled/);
  assert.match(markup, /aria-label="Enable 7-Zip archive tools"/);
  assert.match(markup, /data-cirava-archive-status/);
});

test('7-Zip setting gives an official recovery path for a failed installer signature check', () => {
  const markup = renderArchiveCompressionSetting();
  assert.match(markup, /7-zip\.org\/download\.html/);
  assert.match(markup, /Open 7-Zip's official download page/);
});
