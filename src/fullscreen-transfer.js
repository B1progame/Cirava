import { renderTransferJourney } from './transfer-journey.js';

export function renderFullscreenTransferCenter() {
  return `<div class="fullscreen-transfer-center">
    <button class="fullscreen-transfer-close" type="button" data-fullscreen-close aria-label="Close full-screen transfer mode">×</button>
    <header class="fullscreen-transfer-heading">
      <div><span class="eyebrow">Transfer center</span><h1>In motion</h1><p>Every byte accounted for. Nothing left behind.</p></div>
      <button class="secondary" type="button" data-fullscreen-new-transfer><span aria-hidden="true">＋</span> New transfer</button>
    </header>
    <div class="transfer-overview-strip" data-fullscreen-overview>
      <div><span class="transfer-overview-icon upload" aria-hidden="true">↑</span><span><b>Uploads</b><small>Local files moving to Drive</small></span><strong data-fullscreen-upload-count>0</strong></div>
      <div><span class="transfer-overview-icon download" aria-hidden="true">↓</span><span><b>Downloads</b><small>Drive files arriving here</small></span><strong data-fullscreen-download-count>0</strong></div>
      <div class="transfer-overview-note"><span class="status-dot"></span><span>Transfers stay resumable in the background.</span></div>
    </div>
    ${renderTransferJourney()}
  </div>`;
}
