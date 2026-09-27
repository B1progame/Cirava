const pendingDismissals = new WeakMap();

export function scheduleTransientUploadNoticeDismissal(
  notice,
  schedule = (callback, delay) => window.setTimeout(callback, delay),
  delayMs = 8_000,
) {
  if (!notice) return false;
  const message = notice.textContent || '';
  if (pendingDismissals.get(notice) === message) return false;

  pendingDismissals.set(notice, message);
  schedule(() => {
    if (pendingDismissals.get(notice) !== message) return;
    if (notice.isConnected && notice.textContent === message) notice.remove();
  }, delayMs);
  return true;
}
