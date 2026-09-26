import test from 'node:test';
import assert from 'node:assert/strict';

const loginCredentials = await import('../src/login-credentials.js').catch(() => ({}));

test('an unconfigured desktop clears a cached client ID so setup starts cleanly', () => {
  assert.equal(typeof loginCredentials.clearCachedClientIdWhenUnconfigured, 'function');

  const values = new Map([['cirava.clientId', 'old.apps.googleusercontent.com']]);
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    removeItem: (key) => values.delete(key),
  };

  loginCredentials.clearCachedClientIdWhenUnconfigured(storage, false);
  assert.equal(storage.getItem('cirava.clientId'), null);
});

test('a configured desktop keeps its cached client ID', () => {
  const values = new Map([['cirava.clientId', 'kept.apps.googleusercontent.com']]);
  const storage = { getItem: (key) => values.get(key) ?? null, removeItem: (key) => values.delete(key) };

  loginCredentials.clearCachedClientIdWhenUnconfigured(storage, true);
  assert.equal(storage.getItem('cirava.clientId'), 'kept.apps.googleusercontent.com');
});

test('login exposes an accessible Change credentials link', () => {
  assert.equal(typeof loginCredentials.createChangeCredentialsLink, 'function');

  const button = loginCredentials.createChangeCredentialsLink({
    createElement: (tagName) => ({
      tagName,
      attributes: {},
      setAttribute(name, value) { this.attributes[name] = value; },
      getAttribute(name) { return this.attributes[name] ?? null; },
    }),
  });

  assert.equal(button.tagName, 'button');
  assert.equal(button.type, 'button');
  assert.equal(button.textContent, 'Change credentials');
  assert.equal(button.getAttribute('aria-haspopup'), 'dialog');
});

test('saving credentials keeps the client secret out of browser storage', async () => {
  assert.equal(typeof loginCredentials.saveGoogleCredentials, 'function');

  const calls = [];
  const stored = [];
  await loginCredentials.saveGoogleCredentials({
    api: { save_google_configuration: async (...args) => calls.push(args) },
    storage: { setItem: (...args) => stored.push(args) },
    clientId: '  cirava.apps.googleusercontent.com  ',
    clientSecret: '  secret-value  ',
  });

  assert.deepEqual(calls, [['cirava.apps.googleusercontent.com', 'secret-value']]);
  assert.deepEqual(stored, [['cirava.clientId', 'cirava.apps.googleusercontent.com']]);
});
