import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { scheduleTransientUploadNoticeDismissal } from '../src/transient-upload-notice.js';

test('the clarified disabled-test-upload toast is scheduled to dismiss', async () => {
  const source = await readFile(new URL('../src/main.tsx', import.meta.url), 'utf8');
  const helper = source.match(/function ciravaClarifyTestModeError\(\) \{([\s\S]*?)\n\}/)?.[1] || '';
  assert.match(helper, /scheduleTransientUploadNoticeDismissal\(toast,/);
  assert.doesNotMatch(helper, /toast\.textContent\s*=/);
});

test('the disabled-test notice disappears after its timeout if it is unchanged', () => {
  let dismiss;
  let delay;
  const notice = { textContent: 'Test upload is disabled', isConnected: true, remove() { this.isConnected = false; } };
  assert.equal(scheduleTransientUploadNoticeDismissal(notice, (callback, ms) => { dismiss = callback; delay = ms; }), true);
  assert.equal(delay, 8_000);
  assert.equal(notice.isConnected, true);
  dismiss();
  assert.equal(notice.isConnected, false);
});

test('a replaced or dismissed notice is not removed by an old timeout', () => {
  const callbacks = [];
  const notice = { textContent: 'Old warning', isConnected: true, remove() { this.isConnected = false; } };
  scheduleTransientUploadNoticeDismissal(notice, (callback) => callbacks.push(callback));
  notice.textContent = 'A newer message';
  scheduleTransientUploadNoticeDismissal(notice, (callback) => callbacks.push(callback));
  callbacks[0]();
  assert.equal(notice.isConnected, true);
  callbacks[1]();
  assert.equal(notice.isConnected, false);
});

test('repeated observer passes do not stack duplicate dismissal timers', () => {
  let scheduled = 0;
  const notice = { textContent: 'Same warning', isConnected: true, remove() { this.isConnected = false; } };
  assert.equal(scheduleTransientUploadNoticeDismissal(notice, () => { scheduled += 1; }), true);
  assert.equal(scheduleTransientUploadNoticeDismissal(notice, () => { scheduled += 1; }), false);
  assert.equal(scheduled, 1);
});
