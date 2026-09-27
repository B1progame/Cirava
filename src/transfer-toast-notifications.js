const CREATE_METHODS = new Map([
  ['create_upload', 'upload'],
  ['create_upload_batch', 'upload'],
  ['create_test_upload', 'upload'],
  ['create_download', 'download'],
]);

const installed = new WeakMap();

function itemsFrom(result) {
  const items = Array.isArray(result) ? result : result && typeof result === 'object' ? [result] : [];
  return items.filter((item) => item && typeof item === 'object' && item.id
    && !['cancelled', 'canceled', 'failed', 'skipped'].includes(String(item.status || '').toLowerCase()));
}

function displayName(item) {
  return String(item.name || item.filename || item.file_name || item.title || 'file');
}

function directionFor(item, fallback = 'upload') {
  const value = String(item.direction || item.transfer_type || item.type || fallback).toLowerCase();
  return value.includes('download') ? 'download' : 'upload';
}

function label(direction) {
  return direction === 'download' ? 'Download' : 'Upload';
}

function notifySafely(notify, notice) {
  try { notify(notice); } catch { /* Notifications must never interrupt a transfer. */ }
}

/** Add in-app notices for queued work and real transfer-state transitions. */
export function installTransferToastNotifications(api, notify, timers = globalThis) {
  if (!api || typeof api !== 'object' || typeof notify !== 'function') return false;
  if (installed.has(api)) return true;

  const states = new Map();
  let polling = false;
  const remember = (item, direction) => {
    if (!item?.id) return;
    states.set(String(item.id), {
      status: String(item.status || 'queued').toLowerCase(),
      direction: directionFor(item, direction),
      name: displayName(item),
    });
  };

  for (const [method, direction] of CREATE_METHODS) {
    const original = api[method];
    if (typeof original !== 'function') continue;
    const wrapped = function (...args) {
      return Promise.resolve(original.apply(this, args)).then((result) => {
        const created = itemsFrom(result);
        if (created.length) {
          const one = created.length === 1;
          notifySafely(notify, {
            type: 'queued', direction,
            name: one ? displayName(created[0]) : '',
            count: created.length,
            message: one
              ? `${label(direction)} added to queue: ${displayName(created[0])}`
              : `${created.length} ${direction}s added to queue`,
          });
          for (const item of created) remember(item, direction);
        }
        return result;
      });
    };
    try { api[method] = wrapped; } catch { /* Read-only bridge method; polling can still report transitions. */ }
  }

  const poll = async () => {
    if (polling || typeof api.list_transfers !== 'function') return;
    polling = true;
    try {
      const items = await api.list_transfers();
      if (!Array.isArray(items)) return;
      for (const item of items) {
        if (!item?.id) continue;
        const id = String(item.id);
        const status = String(item.status || '').toLowerCase();
        const prior = states.get(id);
        const current = { status, direction: directionFor(item, prior?.direction), name: displayName(item) };
        if (prior && ['queued', 'paused'].includes(prior.status) && ['preparing', 'transferring', 'downloading', 'uploading'].includes(status)) {
          const direction = current.direction;
          notifySafely(notify, {
            type: 'started', direction, name: current.name, count: 1,
            message: `${label(direction)} started: ${current.name}`,
          });
        } else if (prior && prior.status !== status && ['completed', 'complete', 'failed'].includes(status)) {
          const direction = current.direction;
          const failed = status === 'failed';
          notifySafely(notify, {
            type: failed ? 'failed' : 'completed', direction, name: current.name, count: 1,
            message: failed ? `${label(direction)} failed: ${current.name}` : `${label(direction)} complete: ${current.name}`,
          });
        }
        states.set(id, current);
      }
    } catch { /* Transfer status can be temporarily unavailable while the bridge initializes. */ }
    finally { polling = false; }
  };

  const timer = timers.setInterval(poll, 1000);
  installed.set(api, { poll, timer });
  return true;
}
