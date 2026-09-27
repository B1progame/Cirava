import test from 'node:test';
import assert from 'node:assert/strict';
import { findDriveFileByName } from '../src/drive-item-lookup.js';

test('delete lookup finds a file outside the current Drive root by exact name', async () => {
  const calls = [];
  const api = {
    find_drive_files_by_name: async (name) => {
      calls.push(name);
      return { files: [{ id: 'nested-123', name, mimeType: 'application/octet-stream', size: '5120' }] };
    },
    list_drive_files: async () => { throw new Error('must not use root-only listing'); },
  };

  assert.deepEqual(await findDriveFileByName(api, 'dummy_5120mb.bin'), {
    id: 'nested-123', name: 'dummy_5120mb.bin', mimeType: 'application/octet-stream',
    type: 'file', size: '5120',
  });
  assert.deepEqual(calls, ['dummy_5120mb.bin']);
});

test('ambiguous duplicate names fail safely rather than deleting an arbitrary Drive file', async () => {
  const api = { find_drive_files_by_name: async () => ({ files: [
    { id: 'first', name: 'duplicate.bin' }, { id: 'second', name: 'duplicate.bin' },
  ] }) };
  await assert.rejects(findDriveFileByName(api, 'duplicate.bin'), /More than one Drive item/);
});

test('older bridge fallback still matches only an exact root item name', async () => {
  const api = { list_drive_files: async () => ({ files: [
    { id: 'other', name: 'dummy.bin.old' }, { id: 'exact', name: 'dummy.bin' },
  ] }) };
  assert.equal((await findDriveFileByName(api, 'dummy.bin')).id, 'exact');
});
