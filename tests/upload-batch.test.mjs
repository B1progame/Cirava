import test from 'node:test';
import assert from 'node:assert/strict';
import { createUploadBatch } from '../src/upload-batch.js';

test('real local selections are queued to the chosen Drive destination', async () => {
  let call;
  const api = { create_upload_batch: async (...args) => { call = args; return [{ id: 'upload-1' }]; } };
  await createUploadBatch({ api, paths: ['C:/files/report.pdf'], destinationId: 'folder-123' });
  assert.deepEqual(call, [['C:/files/report.pdf'], 'folder-123', 64 * 1024 * 1024]);
});

test('test selection creates the explicit sparse test payload at the chosen destination', async () => {
  let call;
  const api = { create_test_upload: async (...args) => { call = args; return [{ id: 'test-upload' }]; } };
  await createUploadBatch({ api, paths: [], destinationId: 'folder-cobalt', testUpload: true });
  assert.deepEqual(call, ['folder-cobalt', 64 * 1024 * 1024]);
});

test('deferred upload batches pass the queue choice to the backend', async () => {
  let call;
  const api = { create_upload_batch: async (...args) => { call = args; return [{ id: 'waiting-upload' }]; } };
  await createUploadBatch({ api, paths: ['C:/files/report.pdf'], destinationId: 'folder-123', startImmediately: false });
  assert.deepEqual(call, [['C:/files/report.pdf'], 'folder-123', 64 * 1024 * 1024, false]);
});

test('deferred test uploads pass the queue choice to the backend', async () => {
  let call;
  const api = { create_test_upload: async (...args) => { call = args; return [{ id: 'waiting-test' }]; } };
  await createUploadBatch({ api, paths: [], destinationId: 'folder-cobalt', testUpload: true, startImmediately: false });
  assert.deepEqual(call, ['folder-cobalt', 64 * 1024 * 1024, false]);
});

test('a sample without choosing the test payload or real files cannot be queued', async () => {
  await assert.rejects(createUploadBatch({ api: { create_upload_batch: async () => [] }, paths: [], destinationId: 'root' }), /Choose at least one local file or folder/);
});
