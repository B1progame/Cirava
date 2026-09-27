import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { renderFullscreenTransferCenter } from '../src/fullscreen-transfer.js';

const main = readFileSync(new URL('../src/main.tsx', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/ui-fixes.css', import.meta.url), 'utf8');

test('fullscreen transfer view reuses the normal route art and live transfer summary', () => {
  const html = renderFullscreenTransferCenter();
  assert.match(html, /class="fullscreen-transfer-center"/);
  assert.match(html, /class="transfer-overview-strip"/);
  assert.match(html, /class="transfer-journey"/);
  assert.match(html, /class="transfer-live-summary"/);
  assert.match(html, /Secure cloud route/);
  assert.match(html, /data-fullscreen-new-transfer/);
});

test('fullscreen transfer enhancement binds real transfer actions and is installed by the observer', () => {
  const start = main.indexOf('function ciravaFullscreenTransferCenter()');
  const end = main.indexOf('ciravaSchedule(ciravaFullscreenTransferCenter)', start);
  const enhancer = main.slice(start, end);
  assert.match(enhancer, /cirava-transfer-fullscreen-layer/);
  assert.match(enhancer, /bindTransferJourney\(/);
  assert.match(enhancer, /uploadCount\.textContent\s*!==\s*sourceCounts\[0\]\.textContent/);
  assert.match(enhancer, /downloadCount\.textContent\s*!==\s*sourceCounts\[1\]\.textContent/);
  assert.match(main, /ciravaFullscreenTransferCenter\(\);/);
  assert.doesNotMatch(enhancer, /inner\.innerHTML\s*=\s*renderFullscreenTransferCenter/);
});

test('fullscreen transfer mode expands into a scrollable full-window layout', () => {
  assert.match(styles, /\.cirava-transfer-fullscreen-layer\s*\{/);
  assert.match(styles, /\.cirava-transfer-fullscreen-layer\s*\{[^}]*place-items:\s*center/s);
  assert.match(styles, /\.fullscreen-transfer-center\s*\{[^}]*align-content:\s*start/s);
  assert.match(styles, /\.fullscreen-transfer-heading/);
});
