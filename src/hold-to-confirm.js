export function createHoldProgress({ durationMs = 900, onProgress = () => {}, onConfirm = () => {} } = {}) {
  let startedAt = null;
  let complete = false;
  let progress = 0;

  return {
    begin(now) {
      if (complete || startedAt !== null) return false;
      startedAt = now;
      progress = 0;
      onProgress(progress);
      return true;
    },
    tick(now) {
      if (startedAt === null || complete) return progress;
      progress = Math.max(0, Math.min(1, (now - startedAt) / durationMs));
      onProgress(progress);
      if (progress >= 1) {
        complete = true;
        onConfirm();
      }
      return progress;
    },
    cancel() {
      if (startedAt === null || complete) return false;
      startedAt = null;
      progress = 0;
      onProgress(progress);
      return true;
    },
    get complete() { return complete; },
  };
}

const confirmedClicks = new WeakSet();

/** Trigger a protected control only from another already-confirmed hold action. */
export function clickAfterHold(button) {
  if (!button) return;
  confirmedClicks.add(button);
  try { button.click(); }
  finally { confirmedClicks.delete(button); }
}

export function bindHoldToConfirm(button, { durationMs = 900, label = 'start', onConfirm } = {}) {
  if (button.dataset.holdConfirmBound === 'true') return () => {};
  button.dataset.holdConfirmBound = 'true';
  const prompt = document.createElement('span');
  prompt.className = 'hold-confirm-prompt';
  prompt.textContent = `Hold to ${label}`;
  prompt.id = `cirava-hold-instructions-${Math.random().toString(36).slice(2, 9)}`;
  const describedBy = button.getAttribute('aria-describedby');
  button.setAttribute('aria-describedby', [describedBy, prompt.id].filter(Boolean).join(' '));
  button.append(prompt);
  button.classList.add('hold-to-confirm');

  let interval = 0;
  let activePointer = null;
  let activeKey = null;
  let bypassClick = false;
  let live = true;
  const originalAriaLabel = button.getAttribute('aria-label');
  const setProgress = (value) => {
    button.style.setProperty('--hold-progress', String(value));
    button.dataset.holdProgress = String(Math.round(value * 100));
    if (value > 0 && value < 1) {
      button.dataset.holding = 'true';
      prompt.textContent = 'Keep holding…';
    } else {
      delete button.dataset.holding;
      prompt.textContent = value === 1 ? 'Starting…' : `Hold to ${label}`;
    }
    if (originalAriaLabel) button.setAttribute('aria-label', originalAriaLabel);
  };
  const stop = (cancel = true) => {
    if (interval) window.clearInterval(interval);
    interval = 0;
    activePointer = null;
    activeKey = null;
    if (cancel && !hold.complete) hold.cancel();
  };
  const hold = createHoldProgress({
    durationMs,
    onProgress: setProgress,
    onConfirm: () => {
      stop(false);
      button.dataset.holdConfirmed = 'true';
      bypassClick = true;
      button.click();
      bypassClick = false;
      delete button.dataset.holdConfirmed;
      if (typeof onConfirm === 'function') onConfirm();
    },
  });
  const begin = () => {
    if (!live || button.disabled || !hold.begin(Date.now())) return false;
    interval = window.setInterval(() => hold.tick(Date.now()), 16);
    return true;
  };
  const cancel = () => stop(true);
  const onPointerDown = (event) => {
    if (!event.isPrimary || event.button !== 0 || button.disabled) return;
    activePointer = event.pointerId;
    begin();
  };
  const onPointerUp = (event) => { if (event.pointerId === activePointer) cancel(); };
  const onPointerMove = (event) => {
    if (event.pointerId !== activePointer) return;
    const bounds = button.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) cancel();
  };
  const onKeyDown = (event) => {
    if ((event.key !== ' ' && event.key !== 'Enter') || event.repeat || button.disabled) return;
    event.preventDefault();
    activeKey = event.key;
    begin();
  };
  const onKeyUp = (event) => {
    if (event.key === activeKey) { event.preventDefault(); cancel(); }
  };
  const onClick = (event) => {
    if (bypassClick || confirmedClicks.has(button)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
  };

  button.addEventListener('pointerdown', onPointerDown);
  document.addEventListener('pointerup', onPointerUp, true);
  document.addEventListener('pointercancel', onPointerUp, true);
  document.addEventListener('pointermove', onPointerMove, true);
  button.addEventListener('keydown', onKeyDown);
  button.addEventListener('keyup', onKeyUp);
  button.addEventListener('blur', cancel);
  button.addEventListener('click', onClick, true);

  return () => {
    live = false;
    cancel();
    button.removeEventListener('pointerdown', onPointerDown);
    document.removeEventListener('pointerup', onPointerUp, true);
    document.removeEventListener('pointercancel', onPointerUp, true);
    document.removeEventListener('pointermove', onPointerMove, true);
    button.removeEventListener('keydown', onKeyDown);
    button.removeEventListener('keyup', onKeyUp);
    button.removeEventListener('blur', cancel);
    button.removeEventListener('click', onClick, true);
    button.classList.remove('hold-to-confirm');
    delete button.dataset.holdConfirmBound;
    prompt.remove();
    if (describedBy) button.setAttribute('aria-describedby', describedBy);
    else button.removeAttribute('aria-describedby');
    button.style.removeProperty('--hold-progress');
    delete button.dataset.holding;
  };
}
