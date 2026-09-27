import test from 'node:test';
import assert from 'node:assert/strict';
import { createTransferEtaCountdown, formatTransferJourneyElapsed, formatTransferJourneyEta, getCancellableUploadIds, getPausableUploadIds, getResumableUploadIds, getTransferJourneyActivity, getTransferJourneyFrame, getTransferJourneyPathProgress, getTransferJourneySummary, getTransferJourneyViewBox, renderTransferJourney } from '../src/transfer-journey.js';

test('empty transfer state presents a labeled route with hidden SVG file packets', () => {
  const html = renderTransferJourney();

  assert.match(html, /aria-label="Transfer route: this device, secure cloud, Google Drive"/);
  assert.match(html, /<title id="transfer-journey-title">This device to Google Drive<\/title>/);
  assert.match(html, />This device</);
  assert.match(html, />Secure cloud route</);
  assert.match(html, />Google Drive<\/text>/);
  assert.match(html, /data-upload-active="false" data-download-active="false"/);
  assert.match(html, /class="transfer-file-packet upload"/);
  assert.match(html, /class="transfer-file-packet download"/);
  assert.match(html, /data-file-kind="folder"/);
  assert.match(html, /data-file-kind="image"/);
  assert.match(html, /data-file-kind="document"/);
  assert.doesNotMatch(html, /<animateMotion/);
});

test('only actively transferring records activate their own route direction', () => {
  assert.deepEqual(getTransferJourneyActivity([]), { upload: false, download: false });
  assert.deepEqual(getTransferJourneyActivity([
    { direction: 'upload', status: 'queued' },
    { direction: 'download', status: 'paused' },
    { direction: 'upload', status: 'waiting-for-network' },
    { direction: 'download', status: 'completed' },
  ]), { upload: false, download: false });
  assert.deepEqual(getTransferJourneyActivity([
    { direction: 'upload', status: 'transferring' },
    { direction: 'download', status: 'queued' },
  ]), { upload: true, download: false });
  assert.deepEqual(getTransferJourneyActivity([
    { direction: 'download', status: 'transferring' },
  ]), { upload: false, download: true });
  assert.deepEqual(getTransferJourneyActivity([
    { direction: 'upload', status: 'transferring' },
    { direction: 'download', status: 'transferring' },
  ]), { upload: true, download: true });
});

test('file glyphs shrink at both endpoints and grow around the cloud midpoint', () => {
  const source = getTransferJourneyFrame(0);
  const cloud = getTransferJourneyFrame(0.5);
  const destination = getTransferJourneyFrame(1);
  assert.ok(source.scale < cloud.scale);
  assert.ok(destination.scale < cloud.scale);
  assert.equal(source.opacity, 0);
  assert.equal(destination.opacity, 0);
  assert.equal(cloud.opacity, 1);
});

test('upload travels device to Drive and download travels Drive to device', () => {
  assert.equal(getTransferJourneyPathProgress(0, 'upload'), 0);
  assert.equal(getTransferJourneyPathProgress(1, 'upload'), 1);
  assert.equal(getTransferJourneyPathProgress(0, 'download'), 1);
  assert.equal(getTransferJourneyPathProgress(1, 'download'), 0);
});

test('narrow transfer cards focus the secure cloud in a centered compact view', () => {
  assert.equal(getTransferJourneyViewBox(320), '340 0 220 218');
  assert.equal(getTransferJourneyViewBox(520), '0 0 900 218');
});

test('compact route explicitly centers the cloud artwork in its card', async () => {
  const css = await (await import('node:fs/promises')).readFile(new URL('../src/transfer-journey.css', import.meta.url), 'utf8');
  assert.match(css, /\.transfer-journey\[data-cloud-centered=['"]true['"]\]\s*\{[^}]*align-items:\s*stretch/s);
  assert.match(css, /\.transfer-journey\[data-cloud-centered=['"]true['"]\]\s+\.transfer-journey-art\s*\{[^}]*align-self:\s*center/s);
});

test('live summary aggregates active queue files, transferred bytes, total bytes, and current speed', () => {
  assert.deepEqual(getTransferJourneySummary([
    { status: 'transferring', direction: 'upload', size: 1_000, bytes_transferred: 350, speed_bps: 120 },
    { status: 'queued', direction: 'download', size: 2_000, bytes_transferred: 0, speed_bps: 0 },
    { status: 'paused', direction: 'upload', size: 500, bytes_transferred: 300, speed_bps: 90 },
    { status: 'completed', direction: 'download', size: 400, bytes_transferred: 400, speed_bps: 0 },
    { status: 'failed', direction: 'upload', size: 700, bytes_transferred: 100, speed_bps: 0 },
  ]), {
    visible: true,
    fileCount: 3,
    transferredBytes: 650,
    totalBytes: 3_500,
    speedBps: 120,
    etaSeconds: 24,
    elapsedSeconds: 0,
    progressAnimationActive: true,
    progressPercent: 18.6,
    state: 'Transferring',
  });
});

test('live summary hides when there are no in-progress queue files', () => {
  assert.deepEqual(getTransferJourneySummary([
    { status: 'completed', size: 300, bytes_transferred: 300 },
    { status: 'failed', size: 400, bytes_transferred: 0 },
  ]), {
    visible: false,
    fileCount: 0,
    transferredBytes: 0,
    totalBytes: 0,
    speedBps: 0,
    etaSeconds: null,
    elapsedSeconds: 0,
    progressAnimationActive: false,
    progressPercent: 0,
    state: 'Idle',
  });
});

test('ETA uses aggregate active throughput and remaining bytes; formatting stays readable', () => {
  const summary = getTransferJourneySummary([
    { status: 'transferring', direction: 'upload', size: 10_000, bytes_transferred: 2_000, speed_bps: 400 },
    { status: 'transferring', direction: 'upload', size: 20_000, bytes_transferred: 5_000, speed_bps: 600 },
  ]);
  assert.equal(summary.etaSeconds, 23);
  assert.equal(formatTransferJourneyEta(summary.etaSeconds), '23 sec left');
  assert.equal(formatTransferJourneyEta(60), '1 min left');
  assert.equal(formatTransferJourneyEta(null), 'Calculating…');
  assert.equal(formatTransferJourneyEta(8), '8 sec left');
  assert.equal(formatTransferJourneyEta(1), '1 sec left');
  assert.equal(formatTransferJourneyEta(0), 'Finishing…');
  assert.equal(formatTransferJourneyEta(3_725), '1 hr 3 min left');
});

test('ETA visibly counts down between transfer refreshes and recalibrates when the estimate changes substantially', () => {
  let now = 10_000;
  const countdown = createTransferEtaCountdown(() => now);
  countdown.update(26);
  assert.equal(formatTransferJourneyEta(countdown.remaining()), '26 sec left');
  now += 1000;
  countdown.update(25);
  assert.equal(formatTransferJourneyEta(countdown.remaining()), '25 sec left');
  now += 1000;
  assert.equal(formatTransferJourneyEta(countdown.remaining()), '24 sec left');
  countdown.update(12);
  assert.equal(formatTransferJourneyEta(countdown.remaining()), '12 sec left');
  countdown.update(null);
  assert.equal(countdown.remaining(), null);
});

test('elapsed time counts up from the earliest transfer start and shows hours, minutes, and seconds', () => {
  const summary = getTransferJourneySummary([
    { status: 'transferring', started_at: 1000 },
    { status: 'queued' },
  ], 4661);
  assert.equal(summary.elapsedSeconds, 3661);
  assert.equal(formatTransferJourneyElapsed(summary.elapsedSeconds), '1 hr 1 min 1 sec');
  assert.equal(formatTransferJourneyElapsed(9), '0 hr 0 min 9 sec');
});

test('a paused upload is not reported as moving and remains cancellable from the transfer panel', () => {
  const transfers = [
    { id: 'paused-upload', direction: 'upload', status: 'paused', size: 8_000, bytes_transferred: 1_000 },
    { id: 'queued-upload', direction: 'upload', status: 'queued', size: 2_000, bytes_transferred: 0 },
    { id: 'paused-download', direction: 'download', status: 'paused', size: 4_000 },
    { id: 'done-upload', direction: 'upload', status: 'completed', size: 100 },
  ];
  assert.equal(getTransferJourneySummary(transfers).state, 'Waiting to start');
  assert.equal(getTransferJourneyActivity(transfers).upload, false);
  assert.deepEqual(getCancellableUploadIds(transfers), ['paused-upload', 'queued-upload']);
  const html = renderTransferJourney();
  assert.match(html, /data-cancel-uploads hidden>Cancel uploads/);
  assert.match(html, /data-pause-uploads hidden>Pause uploads/);
});

test('transfer actions target only uploads in supported states', () => {
  const transfers = [
    { id: 'moving', direction: 'upload', status: 'transferring' },
    { id: 'queued', direction: 'upload', status: 'queued' },
    { id: 'paused', direction: 'upload', status: 'paused' },
    { id: 'download', direction: 'download', status: 'transferring' },
    { id: 'verifying', direction: 'upload', status: 'verifying' },
  ];
  assert.deepEqual(getPausableUploadIds(transfers), ['moving', 'queued']);
  assert.deepEqual(getResumableUploadIds(transfers), ['paused']);
});

test('a zero-byte transfer is reported as starting instead of falsely implying data is moving', () => {
  assert.equal(getTransferJourneySummary([
    { direction: 'upload', status: 'transferring', size: 5_000, bytes_transferred: 0, speed_bps: 0 },
  ]).state, 'Connecting to Drive');
});

test('the progress fill animates only for active transfers and honors reduced motion', async () => {
  assert.equal(getTransferJourneySummary([{ status: 'transferring', direction: 'upload' }]).progressAnimationActive, true);
  assert.equal(getTransferJourneySummary([{ status: 'paused', direction: 'upload' }]).progressAnimationActive, false);
  const html = renderTransferJourney();
  assert.match(html, /class="transfer-live-progress"[^>]*data-transfer-active="false"/);
  const css = await (await import('node:fs/promises')).readFile(new URL('../src/transfer-journey.css', import.meta.url), 'utf8');
  assert.match(css, /\.transfer-live-progress\[data-transfer-active=['"]true['"]\]\s*>\s*span::after\s*\{[^}]*animation:\s*transfer-progress-sheen/s);
  assert.match(css, /prefers-reduced-motion:\s*reduce[\s\S]*?\.transfer-live-progress\s*>\s*span::after\s*\{[^}]*animation:\s*none/s);
});

test('upload startup reports the current preparation and first-chunk steps', () => {
  assert.equal(getTransferJourneySummary([
    { direction: 'upload', status: 'queued', size: 5_000 },
  ]).state, 'Waiting to start');
  assert.equal(getTransferJourneySummary([
    { direction: 'upload', status: 'preparing', size: 5_000 },
  ]).state, 'Connecting to Drive');
  assert.equal(getTransferJourneySummary([
    { direction: 'upload', status: 'transferring', size: 5_000, upload_session_url: 'https://drive/session' },
  ]).state, 'Starting upload');
});

test('an upload retry is visible in the live transfer status', () => {
  assert.equal(getTransferJourneySummary([
    { direction: 'upload', status: 'transferring', size: 5_000, retry_count: 2 },
  ]).state, 'Retrying upload · retry 2');
});

test('the route markup has a live progress summary beneath its animation', () => {
  const html = renderTransferJourney();
  assert.match(html, /class="transfer-live-summary" data-live-visible="false"/);
  assert.ok(html.indexOf('class="transfer-journey-art"') < html.indexOf('class="transfer-live-summary"'));
  assert.match(html, /data-live-speed/);
  assert.match(html, /data-live-eta/);
  assert.match(html, /data-live-elapsed/);
  assert.match(html, /data-live-bytes/);
  assert.match(html, /data-live-files/);
  assert.match(html, /role="progressbar"/);
});
