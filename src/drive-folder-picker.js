const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
})[character]);

export function renderDriveFolderPicker({ parentId, currentLabel, folders }) {
  const safeLabel = escapeHtml(currentLabel || 'My Drive / Workspace');
  const safeParentId = escapeHtml(parentId || 'root');
  const options = folders.map(({ id, name }) => {
    const safeId = escapeHtml(id);
    const safeName = escapeHtml(name);
    return `<button type="button" class="cirava-upload-folder-option" data-cirava-folder-id="${safeId}" data-cirava-folder-name="${safeName}" aria-label="Open folder ${safeName}"><svg class="cirava-upload-folder-icon" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M2.5 5.75A1.75 1.75 0 0 1 4.25 4h3.1l1.7 1.8h6.7A1.75 1.75 0 0 1 17.5 7.55v6.7A1.75 1.75 0 0 1 15.75 16h-11a2.25 2.25 0 0 1-2.25-2.25z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M2.8 8h14.4" stroke="currentColor" stroke-width="1.2"/></svg><span class="cirava-upload-folder-name">${safeName}</span><span class="cirava-upload-folder-open">Open <span aria-hidden="true">›</span></span></button>`;
  }).join('');

  const folderCount = `${folders.length} folder${folders.length === 1 ? '' : 's'}`;
  return `<section class="cirava-upload-folder-chooser" aria-label="Choose an upload destination"><header class="cirava-upload-folder-chooser-head"><span><strong>Choose a folder</strong><small>Browsing ${safeLabel}</small></span><small>${folderCount}</small></header><button type="button" class="cirava-upload-folder-current" data-cirava-use-folder="${safeParentId}" aria-label="Use ${safeLabel} as upload destination"><span class="cirava-upload-current-mark" aria-hidden="true"><svg viewBox="0 0 20 20" fill="none"><path d="m4.5 10.2 3.6 3.5 7.5-7.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></span><span class="cirava-upload-folder-current-copy"><strong>Use ${safeLabel}</strong><small>Upload directly into this folder</small></span><span class="cirava-upload-folder-use-label">Use this folder</span></button><div class="cirava-upload-folder-list" role="group" aria-label="Folders inside ${safeLabel}"><div class="cirava-upload-folder-list-head"><strong>Folders</strong><small>Open a folder to browse inside</small></div><div class="cirava-upload-folder-list-items">${options || '<span class="cirava-upload-folder-empty">No folders here yet.</span>'}</div></div></section>`;
}
