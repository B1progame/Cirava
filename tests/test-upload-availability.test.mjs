import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { isTestDataEnabled } from '../src/test-data-setting.js';

const source = readFileSync(new URL('../src/main.tsx', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/upload-planner.css', import.meta.url), 'utf8');

test('Cobalt option is enabled only by the saved Test data setting', () => {
  assert.equal(isTestDataEnabled({ getItem: () => 'true' }), true);
  assert.equal(isTestDataEnabled({ getItem: () => 'false' }), false);
  assert.equal(isTestDataEnabled({ getItem: () => null }), false);
  assert.equal(isTestDataEnabled(undefined), false);
});

test('both upload planners show the Cobalt choice only when Test data is enabled', () => {
  assert.match(source, /testButton\.hidden\s*=\s*!testDataEnabled/);
  assert.match(source, /testChoice\.hidden\s*=\s*!testDataEnabled/);
  assert.match(source, /cobaltCard\.hidden\s*=\s*!testDataEnabled/);
  assert.match(source, /if \(!testDataEnabled && state\.testUpload\)/);
  assert.match(source, /Enable Test data in Settings to show the Cobalt test-file option/);
  assert.match(styles, /\.cirava-upload-test-choice\[hidden\].*display:\s*none\s*!important/);
});
