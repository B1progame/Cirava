import test from 'node:test';
import assert from 'node:assert/strict';
import { installTransferStartNavigation, queueNextDownload } from '../src/transfer-start-navigation.js';

test('navigates after an upload or download is successfully queued', async () => {
  const calls = [];
  const api = {
    create_upload_batch: async () => [{ id: 'upload-1' }],
    create_download: async () => ({ id: 'download-1' }),
  };
  installTransferStartNavigation(api, () => calls.push('transfers'));

  const upload = await api.create_upload_batch(['a.txt'], 'root');
  const download = await api.create_download('drive-1', 'a.txt', 10);

  assert.equal(upload[0].id, 'upload-1');
  assert.equal(download.id, 'download-1');
  assert.deepEqual(calls, ['transfers', 'transfers']);
});

test('does not navigate when no transfer was queued or the request failed', async () => {
  const calls = [];
  const api = {
    create_upload_batch: async () => [],
    create_upload: async () => ({ status: 'cancelled' }),
    create_download: async () => { throw new Error('Drive unavailable'); },
  };
  installTransferStartNavigation(api, () => calls.push('transfers'));

  assert.deepEqual(await api.create_upload_batch([]), []);
  assert.deepEqual(await api.create_upload('file.txt'), { status: 'cancelled' });
  await assert.rejects(api.create_download('drive-1', 'a.txt', 10), /Drive unavailable/);
  assert.deepEqual(calls, []);
});

test('opens Transfers before a long-running folder ZIP download', async () => {
  const calls = [];
  const api = {
    download_drive_folder_zip_by_name: async () => {
      calls.push('download');
      return { status: 'completed' };
    },
  };
  installTransferStartNavigation(api, () => calls.push('transfers'));

  await api.download_drive_folder_zip_by_name('Photos', 'photos.zip');
  assert.deepEqual(calls, ['transfers', 'download']);
});

test('is safe to install repeatedly on the same bridge', async () => {
  let navigations = 0;
  const api = { create_upload: async () => ({ id: 'upload-1' }) };
  installTransferStartNavigation(api, () => { navigations += 1; });
  installTransferStartNavigation(api, () => { navigations += 1; });

  await api.create_upload('file.txt', 'root');
  assert.equal(navigations, 1);
});

test('the explicit Queue download action creates a deferred download record once', async () => {
  const calls = [];
  const api = { create_download: async (...args) => { calls.push(args); return { id: 'deferred-download', deferred: args[7] === false }; } };
  installTransferStartNavigation(api, () => {});
  assert.equal(queueNextDownload(api), true);
  const first = await api.create_download('drive-1', 'file.bin', 100, 10, 2, 'hash', 'ask');
  await api.create_download('drive-2', 'other.bin', 50, 10, 2, 'hash', 'ask');
  assert.equal(first.deferred, true);
  assert.equal(calls[0][7], false, 'the selected download is deferred');
  assert.equal(calls[1][7], undefined, 'later downloads retain the normal immediate behavior');
});
