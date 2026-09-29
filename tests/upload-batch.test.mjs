import test from 'node:test';
import assert from 'node:assert/strict';
import { createGooglePhotosUploadBatch, createUploadBatch } from '../src/upload-batch.js';

test('Google Photos uploads use the native Photos batch bridge and preserve queued versus immediate start', async () => {
  const calls = [];
  const api = { create_google_photos_upload_batch: async (...args) => { calls.push(args); return [{ id: 'photos-upload' }]; } };
  await createGooglePhotosUploadBatch({ api, paths: ['C:/photos/one.jpg'], startImmediately: false });
  await createGooglePhotosUploadBatch({ api, paths: ['C:/photos/two.jpg'], startImmediately: true });
  assert.deepEqual(calls, [[['C:/photos/one.jpg'], false, null], [['C:/photos/two.jpg'], true, null]]);
});

test('Google Photos upload refuses empty selections and missing Photos bridge support', async () => {
  await assert.rejects(createGooglePhotosUploadBatch({ api: {}, paths: ['C:/photos/one.jpg'] }), /Google Photos upload is unavailable/);
  await assert.rejects(createGooglePhotosUploadBatch({ api: { create_google_photos_upload_batch: async () => [] }, paths: [] }), /Choose at least one photo or video/);
});

test('Google Photos album upload sends the chosen album title to the Photos bridge', async () => {
  let call;
  const api = { create_google_photos_upload_batch: async (...args) => { call = args; return [{ id: 'album-upload' }]; } };

  await createGooglePhotosUploadBatch({ api, paths: ['C:/photos/one.jpg'], albumTitle: 'Summer trip', startImmediately: false });

  assert.deepEqual(call, [['C:/photos/one.jpg'], false, 'Summer trip']);
});

test('real local selections are queued to the chosen Drive destination', async () => {
  let call;
  const api = { create_upload_batch: async (...args) => { call = args; return [{ id: 'upload-1' }]; } };
  await createUploadBatch({ api, paths: ['C:/files/report.pdf'], destinationId: 'folder-123' });
  assert.deepEqual(call, [['C:/files/report.pdf'], 'folder-123', 64 * 1024 * 1024, true, null]);
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
  assert.deepEqual(call, [['C:/files/report.pdf'], 'folder-123', 64 * 1024 * 1024, false, null]);
});

test('shared-drive uploads pass the drive ID separately from the destination folder', async () => {
  let call;
  const api = { create_upload_batch: async (...args) => { call = args; return [{ id: 'shared-upload' }]; } };
  await createUploadBatch({ api, paths: ['C:/files/report.pdf'], destinationId: 'shared-folder', destinationDriveId: 'shared-drive' });
  assert.deepEqual(call, [['C:/files/report.pdf'], 'shared-folder', 64 * 1024 * 1024, true, 'shared-drive']);
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
