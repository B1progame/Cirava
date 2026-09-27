import test from 'node:test';
import assert from 'node:assert/strict';
import { installTransferToastNotifications } from '../src/transfer-toast-notifications.js';

test('reports queued uploads and downloads, then announces each item when it starts', async () => {
  const notices = [];
  let transfers = [];
  const api = {
    create_upload_batch: async () => {
      transfers = [{ id: 'u1', name: 'photos.zip', status: 'queued', deferred: true, direction: 'upload' }];
      return transfers;
    },
    create_download: async () => {
      transfers = [...transfers, { id: 'd1', name: 'report.pdf', status: 'queued', deferred: true, direction: 'download' }];
      return transfers.at(-1);
    },
    list_transfers: async () => transfers,
  };
  let poll;
  installTransferToastNotifications(api, (notice) => notices.push(notice), {
    setInterval: (callback) => { poll = callback; return 1; },
    clearInterval: () => {},
  });

  await api.create_upload_batch(['photos.zip'], 'root');
  await api.create_download('drive-1', 'report.pdf', 42);
  assert.deepEqual(notices.map(({ type, direction }) => [type, direction]), [
    ['queued', 'upload'], ['queued', 'download'],
  ]);

  await poll();
  transfers = transfers.map((item) => ({ ...item, status: item.id === 'u1' ? 'transferring' : 'queued' }));
  await poll();
  transfers = transfers.map((item) => ({ ...item, status: 'transferring' }));
  await poll();

  assert.deepEqual(notices.slice(2).map(({ type, direction, name }) => [type, direction, name]), [
    ['started', 'upload', 'photos.zip'], ['started', 'download', 'report.pdf'],
  ]);
});

test('does not show queue toasts for failed requests or duplicate lifecycle notices after reinstall', async () => {
  const notices = [];
  const api = {
    create_upload: async () => { throw new Error('offline'); },
    list_transfers: async () => [],
  };
  const timers = { setInterval: () => 1, clearInterval: () => {} };
  installTransferToastNotifications(api, (notice) => notices.push(notice), timers);
  installTransferToastNotifications(api, (notice) => notices.push(notice), timers);
  await assert.rejects(api.create_upload('a.txt'), /offline/);
  assert.deepEqual(notices, []);
});

test('does not report a download as queued when Drive conflict handling cancels it', async () => {
  const notices = [];
  const api = {
    create_download: async () => ({ status: 'cancelled', local_path: 'report.pdf', error: 'Destination exists' }),
    list_transfers: async () => [],
  };
  installTransferToastNotifications(api, (notice) => notices.push(notice), {
    setInterval: () => 1,
    clearInterval: () => {},
  });

  await api.create_download('drive-1', 'report.pdf', 42);
  assert.deepEqual(notices, []);
});
