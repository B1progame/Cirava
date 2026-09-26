import test from 'node:test';
import assert from 'node:assert/strict';
import { getReleasePresentation } from '../src/release-channel.js';

test('stable semantic versions use stable labels without a beta version suffix', () => {
  assert.deepEqual(getReleasePresentation('1.0.1'), {
    channel: 'release',
    badge: 'Stable',
    version: '1.0.1',
    productLabel: 'Desktop',
  });
});

test('prerelease semantic versions keep beta labels and suffixes', () => {
  assert.deepEqual(getReleasePresentation('1.1.0-beta.2'), {
    channel: 'beta',
    badge: 'beta',
    version: '1.1.0-beta.2',
    productLabel: 'Desktop beta',
  });
});

test('an explicit build channel takes precedence over semantic version inference', () => {
  assert.equal(getReleasePresentation('1.0.1', 'beta').channel, 'beta');
  assert.equal(getReleasePresentation('1.1.0-beta.2', 'release').channel, 'release');
});
