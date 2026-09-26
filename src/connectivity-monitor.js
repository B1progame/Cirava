export function createConnectivityMonitor({
  probe,
  onOffline = () => {},
  onOnline = () => {},
  intervalMs = 10_000,
  setIntervalFn = globalThis.setInterval,
  clearIntervalFn = globalThis.clearInterval,
}) {
  if (typeof probe !== 'function') throw new TypeError('A connectivity probe is required');
  let online = null;
  let inFlight = null;
  let timer = null;
  let stopped = false;
  let lastError = null;

  const checkNow = async () => {
    if (stopped) return online;
    if (inFlight) return inFlight;
    inFlight = (async () => {
      try {
        await probe();
        if (stopped) return online;
        lastError = null;
        if (online !== true) onOnline();
        online = true;
      } catch (error) {
        if (stopped) return online;
        lastError = error;
        if (online !== false) onOffline(error);
        online = false;
      }
      return online;
    })();
    try {
      return await inFlight;
    } finally {
      inFlight = null;
    }
  };

  return {
    start() {
      if (stopped || timer !== null) return;
      void checkNow();
      timer = setIntervalFn(() => { void checkNow(); }, intervalMs);
    },
    checkNow,
    get lastError() { return lastError; },
    stop() {
      stopped = true;
      if (timer !== null) clearIntervalFn(timer);
      timer = null;
    },
    get isOnline() { return online; },
  };
}
