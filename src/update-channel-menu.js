const CHANNELS = new Set(['release', 'beta']);

export function createUpdateChannelMenuState(initialChannel = 'release') {
  let selected = CHANNELS.has(initialChannel) ? initialChannel : 'release';
  let open = false;

  return {
    get open() { return open; },
    get selected() { return selected; },
    toggle() { open = !open; return open; },
    show() { open = true; },
    close() { open = false; },
    escape() {
      if (open) { open = false; return false; }
      return true;
    },
    select(channel) {
      if (CHANNELS.has(channel)) selected = channel;
      open = false;
      return selected;
    },
  };
}
