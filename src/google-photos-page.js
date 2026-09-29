const photoIcon = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="3" stroke="currentColor" stroke-width="1.6"/><circle cx="8.5" cy="9" r="1.4" fill="currentColor"/><path d="m5 17 4.2-4 2.8 2.4 3.1-3 4 4.6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const playIcon = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m9 6 10 6-10 6V6Z" fill="currentColor"/></svg>';
const uploadIcon = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 16V4m0 0L7 9m5-5 5 5M5 15v4h14v-4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const driveIcon = '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m8.2 3 5.2.1 7.4 12.7-2.6 4.3-7.4-12.8L8.2 3Z" stroke="currentColor" stroke-width="1.5"/><path d="M8.2 3 1.4 15l2.6 4.8h14.2l2.6-4H6.2" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>';
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);

function dateGroup(timestamp) {
  const date = new Date(timestamp * 1000);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === today.toDateString()) return 'Today';
  if (date.toDateString() === yesterday.toDateString()) return 'Yesterday';
  return new Intl.DateTimeFormat(undefined, { month: 'long', year: 'numeric' }).format(date);
}
function formatBytes(size) {
  if (!size) return 'File';
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`;
  return `${(size / (1024 * 1024)).toFixed(size >= 1024 ** 3 ? 1 : 0)} ${size >= 1024 ** 3 ? 'GB' : 'MB'}`;
}
function mediaKind(mime = '') { return mime.startsWith('image/') ? 'photo' : mime.startsWith('video/') ? 'video' : 'file'; }
function durationMs(value, fallback = 3000, maximum = 10000) { const match = String(value || '').match(/([0-9.]+)\s*(ms|s|m)/i); if (!match) return fallback; const scale = match[2].toLowerCase() === 'm' ? 60000 : match[2].toLowerCase() === 's' ? 1000 : 1; return Math.max(1000, Math.min(maximum, Number(match[1]) * scale)); }

function createPage(content, getApi) {
  const page = document.createElement('section');
  page.className = 'page google-photos-page'; page.hidden = true;
  page.innerHTML = `<header class="photos-topbar"><div class="photos-brand"><span class="photos-brand-mark">${photoIcon}</span><span>Cirava Photos</span></div><div class="photos-top-actions"><button type="button" class="secondary" data-photos-folder>Choose folder</button><button type="button" class="secondary" data-drive-refresh hidden>${driveIcon}<span>Refresh Drive</span></button><button type="button" class="primary photos-add-button" data-photos-files>${uploadIcon}<span>Add photos</span></button><button type="button" class="primary photos-add-button" data-picker-start hidden>${photoIcon}<span>Choose from Google Photos</span></button></div></header>
    <div class="photos-heading"><div><span class="eyebrow" data-photos-eyebrow>UPLOAD FROM THIS DEVICE</span><h1 data-photos-title>Your photos</h1><p data-photos-description>Pick the moments you want to add to your Google Photos library.</p></div></div>
    <nav class="photos-source-tabs" aria-label="Photo source"><button type="button" class="active" data-source="device" aria-pressed="true">This device</button><button type="button" data-source="drive" aria-pressed="false">Google Drive</button><button type="button" data-source="photos" aria-pressed="false">Google Photos</button></nav>
    <div class="photos-toolbar"><div class="photos-filter-tabs" role="group" aria-label="Filter files"><button type="button" class="active" data-filter="all" aria-pressed="true">All</button><button type="button" data-filter="photo" aria-pressed="false">Photos</button><button type="button" data-filter="video" aria-pressed="false">Videos</button><button type="button" data-filter="file" aria-pressed="false">Other files</button></div><div class="photos-search-wrap"><svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.8" stroke="currentColor" stroke-width="1.7"/><path d="m16 16 4.5 4.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/></svg><input type="search" placeholder="Search this collection" aria-label="Search media" data-photos-search></div><button type="button" class="photos-select-all" data-photos-select-all disabled>Select all</button></div>
    <div class="photos-library" data-photos-library aria-live="polite"></div>
    <div class="photos-bottom-note"><span class="photos-lock">✓</span><span data-photos-note><strong>Original quality</strong><br>Photos are uploaded at full resolution and count toward your Google Account storage.</span></div>
    <footer class="google-photos-footer"><span data-photos-status role="status">Choose a source to begin</span><div><button type="button" class="secondary" data-photos-queue disabled>Add to queue</button><button type="button" class="primary" data-photos-action disabled>Upload selected</button></div></footer>`;
  content.append(page);
  const library = page.querySelector('[data-photos-library]');
  const status = page.querySelector('[data-photos-status]');
  const queue = page.querySelector('[data-photos-queue]');
  const action = page.querySelector('[data-photos-action]');
  const selectAll = page.querySelector('[data-photos-select-all]');
  const search = page.querySelector('[data-photos-search]');
  const openUploadPlanner = (paths = []) => window.dispatchEvent(new CustomEvent('cirava:open-upload-planner', { detail: { target: 'photos', paths } }));
  let source = 'device', items = [], selected = new Set(), filter = 'all', drivePageToken = null, driveHasMore = false, driveLoading = false, pickerRun = 0, activePickerId = null, pickerCollectionId = null, pickerNextOffset = null, pickerTotal = 0, searchTimer;
  let activeContextMenu = null, activePreview = null;
  const keyOf = (item) => source === 'device' ? item.path : item.id;
  const showError = (message) => { status.textContent = message; status.classList.add('is-error'); };
  const closeContextMenu = () => {
    if (!activeContextMenu) return;
    document.removeEventListener('pointerdown', activeContextMenu.onOutside, true);
    window.removeEventListener('resize', activeContextMenu.close);
    activeContextMenu.menu.remove(); activeContextMenu = null;
  };
  const closePreview = () => {
    if (!activePreview) return;
    document.removeEventListener('keydown', activePreview.onKeyDown);
    activePreview.overlay.remove(); activePreview = null;
  };
  const showPreview = (item) => {
    const previewUrl = item.preview || item.thumbnailLink;
    if (!previewUrl || !(String(previewUrl).startsWith('data:image/') || /^https:\/\//i.test(previewUrl))) return;
    closeContextMenu(); closePreview();
    const overlay = document.createElement('div'); overlay.className = 'photos-preview-overlay';
    overlay.innerHTML = `<section class="photos-preview-dialog" role="dialog" aria-modal="true" aria-label="Preview ${escapeHtml(item.name)}"><button type="button" class="photos-preview-close" data-preview-close aria-label="Close preview">×</button><img src="${escapeHtml(previewUrl)}" alt="${escapeHtml(item.name)}" referrerpolicy="no-referrer"><p>${escapeHtml(item.name)}</p></section>`;
    document.body.append(overlay);
    const close = () => closePreview();
    const onKeyDown = (event) => { if (event.key === 'Escape') close(); };
    overlay.addEventListener('click', (event) => { if (event.target === overlay) close(); });
    overlay.querySelector('[data-preview-close]').addEventListener('click', close);
    document.addEventListener('keydown', onKeyDown);
    activePreview = { overlay, onKeyDown };
    overlay.querySelector('[data-preview-close]').focus();
  };
  const openContextMenu = (event, item, tile) => {
    event.preventDefault(); closeContextMenu();
    const key = keyOf(item); const isSelected = selected.has(key);
    const previewUrl = item.preview || item.thumbnailLink;
    const previewAvailable = Boolean(previewUrl && (String(previewUrl).startsWith('data:image/') || /^https:\/\//i.test(previewUrl)));
    const externalUrl = source === 'drive' ? item.webViewLink : source === 'photos' ? item.productUrl : null;
    let safeExternalUrl = null;
    try { const parsed = new URL(externalUrl); if (parsed.protocol === 'https:') safeExternalUrl = parsed.href; } catch { /* no safe external target */ }
    const safePhotosUrl = source === 'photos' && safeExternalUrl && new URL(safeExternalUrl).hostname === 'photos.google.com' ? safeExternalUrl : null;
    const menu = document.createElement('div'); menu.className = 'photos-context-menu'; menu.setAttribute('role', 'menu'); menu.setAttribute('aria-label', `Actions for ${item.name}`);
    menu.innerHTML = `${previewAvailable ? '<button type="button" role="menuitem" data-photo-action="preview">Preview</button>' : ''}<button type="button" role="menuitem" class="${isSelected ? 'is-destructive' : ''}" data-photo-action="selection">${isSelected ? 'Remove from selection' : 'Add to selection'}</button>${source === 'photos' ? '<button type="button" role="menuitem" class="is-destructive" data-photo-action="delete-cloud">Delete in Google Photos…</button>' : ''}${safeExternalUrl && source !== 'photos' ? `<a role="menuitem" data-photo-action="open" href="${escapeHtml(safeExternalUrl)}" target="_blank" rel="noopener noreferrer">Open in Google Drive</a>` : ''}`;
    menu.style.left = `${Math.max(8, Math.min(event.clientX || tile.getBoundingClientRect().left, window.innerWidth - 236))}px`;
    menu.style.top = `${Math.max(8, Math.min(event.clientY || tile.getBoundingClientRect().top, window.innerHeight - 120))}px`;
    document.body.append(menu);
    const bounds = menu.getBoundingClientRect();
    menu.style.left = `${Math.max(8, Math.min(bounds.left, window.innerWidth - bounds.width - 8))}px`;
    menu.style.top = `${Math.max(8, Math.min(bounds.top, window.innerHeight - bounds.height - 8))}px`;
    const close = () => closeContextMenu();
    menu.addEventListener('click', (clickEvent) => {
      const action = clickEvent.target.closest('[data-photo-action]')?.dataset.photoAction;
      if (action === 'preview') showPreview(item);
      else if (action === 'selection') {
        close();
        if (isSelected) selected.delete(key); else selected.add(key);
        render();
        status.classList.remove('is-error');
        status.textContent = isSelected ? `Removed ${item.name} from the selection. The source file was not deleted.` : `Added ${item.name} to the selection.`;
      } else if (action === 'delete-cloud') {
        close();
        const api = getApi();
        if (typeof api?.open_google_photos !== 'function') { showError('Open Google Photos in your desktop app to delete this item.'); return; }
        status.textContent = 'Opening Google Photos in your default browser. Review and confirm deletion there.';
        const opening = safePhotosUrl ? api.open_google_photos(safePhotosUrl) : api.open_google_photos();
        Promise.resolve(opening).catch((error) => showError(error instanceof Error ? error.message : 'Could not open Google Photos in your default browser.'));
      }
    });
    menu.addEventListener('keydown', (keyEvent) => {
      const options = [...menu.querySelectorAll('[role="menuitem"]')]; const current = options.indexOf(document.activeElement);
      if (keyEvent.key === 'Escape') { keyEvent.preventDefault(); close(); tile.focus(); }
      else if (keyEvent.key === 'ArrowDown' || keyEvent.key === 'ArrowUp') { keyEvent.preventDefault(); options[(current + (keyEvent.key === 'ArrowDown' ? 1 : options.length - 1)) % options.length]?.focus(); }
      else if (keyEvent.key === 'Home') { keyEvent.preventDefault(); options[0]?.focus(); }
      else if (keyEvent.key === 'End') { keyEvent.preventDefault(); options.at(-1)?.focus(); }
    });
    const onOutside = (outsideEvent) => { if (!menu.contains(outsideEvent.target)) close(); };
    document.addEventListener('pointerdown', onOutside, true); window.addEventListener('resize', close);
    activeContextMenu = { menu, close, onOutside };
    menu.querySelector('[role="menuitem"]')?.focus();
  };
  const empty = (title, description, buttonText, buttonHandler) => {
    library.innerHTML = `<div class="photos-welcome"><div class="photos-welcome-art">${photoIcon}</div><h2>${title}</h2><p>${description}</p>${buttonText ? `<button type="button" class="primary" data-empty-action>${uploadIcon}<span>${buttonText}</span></button>` : ''}</div>`;
    library.querySelector('[data-empty-action]')?.addEventListener('click', buttonHandler);
  };
  const render = () => {
    closeContextMenu();
    const query = search.value.trim().toLocaleLowerCase();
    const visible = items.filter((item) => (filter === 'all' || item.kind === filter) && item.name.toLocaleLowerCase().includes(query));
    const selectedItems = items.filter((item) => selected.has(keyOf(item)));
    const photosSource = source === 'photos';
    const driveSource = source === 'drive';
    queue.hidden = action.hidden = photosSource;
    queue.disabled = action.disabled = selectedItems.length === 0;
    queue.textContent = driveSource ? 'Queue downloads' : 'Add to queue';
    action.textContent = driveSource ? 'Download selected' : 'Upload selected';
    selectAll.disabled = !items.length;
    selectAll.textContent = items.length && selected.size === items.length ? 'Clear selection' : 'Select all';
    if (!status.classList.contains('is-error') && !driveLoading) status.textContent = `${selected.size} selected · ${photosSource && pickerTotal > items.length ? `showing ${items.length} of ${pickerTotal}` : `${items.length} ${items.length === 1 ? 'item' : 'items'} ${photosSource ? 'from your library' : 'ready'}`}`;
    if (!items.length) {
      if (source === 'device') empty('A little room for your memories', 'Choose photos or a folder from this device. They’ll appear here so you can review them before uploading.', 'Choose photos', () => openUploadPlanner());
      else if (source === 'drive') empty('Your Drive, in one view', 'Browse pictures and files across My Drive and shared drives. Results are loaded a page at a time.', driveLoading ? 'Loading Drive…' : 'Load files from Drive', () => void loadDrive(true));
      else empty('Pick from your Google Photos library', 'Google opens its secure picker so you can choose the photos and videos Cirava may see.', 'Choose from Google Photos', () => void startPhotosPicker());
      return;
    }
    if (!visible.length) { library.innerHTML = '<p class="photos-no-results">No matches. Try another name or filter.</p>'; return; }
    const groups = new Map();
    for (const item of visible) { const label = dateGroup(item.modified || Date.now() / 1000); if (!groups.has(label)) groups.set(label, []); groups.get(label).push(item); }
    library.innerHTML = [...groups].map(([label, group]) => `<section class="photos-date-group"><h2>${escapeHtml(label)}<span>${group.length}</span></h2><div class="photos-grid">${group.map((item) => {
      const isSelected = selected.has(keyOf(item));
      const safeName = escapeHtml(item.name);
      const imagePreview = item.preview || (item.thumbnailLink ? item.thumbnailLink : null);
      const glyph = item.kind === 'video' ? playIcon : item.kind === 'file' ? driveIcon : photoIcon;
      const picture = imagePreview ? `<img src="${escapeHtml(imagePreview)}" alt="" loading="lazy" draggable="false" referrerpolicy="no-referrer">` : `<div class="photos-fallback ${item.kind}">${glyph}</div>`;
      const encoded = encodeURIComponent(keyOf(item));
      return `<button type="button" class="photos-tile${isSelected ? ' is-selected' : ''}${item.kind === 'file' ? ' is-file' : ''}" data-photo-key="${encoded}" aria-pressed="${isSelected}" aria-haspopup="menu" aria-label="${isSelected ? 'Selected' : 'Select'} ${safeName}; press Shift+F10 for actions"><span class="photos-thumb">${picture}${item.kind === 'video' ? `<span class="photos-video-badge">${playIcon}</span>` : ''}<span class="photos-check" aria-hidden="true">✓</span></span><span class="photos-caption"><span title="${safeName}">${safeName}</span><small>${formatBytes(Number(item.size) || 0)}</small></span></button>`;
    }).join('')}</div></section>`).join('') + (source === 'drive' && driveHasMore ? '<button class="photos-load-more secondary" type="button" data-drive-more>Load more from Drive</button>' : source === 'photos' && pickerNextOffset !== null ? '<button class="photos-load-more secondary" type="button" data-photos-more>Load more from Google Photos</button>' : '');
    library.querySelectorAll('[data-photo-key]').forEach((button) => {
      const item = items.find((entry) => keyOf(entry) === decodeURIComponent(button.dataset.photoKey));
      button.addEventListener('contextmenu', (event) => { if (item) openContextMenu(event, item, button); });
      button.addEventListener('keydown', (event) => { if (item && (event.key === 'ContextMenu' || event.key === 'Apps' || (event.shiftKey && event.key === 'F10'))) openContextMenu({ preventDefault: () => event.preventDefault(), clientX: 0, clientY: 0 }, item, button); });
      button.addEventListener('click', () => {
      const key = decodeURIComponent(button.dataset.photoKey);
      if (selected.has(key)) selected.delete(key); else selected.add(key);
      render();
    });
    });
    library.querySelectorAll('.photos-thumb img').forEach((image) => image.addEventListener('error', () => {
      const fallback = document.createElement('div'); fallback.className = `photos-fallback ${image.closest('.photos-tile')?.classList.contains('is-file') ? 'file' : 'photo'}`; fallback.innerHTML = fallback.classList.contains('file') ? driveIcon : photoIcon; image.replaceWith(fallback);
    }, { once: true }));
    library.querySelector('[data-drive-more]')?.addEventListener('click', () => void loadDrive(false));
    library.querySelector('[data-photos-more]')?.addEventListener('click', () => void loadPhotosMore());
  };
  const chooseLocal = async (kind) => {
    const api = getApi(); const picker = kind === 'files' ? api?.pick_files : api?.pick_folder;
    if (typeof picker !== 'function') { showError('The local file picker is available in the Cirava desktop app.'); return; }
    status.textContent = 'Choose media in the file picker…'; status.classList.remove('is-error');
    try {
      const paths = await picker.call(api) || []; if (!paths.length) { status.textContent = 'Nothing selected.'; return; }
      if (typeof api.get_google_photos_local_previews !== 'function') throw new Error('Media previews are unavailable. Restart Cirava and try again.');
      status.textContent = 'Gathering your photos…'; items = await api.get_google_photos_local_previews(paths, 300);
      if (!items.length) throw new Error('No supported photos or videos were found in that selection.');
      items.sort((a, b) => b.modified - a.modified); selected = new Set(items.map((item) => item.path)); search.value = ''; render();
      if (items.length >= 300) status.textContent = 'Showing the first 300 items. Choose a smaller folder to review individual files.';
    } catch (error) { showError(error instanceof Error ? error.message : 'Could not read local media.'); }
  };
  const loadDrive = async (reset) => {
    const api = getApi(); if (typeof api?.list_drive_gallery_files !== 'function') { showError('Drive browsing is unavailable. Restart Cirava and reconnect Google.'); return; }
    if (driveLoading) return;
    if (reset) { items = []; selected.clear(); drivePageToken = null; driveHasMore = false; }
    driveLoading = true; status.classList.remove('is-error'); status.textContent = 'Loading files from Drive…'; render();
    try {
      const page = await api.list_drive_gallery_files(drivePageToken, search.value.trim(), false, 100);
      const files = (page.files || []).filter((file) => file.mimeType !== 'application/vnd.google-apps.folder').map((file) => ({ ...file, modified: Date.parse(file.modifiedTime || '') / 1000 || Date.now() / 1000, size: Number(file.size) || 0, kind: mediaKind(file.mimeType), thumbnailLink: file.thumbnailLink || null }));
      const combined = reset ? files : [...items, ...files]; items = [...new Map(combined.map((item) => [item.id, item])).values()];
      drivePageToken = page.nextPageToken || null; driveHasMore = Boolean(drivePageToken); items.sort((a, b) => b.modified - a.modified); selected = new Set(items.map((item) => item.id));
      if (!items.length) empty('No files found in Drive', 'Try a different search, or refresh to check Drive again.', null, null);
    } catch (error) { showError(error instanceof Error ? error.message : 'Could not load Drive files.'); }
    finally { driveLoading = false; render(); }
  };
  const startPhotosPicker = async () => {
    const api = getApi(); if (typeof api?.start_google_photos_picker !== 'function') { showError('Google Photos Picker is unavailable. Reconnect Google and check that the Photos Picker API is enabled.'); return; }
    status.classList.remove('is-error'); status.textContent = 'Opening Google Photos…';
    try {
      const run = ++pickerRun; const session = await api.start_google_photos_picker(); activePickerId = session.session_id;
      status.textContent = 'Choose photos in the Google Photos window. Cirava will load your selection here.';
      const interval = durationMs(session.polling_config?.pollInterval);
      const deadline = Date.now() + durationMs(session.polling_config?.timeoutIn, 600000, 900000);
      while (run === pickerRun && Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, interval)); if (run !== pickerRun) return;
        const result = await api.get_google_photos_picker_selection(session.session_id);
        if (result.ready) {
          items = (result.items || []).map((item) => ({ ...item, modified: Number(item.modified) || Date.now() / 1000, size: Number(item.size) || 0 }));
          items.sort((a, b) => b.modified - a.modified); selected = new Set(items.map((item) => item.id));
          pickerCollectionId = result.collection_id; pickerNextOffset = result.next_offset ?? null; pickerTotal = result.total || items.length; render();
          status.textContent = `${pickerTotal} item${pickerTotal === 1 ? '' : 's'} selected from Google Photos${pickerNextOffset !== null ? ` · showing the first ${items.length}` : ''}.`;
          activePickerId = null;
          return;
        }
      }
      if (run === pickerRun) { if (activePickerId) void api.cancel_google_photos_picker?.(activePickerId); activePickerId = null; showError('The Google Photos selection timed out. Choose Google Photos again to start a new session.'); }
    } catch (error) { if (activePickerId) void api?.cancel_google_photos_picker?.(activePickerId); activePickerId = null; showError(error instanceof Error ? error.message : 'Could not read the Google Photos selection.'); }
  };
  const loadPhotosMore = async () => {
    const api = getApi(); if (!pickerCollectionId || pickerNextOffset === null || typeof api?.get_google_photos_picker_page !== 'function') return;
    const button = library.querySelector('[data-photos-more]'); if (button) { button.disabled = true; button.textContent = 'Loading more…'; }
    try {
      const page = await api.get_google_photos_picker_page(pickerCollectionId, pickerNextOffset, 100);
      const newItems = (page.items || []).map((item) => ({ ...item, modified: Number(item.modified) || Date.now() / 1000, size: Number(item.size) || 0 }));
      items = [...items, ...newItems]; newItems.forEach((item) => selected.add(item.id));
      pickerNextOffset = page.next_offset ?? null; pickerTotal = page.total || pickerTotal; items.sort((a, b) => b.modified - a.modified); render();
    } catch (error) { if (button) { button.disabled = false; button.textContent = 'Load more from Google Photos'; } showError(error instanceof Error ? error.message : 'Could not load more photos.'); }
  };
  const enqueue = async (startImmediately) => {
    const api = getApi(); const chosen = items.filter((item) => selected.has(keyOf(item)));
    if (source === 'device') { openUploadPlanner(chosen.map((item) => item.path)); return; }
    queue.disabled = action.disabled = true; status.classList.remove('is-error');
    try {
      let result;
      const directories = await api.pick_folder(); const directory = directories?.[0]; if (!directory) throw new Error('Choose a download folder first.');
      result = await api.create_drive_gallery_downloads(chosen, directory, startImmediately);
      if (!result.records?.length) throw new Error(result.skipped ? 'These Google Docs, Sheets, or Slides need export conversion before they can be downloaded here.' : 'No downloadable Drive files were selected.');
      const skippedMessage = result.skipped ? ` · ${result.skipped} Google-native item${result.skipped === 1 ? '' : 's'} need export conversion` : '';
      status.textContent = `${(result.records || result).length} item${(result.records || result).length === 1 ? '' : 's'} ${startImmediately ? 'started' : 'added to the queue'}${skippedMessage}; opening Transfers…`;
      document.querySelectorAll('.nav-item').forEach((item) => { if (item.textContent?.replace(/\s+/g, ' ').trim() === 'Transfers') item.click(); });
    } catch (error) { render(); showError(error instanceof Error ? error.message : 'Could not add the selection to transfers.'); }
  };
  page.querySelector('[data-photos-files]').addEventListener('click', () => openUploadPlanner());
  page.querySelector('[data-photos-folder]').addEventListener('click', () => void chooseLocal('folder'));
  page.querySelector('[data-drive-refresh]').addEventListener('click', () => void loadDrive(true));
  page.querySelector('[data-picker-start]').addEventListener('click', () => void startPhotosPicker());
  queue.addEventListener('click', () => void enqueue(false)); action.addEventListener('click', () => void enqueue(true));
  search.addEventListener('input', () => { if (source === 'drive') { clearTimeout(searchTimer); searchTimer = setTimeout(() => void loadDrive(true), 350); } else render(); });
  page.querySelectorAll('[data-filter]').forEach((button) => button.addEventListener('click', () => {
    filter = button.dataset.filter; page.querySelectorAll('[data-filter]').forEach((tab) => { const active = tab === button; tab.classList.toggle('active', active); tab.setAttribute('aria-pressed', String(active)); }); render();
  }));
  selectAll.addEventListener('click', () => { selected = selected.size === items.length ? new Set() : new Set(items.map((item) => keyOf(item))); render(); });
  page.querySelectorAll('[data-source]').forEach((button) => button.addEventListener('click', () => {
    const next = button.dataset.source; if (source === 'photos' && next !== 'photos') { pickerRun++; if (activePickerId) void getApi()?.cancel_google_photos_picker?.(activePickerId); activePickerId = null; }
    source = next; items = []; selected.clear(); pickerCollectionId = null; pickerNextOffset = null; pickerTotal = 0; search.value = ''; filter = 'all';
    page.querySelectorAll('[data-source]').forEach((tab) => { const active = tab === button; tab.classList.toggle('active', active); tab.setAttribute('aria-pressed', String(active)); });
    page.querySelector('[data-photos-eyebrow]').textContent = source === 'device' ? 'UPLOAD FROM THIS DEVICE' : source === 'drive' ? 'YOUR GOOGLE DRIVE' : 'YOUR GOOGLE PHOTOS';
    page.querySelector('[data-photos-title]').textContent = source === 'device' ? 'Your photos' : source === 'drive' ? 'Drive library' : 'Google Photos';
    page.querySelector('[data-photos-description]').textContent = source === 'device' ? 'Pick the moments you want to add to your Google Photos library.' : source === 'drive' ? 'Search across My Drive and shared drives, not just the folder you have open.' : 'Choose photos in Google’s secure picker and browse them here.';
    page.querySelector('[data-photos-folder]').hidden = source !== 'device'; page.querySelector('[data-photos-files]').hidden = source !== 'device'; page.querySelector('[data-drive-refresh]').hidden = source !== 'drive'; page.querySelector('[data-picker-start]').hidden = source !== 'photos';
    page.querySelector('[data-photos-note]').innerHTML = source === 'drive' ? '<strong>Files stay in your Drive</strong><br>Download selections to this device. Drive results include accessible shared drives; use search and Load more to explore.' : source === 'photos' ? '<strong>You stay in control</strong><br>Google shares only the items you choose. Picker preview links expire, so choose again later to refresh them.' : '<strong>Original quality</strong><br>Photos are uploaded at full resolution and count toward your Google Account storage.';
    if (source === 'device') empty('A little room for your memories', 'Choose photos or a folder from this device. They’ll appear here so you can review them before uploading.', 'Choose photos', () => openUploadPlanner());
    if (source === 'drive') { empty('Your Drive, in one view', 'Browse pictures and files across My Drive and shared drives. Results are loaded a page at a time.', 'Load files from Drive', () => void loadDrive(true)); void loadDrive(true); }
    if (source === 'photos') empty('Pick from your Google Photos library', 'Google opens its secure picker so you can choose the photos and videos Cirava may see.', 'Choose from Google Photos', () => void startPhotosPicker());
    render();
  }));
  empty('A little room for your memories', 'Choose photos or a folder from this device. They’ll appear here so you can review them before uploading.', 'Choose photos', () => openUploadPlanner());
  return page;
}

export function getGooglePhotosNavigationPlacement(sidebar) {
  if (!sidebar) return null;
  const navItems = Array.from(sidebar.querySelectorAll('.nav-item'));
  const labelOf = (item) => item.textContent?.replace(/\s+/g, ' ').trim();
  const driveNav = navItems.find((item) => labelOf(item) === 'Drive');
  if (driveNav) return { anchor: driveNav, position: 'after', className: driveNav.className };

  const settingsNav = navItems.find((item) => labelOf(item) === 'Settings');
  if (settingsNav) return { anchor: settingsNav, position: 'before', className: settingsNav.className };

  const lastNav = navItems.at(-1);
  return lastNav
    ? { anchor: lastNav, position: 'after', className: lastNav.className }
    : { anchor: null, position: 'append', className: 'nav-item' };
}

export function installGooglePhotosPage(getApi = () => window.pywebview?.api) {
  const sidebar = document.querySelector('.sidebar');
  const content = document.querySelector('.main .content'); if (!sidebar || !content) return;
  const placement = getGooglePhotosNavigationPlacement(sidebar);
  let nav = sidebar.querySelector('[data-google-photos-nav]');
  if (!nav) {
    nav = document.createElement('button'); nav.type = 'button'; nav.className = placement?.className || 'nav-item';
    nav.classList.remove('active'); nav.dataset.googlePhotosNav = 'true'; nav.setAttribute('aria-label', 'Google Photos');
    nav.innerHTML = `<span class="nav-icon">${photoIcon}</span><span class="nav-title">Google Photos</span>`;
    if (placement?.position === 'after') placement.anchor.insertAdjacentElement('afterend', nav);
    else if (placement?.position === 'before') placement.anchor.insertAdjacentElement('beforebegin', nav);
    else sidebar.append(nav);
  }
  let siblingVisibility = null;
  const activate = () => { let page = content.querySelector('.google-photos-page'); if (!page) page = createPage(content, getApi); if (!siblingVisibility) siblingVisibility = new Map(Array.from(content.children).filter((child) => child !== page).map((child) => [child, child.hidden])); for (const child of Array.from(content.children)) child.hidden = child !== page; page.hidden = false; sidebar.querySelectorAll('.nav-item').forEach((item) => item.classList.toggle('active', item === nav)); nav.setAttribute('aria-current', 'page'); };
  const deactivate = () => { const page = content.querySelector('.google-photos-page'); if (!page) return; page.hidden = true; for (const [child, wasHidden] of siblingVisibility || []) child.hidden = wasHidden; siblingVisibility = null; nav.classList.remove('active'); nav.removeAttribute('aria-current'); };
  if (nav.dataset.photosHandler !== 'true') { nav.dataset.photosHandler = 'true'; nav.addEventListener('click', (event) => { event.preventDefault(); event.stopPropagation(); activate(); }); }
  if (document.documentElement.dataset.photosRouteHandler !== 'true') { document.documentElement.dataset.photosRouteHandler = 'true'; document.addEventListener('click', (event) => { const target = event.target instanceof Element ? event.target.closest('.nav-item') : null; if (target && !target.hasAttribute('data-google-photos-nav')) deactivate(); }, true); }
}
