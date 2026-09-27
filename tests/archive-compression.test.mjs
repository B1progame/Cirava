import test from 'node:test';
import assert from 'node:assert/strict';
import { createArchiveUploadFlow, formatArchiveSavings } from '../src/archive-compression.js';

test('a previewed archive is the one queued only for its exact source selection', async () => {
  const calls = [];
  const flow = createArchiveUploadFlow({
    prepare_compressed_upload: async (...args) => { calls.push(args); return { archive_path: 'stage/photo.cirava.zip', archive_bytes: 25, saved_bytes: 75, saved_percent: 75 }; },
  });
  const paths = ['C:/photos/photo.jpg'];
  await flow.preview(paths, 3);
  assert.deepEqual(calls, [[paths, 3]]);
  assert.deepEqual(flow.uploadPaths(paths), ['stage/photo.cirava.zip']);
  assert.deepEqual(flow.uploadPaths(['C:/photos/other.jpg']), ['C:/photos/other.jpg']);
});

test('changing files invalidates a prepared archive and preview states exact savings', async () => {
  const flow = createArchiveUploadFlow({ prepare_compressed_upload: async () => ({ archive_path: 'stage/a.zip', archive_bytes: 1024, saved_bytes: 0 }) });
  await flow.preview(['a.txt']);
  assert.equal(formatArchiveSavings(flow.getPrepared(['a.txt'])), 'Archive: 0.0 MB · this selection did not compress smaller.');
  flow.clear();
  assert.deepEqual(flow.uploadPaths(['a.txt']), ['a.txt']);
});

test('a bridge response without a real archive never enables compressed upload', async () => {
  const flow = createArchiveUploadFlow({ prepare_compressed_upload: async () => ({ saved_bytes: 12 }) });
  await assert.rejects(flow.preview(['a.txt']), /did not return a prepared archive/);
  assert.deepEqual(flow.uploadPaths(['a.txt']), ['a.txt']);
});

test('preview reports the measured archive bytes and size reduction', () => {
  assert.equal(formatArchiveSavings({ archive_bytes: 2 * 1024 ** 3, saved_bytes: 3 * 1024 ** 3, saved_percent: 60 }), 'Archive: 2.00 GB · saves 3.00 GB (60%).');
});
