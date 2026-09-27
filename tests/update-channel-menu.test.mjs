import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createUpdateChannelMenuState } from '../src/update-channel-menu.js';

const source = readFileSync(new URL('../src/main.tsx', import.meta.url), 'utf8');
const updateStart = source.indexOf('function ciravaUpdateScreen');
const updateEnd = source.indexOf('requestAnimationFrame(ciravaUpdateScreen)', updateStart);
const updateScreen = source.slice(updateStart, updateEnd);

test('the release channel menu starts closed and opens only on request', () => {
  const menu = createUpdateChannelMenuState('release');
  assert.equal(menu.open, false);
  assert.equal(menu.toggle(), true);
  assert.equal(menu.open, true);
});

test('choosing a release channel stores it and dismisses the menu', () => {
  const menu = createUpdateChannelMenuState('release');
  menu.show();
  assert.equal(menu.select('beta'), 'beta');
  assert.equal(menu.open, false);
  assert.equal(menu.selected, 'beta');
});

test('the update screen renders a button-controlled hidden channel menu', () => {
  assert.match(updateScreen, /cirava-update-channel-trigger/);
  assert.match(updateScreen, /cirava-update-channel-menu/);
  assert.match(updateScreen, /channelMenu\.hidden\s*=\s*!channelMenuState\.open/);
});

test('invalid channel values cannot replace the current update feed', () => {
  const menu = createUpdateChannelMenuState('release');
  menu.show();
  assert.equal(menu.select('nightly'), 'release');
  assert.equal(menu.selected, 'release');
});

test('Escape closes the channel menu first and the update dialog only on a second press', () => {
  const menu = createUpdateChannelMenuState('release');
  menu.show();
  assert.equal(menu.escape(), false);
  assert.equal(menu.open, false);
  assert.equal(menu.escape(), true);
});
