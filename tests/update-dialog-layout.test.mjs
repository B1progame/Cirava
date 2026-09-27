import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../src/main.tsx', import.meta.url), 'utf8');
const updateStart = source.indexOf('function ciravaUpdateScreen');
const updateEnd = source.indexOf('requestAnimationFrame(ciravaUpdateScreen)', updateStart);
const main = source.slice(updateStart, updateEnd);
const styles = readFileSync(new URL('../src/ui-fixes.css', import.meta.url), 'utf8');

test('release channel control sits below the update copy, not in the brand row', () => {
  assert.match(main, /channelField\.append\(channelLabel, channelControl\)/);
  assert.match(main, /identity\.append\(mark, kicker, version\)/);
  assert.match(main, /dialog\.append\(close, identity, title, copy, channelField, progress/);
  assert.doesNotMatch(main, /channelField\.hidden\s*=/);
});

test('changing channels keeps the chosen channel when the dialog reopens to check it', () => {
  assert.match(main, /createUpdateChannelMenuState\(initialChannel\)/);
  assert.match(main, /channelTrigger\.textContent\s*=\s*channelMenuState\.selected\s*===\s*'beta'/);
  assert.match(main, /selectedChannel\s*=\s*chosen/);
});

test('an unavailable selected feed is not silently replaced by the other channel', () => {
  assert.match(main, /getUpdateFeed\(selectedChannel,\s*manifestUrls\)/);
  assert.doesNotMatch(main, /manifestUrls\[selectedChannel[^\n]+\|\|\s*manifestUrls\.release/);
});

test('release channel has a labeled, responsive control with dark-theme styling', () => {
  assert.match(styles, /\.cirava-update-channel-field\s*\{[^}]*display:\s*flex/s);
  assert.match(styles, /\.cirava-update-channel-control\s*\{[^}]*width:\s*min\(230px, 62%\)/s);
  assert.match(styles, /html\[data-theme='dark'\] \.cirava-update-channel-field/);
});
