import test from 'node:test';
import assert from 'node:assert/strict';
import { restartCiravaForUpdate } from '../src/update-flow.js';

test('a verified in-place update automatically replaces the app and requests restart', async () => {
  const calls = [];
  const bridge = {
    restart_staged_update: async (...args) => calls.push(['apply', ...args]),
    request_quit: async () => calls.push(['quit']),
  };
  const result = await restartCiravaForUpdate(bridge, { path: 'C:/AppData/Cirava/updates/app.exe' }, 'in_place');
  assert.deepEqual(calls, [['apply', 'C:/AppData/Cirava/updates/app.exe', 'in_place'], ['quit']]);
  assert.equal(result.restarted, true);
});

test('a verified major installer is launched and Cirava exits for the install/relaunch', async () => {
  const calls = [];
  const bridge = {
    restart_staged_update: async (...args) => calls.push(['installer', ...args]),
    request_quit: async () => calls.push(['quit']),
  };
  await restartCiravaForUpdate(bridge, { path: 'C:/AppData/Cirava/updates/setup.exe' }, 'installer');
  assert.deepEqual(calls, [['installer', 'C:/AppData/Cirava/updates/setup.exe', 'installer'], ['quit']]);
});

test('missing restart bridge methods fail clearly instead of leaving a misleading ready state', async () => {
  await assert.rejects(restartCiravaForUpdate({}, { path: 'update.exe' }, 'in_place'), /cannot restart itself/);
});
