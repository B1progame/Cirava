import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const main = readFileSync(new URL('../src/main.tsx', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/ui-fixes.css', import.meta.url), 'utf8');

test('release channel control sits below the update copy, not in the brand row', () => {
  assert.match(main, /channelField\.append\(channelLabel, channelSelect\)/);
  assert.match(main, /identity\.append\(mark, kicker, version\)/);
  assert.match(main, /dialog\.append\(close, identity, title, copy, channelField, progress/);
  assert.match(main, /channelField\.hidden = !manifestUrls\.release \|\| !manifestUrls\.beta/);
});

test('release channel has a labeled, responsive control with dark-theme styling', () => {
  assert.match(styles, /\.cirava-update-channel-field\s*\{[^}]*display:\s*flex/s);
  assert.match(styles, /\.cirava-update-channel\s*\{[^}]*width:\s*min\(230px, 62%\)/s);
  assert.match(styles, /html\[data-theme='dark'\] \.cirava-update-channel-field/);
});
