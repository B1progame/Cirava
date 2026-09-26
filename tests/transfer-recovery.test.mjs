import test from 'node:test';
import assert from 'node:assert/strict';

const { getTransferProgress, findResumableTransfer, findCancellableTransfer } = await import('../src/transfer-recovery.js').catch(() => ({}));

test('transfer progress normalizes the durable backend fields for a large file', () => {
  assert.equal(typeof getTransferProgress, 'function');
  assert.deepEqual(getTransferProgress({ size: 4_404_019_200, bytes_transferred: 436_207_616, speed_bps: 2_386_177 }), {
    sizeBytes: 4_404_019_200,
    bytesTransferred: 436_207_616,
    progress: 9.9,
    speedBps: 2_386_177,
  });
});

test('paused queue rows resolve to the correct durable transfer by filename, direction, and occurrence', () => {
  assert.equal(typeof findResumableTransfer, 'function');
  const transfers = [
    { id: 'upload-a', filename: 'same.bin', direction: 'upload', status: 'paused' },
    { id: 'download-a', filename: 'same.bin', direction: 'download', status: 'paused' },
    { id: 'upload-b', filename: 'same.bin', direction: 'upload', status: 'paused' },
  ];
  assert.equal(findResumableTransfer({ name: 'same.bin', kind: 'upload' }, transfers, 0).id, 'upload-a');
  assert.equal(findResumableTransfer({ name: 'same.bin', kind: 'upload' }, transfers, 1).id, 'upload-b');
  assert.equal(findResumableTransfer({ name: 'same.bin', kind: 'download' }, transfers, 0).id, 'download-a');
});

test('only active upload rows resolve to a cancellable transfer', () => {
  assert.equal(typeof findCancellableTransfer, 'function');
  const transfers = [
    { id: 'done', filename: 'same.bin', direction: 'upload', status: 'completed' },
    { id: 'active', filename: 'same.bin', direction: 'upload', status: 'transferring' },
    { id: 'download', filename: 'same.bin', direction: 'download', status: 'transferring' },
    { id: 'paused', filename: 'later.bin', direction: 'upload', status: 'paused' },
  ];
  assert.equal(findCancellableTransfer({ name: 'same.bin', kind: 'upload' }, transfers, 1).id, 'active');
  assert.equal(findCancellableTransfer({ name: 'same.bin', kind: 'download' }, transfers), null);
  assert.equal(findCancellableTransfer({ name: 'later.bin', kind: 'upload' }, transfers), null);
});
