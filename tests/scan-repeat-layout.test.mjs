import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const stylesheet = readFileSync(new URL('../src/workflows/scan-repeat/scan-repeat.css', import.meta.url), 'utf8');

test('scan workflow keeps two cards per row at narrow widths, with the third below', () => {
  assert.doesNotMatch(
    stylesheet,
    /\.scan-repeat-grid\s*\{\s*grid-template-columns:\s*(?:1fr|minmax\(0,\s*1fr\))\s*;/,
    'responsive scan card rules should never collapse the grid to a single column',
  );
  assert.match(stylesheet, /\.scan-control-card:last-child\s*\{\s*grid-column:\s*1\s*\/\s*-1\s*;/);
});
