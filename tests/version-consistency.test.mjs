import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const packageJson = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
const lockJson = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8'));
const backendVersion = readFileSync(new URL('../backend/cirava_backend/__init__.py', import.meta.url), 'utf8').match(/__version__\s*=\s*"([^"]+)"/)?.[1];

test('the generated stable desktop release uses version 1.1.1 in frontend and backend metadata', () => {
  assert.equal(packageJson.version, '1.1.1');
  assert.equal(lockJson.version, '1.1.1');
  assert.equal(lockJson.packages[''].version, '1.1.1');
  assert.equal(backendVersion, '1.1.1');
});
