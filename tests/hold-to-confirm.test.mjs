import test from 'node:test';
import assert from 'node:assert/strict';

const { createHoldProgress } = await import('../src/hold-to-confirm.js').catch(() => ({}));

test('a short press never starts an upload, but a completed hold starts it exactly once', () => {
  assert.equal(typeof createHoldProgress, 'function');
  let starts = 0;
  const progress = [];
  const hold = createHoldProgress({ durationMs: 900, onProgress: (value) => progress.push(value), onConfirm: () => starts++ });

  hold.begin(100);
  assert.ok(hold.tick(999) < 1);
  assert.equal(starts, 0);
  assert.equal(hold.tick(1000), 1);
  assert.equal(hold.tick(1200), 1);

  assert.equal(starts, 1);
  assert.equal(progress.at(-1), 1);
});

test('releasing early resets the hold so the user must press again', () => {
  let starts = 0;
  const progress = [];
  const hold = createHoldProgress({ durationMs: 800, onProgress: (value) => progress.push(value), onConfirm: () => starts++ });

  hold.begin(0);
  hold.tick(400);
  hold.cancel();
  assert.equal(progress.at(-1), 0);
  assert.equal(starts, 0);
  hold.begin(1000);
  hold.tick(1800);
  assert.equal(starts, 1);
});
