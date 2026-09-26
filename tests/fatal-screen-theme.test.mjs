import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

test('startup error screen has complete dark-theme styling', async () => {
  const css = await readFile(new URL('../src/styles.css', import.meta.url), 'utf8');
  assert.match(css, /html\[data-theme=['"]dark['"]\]\s+\.fatal-screen\s*\{/);
  assert.match(css, /html\[data-theme=['"]dark['"]\]\s+\.fatal-card\s*\{/);
  assert.match(css, /html\[data-theme=['"]dark['"]\]\s+\.fatal-card\s+h1\s*\{/);
  assert.match(css, /html\[data-theme=['"]dark['"]\]\s+\.fatal-card\s+pre\s*\{/);
});
