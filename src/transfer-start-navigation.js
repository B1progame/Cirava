const QUEUED_TRANSFER_METHODS = [
  'create_upload',
  'create_upload_batch',
  'create_test_upload',
  'create_download',
  'resume_transfer',
  'retry_transfer',
];

const IMMEDIATE_TRANSFER_METHODS = [
  'download_drive_folder_zip',
  'download_drive_folder_zip_by_name',
];

const installedMethods = new WeakMap();
const queuedDownloadRequests = new WeakMap();

/** Mark the next native file-download planner submission as queued, not started. */
export function queueNextDownload(api) {
  if (!api || typeof api !== 'object') return false;
  const request = { expiresAt: Date.now() + 120_000 };
  queuedDownloadRequests.set(api, request);
  return true;
}

function representsStartedWork(result) {
  if (Array.isArray(result)) return result.some(representsStartedWork);
  if (result === null || result === undefined || result === false) return false;
  const status = String(result.status || '').toLowerCase();
  return !['cancelled', 'canceled', 'failed', 'skipped'].includes(status);
}

function navigateSafely(navigate) {
  try { navigate(); } catch { /* Navigation must never fail a transfer request. */ }
}

/**
 * Keep the user on the Transfers page once a transfer has actually started.
 * The Drive ZIP bridge runs the download as one long operation instead of
 * returning a queued record, so its navigation happens immediately on call.
 */
export function installTransferStartNavigation(api, navigate) {
  if (!api || typeof api !== 'object' || typeof navigate !== 'function') return false;

  let methods = installedMethods.get(api);
  if (!methods) {
    methods = new Set();
    installedMethods.set(api, methods);
  }

  let allAvailableMethodsInstalled = true;
  for (const method of QUEUED_TRANSFER_METHODS) {
    const original = api[method];
    if (typeof original !== 'function') continue;
    if (methods.has(method)) continue;

    const wrapped = function (...args) {
      if (method === 'create_download') {
        const request = queuedDownloadRequests.get(api);
        if (request) {
          queuedDownloadRequests.delete(api);
          if (request.expiresAt > Date.now()) args[7] = false;
        }
      }
      const result = original.apply(this, args);
      return Promise.resolve(result).then((value) => {
        if (representsStartedWork(value)) navigateSafely(navigate);
        return value;
      });
    };

    try {
      api[method] = wrapped;
      if (api[method] !== wrapped) {
        allAvailableMethodsInstalled = false;
        continue;
      }
      methods.add(method);
    } catch {
      allAvailableMethodsInstalled = false;
    }
  }

  for (const method of IMMEDIATE_TRANSFER_METHODS) {
    const original = api[method];
    if (typeof original !== 'function') continue;
    if (methods.has(method)) continue;

    const wrapped = function (...args) {
      navigateSafely(navigate);
      return original.apply(this, args);
    };

    try {
      api[method] = wrapped;
      if (api[method] !== wrapped) {
        allAvailableMethodsInstalled = false;
        continue;
      }
      methods.add(method);
    } catch {
      allAvailableMethodsInstalled = false;
    }
  }

  return allAvailableMethodsInstalled && methods.size > 0;
}
