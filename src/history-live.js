const FINISHED = new Set(['completed', 'failed', 'cancelled']);

function readableSize(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
  return `${value >= 100 ? Math.round(value) : value.toFixed(1)} ${units[unit]}`;
}

export function getHistoryTransfers(transfers) {
  if (!Array.isArray(transfers)) return [];
  return transfers.filter((item) => FINISHED.has(item?.status)).map((item) => {
    const bytes = Number(item.sizeBytes ?? item.size ?? 0) || 0;
    return {
      ...item,
      id: item.id,
      name: item.name ?? item.filename ?? 'Unnamed transfer',
      kind: item.kind ?? item.direction ?? 'download',
      localPath: item.localPath ?? item.local_path ?? '',
      driveFileId: item.driveFileId ?? item.drive_file_id ?? '',
      size: typeof item.size === 'string' ? item.size : readableSize(bytes),
      sizeBytes: bytes,
      createdAt: item.createdAt ?? item.created_at ?? 0,
      completedAt: item.completedAt ?? item.completed_at ?? null,
    };
  });
}

export function resolveHistoryTransfer(row, transfers, occurrence = 0) {
  const matches = getHistoryTransfers(transfers).filter((item) =>
    item.name === row?.name && item.kind === row?.kind && item.status === row?.status,
  );
  return matches[occurrence] || null;
}

function transferSignature(row) {
  return JSON.stringify([row.name, row.kind, row.status]);
}

function readHistoryRow(card) {
  const paragraph = card.querySelector('p')?.textContent?.trim() || '';
  return {
    name: card.querySelector('strong')?.textContent?.trim() || '',
    kind: /^Uploaded\b/i.test(paragraph) ? 'upload' : 'download',
    status: card.querySelector('time')?.textContent?.trim() || '',
  };
}

function historyApi() { return window.pywebview?.api || null; }

function showHistoryToast(message, error = false) {
  document.querySelector('[data-cirava-history-toast]')?.remove();
  const toast = document.createElement('div');
  toast.className = `toast${error ? ' error' : ''}`;
  toast.dataset.ciravaHistoryToast = 'true';
  toast.setAttribute('role', 'status');
  toast.textContent = message;
  document.body.append(toast);
  window.setTimeout(() => toast.remove(), 2800);
}

function closeHistoryMenu() {
  document.querySelector('[data-cirava-history-menu]')?.remove();
}

function addHistoryEmptyState(day) {
  let empty = day.querySelector('[data-cirava-history-empty]');
  if (!empty) {
    empty = document.createElement('div');
    empty.className = 'history-empty-state';
    empty.dataset.ciravaHistoryEmpty = 'true';
    empty.innerHTML = '<span class="history-empty-mark" aria-hidden="true">✓</span><div><strong>No completed transfers yet</strong><p>Your finished uploads and downloads will be recorded here.</p></div><button type="button" class="secondary">Go to transfers</button>';
    day.append(empty);
    empty.querySelector('button')?.addEventListener('click', () => {
      Array.from(document.querySelectorAll('.nav-item')).find((item) => item.textContent?.trim() === 'Transfers')?.click();
    });
  }
}

function placeMenu(menu, anchor) {
  const rect = anchor.getBoundingClientRect();
  menu.style.top = `${Math.min(rect.bottom + 6, window.innerHeight - menu.offsetHeight - 12)}px`;
  menu.style.left = `${Math.max(12, Math.min(rect.right - menu.offsetWidth, window.innerWidth - menu.offsetWidth - 12))}px`;
}

async function openHistoryMenu(card, anchor, row, occurrence) {
  closeHistoryMenu();
  const menu = document.createElement('div');
  menu.className = 'history-action-menu';
  menu.dataset.ciravaHistoryMenu = 'true';
  menu.setAttribute('role', 'menu');
  menu.innerHTML = '<span class="history-menu-status" role="status">Loading transfer…</span>';
  document.body.append(menu);
  const api = historyApi();
  if (!api?.list_transfers) {
    menu.querySelector('.history-menu-status').textContent = 'Open this history item in the Cirava desktop app to use its actions.';
    placeMenu(menu, anchor);
    return;
  }

  try {
    const records = await api.list_transfers();
    const transfer = resolveHistoryTransfer(row, records, occurrence);
    if (!transfer?.id) throw new Error('This transfer is no longer in history.');
    if (!menu.isConnected) return;
    menu.innerHTML = '';
    const action = (label, handler, disabled = false, danger = false) => {
      const item = document.createElement('button');
      item.type = 'button'; item.setAttribute('role', 'menuitem'); item.textContent = label;
      item.disabled = disabled;
      if (danger) item.classList.add('danger-action');
      item.addEventListener('click', async () => {
        item.disabled = true;
        try { await handler(transfer); closeHistoryMenu(); }
        catch (error) { item.disabled = false; showHistoryToast(error instanceof Error ? error.message : 'History action failed.', true); }
      });
      menu.append(item);
    };
    action('Reveal local file', async (item) => {
      if (!api.reveal_local) throw new Error('Reveal is available in the Cirava desktop app.');
      await api.reveal_local(item.id);
      showHistoryToast('Opened the local file location.');
    }, !transfer.localPath || !api.reveal_local);
    action('Open in Drive', async (item) => {
      if (!api.open_drive_file) throw new Error('Open in Drive is available in the Cirava desktop app.');
      await api.open_drive_file(item.id);
      showHistoryToast('Opened the Drive item.');
    }, !transfer.driveFileId || !api.open_drive_file);
    action('Copy Drive link', async (item) => {
      if (!item.driveFileId) throw new Error('This transfer has no Drive link.');
      await navigator.clipboard.writeText(`https://drive.google.com/open?id=${item.driveFileId}`);
      showHistoryToast('Drive link copied.');
    }, !transfer.driveFileId || !navigator.clipboard?.writeText);
    if (transfer.status === 'failed' && api.retry_transfer) {
      action('Retry transfer', async (item) => {
        await api.retry_transfer(item.id);
        showHistoryToast('Transfer queued to retry.');
      });
    }
    action('Remove from history', async (item) => {
      if (!api.remove_transfer) throw new Error('Removing history is available in the Cirava desktop app.');
      if (!window.confirm(`Remove “${item.name}” from history? This will not delete the file.`)) return;
      await api.remove_transfer(item.id);
      const more = card.querySelector('.row-more');
      if (more) { more.disabled = true; more.setAttribute('aria-label', 'History is updating'); }
      showHistoryToast('Transfer removed from history.');
    }, !api.remove_transfer, true);
    placeMenu(menu, anchor);
  } catch (error) {
    if (menu.isConnected) {
      menu.querySelector('.history-menu-status').textContent = error instanceof Error ? error.message : 'Could not load this transfer.';
      placeMenu(menu, anchor);
    }
  }
}

export function enhanceTransferHistory() {
  const page = Array.from(document.querySelectorAll('.page')).find((candidate) =>
    candidate.querySelector('.page-heading .eyebrow')?.textContent?.trim() === 'Transfer history',
  );
  if (!page) { closeHistoryMenu(); return; }
  const day = page.querySelector('.history-day');
  if (!day) return;

  const label = day.querySelector(':scope > span');
  const previewOnly = label?.textContent?.trim() === 'Preview history';
  if (previewOnly) {
    day.querySelectorAll('.history-card').forEach((card) => card.remove());
    if (label) label.textContent = 'History';
  }

  const cards = Array.from(day.querySelectorAll('.history-card'));
  const clear = page.querySelector('.page-heading button');
  if (clear) {
    clear.disabled = cards.length === 0;
    clear.title = cards.length ? 'Remove all completed transfers from history' : 'There are no completed transfers to clear';
  }
  if (label && !previewOnly) label.textContent = cards.length ? 'Recent transfers' : 'History';
  if (cards.length === 0) addHistoryEmptyState(day);
  else day.querySelector('[data-cirava-history-empty]')?.remove();

  const occurrenceBySignature = new Map();
  cards.forEach((card) => {
    const row = readHistoryRow(card);
    const signature = transferSignature(row);
    const occurrence = occurrenceBySignature.get(signature) || 0;
    occurrenceBySignature.set(signature, occurrence + 1);
    const more = card.querySelector('.row-more');
    if (more) more.dataset.ciravaHistoryOccurrence = String(occurrence);
    if (!more || more.dataset.ciravaHistoryActionReady) return;
    more.dataset.ciravaHistoryActionReady = 'true';
    more.setAttribute('aria-label', `Actions for ${row.name}`);
    more.setAttribute('aria-haspopup', 'menu');
    more.addEventListener('click', (event) => {
      event.preventDefault(); event.stopPropagation();
      if (document.querySelector('[data-cirava-history-menu]')) { closeHistoryMenu(); return; }
      void openHistoryMenu(card, more, readHistoryRow(card), Number(more.dataset.ciravaHistoryOccurrence) || 0);
    }, true);
  });
}

if (typeof document !== 'undefined') {
  document.addEventListener('pointerdown', (event) => {
    if (!event.target.closest('[data-cirava-history-menu], .history-card .row-more')) closeHistoryMenu();
  });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closeHistoryMenu(); });
  window.addEventListener('resize', closeHistoryMenu);
  window.addEventListener('scroll', closeHistoryMenu, true);
}
