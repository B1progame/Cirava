import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const packageJson = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
const lockJson = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8'));
const backendVersion = readFileSync(new URL('../backend/cirava_backend/__init__.py', import.meta.url), 'utf8').match(/__version__\s*=\s*"([^"]+)"/)?.[1];

test('the generated stable desktop release uses one version in frontend and backend metadata', () => {
  assert.match(packageJson.version, /^\d+\.\d+\.\d+$/);
  assert.equal(lockJson.version, packageJson.version);
  assert.equal(lockJson.packages[''].version, packageJson.version);
  assert.equal(backendVersion, packageJson.version);
});
