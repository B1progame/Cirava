export function createChangeCredentialsLink(documentRef) {
  const button = documentRef.createElement('button');
  button.type = 'button';
  button.className = 'login-change-credentials';
  button.textContent = 'Change credentials';
  button.setAttribute('aria-haspopup', 'dialog');
  return button;
}

export function clearCachedClientIdWhenUnconfigured(storage, configured) {
  if (!configured) storage.removeItem('cirava.clientId');
}

export async function saveGoogleCredentials({ api, storage, clientId, clientSecret }) {
  const normalizedClientId = String(clientId || '').trim();
  if (!normalizedClientId) throw new Error('Enter the complete Desktop OAuth client ID.');
  if (!api || typeof api.save_google_configuration !== 'function') {
    throw new Error('Open Cirava.exe to change Google credentials.');
  }

  const normalizedSecret = String(clientSecret || '').trim();
  await api.save_google_configuration(normalizedClientId, normalizedSecret || undefined);
  storage.setItem('cirava.clientId', normalizedClientId);
}

function openCredentialEditor() {
  const dialog = document.createElement('dialog');
  dialog.className = 'login-credentials-dialog';
  dialog.setAttribute('aria-labelledby', 'login-credentials-title');
  dialog.innerHTML = `
    <form class="login-credentials-form">
      <div class="login-credentials-heading">
        <div><span class="eyebrow">Connection settings</span><h2 id="login-credentials-title">Change credentials</h2></div>
        <button class="login-credentials-close" type="button" aria-label="Close">×</button>
      </div>
      <p>Update the Google Desktop OAuth client Cirava uses. Your Google password is never requested.</p>
      <label>Client ID<input name="clientId" type="text" autocomplete="off" spellcheck="false" placeholder="...apps.googleusercontent.com" required></label>
      <label>Client secret <span>(optional)</span><input name="clientSecret" type="password" autocomplete="new-password" placeholder="Leave blank to keep the current secret"></label>
      <p class="login-credentials-status" role="status" aria-live="polite" hidden></p>
      <div class="login-credentials-actions"><button class="secondary" type="button" data-cancel>Cancel</button><button class="primary" type="submit">Save credentials</button></div>
    </form>`;

  const form = dialog.querySelector('form');
  const clientId = form.elements.namedItem('clientId');
  const clientSecret = form.elements.namedItem('clientSecret');
  const status = dialog.querySelector('.login-credentials-status');
  const submit = form.querySelector('[type="submit"]');
  clientId.value = window.localStorage.getItem('cirava.clientId') || '';

  const close = () => dialog.close();
  dialog.querySelector('.login-credentials-close').addEventListener('click', close);
  dialog.querySelector('[data-cancel]').addEventListener('click', close);
  dialog.addEventListener('close', () => dialog.remove(), { once: true });
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    status.hidden = false;
    status.textContent = 'Saving securely…';
    submit.disabled = true;
    try {
      await saveGoogleCredentials({
        api: window.pywebview?.api,
        storage: window.localStorage,
        clientId: clientId.value,
        clientSecret: clientSecret.value,
      });
      status.textContent = 'Credentials saved securely. You can continue with Google sign-in.';
      window.setTimeout(close, 900);
    } catch (error) {
      status.textContent = error instanceof Error ? error.message : 'Could not save Google credentials.';
    } finally {
      submit.disabled = false;
    }
  });

  document.body.append(dialog);
  dialog.showModal();
  clientId.focus();
}

function installLoginCredentialsLink() {
  const addLink = () => {
    const footer = document.querySelector('.login-foot');
    const card = footer?.closest('.login-card');
    if (!footer || !card || card.querySelector('.login-change-credentials')) return;

    const row = document.createElement('div');
    row.className = 'login-change-row';
    const button = createChangeCredentialsLink(document);
    button.addEventListener('click', openCredentialEditor);
    row.append(button);
    footer.after(row);
  };

  const observer = new MutationObserver(addLink);
  observer.observe(document.body, { childList: true, subtree: true });
  addLink();
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', installLoginCredentialsLink, { once: true });
  } else {
    installLoginCredentialsLink();
  }
}
