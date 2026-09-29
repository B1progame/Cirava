export function installSharedDriveControls(host, getApi, onDestination, onError = () => {}) {
  if (!host || host.querySelector('[data-shared-drive-controls]')) return;
  const wrap = document.createElement('div');
  wrap.className = 'shared-drive-controls';
  wrap.dataset.sharedDriveControls = 'true';
  const label = document.createElement('label');
  label.textContent = 'Drive location';
  const picker = document.createElement('div');
  picker.className = 'shared-drive-picker';
  const trigger = document.createElement('button');
  trigger.type = 'button';
  trigger.className = 'shared-drive-select';
  trigger.setAttribute('aria-label', 'Choose My Drive or a shared drive');
  trigger.setAttribute('aria-haspopup', 'listbox');
  trigger.setAttribute('aria-expanded', 'false');
  trigger.textContent = 'My Drive';
  const menu = document.createElement('div');
  menu.className = 'shared-drive-menu';
  menu.id = `shared-drive-options-${Date.now()}`;
  menu.setAttribute('role', 'listbox');
  menu.setAttribute('aria-label', 'Drive location');
  menu.hidden = true;
  trigger.setAttribute('aria-controls', menu.id);
  picker.append(trigger);
  label.append(picker);
  const linkDetails = document.createElement('details');
  linkDetails.className = 'shared-drive-link-details';
  const linkSummary = document.createElement('summary');
  linkSummary.textContent = 'Use a shared-drive or folder link';
  const linkRow = document.createElement('div');
  linkRow.className = 'shared-drive-link-row';
  const input = document.createElement('input');
  input.type = 'url';
  input.placeholder = 'Paste a shared-drive or folder link';
  input.setAttribute('aria-label', 'Shared-drive or folder link');
  const useLink = document.createElement('button');
  useLink.type = 'button';
  useLink.className = 'secondary';
  useLink.textContent = 'Use link';
  linkRow.append(input, useLink);
  const note = document.createElement('small');
  note.className = 'shared-drive-note';
  note.textContent = 'Shared-drive access depends on your Google account membership.';
  linkDetails.append(linkSummary, linkRow, note);
  wrap.append(label, linkDetails);
  const folderList = host.querySelector('.cirava-upload-folders');
  if (folderList) host.insertBefore(wrap, folderList);
  else host.append(wrap);
  (host.closest('.cirava-direct-upload-backdrop') || document.body).append(menu);

  const options = [{ id: '', name: 'My Drive', parentId: 'root' }];
  let selectedId = '';
  let activeIndex = 0;
  const closeMenu = ({ restoreFocus = false } = {}) => {
    menu.hidden = true;
    trigger.setAttribute('aria-expanded', 'false');
    if (restoreFocus) trigger.focus();
  };
  const renderOptions = () => {
    menu.replaceChildren(...options.map((drive, index) => {
      const option = document.createElement('button');
      option.type = 'button';
      option.className = 'shared-drive-option';
      option.setAttribute('role', 'option');
      option.setAttribute('aria-selected', String(drive.id === selectedId));
      option.tabIndex = -1;
      option.textContent = drive.name;
      option.addEventListener('click', () => {
        selectedId = drive.id;
        trigger.textContent = drive.name;
        closeMenu();
        onDestination({ driveId: drive.id || null, parentId: drive.id || 'root', name: drive.id ? `Shared drive / ${drive.name}` : 'My Drive / Workspace' });
      });
      option.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') { event.preventDefault(); closeMenu({ restoreFocus: true }); return; }
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Home' || event.key === 'End') {
          event.preventDefault();
          activeIndex = event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1 : (activeIndex + (event.key === 'ArrowDown' ? 1 : -1) + options.length) % options.length;
          menu.querySelectorAll('[role="option"]')[activeIndex]?.focus();
        }
      });
      return option;
    }));
  };
  renderOptions();
  const openMenu = () => {
    const bounds = trigger.getBoundingClientRect();
    menu.style.left = `${Math.round(bounds.left)}px`;
    menu.style.top = `${Math.round(bounds.bottom + 5)}px`;
    menu.style.width = `${Math.round(bounds.width)}px`;
    menu.hidden = false;
    trigger.setAttribute('aria-expanded', 'true');
    activeIndex = Math.max(0, options.findIndex((drive) => drive.id === selectedId));
    menu.querySelectorAll('[role="option"]')[activeIndex]?.focus();
  };
  trigger.addEventListener('click', () => menu.hidden ? openMenu() : closeMenu());
  trigger.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openMenu(); }
    if (event.key === 'Escape' && !menu.hidden) closeMenu();
  });
  const dismissOutside = (event) => {
    if (!wrap.isConnected) { document.removeEventListener('pointerdown', dismissOutside); menu.remove(); return; }
    if (!wrap.contains(event.target) && !menu.contains(event.target)) closeMenu();
  };
  document.addEventListener('pointerdown', dismissOutside);
  const dismissOnViewportChange = () => closeMenu();
  window.addEventListener('resize', dismissOnViewportChange, { passive: true });
  window.addEventListener('scroll', dismissOnViewportChange, { passive: true, capture: true });
  const api = getApi?.();
  if (typeof api?.list_shared_drives === 'function') {
    Promise.resolve(api.list_shared_drives()).then((result) => {
      for (const drive of result?.drives || []) {
        options.push({ id: drive.id, name: drive.name || 'Shared drive', parentId: drive.id });
      }
      renderOptions();
    }).catch((error) => onError(error instanceof Error ? error.message : 'Could not list shared drives.'));
  }
  useLink.addEventListener('click', async () => {
    if (!input.value.trim()) { onError('Paste a Google Drive shared-drive or folder link first.'); return; }
    const currentApi = getApi?.();
    if (typeof currentApi?.resolve_shared_drive_link !== 'function') { onError('Shared-drive links are available in the Cirava desktop app.'); return; }
    useLink.disabled = true;
    try {
      const target = await currentApi.resolve_shared_drive_link(input.value.trim());
      selectedId = target.drive_id;
      if (!options.some((drive) => drive.id === target.drive_id)) {
        options.push({ id: target.drive_id, name: `Shared drive / ${target.name}`, parentId: target.parent_id });
      }
      renderOptions();
      trigger.textContent = target.name;
      closeMenu();
      onDestination({ driveId: target.drive_id, parentId: target.parent_id, name: target.name });
      input.value = '';
      note.textContent = `Destination selected: ${target.name}`;
    } catch (error) {
      onError(error instanceof Error ? error.message : 'That link could not be used as a shared-drive destination.');
    } finally {
      useLink.disabled = false;
    }
  });
}
