const BYTE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB'];

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character]);
}

export function formatDriveStorageBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes) || bytes < 0) return 'Unknown';
  if (bytes < 1024) return `${Math.round(bytes)} B`;
  const unit = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), BYTE_UNITS.length - 1);
  const amount = bytes / (1024 ** unit);
  return `${amount >= 100 ? Math.round(amount) : amount.toFixed(1)} ${BYTE_UNITS[unit]}`;
}

export function renderDriveTrashRows(files = []) {
  if (!files.length) {
    return '<div class="cirava-trash-empty"><strong>Your trash is empty</strong><p>Items you move to trash will appear here. You can restore them or permanently delete them.</p></div>';
  }
  const rows = files.map((file) => {
    const id = escapeHtml(file.id);
    const name = escapeHtml(file.name || 'Untitled item');
    const bytes = Number(file.size);
    const size = file.size != null && Number.isFinite(bytes) ? formatDriveStorageBytes(bytes) : '—';
    const trashedTime = file.trashedTime || file.modifiedTime;
    const date = trashedTime && Number.isFinite(Date.parse(trashedTime))
      ? new Date(trashedTime).toLocaleString()
      : 'Date unavailable';
    const type = file.mimeType === 'application/vnd.google-apps.folder' ? 'Folder' : 'File';
    return `<div class="cirava-trash-row" role="row"><span class="cirava-trash-item"><span class="cirava-trash-type">${type}</span><strong>${name}</strong></span><span>${escapeHtml(date)}</span><span>${escapeHtml(size)}</span><span><button type="button" class="secondary" data-trash-restore="${id}">Restore</button></span></div>`;
  }).join('');
  return `<div class="cirava-trash-table" role="table" aria-label="Items in Drive trash"><div class="cirava-trash-row cirava-trash-head" role="row"><span>Name</span><span>Date trashed</span><span>File size</span><span>Action</span></div>${rows}</div>`;
}

function quotaMarkup(quota = {}) {
  if (quota == null) {
    return '<section class="cirava-trash-storage" aria-label="Google Drive storage"><div><span class="eyebrow">GOOGLE DRIVE STORAGE</span><strong>Usage unavailable</strong></div><p>Reconnect Google or refresh to check your account storage.</p></section>';
  }
  const used = Number(quota.usage);
  const limit = Number(quota.limit);
  const drive = quota.usageInDrive;
  const trash = quota.usageInDriveTrash;
  const hasUsage = Number.isFinite(used) && used >= 0;
  const hasLimit = Number.isFinite(limit) && limit > 0;
  const percent = hasUsage && hasLimit ? Math.min(100, Math.max(0, (used / limit) * 100)) : 0;
  const usageText = hasUsage ? formatDriveStorageBytes(used) : 'Usage unavailable';
  const limitText = hasLimit ? formatDriveStorageBytes(limit) : quota.limit == null ? 'Unlimited storage' : 'Storage limit unavailable';
  const driveText = drive == null ? '—' : formatDriveStorageBytes(drive);
  const trashText = trash == null ? '—' : formatDriveStorageBytes(trash);
  return `<section class="cirava-trash-storage" aria-label="Google Drive storage"><div><span class="eyebrow">GOOGLE DRIVE STORAGE</span><strong>${escapeHtml(usageText)} <small>of ${escapeHtml(limitText)}</small></strong></div><div class="cirava-trash-meter" role="progressbar" aria-label="Storage used" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent.toFixed(1)}"><span style="width:${percent.toFixed(1)}%"></span></div><p><span>Drive files <strong>${escapeHtml(driveText)}</strong></span><span>In trash <strong>${escapeHtml(trashText)}</strong></span></p></section>`;
}

export function renderDriveTrash(files = [], quota = {}) {
  return `${quotaMarkup(quota)}<div class="cirava-trash-list-heading"><h3>Items in trash</h3><span>${files.length} ${files.length === 1 ? 'item' : 'items'}</span></div>${renderDriveTrashRows(files)}`;
}

export function installDriveTrash() {
  const toolbar = document.querySelector('.drive-toolbar');
  if (!toolbar || !document.querySelector('.breadcrumbs')) return;

  let panel = document.querySelector('[data-cirava-trash-panel]');
  if (!panel) {
    panel = document.createElement('div');
    panel.className = 'cirava-trash-overlay';
    panel.dataset.ciravaTrashPanel = 'true';
    panel.hidden = true;
    panel.innerHTML = `<section class="cirava-trash-dialog" role="dialog" aria-modal="true" aria-labelledby="cirava-trash-title"><header class="cirava-trash-header"><div><span class="eyebrow">GOOGLE DRIVE</span><h2 id="cirava-trash-title">Trash</h2><p>Restore items or permanently delete them from your Drive.</p></div><button type="button" class="secondary" data-trash-close aria-label="Close Trash">Close</button></header><div class="cirava-trash-actions"><button type="button" class="secondary" data-trash-refresh>Refresh</button><button type="button" class="danger-button" data-trash-empty>Empty trash</button></div><p class="cirava-trash-notice" data-trash-notice role="status" aria-live="polite" hidden></p><div data-trash-content><div class="cirava-trash-loading">Loading your Drive trash…</div></div><div class="cirava-trash-confirm" data-trash-confirm hidden role="alertdialog" aria-modal="true" aria-labelledby="cirava-trash-confirm-title"><h3 id="cirava-trash-confirm-title">Permanently delete all items?</h3><p>This cannot be undone. Every item currently in your Google Drive trash will be permanently deleted.</p><div><button type="button" class="secondary" data-trash-cancel-empty>Cancel</button><button type="button" class="danger-button" data-trash-confirm-empty>Permanently delete</button></div></div></section>`;
    document.body.append(panel);

    const setNotice = (message, state = 'success') => {
      const notice = panel.querySelector('[data-trash-notice]');
      notice.textContent = message;
      notice.dataset.state = state;
      notice.hidden = !message;
    };
    const loadTrash = async () => {
      const content = panel.querySelector('[data-trash-content]');
      const api = window.pywebview?.api;
      if (!api?.list_trashed_drive_files || !api?.get_storage_quota) {
        content.innerHTML = '<div class="cirava-trash-empty"><strong>Connect Google to view Trash</strong><p>Reconnect your Google account and approve full Drive access to view your complete trash and storage usage.</p></div>';
        return;
      }
      content.innerHTML = '<div class="cirava-trash-loading">Loading your Drive trash…</div>';
      setNotice('');
      const [trashResult, quotaResult] = await Promise.allSettled([
        api.list_trashed_drive_files(),
        api.get_storage_quota(),
      ]);
      if (trashResult.status === 'rejected') {
        content.innerHTML = `<div class="cirava-trash-empty"><strong>Could not load your trash</strong><p>${escapeHtml(trashResult.reason instanceof Error ? trashResult.reason.message : 'Reconnect Google and try again.')}</p></div>`;
        panel.querySelector('[data-trash-empty]').disabled = true;
        return;
      }
      const files = Array.isArray(trashResult.value?.files) ? trashResult.value.files : [];
      content.innerHTML = renderDriveTrash(files, quotaResult.status === 'fulfilled' ? quotaResult.value : null);
      panel.querySelector('[data-trash-empty]').disabled = files.length === 0;
      if (quotaResult.status === 'rejected') setNotice('Trash loaded, but storage usage could not be read.', 'error');
    };

    panel.addEventListener('click', async (event) => {
      const target = event.target instanceof Element ? event.target.closest('button') : null;
      if (!target) return;
      if (target.matches('[data-trash-close]')) {
        panel.hidden = true;
        document.querySelector('[data-cirava-trash-open]')?.focus();
      } else if (target.matches('[data-trash-refresh]')) {
        await loadTrash();
      } else if (target.matches('[data-trash-empty]')) {
        panel.querySelector('[data-trash-confirm]').hidden = false;
        panel.querySelector('[data-trash-confirm-empty]').focus();
      } else if (target.matches('[data-trash-cancel-empty]')) {
        panel.querySelector('[data-trash-confirm]').hidden = true;
        panel.querySelector('[data-trash-empty]').focus();
      } else if (target.matches('[data-trash-confirm-empty]')) {
        target.disabled = true;
        try {
          await window.pywebview.api.empty_drive_trash();
          panel.querySelector('[data-trash-confirm]').hidden = true;
          setNotice('Trash emptied. Items were permanently deleted.');
          await loadTrash();
          setNotice('Trash emptied. Items were permanently deleted.');
        } catch (error) {
          setNotice(error instanceof Error ? error.message : 'Could not empty trash. Try again.', 'error');
        } finally {
          target.disabled = false;
        }
      } else if (target.matches('[data-trash-restore]')) {
        target.disabled = true;
        const fileId = target.dataset.trashRestore;
        try {
          await window.pywebview.api.restore_drive_file(fileId);
          setNotice('Item restored to Drive.');
          await loadTrash();
          setNotice('Item restored to Drive.');
        } catch (error) {
          target.disabled = false;
          setNotice(error instanceof Error ? error.message : 'Could not restore this item. Try again.', 'error');
        }
      }
    });
    panel.addEventListener('keydown', (event) => {
      if (event.key === 'Escape' && !panel.hidden) {
        panel.hidden = true;
        document.querySelector('[data-cirava-trash-open]')?.focus();
      }
    });
    panel.__ciravaLoadTrash = loadTrash;
  }

  if (!toolbar.querySelector('[data-cirava-trash-open]')) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'filter-button';
    button.dataset.ciravaTrashOpen = 'true';
    button.textContent = 'Trash';
    button.setAttribute('aria-haspopup', 'dialog');
    button.addEventListener('click', async () => {
      panel.hidden = false;
      panel.querySelector('[data-trash-close]').focus();
      await panel.__ciravaLoadTrash();
    });
    const createControl = toolbar.querySelector('.drive-create-control');
    toolbar.insertBefore(button, createControl || null);
  }
}
