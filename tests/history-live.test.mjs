import test from 'node:test';
import assert from 'node:assert/strict';

const { getHistoryTransfers, resolveHistoryTransfer } = await import('../src/history-live.js').catch(() => ({}));

test('history contains only finished backend transfers and preserves their real metadata', () => {
  assert.equal(typeof getHistoryTransfers, 'function');
  const rows = getHistoryTransfers([
    { id: 'active', filename: 'still-moving.zip', direction: 'upload', status: 'transferring', size: 500 },
    { id: 'done', filename: 'archive.zip', direction: 'download', status: 'completed', size: 1024, local_path: 'C:/archive.zip', drive_file_id: 'drive-1', created_at: 10, completed_at: 20 },
    { id: 'failed', filename: 'broken.bin', direction: 'upload', status: 'failed', size: 12, created_at: 30 },
  ]);

  assert.deepEqual(rows.map(({ id }) => id), ['done', 'failed']);
  assert.equal(rows[0].name, 'archive.zip');
  assert.equal(rows[0].kind, 'download');
  assert.equal(rows[0].localPath, 'C:/archive.zip');
  assert.equal(rows[0].driveFileId, 'drive-1');
  assert.equal(rows[0].completedAt, 20);
});

test('empty history stays empty instead of manufacturing preview transfers', () => {
  assert.deepEqual(getHistoryTransfers([]), []);
});

test('duplicate history names resolve by direction, status, and visible occurrence', () => {
  const records = [
    { id: 'upload-one', filename: 'same.bin', direction: 'upload', status: 'completed', size: 1 },
    { id: 'download-one', filename: 'same.bin', direction: 'download', status: 'completed', size: 1 },
    { id: 'upload-two', filename: 'same.bin', direction: 'upload', status: 'completed', size: 1 },
  ];
  const row = { name: 'same.bin', kind: 'upload', status: 'completed' };

  assert.equal(resolveHistoryTransfer(row, records, 0).id, 'upload-one');
  assert.equal(resolveHistoryTransfer(row, records, 1).id, 'upload-two');
  assert.equal(resolveHistoryTransfer({ ...row, kind: 'download' }, records, 0).id, 'download-one');
  assert.equal(resolveHistoryTransfer({ ...row, name: 'missing.bin' }, records, 0), null);
});
