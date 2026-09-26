import test from 'node:test';
import assert from 'node:assert/strict';

const { renderDriveFolderPicker } = await import('../src/drive-folder-picker.js').catch(() => ({}));

test('folder picker clearly separates the current destination from navigable child folders', () => {
  assert.equal(typeof renderDriveFolderPicker, 'function');

  const html = renderDriveFolderPicker({
    parentId: 'root',
    currentLabel: 'My Drive / Workspace',
    folders: [
      { id: 'folder-hallo', name: 'hallo' },
      { id: 'folder-test', name: 'test' },
    ],
  });

  assert.match(html, /class="cirava-upload-folder-chooser"/);
  assert.match(html, /aria-label="Use My Drive \/ Workspace as upload destination"/);
  assert.match(html, /Upload directly into this folder/);
  assert.match(html, /aria-label="Folders inside My Drive \/ Workspace"/);
  assert.match(html, /data-cirava-folder-id="folder-hallo"[^>]*>.*hallo.*Open <span/);
  assert.match(html, /data-cirava-folder-id="folder-test"[^>]*>.*test.*Open <span/);
  assert.match(html, /2 folders/);
});

test('empty folder picker gives a clear empty message without an empty scroll region', () => {
  const html = renderDriveFolderPicker({ parentId: 'empty', currentLabel: 'Archive', folders: [] });
  assert.match(html, /No folders here yet/);
  assert.match(html, /Use Archive as upload destination/);
});

test('folder picker escapes Drive names before placing them in attributes and labels', () => {
  const html = renderDriveFolderPicker({
    parentId: 'root',
    currentLabel: 'My Drive',
    folders: [{ id: 'folder-1', name: '<img src=x onerror=alert(1)>' }],
  });

  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.doesNotMatch(html, /<img src=x/);
});
