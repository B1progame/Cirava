import test from 'node:test';
import assert from 'node:assert/strict';
import { createConnectivityMonitor } from '../src/connectivity-monitor.js';

function fakeClock() {
  let callback;
  let delay;
  return {
    setIntervalFn(fn, ms) { callback = fn; delay = ms; return 1; },
    clearIntervalFn() { callback = undefined; },
    tick() { callback?.(); },
    get delay() { return delay; },
  };
}

test('connectivity is checked immediately and then every ten seconds', async () => {
  const clock = fakeClock();
  let attempts = 0;
  const monitor = createConnectivityMonitor({
    probe: async () => { attempts += 1; },
    setIntervalFn: clock.setIntervalFn,
    clearIntervalFn: clock.clearIntervalFn,
  });

  monitor.start();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(attempts, 1);
  assert.equal(clock.delay, 10_000);
  clock.tick();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(attempts, 2);
  monitor.stop();
});

test('offline and recovered callbacks fire only when connectivity changes', async () => {
  const clock = fakeClock();
  let available = false;
  const events = [];
  const monitor = createConnectivityMonitor({
    probe: async () => { if (!available) throw new Error('Network unreachable'); },
    onOffline: (error) => events.push(`offline:${error.message}`),
    onOnline: () => events.push('online'),
    setIntervalFn: clock.setIntervalFn,
    clearIntervalFn: clock.clearIntervalFn,
  });

  monitor.start();
  await new Promise((resolve) => setImmediate(resolve));
  clock.tick();
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(events, ['offline:Network unreachable']);
  available = true;
  clock.tick();
  await new Promise((resolve) => setImmediate(resolve));
  assert.deepEqual(events, ['offline:Network unreachable', 'online']);
  assert.equal(monitor.isOnline, true);
  monitor.stop();
});

test('a timed manual check does not overlap an in-flight connectivity probe', async () => {
  const clock = fakeClock();
  const resolveProbes = [];
  const monitor = createConnectivityMonitor({
    probe: () => new Promise((resolve) => { resolveProbes.push(resolve); }),
    setIntervalFn: clock.setIntervalFn,
    clearIntervalFn: clock.clearIntervalFn,
  });

  monitor.start();
  clock.tick();
  assert.equal(resolveProbes.length, 1);
  resolveProbes[0]();
  await new Promise((resolve) => setImmediate(resolve));
  const manualCheck = monitor.checkNow();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(resolveProbes.length, 2);
  resolveProbes[1]();
  await manualCheck;
  monitor.stop();
});
