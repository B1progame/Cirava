import test from 'node:test';
import assert from 'node:assert/strict';
import { startUploadWithFeedback } from '../src/upload-start.js';

test('upload reports progress and navigates only after the backend returns queued transfers', async () => {
  const events = [];
  const result = await startUploadWithFeedback({
    createBatch: async () => [{ id: 'up-1' }, { id: 'up-2' }],
    navigate: () => events.push('navigate'),
    onStatus: (status) => events.push(status),
  });
  assert.equal(result.length, 2);
  assert.deepEqual(events, ['Creating a resumable upload…', '2 uploads queued. Opening Transfers…', 'navigate']);
});

test('upload keeps errors visible and does not navigate when queue creation fails', async () => {
  const events = [];
  await assert.rejects(startUploadWithFeedback({
    createBatch: async () => { throw new Error('Drive authorization expired'); },
    navigate: () => events.push('navigate'),
    onStatus: (status) => events.push(status),
  }), /Drive authorization expired/);
  assert.deepEqual(events, ['Creating a resumable upload…', 'Drive authorization expired']);
});

test('an empty batch is reported as failure rather than looking like an upload started', async () => {
  const events = [];
  await assert.rejects(startUploadWithFeedback({ createBatch: async () => [], navigate() {}, onStatus: (s) => events.push(s) }), /No files were found/);
  assert.equal(events.at(-1), 'No files were found in the selected paths.');
});
