import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../src/main.tsx', import.meta.url), 'utf8');
const styles = readFileSync(new URL('../src/ui-fixes.css', import.meta.url), 'utf8');
const selectionStyles = readFileSync(new URL('../src/drive-multiselect.css', import.meta.url), 'utf8');
const inspectBridge = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

test('row overflow opens an explicit menu instead of immediately choosing a folder or downloading', () => {
  assert.ok(source.includes('function ciravaDriveRowActionMenu()'));
  assert.match(source, /addEventListener\('contextmenu'/);
  assert.match(source, /requestedPoint/);
  assert.match(source, /Shift\+F10|event\.key === 'ContextMenu'/);
  assert.ok(source.includes('Choose as upload destination'));
  assert.ok(source.includes("'Download'"));
  assert.ok(source.includes("'Edit file'"));
  assert.ok(source.includes("'Delete'"));
  assert.ok(source.includes("actionButton(checkbox?.checked ? 'Deselect item' : 'Select item'"));
});

test('file and folder rows keep native left-click behavior while right-click opens item actions', () => {
  const selection = readFileSync(new URL('../src/drive-multiselect.js', import.meta.url), 'utf8');
  assert.match(source, /target\?\.closest<HTMLElement>\('\.file-row'\)/);
  assert.match(source, /document\.addEventListener\('contextmenu'/);
  assert.match(source, /trigger\.click\(\)/);
  assert.ok(source.includes("'Download'"));
  assert.ok(source.includes("'Delete'"));
  assert.match(selection, /row\.addEventListener\('click'/);
  assert.match(selection, /if \(!driveSelection\.isModeEnabled\(\)\) return/);
});

test('row menu exposes delete and download through the existing real Drive actions', () => {
  assert.match(source, /cirava:trash-drive-file/);
  assert.match(source, /nativeDownload\?\.click\(\)/);
  assert.match(styles, /\.drive-row-menu button\.is-danger/);
  assert.match(styles, /html\[data-theme='dark'\] \.drive-row-menu/);
});

test('selecting from the context menu updates selection state directly instead of clicking a hidden checkbox', () => {
  assert.match(source, /toggleDriveRowSelection\(row\)/);
  assert.match(source, /Download as ZIP/);
  assert.match(source, /download_drive_folder_zip_by_name/);
  assert.match(selectionStyles, /\.file-row\.is-selected\s*\{[^}]*background:[^}]*!important/s);
  assert.match(selectionStyles, /\.file-row\.is-selected \.file-name/);
});

test('inspection browser bridge provides Drive listing so the Drive page and Create menu can be tested', () => {
  assert.ok(inspectBridge.includes('list_drive_files: async () => ({ files: [] })'));
  assert.ok(styles.includes('.drive-toolbar { contain: layout style; }'));
  assert.ok(styles.includes('.drive-toolbar { position: relative; z-index: 30; overflow: visible; }'));
  assert.ok(styles.includes('.drive-create-menu { z-index: 32; }'));
});
