export function runWithDriveFolderName(name, action, targetWindow = window) {
  const originalPrompt = targetWindow.prompt;
  let intercepted = false;
  const customPrompt = function (message, fallback) {
    if (!intercepted && String(message) === 'Create folder in this folder') {
      intercepted = true;
      return name;
    }
    return typeof originalPrompt === 'function'
      ? originalPrompt.call(targetWindow, message, fallback)
      : null;
  };

  try {
    targetWindow.prompt = customPrompt;
    if (targetWindow.prompt !== customPrompt) return false;
    action();
  } finally {
    targetWindow.prompt = originalPrompt;
  }
  return intercepted;
}

function makeElement(documentObject, tag, className, text) {
  const element = documentObject.createElement(tag);
  if (className) element.className = className;
  if (text != null) element.textContent = text;
  return element;
}

export function installDriveCreateDialog(documentObject = document, windowObject = window) {
  if (documentObject.documentElement.dataset.driveCreateDialogInstalled === 'true') return;
  documentObject.documentElement.dataset.driveCreateDialogInstalled = 'true';
  let forwardingCreateClick = false;

  documentObject.addEventListener('click', (event) => {
    const target = event.target;
    if (!(target instanceof windowObject.Element)) return;
    const folderButton = target.closest('.drive-create-menu button, .drive-context-menu button');
    if (!folderButton || !/^new folder$/i.test(folderButton.textContent?.trim() || '')) return;
    if (forwardingCreateClick) {
      forwardingCreateClick = false;
      return;
    }

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    if (documentObject.querySelector('.cirava-folder-name-backdrop')) return;

    const menu = folderButton.closest('.drive-create-menu, .drive-context-menu');
    const context = menu?.querySelector('.context-menu-title, .drive-create-section-title')?.textContent?.trim() || 'the current Drive folder';
    const backdrop = makeElement(documentObject, 'div', 'cirava-folder-name-backdrop');
    backdrop.setAttribute('role', 'presentation');
    const dialog = makeElement(documentObject, 'section', 'cirava-folder-name-dialog');
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('aria-labelledby', 'cirava-folder-name-title');

    const header = makeElement(documentObject, 'header', 'cirava-folder-name-header');
    const icon = makeElement(documentObject, 'span', 'cirava-folder-name-icon');
    icon.setAttribute('aria-hidden', 'true');
    icon.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 6.5a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="M12 10v6M9 13h6"/></svg>';
    const headingGroup = makeElement(documentObject, 'div');
    headingGroup.append(
      makeElement(documentObject, 'span', 'cirava-folder-name-kicker', 'CREATE IN DRIVE'),
      makeElement(documentObject, 'h2', '', 'Give this folder a name.'),
    );
    headingGroup.querySelector('h2').id = 'cirava-folder-name-title';
    const closeButton = makeElement(documentObject, 'button', 'cirava-folder-name-close', '×');
    closeButton.type = 'button';
    closeButton.setAttribute('aria-label', 'Close');
    header.append(icon, headingGroup, closeButton);

    const description = makeElement(documentObject, 'p', 'cirava-folder-name-description');
    description.textContent = `This folder will be created in ${context.replace(/^create in\s+/i, '')}.`;
    const form = makeElement(documentObject, 'form', 'cirava-folder-name-form');
    const label = makeElement(documentObject, 'label', '', 'Folder name');
    label.htmlFor = 'cirava-folder-name-input';
    const input = makeElement(documentObject, 'input', 'cirava-folder-name-input');
    input.id = 'cirava-folder-name-input';
    input.type = 'text';
    input.name = 'folderName';
    input.maxLength = 255;
    input.required = true;
    input.autocomplete = 'off';
    input.placeholder = 'e.g. Project files';
    const error = makeElement(documentObject, 'span', 'cirava-folder-name-error');
    error.setAttribute('role', 'alert');
    form.append(label, input, error);

    const footer = makeElement(documentObject, 'footer', 'cirava-folder-name-footer');
    const cancelButton = makeElement(documentObject, 'button', 'secondary', 'Cancel');
    cancelButton.type = 'button';
    const createButton = makeElement(documentObject, 'button', 'primary', 'Create folder');
    createButton.type = 'submit';
    footer.append(cancelButton, createButton);
    dialog.append(header, description, form, footer);
    backdrop.append(dialog);
    documentObject.body.append(backdrop);

    const close = (closeMenu) => {
      backdrop.remove();
      if (closeMenu && folderButton.isConnected) {
        menu?.querySelector('.create-trigger')?.click();
      }
      if (folderButton.isConnected) folderButton.focus();
    };
    closeButton.addEventListener('click', () => close(true));
    cancelButton.addEventListener('click', () => close(true));
    backdrop.addEventListener('click', (backdropEvent) => {
      if (backdropEvent.target === backdrop) close(true);
    });
    dialog.addEventListener('keydown', (keyEvent) => {
      if (keyEvent.key === 'Escape') { keyEvent.preventDefault(); close(true); }
    });
    input.addEventListener('input', () => { error.textContent = ''; });
    form.addEventListener('submit', (submitEvent) => {
      submitEvent.preventDefault();
      const name = input.value.trim();
      if (!name) {
        error.textContent = 'Enter a folder name to continue.';
        input.focus();
        return;
      }
      if (!folderButton.isConnected) {
        error.textContent = 'The Drive menu changed. Close this dialog and try again.';
        return;
      }
      createButton.disabled = true;
      createButton.textContent = 'Creating…';
      forwardingCreateClick = true;
      let intercepted = false;
      try {
        intercepted = runWithDriveFolderName(name, () => folderButton.click(), windowObject);
      } catch {
        intercepted = false;
      } finally {
        forwardingCreateClick = false;
      }
      if (!intercepted) {
        createButton.disabled = false;
        createButton.textContent = 'Create folder';
        error.textContent = 'Could not start folder creation. Please try again.';
        return;
      }
      close(false);
    });
    windowObject.requestAnimationFrame(() => input.focus());
  }, true);
}
