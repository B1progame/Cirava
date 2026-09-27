import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { formatDriveStorageBytes, renderDriveTrash, renderDriveTrashRows } from '../src/drive-trash.js';

test('Drive storage is displayed in readable binary units without inventing missing values', () => {
  assert.equal(formatDriveStorageBytes(0), '0 B');
  assert.equal(formatDriveStorageBytes(1024), '1.0 KB');
  assert.equal(formatDriveStorageBytes(5 * 1024 ** 3), '5.0 GB');
  assert.equal(formatDriveStorageBytes(undefined), 'Unknown');
});

test('trash rows show file details and a restore action while escaping Drive-provided text', () => {
  const rows = renderDriveTrashRows([{
    id: 'item" onclick="alert(1)',
    name: '<img src=x onerror=alert(1)>',
    mimeType: 'application/vnd.google-apps.folder',
    size: '1048576',
    trashedTime: '2026-09-27T10:00:00.000Z',
  }]);

  assert.match(rows, /Items in Drive trash/);
  assert.match(rows, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(rows, /item&quot; onclick=&quot;alert\(1\)/);
  assert.match(rows, /Folder/);
  assert.match(rows, /1\.0 MB/);
  assert.match(rows, /data-trash-restore=/);
});

test('trash view reports account storage and a useful empty state', () => {
  const view = renderDriveTrash([], {
    limit: '1000', usage: '250', usageInDrive: '200', usageInDriveTrash: '50',
  });
  assert.match(view, /250 B/);
  assert.match(view, /of 1000 B/);
  assert.match(view, /Drive files/);
  assert.match(view, /In trash/);
  assert.match(view, /Your trash is empty/);
  assert.match(view, /aria-valuenow="25\.0"/);
  assert.match(renderDriveTrash([], { usage: '400' }), /Unlimited storage/);
  assert.match(renderDriveTrash([], null), /Usage unavailable/);
});

test('Drive toolbar installs Trash and the destructive action requires a second confirmation', () => {
  const source = readFileSync(new URL('../src/main.tsx', import.meta.url), 'utf8');
  const trash = readFileSync(new URL('../src/drive-trash.js', import.meta.url), 'utf8');
  assert.match(source, /installDriveTrash\(\)/);
  assert.match(source, /from '\.\/drive-trash\.js'/);
  assert.match(trash, /role="alertdialog"/);
  assert.match(trash, /data-trash-cancel-empty/);
  assert.match(trash, /Permanently delete/);
});
