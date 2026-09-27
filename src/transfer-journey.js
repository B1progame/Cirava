const ROUTE_PATH = 'M 122 100 C 220 27 317 27 450 100 C 583 173 680 173 778 100';
const QUEUED_STATUSES = new Set(['queued', 'preparing', 'transferring', 'paused', 'waiting-for-network', 'rate-limited', 'verifying']);
const CANCELLABLE_UPLOAD_STATUSES = new Set(['queued', 'preparing', 'transferring', 'paused', 'waiting-for-network', 'rate-limited']);
const PAUSABLE_UPLOAD_STATUSES = new Set(['queued', 'preparing', 'transferring', 'waiting-for-network', 'rate-limited']);

function getUploadIdsInStatuses(transfers, statuses) {
  if (!Array.isArray(transfers)) return [];
  return transfers
    .filter((item) => (item?.direction ?? item?.kind) === 'upload' && statuses.has(item?.status))
    .map((item) => item.id ?? item.transferId ?? item.transfer_id)
    .filter((id) => id != null && String(id).length > 0)
    .map(String);
}

export function getCancellableUploadIds(transfers) {
  return getUploadIdsInStatuses(transfers, CANCELLABLE_UPLOAD_STATUSES);
}

export function getPausableUploadIds(transfers) { return getUploadIdsInStatuses(transfers, PAUSABLE_UPLOAD_STATUSES); }
export function getResumableUploadIds(transfers) { return getUploadIdsInStatuses(transfers, new Set(['paused'])); }

export function getTransferJourneyViewBox(width) {
  return Number(width) < 520 ? '340 0 220 218' : '0 0 900 218';
}

export function getTransferJourneyActivity(transfers) {
  const activity = { upload: false, download: false };
  if (!Array.isArray(transfers)) return activity;
  for (const transfer of transfers) {
    if (transfer?.status !== 'transferring') continue;
    const direction = transfer.direction ?? transfer.kind;
    if (direction === 'upload' || direction === 'download') activity[direction] = true;
  }
  return activity;
}

export function getTransferJourneyFrame(progress) {
  const t = Math.max(0, Math.min(1, Number(progress) || 0));
  const travel = 1 - Math.abs(2 * t - 1);
  return {
    scale: 0.42 + travel * 0.88,
    opacity: Math.max(0, Math.min(1, t * 8, (1 - t) * 8)),
  };
}

export function getTransferJourneyPathProgress(progress, direction) {
  const t = Math.max(0, Math.min(1, Number(progress) || 0));
  return direction === 'download' ? 1 - t : t;
}

export function getTransferJourneySummary(transfers) {
  const empty = {
    visible: false,
    fileCount: 0,
    transferredBytes: 0,
    totalBytes: 0,
    speedBps: 0,
    etaSeconds: null,
    progressPercent: 0,
    state: 'Idle',
  };
  const active = Array.isArray(transfers)
    ? transfers.filter((item) => QUEUED_STATUSES.has(item?.status))
    : [];
  if (!active.length) return empty;

  const totalBytes = active.reduce((sum, item) => sum + Math.max(0, Number(item.sizeBytes ?? item.size) || 0), 0);
  const transferredBytes = active.reduce((sum, item) => {
    const size = Math.max(0, Number(item.sizeBytes ?? item.size) || 0);
    const moved = Math.max(0, Number(item.bytesTransferred ?? item.bytes_transferred) || 0);
    return sum + (size ? Math.min(moved, size) : moved);
  }, 0);
  const speedBps = active.reduce((sum, item) => item.status === 'transferring'
    ? sum + Math.max(0, Number(item.speedBps ?? item.speed_bps) || 0)
    : sum, 0);
  const moving = active.filter((item) => item.status === 'transferring');
  const starting = moving.length && moving.every((item) => (Number(item.bytesTransferred ?? item.bytes_transferred) || 0) === 0 && (Number(item.speedBps ?? item.speed_bps) || 0) === 0);
  const retrying = moving.find((item) => Number(item.retryCount ?? item.retry_count) > 0);
  const movingDirections = new Set(moving.map((item) => item.direction ?? item.kind));
  const state = active.some((item) => item.status === 'waiting-for-network') ? 'Waiting for connection'
    : active.some((item) => item.status === 'rate-limited') ? 'Pacing the transfer'
      : active.some((item) => item.status === 'verifying') ? 'Finishing up'
        : starting && retrying ? `Retrying upload · retry ${Number(retrying.retryCount ?? retrying.retry_count)}`
          : starting && movingDirections.size === 1 && movingDirections.has('upload')
            ? moving.every((item) => item.uploadSessionUrl ?? item.upload_session_url) ? 'Starting upload' : 'Connecting to Drive'
            : starting && movingDirections.size === 1 && movingDirections.has('download') ? 'Starting download'
              : moving.length ? 'Transferring'
                : active.some((item) => item.status === 'preparing') ? 'Connecting to Drive'
                  : active.some((item) => item.status === 'queued') ? 'Waiting to start'
                    : 'Paused';

  return {
    visible: true,
    fileCount: active.length,
    transferredBytes,
    totalBytes,
    speedBps,
    etaSeconds: speedBps > 0 && totalBytes > transferredBytes
      ? Math.ceil((totalBytes - transferredBytes) / speedBps)
      : null,
    progressPercent: totalBytes > 0 ? Math.round((transferredBytes / totalBytes) * 1000) / 10 : 0,
    state,
  };
}

export function formatTransferJourneyBytes(value) {
  const bytes = Math.max(0, Number(value) || 0);
  if (bytes < 1024) return `${Math.round(bytes)} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let size = bytes / 1024;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit += 1; }
  return `${size >= 100 ? Math.round(size) : size.toFixed(1)} ${units[unit]}`;
}

export function formatTransferJourneyEta(seconds) {
  if (seconds == null) return 'Calculating…';
  const remainingSeconds = Number(seconds);
  if (!Number.isFinite(remainingSeconds) || remainingSeconds < 0) return 'Calculating…';
  if (remainingSeconds < 60) return 'Less than a minute left';
  const totalMinutes = Math.ceil(remainingSeconds / 60);
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;
  if (days) return `${days} day${days === 1 ? '' : 's'}${hours ? ` ${hours} hr` : ''} left`;
  if (hours) return `${hours} hr${minutes ? ` ${minutes} min` : ''} left`;
  return `${totalMinutes} min left`;
}

function renderPacket(direction, kind, phase) {
  let glyph;
  if (kind === 'folder') {
    glyph = '<path class="journey-file-glyph folder" d="M-7-4h5l2 2h5v9H-7z"/><path class="journey-file-fold" d="M-7-1H5"/>';
  } else if (kind === 'image') {
    glyph = '<rect class="journey-file-glyph image" x="-7" y="-6" width="14" height="12" rx="2"/><circle class="journey-image-sun" cx="3" cy="-3" r="1.4"/><path class="journey-image-hill" d="m-5 4 4-4 2 2 2-2 3 4"/>';
  } else {
    glyph = '<path class="journey-file-glyph document" d="M-5-7h7l4 4v10H-5z"/><path class="journey-document-fold" d="M2-7v4h4M-2 1h6M-2 4h6"/>';
  }
  return `<g class="transfer-file-packet ${direction}" data-file-kind="${kind}" data-phase="${phase}" aria-hidden="true" opacity="0"><circle class="journey-file-tile" r="11"/>${glyph}</g>`;
}

export function renderTransferJourney() {
  const packets = ['folder', 'image', 'document'];
  const uploadPackets = packets.map((kind, index) => renderPacket('upload', kind, index / packets.length)).join('');
  const downloadPackets = packets.map((kind, index) => renderPacket('download', kind, index / packets.length)).join('');
  return `<section class="transfer-journey" data-upload-active="false" data-download-active="false" aria-label="Transfer route: this device, secure cloud, Google Drive">
    <div class="transfer-journey-copy">
      <div><span class="transfer-journey-kicker">The route your files take</span><h3>From here to safely there.</h3></div>
      <p>File movement appears here only while a transfer is active.</p>
    </div>
    <svg class="transfer-journey-art" viewBox="0 0 900 218" role="img" aria-labelledby="transfer-journey-title transfer-journey-description">
      <title id="transfer-journey-title">This device to Google Drive</title>
      <desc id="transfer-journey-description">An illustration of the device, secure cloud route, and Google Drive. File icons move in the active transfer direction only.</desc>
      <defs>
        <linearGradient id="transfer-route-gradient" x1="0" y1="0" x2="1" y2="0"><stop stop-color="#718cf2" stop-opacity=".3"/><stop offset=".52" stop-color="#54c6c1" stop-opacity=".7"/><stop offset="1" stop-color="#718cf2" stop-opacity=".3"/></linearGradient>
        <linearGradient id="transfer-cloud-gradient" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#edf2ff"/><stop offset="1" stop-color="#e6faf7"/></linearGradient>
        <filter id="transfer-soft-shadow" x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="0" dy="8" stdDeviation="9" flood-color="#7389c7" flood-opacity=".12"/></filter>
        <path id="transfer-journey-path" d="${ROUTE_PATH}"/>
      </defs>
      <path class="transfer-route-glow" d="${ROUTE_PATH}"/>
      <path class="transfer-route-line" d="${ROUTE_PATH}"/>
      ${uploadPackets}${downloadPackets}

      <g class="transfer-journey-node device-node" filter="url(#transfer-soft-shadow)">
        <circle class="journey-node-halo" cx="122" cy="100" r="39"/>
        <rect class="journey-device" x="103" y="86" width="38" height="25" rx="4"/>
        <path class="journey-device" d="M 98 116 H 146 L 142 120 H 102 Z"/>
        <path class="journey-device-detail" d="M 108 91 H 136 V 106 H 108 Z"/>
      </g>
      <g class="transfer-journey-node cloud-node" filter="url(#transfer-soft-shadow)">
        <circle class="journey-cloud-halo" cx="450" cy="100" r="50"/>
        <path class="journey-cloud" d="M 424 111 H 475 C 485 111 490 105 490 97 C 490 89 484 83 476 82 C 473 68 462 60 449 60 C 436 60 426 69 423 82 C 413 82 406 89 406 98 C 406 105 413 111 424 111 Z"/>
        <path class="journey-lock" d="M 440 91 V 87 C 440 81 449 81 449 87 V 91 M 438 91 H 451 V 101 H 438 Z"/>
      </g>
      <g class="transfer-journey-node drive-node" filter="url(#transfer-soft-shadow)">
        <circle class="journey-node-halo" cx="778" cy="100" r="39"/>
        <rect class="journey-server" x="759" y="77" width="38" height="15" rx="4"/>
        <rect class="journey-server" x="759" y="96" width="38" height="15" rx="4"/>
        <rect class="journey-server" x="759" y="115" width="38" height="15" rx="4"/>
        <circle class="journey-server-light" cx="766" cy="84.5" r="2"/><circle class="journey-server-light" cx="766" cy="103.5" r="2"/><circle class="journey-server-light" cx="766" cy="122.5" r="2"/>
        <path class="journey-server-line" d="M 773 84 H 790 M 773 103 H 790 M 773 122 H 790"/>
      </g>
      <text class="journey-label" x="122" y="166" text-anchor="middle">This device</text>
      <text class="journey-caption" x="122" y="183" text-anchor="middle">Your files</text>
      <text class="journey-label" x="450" y="166" text-anchor="middle">Secure cloud route</text>
      <text class="journey-caption" x="450" y="183" text-anchor="middle">Encrypted in transit</text>
      <text class="journey-label" x="778" y="166" text-anchor="middle">Google Drive</text>
      <text class="journey-caption" x="778" y="183" text-anchor="middle">Saved to your account</text>
    </svg>
    <div class="transfer-live-summary" data-live-visible="false">
      <div class="transfer-live-heading"><div><span class="transfer-live-kicker">TRANSFER STATUS</span><strong data-live-state aria-live="polite">Preparing transfer</strong></div><span class="transfer-live-files-total" data-live-files>0 files</span><button class="transfer-pause-uploads" type="button" data-pause-uploads hidden>Pause uploads</button><button class="transfer-cancel-uploads" type="button" data-cancel-uploads hidden>Cancel uploads</button><span class="transfer-cancel-feedback" data-cancel-feedback role="status" aria-live="polite"></span></div>
      <div class="transfer-live-stats">
        <div><span>Live speed</span><strong data-live-speed>0 B/s</strong></div>
        <div><span>Transferred</span><strong><span data-live-bytes>0 B</span><small> / <span data-live-total>0 B</span></small></strong></div>
        <div><span>Files in queue</span><strong data-live-file-count>0</strong></div>
        <div><span>Time remaining</span><strong data-live-eta>Calculating…</strong></div>
      </div>
      <div class="transfer-live-progress-row"><div class="transfer-live-progress" role="progressbar" aria-label="Overall transfer progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><span data-live-progress-fill></span></div><span data-live-progress-label>0%</span></div>
    </div>
    <div class="transfer-journey-legend" aria-hidden="true"><span><i class="upload-key"></i>Upload</span><span><i class="download-key"></i>Download</span></div>
  </section>`;
}

export function bindTransferJourney(section, listTransfers, cancelTransfer, pauseTransfer, resumeTransfer) {
  if (!section || section.dataset.motionBound === 'true') return;
  section.dataset.motionBound = 'true';
  const svg = section.querySelector('svg.transfer-journey-art');
  const path = svg?.querySelector('#transfer-journey-path');
  if (!svg || !path) return;

  const updateLayout = () => {
    const width = section.getBoundingClientRect().width;
    const centered = width < 520;
    section.dataset.cloudCentered = String(centered);
    svg.setAttribute('viewBox', getTransferJourneyViewBox(width));
  };
  updateLayout();
  const resizeObserver = typeof ResizeObserver === 'function' ? new ResizeObserver(updateLayout) : null;
  resizeObserver?.observe(section);

  const packets = Array.from(svg.querySelectorAll('.transfer-file-packet'));
  const summary = section.querySelector('.transfer-live-summary');
  const cancelButton = summary?.querySelector('[data-cancel-uploads]');
  const pauseButton = summary?.querySelector('[data-pause-uploads]');
  const cancelFeedback = summary?.querySelector('[data-cancel-feedback]');
  const prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    || document.documentElement.dataset.reduceMotion === 'true';
  const duration = 5200;
  let activity = { upload: false, download: false };
  let startedAt = 0;
  let frameId = 0;
  let polling = false;
  let disposed = false;
  let pathLength = 0;
  let latestTransfers = [];
  try { pathLength = path.getTotalLength(); } catch { /* Keep the illustration still if SVG geometry is unavailable. */ }

  const hasActivity = (state) => state.upload || state.download;
  const renderFrame = (now) => {
    frameId = 0;
    if (disposed || !section.isConnected || !hasActivity(activity) || prefersReducedMotion || !pathLength) return;
    const elapsed = (now - startedAt) / duration;
    for (const packet of packets) {
      const direction = packet.classList.contains('upload') ? 'upload' : 'download';
      if (!activity[direction]) { packet.setAttribute('opacity', '0'); continue; }
      const progress = (elapsed + Number(packet.dataset.phase || 0)) % 1;
      const pathProgress = getTransferJourneyPathProgress(progress, direction);
      const point = path.getPointAtLength(pathLength * pathProgress);
      const frame = getTransferJourneyFrame(progress);
      packet.setAttribute('transform', `translate(${point.x} ${point.y}) scale(${frame.scale})`);
      packet.setAttribute('opacity', String(frame.opacity));
    }
    frameId = window.requestAnimationFrame(renderFrame);
  };

  const setActivity = (next) => {
    const changed = next.upload !== activity.upload || next.download !== activity.download;
    const wasIdle = !hasActivity(activity);
    activity = next;
    section.dataset.uploadActive = String(next.upload);
    section.dataset.downloadActive = String(next.download);
    if (changed && wasIdle && hasActivity(next)) startedAt = performance.now();
    if (hasActivity(next) && !prefersReducedMotion && pathLength && !frameId) {
      frameId = window.requestAnimationFrame(renderFrame);
    } else if (!hasActivity(next) && frameId) {
      window.cancelAnimationFrame(frameId);
      frameId = 0;
      for (const packet of packets) packet.setAttribute('opacity', '0');
    }
  };

  const updateSummary = (transfers) => {
    if (!summary) return;
    latestTransfers = Array.isArray(transfers) ? transfers : [];
    const totals = getTransferJourneySummary(transfers);
    summary.dataset.liveVisible = String(totals.visible);
    if (cancelButton) cancelButton.hidden = !getCancellableUploadIds(latestTransfers).length;
    const pausableIds = getPausableUploadIds(latestTransfers);
    const resumableIds = getResumableUploadIds(latestTransfers);
    if (pauseButton) {
      pauseButton.hidden = !pausableIds.length && !resumableIds.length;
      pauseButton.textContent = pausableIds.length ? 'Pause uploads' : 'Resume uploads';
      pauseButton.dataset.action = pausableIds.length ? 'pause' : 'resume';
    }
    const setText = (selector, value) => {
      const node = summary.querySelector(selector);
      if (node && node.textContent !== value) node.textContent = value;
    };
    setText('[data-live-state]', totals.state);
    setText('[data-live-files]', `${totals.fileCount} ${totals.fileCount === 1 ? 'file' : 'files'}`);
    setText('[data-live-speed]', `${formatTransferJourneyBytes(totals.speedBps)}/s`);
    setText('[data-live-eta]', formatTransferJourneyEta(totals.etaSeconds));
    setText('[data-live-bytes]', formatTransferJourneyBytes(totals.transferredBytes));
    setText('[data-live-total]', formatTransferJourneyBytes(totals.totalBytes));
    setText('[data-live-file-count]', String(totals.fileCount));
    setText('[data-live-progress-label]', `${totals.progressPercent}%`);
    const progress = summary.querySelector('[role="progressbar"]');
    progress?.setAttribute('aria-valuenow', String(totals.progressPercent));
    const fill = summary.querySelector('[data-live-progress-fill]');
    if (fill) fill.style.width = `${totals.progressPercent}%`;
  };

  cancelButton?.addEventListener('click', async () => {
    const transferIds = getCancellableUploadIds(latestTransfers);
    if (!transferIds.length || typeof cancelTransfer !== 'function' || cancelButton.disabled) return;
    cancelButton.disabled = true;
    cancelButton.textContent = 'Cancelling…';
    if (cancelFeedback) cancelFeedback.textContent = '';
    try {
      await Promise.all(transferIds.map((id) => cancelTransfer(id)));
      await sync();
      if (cancelFeedback) cancelFeedback.textContent = 'Uploads cancelled';
    } catch {
      if (cancelFeedback) cancelFeedback.textContent = 'Could not cancel uploads. Try again.';
    } finally {
      cancelButton.disabled = false;
      cancelButton.textContent = 'Cancel uploads';
      cancelButton.hidden = !getCancellableUploadIds(latestTransfers).length;
    }
  });

  pauseButton?.addEventListener('click', async () => {
    const pausing = pauseButton.dataset.action !== 'resume';
    const transferIds = pausing ? getPausableUploadIds(latestTransfers) : getResumableUploadIds(latestTransfers);
    const action = pausing ? pauseTransfer : resumeTransfer;
    if (!transferIds.length || typeof action !== 'function' || pauseButton.disabled) return;
    pauseButton.disabled = true;
    pauseButton.textContent = pausing ? 'Pausing…' : 'Resuming…';
    if (cancelFeedback) cancelFeedback.textContent = '';
    try {
      await Promise.all(transferIds.map((id) => action(id)));
      await sync();
      if (cancelFeedback) cancelFeedback.textContent = pausing ? 'Uploads paused' : 'Uploads resumed';
    } catch {
      if (cancelFeedback) cancelFeedback.textContent = `Could not ${pausing ? 'pause' : 'resume'} uploads. Try again.`;
    } finally {
      pauseButton.disabled = false;
    }
  });

  const sync = async () => {
    if (disposed || polling) return;
    if (!section.isConnected) { dispose(); return; }
    if (typeof listTransfers !== 'function') { setActivity({ upload: false, download: false }); updateSummary([]); return; }
    polling = true;
    try {
      const transfers = await listTransfers();
      setActivity(getTransferJourneyActivity(transfers));
      updateSummary(transfers);
    }
    catch { setActivity({ upload: false, download: false }); updateSummary([]); }
    finally { polling = false; }
  };
  const timer = window.setInterval(sync, 900);
  function dispose() {
    if (disposed) return;
    disposed = true;
    window.clearInterval(timer);
    if (frameId) window.cancelAnimationFrame(frameId);
    resizeObserver?.disconnect();
  }
  sync();
}
