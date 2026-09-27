import test from 'node:test';
import assert from 'node:assert/strict';
import { getUpdateFeed, getUpdateFeeds } from '../src/update-feeds.js';

test('ordinary builds have working stable and beta feeds by default', () => {
  const feeds = getUpdateFeeds({});
  assert.equal(feeds.release, 'https://github.com/B1progame/Cirava/releases/latest/download/update-manifest.json');
  assert.equal(feeds.beta, 'https://api.github.com/repos/B1progame/Cirava/releases?per_page=100');
});

test('configured feed URLs override defaults without disabling the other channel', () => {
  const feeds = getUpdateFeeds({
    VITE_CIRAVA_STABLE_MANIFEST_URL: 'https://updates.example/stable.json',
    VITE_CIRAVA_BETA_RELEASES_API_URL: 'https://updates.example/beta',
  });
  assert.equal(feeds.release, 'https://updates.example/stable.json');
  assert.equal(feeds.beta, 'https://updates.example/beta');
});

test('selecting a channel never silently falls back to the other release channel', () => {
  assert.equal(getUpdateFeed('beta', { release: 'https://stable.example/feed', beta: '' }), '');
  assert.equal(getUpdateFeed('release', { release: 'https://stable.example/feed', beta: '' }), 'https://stable.example/feed');
});
