export function createDriveSelection() {
  const selected = new Set();
  let anchor = null;
  let modeEnabled = false;

  return {
    setMode(enabled) {
      modeEnabled = Boolean(enabled);
      if (!modeEnabled) this.clear();
      return modeEnabled;
    },
    isModeEnabled() { return modeEnabled; },
    toggle(id, orderedIds, { additive = false, range = false } = {}) {
      const ids = Array.from(orderedIds || []);
      if (range && anchor && ids.includes(anchor) && ids.includes(id)) {
        if (!additive) selected.clear();
        const start = ids.indexOf(anchor);
        const end = ids.indexOf(id);
        ids.slice(Math.min(start, end), Math.max(start, end) + 1).forEach((item) => selected.add(item));
      } else if (additive) {
        selected.has(id) ? selected.delete(id) : selected.add(id);
        anchor = id;
      } else {
        selected.clear();
        selected.add(id);
        anchor = id;
      }
      return this.getSelected();
    },
    selectAll(ids) {
      selected.clear();
      Array.from(ids || []).forEach((id) => selected.add(id));
      anchor = Array.from(ids || []).at(-1) || null;
      return this.getSelected();
    },
    toggleAll(ids) {
      const visible = Array.from(ids || []);
      const allSelected = visible.length > 0 && visible.every((id) => selected.has(id));
      visible.forEach((id) => allSelected ? selected.delete(id) : selected.add(id));
      anchor = allSelected ? null : visible.at(-1) || null;
      return this.getSelected();
    },
    prune(ids) {
      const visible = new Set(ids || []);
      selected.forEach((id) => { if (!visible.has(id)) selected.delete(id); });
      if (anchor && !visible.has(anchor)) anchor = null;
      return this.getSelected();
    },
    clear() {
      selected.clear();
      anchor = null;
      return [];
    },
    getSelected() { return Array.from(selected); },
  };
}

const driveSelection = createDriveSelection();
let previousView = null;

export function toggleDriveRowSelection(row) {
  const table = row?.closest?.('.file-table');
  if (!table) return false;
  if (!row.dataset.ciravaSelectionKey) enhanceDriveMultiSelect();
  const key = row.dataset.ciravaSelectionKey;
  if (!key) return false;
  if (!driveSelection.isModeEnabled()) driveSelection.setMode(true);
  const orderedIds = Array.from(table.querySelectorAll('.file-row')).map((item) => item.dataset.ciravaSelectionKey || '');
  driveSelection.toggle(key, orderedIds, { additive: true });
  enhanceDriveMultiSelect();
  return true;
}

function selectionKey(row, duplicateIndex) {
  const name = row.querySelector('.file-name strong')?.textContent?.trim() || '';
  const modified = row.children[2]?.textContent?.trim() || '';
  const size = row.children[1]?.textContent?.trim() || '';
  const kind = row.querySelector('.folder-count')?.textContent?.trim() || 'file';
  return JSON.stringify([name, modified, size, kind, duplicateIndex]);
}

export function enhanceDriveMultiSelect() {
  const table = document.querySelector('.file-table');
  const toolbar = document.querySelector('.drive-toolbar');
  let modeButton = toolbar?.querySelector('button[data-cirava-selection-mode]');
  if (toolbar && !modeButton) {
    modeButton = document.createElement('button');
    modeButton.type = 'button';
    modeButton.className = 'secondary cirava-selection-mode';
    modeButton.dataset.ciravaSelectionMode = 'true';
    modeButton.addEventListener('click', () => {
      driveSelection.setMode(!driveSelection.isModeEnabled());
      enhanceDriveMultiSelect();
    });
    const createControl = toolbar.querySelector('.drive-create-control');
    if (createControl) createControl.before(modeButton);
    else toolbar.append(modeButton);
  }
  if (!table) {
    document.querySelector('[data-cirava-selection-bar]')?.remove();
    previousView = null;
    if (!toolbar) driveSelection.setMode(false);
    if (modeButton) {
      modeButton.textContent = driveSelection.isModeEnabled() ? 'Done selecting' : 'Select mode';
      modeButton.setAttribute('aria-pressed', String(driveSelection.isModeEnabled()));
      modeButton.disabled = false;
      modeButton.title = '';
    }
    return;
  }
  const modeEnabled = driveSelection.isModeEnabled();
  if (modeButton) {
    modeButton.textContent = modeEnabled ? 'Done selecting' : 'Select mode';
    modeButton.setAttribute('aria-pressed', String(modeEnabled));
    modeButton.disabled = table.querySelectorAll('.file-row').length === 0;
    modeButton.title = modeButton.disabled ? 'There are no visible items to select' : '';
  }
  table.classList.toggle('cirava-select-mode', modeEnabled);

  const breadcrumb = document.querySelector('.breadcrumbs')?.textContent?.trim() || 'root';
  if (previousView !== null && previousView !== breadcrumb) driveSelection.clear();
  previousView = breadcrumb;

  const rows = Array.from(table.querySelectorAll('.file-row'));
  const duplicateCounts = new Map();
  const rowEntries = rows.map((row) => {
    const base = [row.querySelector('.file-name strong')?.textContent?.trim() || '', row.children[2]?.textContent?.trim() || '', row.children[1]?.textContent?.trim() || '', row.querySelector('.folder-count')?.textContent?.trim() || 'file'].join('\u0000');
    const index = duplicateCounts.get(base) || 0;
    duplicateCounts.set(base, index + 1);
    const key = selectionKey(row, index);
    row.dataset.ciravaSelectionKey = key;
    return { row, key };
  });
  const visibleKeys = rowEntries.map(({ key }) => key);
  driveSelection.prune(visibleKeys);

  let bar = document.querySelector('[data-cirava-selection-bar]');
  if (!bar) {
    bar = document.createElement('div');
    bar.className = 'cirava-selection-bar';
    bar.dataset.ciravaSelectionBar = 'true';
    bar.innerHTML = '<span class="cirava-selection-count" aria-live="polite"></span><button type="button" class="cirava-selection-clear">Clear selection</button>';
    table.before(bar);
    bar.querySelector('button')?.addEventListener('click', () => { driveSelection.clear(); enhanceDriveMultiSelect(); });
  } else if (bar.nextElementSibling !== table) {
    table.before(bar);
  }

  const header = table.querySelector('.table-head');
  if (header && !header.querySelector('[data-cirava-select-all]')) {
    const selectAll = document.createElement('input');
    selectAll.type = 'checkbox';
    selectAll.className = 'cirava-select-box cirava-select-all';
    selectAll.dataset.ciravaSelectAll = 'true';
    selectAll.setAttribute('aria-label', 'Select all visible Drive items');
    header.firstElementChild?.prepend(selectAll);
    selectAll.addEventListener('change', () => {
      const currentKeys = Array.from(table.querySelectorAll('.file-row')).map((row) => row.dataset.ciravaSelectionKey || '');
      driveSelection.toggleAll(currentKeys);
      enhanceDriveMultiSelect();
    });
  }

  rowEntries.forEach(({ row, key }) => {
    const nameCell = row.querySelector<HTMLElement>('.file-name');
    if (!nameCell) return;
    let checkbox = nameCell.querySelector('[data-cirava-select-item]');
    if (!checkbox) {
      checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.className = 'cirava-select-box';
      checkbox.dataset.ciravaSelectItem = 'true';
      checkbox.setAttribute('aria-label', 'Select item');
      nameCell.prepend(checkbox);
      checkbox.addEventListener('click', (event) => { event.stopPropagation(); checkbox.dataset.shiftSelection = String(event.shiftKey); });
      checkbox.addEventListener('change', (event) => {
        const nativeEvent = event;
        const selected = driveSelection.getSelected().includes(row.dataset.ciravaSelectionKey || '');
        const currentKeys = Array.from(table.querySelectorAll('.file-row')).map((item) => item.dataset.ciravaSelectionKey || '');
        if (checkbox.checked !== selected) driveSelection.toggle(row.dataset.ciravaSelectionKey || '', currentKeys, { additive: true, range: nativeEvent.shiftKey || checkbox.dataset.shiftSelection === 'true' });
        checkbox.dataset.shiftSelection = 'false';
        enhanceDriveMultiSelect();
      });
    }
    checkbox.setAttribute('aria-label', `Select ${row.querySelector('.file-name strong')?.textContent?.trim() || 'item'}`);
    checkbox.checked = driveSelection.getSelected().includes(key);
    if (!row.dataset.ciravaSelectionBound) {
      row.dataset.ciravaSelectionBound = 'true';
      row.addEventListener('click', (event) => {
        if (!driveSelection.isModeEnabled()) return;
        if (event.target.closest('button, input, a, [role="button"]')) return;
        event.preventDefault();
        event.stopPropagation();
        const currentKeys = Array.from(table.querySelectorAll('.file-row')).map((item) => item.dataset.ciravaSelectionKey || '');
        driveSelection.toggle(row.dataset.ciravaSelectionKey || '', currentKeys, { additive: event.ctrlKey || event.metaKey, range: event.shiftKey });
        enhanceDriveMultiSelect();
      });
      row.addEventListener('dblclick', (event) => {
        if (!driveSelection.isModeEnabled()) return;
        event.stopPropagation();
        event.preventDefault();
      });
    }
    const isSelected = driveSelection.getSelected().includes(key);
    row.classList.toggle('is-selected', isSelected);
    row.setAttribute('aria-selected', String(isSelected));
  });

  const selected = driveSelection.getSelected();
  const count = bar.querySelector('.cirava-selection-count');
  if (count) count.textContent = selected.length ? `${selected.length} selected` : 'Select more than one item';
  bar.classList.toggle('has-selection', selected.length > 0);
  bar.hidden = !modeEnabled;
  const selectAll = header?.querySelector('[data-cirava-select-all]');
  if (selectAll) {
    const selectedVisible = visibleKeys.filter((key) => selected.includes(key)).length;
    selectAll.checked = visibleKeys.length > 0 && selectedVisible === visibleKeys.length;
    selectAll.indeterminate = selectedVisible > 0 && selectedVisible < visibleKeys.length;
  }
}
