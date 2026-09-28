import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../src/main.tsx', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/ui-fixes.css', import.meta.url), 'utf8');

test('both upload entry points use non-overlaying accessible 7-Zip level controls', () => {
  assert.equal((source.match(/data-cirava-compression-level/g) || []).length, 5);
  assert.ok(!source.includes('<select data-cirava-compression-level'), 'native dropdowns can pop over the upload controls');
  assert.match(source, /role="group" aria-label="Compression level" data-cirava-compression-level/);
  assert.match(source, /data-compression-level="1" aria-pressed="false"/);
  assert.match(source, /data-compression-level="5" aria-pressed="true"/);
  assert.equal((source.match(/class="archive-level-options"/g) || []).length, 2);
  assert.match(source, /picker\.dataset\.value\s*=\s*button\.dataset\.compressionLevel/);
  assert.match(source, /option\.setAttribute\('aria-pressed', String\(option === button\)\)/);
  assert.match(styles, /\.archive-level-options\s*\{[^}]*grid-template-columns:\s*repeat\(5,\s*minmax\(0,\s*1fr\)\)/s);
});
