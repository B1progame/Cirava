import { createConnectivityMonitor } from './connectivity-monitor.js';

const OFFLINE_INTERVAL_MS = 10_000;
const CONNECTIVITY_URL = 'https://www.google.com/generate_204';

function errorMessage(error) {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    return 'Your device reports that it is offline. Check Wi-Fi or Ethernet.';
  }
  if (error?.name === 'AbortError') return 'The internet check timed out. Your connection may be unavailable.';
  return 'Cirava could not reach Google. Check your internet connection and try again.';
}

export function startOfflineRecovery({
  documentRef = document,
  windowRef = window,
  fetchImpl = window.fetch.bind(window),
} = {}) {
  const overlay = documentRef.createElement('section');
  overlay.className = 'offline-recovery';
  overlay.hidden = true;
  overlay.setAttribute('role', 'alertdialog');
  overlay.setAttribute('aria-modal', 'true');
  overlay.setAttribute('aria-labelledby', 'offline-recovery-title');
  overlay.innerHTML = `
    <div class="offline-recovery-card">
      <div class="offline-recovery-brand"><img src="/cirava-logo.png" alt="" /><strong>cirava</strong></div>
      <div class="offline-recovery-orb" aria-hidden="true">
        <img src="/cirava-logo.png" alt="" />
        <video src="/cirava-startup.mp4" autoplay muted loop playsinline></video>
      </div>
      <span class="offline-recovery-kicker">CONNECTION INTERRUPTED</span>
      <h1 id="offline-recovery-title">No internet connection</h1>
      <p class="offline-recovery-copy">Cirava needs an internet connection to reach Google Drive. Your local files and transfer progress are safe.</p>
      <p class="offline-recovery-error" role="status" aria-live="polite"></p>
      <p class="offline-recovery-retry-note">We’ll check again automatically every 10 seconds.</p>
      <button class="offline-recovery-retry" type="button">Check connection now</button>
    </div>`;
  documentRef.body.append(overlay);

  const error = overlay.querySelector('.offline-recovery-error');
  const retry = overlay.querySelector('.offline-recovery-retry');
  const probe = async () => {
    if (windowRef.navigator.onLine === false) throw new Error('offline');
    const controller = new AbortController();
    const timeout = windowRef.setTimeout(() => controller.abort(), 5_000);
    try {
      await fetchImpl(`${CONNECTIVITY_URL}?t=${Date.now()}`, {
        method: 'GET',
        mode: 'no-cors',
        cache: 'no-store',
        credentials: 'omit',
        signal: controller.signal,
      });
    } finally {
      windowRef.clearTimeout(timeout);
    }
  };

  const monitor = createConnectivityMonitor({
    probe,
    intervalMs: OFFLINE_INTERVAL_MS,
    onOffline: (reason) => {
      error.textContent = errorMessage(reason);
      overlay.hidden = false;
      documentRef.body.classList.add('has-offline-recovery');
    },
    onOnline: () => {
      overlay.hidden = true;
      documentRef.body.classList.remove('has-offline-recovery');
      retry.disabled = false;
      retry.textContent = 'Check connection now';
    },
  });

  retry.addEventListener('click', async () => {
    retry.disabled = true;
    retry.textContent = 'Checking…';
    const online = await monitor.checkNow();
    if (!online) {
      error.textContent = errorMessage(monitor.lastError);
      retry.disabled = false;
      retry.textContent = 'Try again';
    }
  });
  windowRef.addEventListener('offline', () => { void monitor.checkNow(); });
  windowRef.addEventListener('online', () => { void monitor.checkNow(); });
  monitor.start();
  return monitor;
}
