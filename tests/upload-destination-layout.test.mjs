import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const controls = readFileSync(new URL('../src/shared-drive-controls.js', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/upload-planner.css', import.meta.url), 'utf8');

test('shared-drive link controls stay collapsed until requested so folder picker fits above planner actions', () => {
  assert.match(controls, /linkDetails\.className = 'shared-drive-link-details'/);
  assert.match(controls, /linkSummary\.textContent = 'Use a shared-drive or folder link'/);
  assert.match(controls, /host\.insertBefore\(wrap, folderList\)/);
  assert.match(styles, /\.cirava-upload-destination-step \.cirava-upload-folders:not\(\[hidden\]\) \{ min-height: 0; max-height: none; overflow: auto; \}/);
  assert.match(readFileSync(new URL('../src/shared-drive-controls.css', import.meta.url), 'utf8'), /\.shared-drive-controls\{[^}]*margin:5px 0/);
});
