const TERMINAL = new Set(['completed', 'failed', 'cancelled']);
let recoveryObserver;
let recoveryScan;

export function getTransferProgress(record = {}) {
  const sizeBytes = Number(record.sizeBytes ?? record.size ?? 0) || 0;
  const bytesTransferred = Number(record.bytesTransferred ?? record.bytes_transferred ?? 0) || 0;
  const speedBps = Number(record.speedBps ?? record.speed_bps ?? 0) || 0;
  return {
    sizeBytes,
    bytesTransferred,
    progress: sizeBytes > 0 ? Math.round((bytesTransferred / sizeBytes) * 1000) / 10 : 0,
    speedBps,
  };
}

export function findResumableTransfer(row, transfers, occurrence = 0) {
  if (!row?.name || !Array.isArray(transfers)) return null;
  const match = transfers.filter((transfer) =>
    (transfer.filename ?? transfer.name) === row.name
    && (transfer.direction ?? transfer.kind) === row.kind
  )[occurrence];
  return match?.status === 'paused' && !TERMINAL.has(match.status) ? match : null;
}

const CANCELLABLE_UPLOAD_STATES = new Set(['queued', 'preparing', 'transferring', 'waiting-for-network', 'rate-limited', 'retrying']);

export function findCancellableTransfer(row, transfers, occurrence = 0) {
  if (!row?.name || row.kind?.toLowerCase() !== 'upload' || !Array.isArray(transfers)) return null;
  const match = transfers.filter((transfer) =>
    (transfer.filename ?? transfer.name) === row.name
    && (transfer.direction ?? transfer.kind)?.toLowerCase() === 'upload'
  )[occurrence];
  return CANCELLABLE_UPLOAD_STATES.has(String(match?.status ?? '').toLowerCase()) ? match : null;
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
  return `${value >= 100 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`;
}

function readQueueIdentity(row) {
  const name = row.querySelector('.queue-main strong')?.textContent?.trim() || '';
  const direction = row.querySelector('.queue-main span')?.textContent?.split(' · ')[0]?.trim().toLowerCase() || '';
  return { name, kind: direction };
}

async function enhancePausedRows() {
  const page = Array.from(document.querySelectorAll('.page')).find((candidate) =>
    candidate.querySelector('.page-heading .eyebrow')?.textContent?.trim() === 'Transfer center',
  );
  if (!page) return;
  const api = window.pywebview?.api;
  if (!api?.list_transfers) return;
  const rows = Array.from(page.querySelectorAll('.queue-row'));
  if (!rows.length) return;

  let transfers;
  try { transfers = await api.list_transfers(); }
  catch { return; }
  const occurrences = new Map();
  rows.forEach((row) => {
    const identity = readQueueIdentity(row);
    const signature = `${identity.kind}\u0000${identity.name}`;
    const occurrence = occurrences.get(signature) || 0;
    occurrences.set(signature, occurrence + 1);
    const resumeItem = findResumableTransfer(identity, transfers, occurrence);
    const cancelItem = findCancellableTransfer(identity, transfers, occurrence);
    const queueMeta = row.querySelector('.queue-meta');
    if (!queueMeta) return;
    if (!resumeItem || !api.resume_transfer) {
      row.querySelector('[data-cirava-resume-transfer]')?.remove();
    } else if (!row.querySelector('[data-cirava-resume-transfer]')) {
      const progress = getTransferProgress(resumeItem);
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'transfer-resume';
      button.dataset.ciravaResumeTransfer = 'true';
      button.textContent = `Resume · ${progress.progress}% saved`;
      button.title = `${formatBytes(progress.bytesTransferred)} of ${formatBytes(progress.sizeBytes)} saved${resumeItem.average_speed_bps ? ` · previous average ${formatBytes(resumeItem.average_speed_bps)}/s` : ''}`;
      button.addEventListener('click', async () => {
        button.disabled = true;
        button.textContent = 'Resuming…';
        try {
          await api.resume_transfer(resumeItem.id);
          button.textContent = 'Transfer resumed';
          window.setTimeout(() => button.remove(), 1000);
        } catch (error) {
          button.disabled = false;
          button.textContent = 'Resume failed · try again';
          button.title = error instanceof Error ? error.message : 'Could not resume this transfer.';
        }
      });
      queueMeta.append(button);
    }
    const existingCancel = row.querySelector<HTMLButtonElement>('[data-cirava-cancel-upload]');
    if (!cancelItem || !api.cancel_transfer) {
      existingCancel?.remove();
      return;
    }
    if (existingCancel) return;
    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.className = 'transfer-cancel-upload';
    cancel.dataset.ciravaCancelUpload = 'true';
    cancel.textContent = 'Cancel upload';
    cancel.setAttribute('aria-label', `Cancel upload of ${identity.name}`);
    cancel.addEventListener('click', async () => {
      cancel.disabled = true;
      cancel.textContent = 'Cancelling…';
      try {
        await api.cancel_transfer(cancelItem.id);
        cancel.textContent = 'Upload cancelled';
      } catch (error) {
        cancel.disabled = false;
        cancel.textContent = 'Cancel upload';
        cancel.title = error instanceof Error ? error.message : 'Could not cancel this upload.';
      }
    });
    queueMeta.append(cancel);
  });
}

export function enhanceTransferRecovery() {
  if (typeof document === 'undefined' || !document.body) return;
  if (!recoveryObserver) {
    recoveryObserver = new MutationObserver(() => enhanceTransferRecovery());
    recoveryObserver.observe(document.body, { childList: true, subtree: true });
  }
  if (recoveryScan) return;
  recoveryScan = enhancePausedRows().finally(() => { recoveryScan = null; });
}
