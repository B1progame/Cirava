# Cirava build plan

## Product direction

Cirava is a calm, premium desktop transfer client: a light-blue instrument panel for moving authorized Google Drive files quickly, resumably, and transparently. The distinctive element is the transfer map: real queue state becomes a visual path between local storage and Drive. The rest of the UI stays quiet and information-dense.

## Prompt analysis

Prompt 1 defines the transfer engine: desktop-native architecture, OAuth, minimum scopes, resumable ordered uploads, segmented range downloads, bounded memory, adaptive chunk/worker control, retry/backoff, integrity, persistence, diagnostics, conflict handling, and speed modes.

Prompt 2 defines the product shell: first-run setup, current Google setup guidance, login, Drive explorer, planners, drag/drop, transfer visualization, settings, history, about, updater, error UX, responsive desktop behavior, accessibility, and motion.

## Completed slices

- React/Vite shell with Cirava visual tokens, dynamic light background, reduced-motion support, keyboard focus styles, navigation, Home, Drive, Transfers, History, Settings, About.
- Upload planner, animated resumable transfer map, queue, diagnostics panel, toasts, search, transfer modes, account menu, logout/login hero.
- Five-step first-run setup state machine with distinct Project, Drive API, Test user, Desktop OAuth client, and Connection validation stages; optional client secret field; official Google Cloud Console link; and `?reset=1` repeatable developer path.
- Python backend bridge with SQLite transfer persistence and pywebview entry point.
- Windows DPAPI token protection, desktop OAuth loopback + PKCE, minimum `drive.file` scope, state validation, no token logging.
- Ordered Drive resumable uploader with 256 KiB alignment, adaptive chunk hysteresis, retry policy, and segmented random-access downloader.
- Streaming MD5 verification, non-blocking token-bucket bandwidth limiting, automatic access-token refresh, and a PyInstaller desktop bundle (`dist/Cirava.exe`).
- Native pywebview file/folder pickers, recursive upload batches, persisted segmented-download range maps, and explicit ask/skip/replace/keep-both conflict policies.
- Recursive uploads now retain relative paths, migrate them into the transfer store, and create matching Drive folders before uploading each file.
- Signed/checksummed updater manifest validation and staging boundary, with backend tests covering OAuth, transfers, bridge behavior, and updates.
- Cooperative pause/cancel/resume/retry controls with worker stop checks between upload chunks and download segments, plus bridge-backed transfer-center controls.
- Measured current/average/peak throughput and disk-write rates persisted per transfer, surfaced in the Diagnostics panel; repeated folder paths are deduplicated within a running batch.
- Corrected the Inno Setup source to consume the verified single-file `dist/Cirava.exe`; added an updater manifest template and `.env.example` deployment configuration.
- Added a `package:desktop` pipeline that keeps the verified PyInstaller artifact in `packaging/output/Cirava.exe`, outside Vite's cleanable `dist` directory; TypeScript validation passes.
- Paused transfers can now be restarted after a new API process, and folder reuse checks Drive before creating missing folders.
- About now stages a verified signed update when the configured manifest reports a newer release, and communicates the restart requirement.
- Transfer modes now select real upload chunk sizes: Eco 16 MiB, Auto/Fast 64 MiB, Max 128 MiB, all Drive-aligned.
- Desktop bridge, Drive-list, file-picker, and queueing failures now surface as dismissible UI errors; the browser preview remains intentionally self-contained.
- Drive explorer now requests the active parent ID, supports nested folder traversal, resets search per folder, and exposes a My Drive breadcrumb return.
- Drive files now expose real Download row actions: native save path selection, conflict-safe segmented downloads, and MD5 verification from Drive metadata.
- Drive folders can now be selected as upload destinations; the planner reflects the selected folder and the bridge queues uploads with its parent ID.
- History now renders persisted completed, failed, and cancelled transfer records, retaining a preview fallback only when no backend records exist.
- History cleanup now removes only finished transfer records, while active work remains visible; Transfers also exposes a functional New transfer action.
- Persisted transfer failures now flow into the live bridge model and appear as queue-row diagnostics via the native title surface.
- Adaptive upload chunk sizing is now connected to the real resumable uploader: aligned chunks grow after stable latency/throughput and shrink under unhealthy observations, with a regression test.
- Segmented downloads now adapt worker concurrency in bounded waves, increasing after stable ranges and backing off on slow/erroring ranges while retaining range-map resume behavior.
- Added fake-Drive bridge integration coverage for real upload and download workers, including persisted completion state and MD5 verification.
- Drive resumable uploads now retry Google 429/5xx responses through the exponential backoff policy, with explicit regression coverage for rate limits.
- Live Drive listing failures now clear native-mode rows instead of leaving preview fixtures visible, so the desktop shell cannot misrepresent stale demo data as the user’s Drive.
- Staged updates now use executable filenames and expose a path-validated `restart_staged_update` handoff from the About page; arbitrary paths are rejected.
- Transfer mode now persists in local preferences across launches, and About identifies the packaged engine as the adaptive Drive engine.
- Selected speed modes now affect both directions: upload chunk sizing and segmented-download worker counts are coordinated from the same mode choice.
- Inno Setup now offers an optional per-user Windows startup shortcut and removes it with the uninstall; the packaging README documents the behavior.
- Upload resumable-session URLs are now persisted with transfer records; paused/restarted uploads reuse the Drive session and saved byte offset instead of re-uploading from zero. Pause-state telemetry is synchronized before worker transitions.
- Legacy transfer databases migrate the new session field safely, with Windows-specific migration coverage.
- Settings toggles now persist locally; Reduce motion and Animated background apply actual document-level behavior, and controls expose pressed state for accessibility.
- Expired Drive resumable sessions now clear their stale URL and offset on `404`, allowing Retry to create a fresh session rather than failing repeatedly.
- Drive listings now follow pagination tokens across all result pages, preserving large-Drive explorer and folder lookup behavior beyond 1,000 entries.
- OAuth failures now reset the login state and surface a safe retry message instead of leaving the sign-in button permanently disabled.
- Segmented Drive range downloads now retry transient network and 429/5xx failures with cooperative pause/cancel checks, while preserving range-map resume state; regression coverage now exercises the retry path.
- Transfer diagnostics now use persisted byte/speed/retry counters for remaining bytes, ETA, retries, bottleneck inference, and a rolling 60-second throughput graph instead of decorative or hard-coded values.
- Upload restart recovery now probes the Drive resumable session with `Content-Range: bytes */total` and resumes from Drive's acknowledged range; 308 protocol coverage protects against trusting a locally persisted but unacknowledged chunk.
- Upload planning now uses a real 720 ms press-and-hold gesture with cancelable progress, and the application drop zone forwards native file paths when the desktop webview exposes them instead of treating every drop as a fake preview.
- Drive downloads now open a dedicated Download Planner with destination assignment, conflict-safe messaging, adaptive segmented-transfer details, and a guarded Hold to download action before the backend queue is touched.
- Drive explorer sorting is now functional across name, size, and modified time with ascending/descending state exposed through the accessible sort control.
- Manual transfer mode now persists independently configurable upload chunk sizes (16–256 MiB) and segmented-download worker counts (1–16), and feeds both values into real bridge queue requests.
- Transfer center now has a functional full-screen transfer mode with live progress, speed, ETA, retry count, and pause/cancel controls for background-friendly monitoring.
- Batch uploads now use a bounded four-slot cross-file scheduler, preventing unbounded upload threads while allowing multiple files to saturate fast connections and preserving queued pause/cancel behavior.
- Settings navigation is now functional across General, Transfers, Network, Google account, Appearance, and Updates; Network exposes a bandwidth ceiling and recovery policies, while account/update sections provide actionable state and guidance.
- Transfer rows now expose validated actions for revealing the local file, opening the Drive file, copying a Drive link, and removing finished history entries; active transfers cannot be removed.
- Network bandwidth ceilings are now persisted through the bridge and enforced by a shared token bucket across upload chunks and download ranges; Unlimited disables the cap.
- Setup “Test configuration” now calls a real backend validation path in the desktop build, checking OAuth client shape plus public Google authorization and Drive endpoint reachability, with an actionable visible error state; browser preview retains its deterministic fallback.
- Account sign-out now clears backend OAuth tokens through the bridge before returning to login; the account/settings copy explicitly supports switching accounts through that flow.
- Windows packaging now has a generated Cirava icon embedded in PyInstaller and Inno Setup, a coherent per-user installer configuration, and a PATH-independent `package:installer` helper.
- Drive explorer now exposes a desktop-backed New folder action and a refresh action alongside browsing, sorting, folder destinations, and download planning.
- Added the required repository handoff documents: README, ARCHITECTURE, SECURITY, PERFORMANCE, GOOGLE_SETUP, and TESTING.
- Retry callbacks now persist retry count, rate-limit events, last HTTP status, and computed backoff delay; Diagnostics surfaces active backoff and rate-limit totals.
- Drive API listing now carries all-drives parameters and capability fields, exposes Shared Drive listing, and provides a Workspace export endpoint boundary.
- The shell now includes explicit Local Files and Diagnostics navigation pages.
- Shared Drive selection is now exposed in the Drive toolbar, persists through the backend settings store, and routes listing, folder creation, and root uploads through the selected shared-drive ID.
- Native Workspace items now retain MIME/capability metadata in the explorer, advertise an Exportable action, offer PDF/DOCX/TXT/XLSX/CSV choices, and route through `files.export`; binary items remain on segmented range downloads.
- Cross-file uploads now use a persisted 1–8 worker ceiling with a hill-climbing adaptive controller that increases only after sustained aggregate-throughput improvement and backs off on errors/rate limits; the bridge exposes the bounded setting.

## Verification evidence

- Motion guide pass: added `video-motion/cirava-guide-video`, a 26-second 1920×1080 Remotion composition built from the supplied Google Cloud screenshots. It uses five setup scenes, scene-specific cursor paths with click pulses, glass captions, progress rail, and a light liquid-glass Cirava surface; bundle, lint, still-frame preview, and all-frame MP4 render pass.
- Startup-crash regression pass: the first-run walkthrough observer now compares generated markup before writing it, preventing a self-triggering `MutationObserver` loop that previously crashed Chromium/IAB. Added a visible HTML boot screen and a React startup error boundary so a failed mount can never present a blank window. Verified the repaired setup page in a fresh IAB tab, then rebuilt the desktop executable and installer.

- `npm run build` passes.
- `npm run package:desktop` passes and produces `packaging/output/Cirava.exe`.
- `npm run backend:check` passes.
- `PYTHONPATH=backend python -m unittest discover -s backend\\tests -v`: 52 tests pass, including scheduler cancellation, bounded upload-concurrency persistence and hill-climbing, finished-transfer removal validation, bandwidth-limit persistence, configuration endpoint validation, Shared Drive query construction and persisted selection, Workspace export endpoint construction, and retry callback telemetry.
- IAB tested: setup steps, configuration validation, setup → login, login waiting state, Home, plus menu, planner, transfer map, diagnostics, Drive search, settings, history, About, logout.
- Responsive IAB pass completed at 1100×700 and 1440×900 on a fresh Vite session; measured body width matched the viewport and the updated ETA/telemetry surfaces were visible without horizontal overflow.
- IAB verified that a short click on “Hold to upload” leaves the planner open; sustained pointer behavior is implemented through pointer capture and remains available in the desktop webview.
- IAB verified the Download Planner, local destination assignment, disabled-until-ready state, and short-click protection for “Hold to download”.
- IAB verified Drive row reordering and the accessible “Sort by name, descending” state.
- IAB verified Manual mode renders accessible chunk-size and worker controls, and that 128 MiB / 7 workers persist after navigating away and back.
- IAB verified the full-screen transfer dialog opens from the active queue and visibly exposes the current transfer telemetry plus pause/cancel actions.
- Backend regression suite and Python compilation pass after adding the bounded upload scheduler.
- IAB verified the Network settings section renders its transfer-ceiling selector and connection-recovery controls after switching tabs.
- IAB verified transfer-row action menus and the finished-only “Remove from history” action.
- IAB verified the Network bandwidth selector changes to 500 Mbps and remains exposed alongside recovery controls.
- Fresh IAB onboarding regression verified the updated Test configuration flow reaches the “Everything is ready” state.
- Fresh IAB regression verified account menu → Sign out returns to the Google login hero.
- Fresh IAB onboarding regression verified the Drive explorer renders New folder and Refresh controls with no horizontal overflow.
- Fresh IAB regression verified Local Files and Diagnostics navigation, visible backoff telemetry, and zero measured horizontal overflow.
- Fresh IAB regression verified the Drive toolbar exposes the Shared Drive picker, New folder, and Refresh controls without horizontal overflow.
- Fresh IAB regression verified a native Workspace preview item renders as Exportable with an accessible `Export project-brief` action and no horizontal overflow.
- Fresh post-build IAB regression verified Manual mode exposes the persisted upload-worker control alongside chunk size and download workers, with no horizontal overflow.
- `npm run package:installer` passes with no Inno warnings; isolated silent-install smoke test returned exit code 0 and created both `Cirava.exe` and `unins000.exe` before cleanup.
- Post-control release matrix passes again: TypeScript, Vite build, 52 backend tests, PyInstaller desktop packaging, and Inno Setup installer compilation.
- The shell now listens for native online/offline events, surfaces an explicit offline recovery message, and clears that message when connectivity returns.
- The shell now detects long visibility gaps (sleep/background resume), rechecks persisted transfer state through the desktop bridge, and reports reconnecting/recovered states without blocking startup.
- Release artifacts were rebuilt after lifecycle recovery changes: desktop PyInstaller bundle and Inno Setup installer both compiled successfully.
- Transfer records now persist `priority` (Low/Normal/High) and `queue_order`, with SQLite migration coverage, bridge methods for priority/reorder, priority-aware listing, and accessible queue controls for changing priority and moving rows up/down.
- IAB verified two queue rows expose priority selectors and move controls; changing priority and reordering updates the visible queue without horizontal overflow.
- Queue-enabled release artifacts were rebuilt successfully with PyInstaller and Inno Setup after the 53-test backend / TypeScript / Vite verification matrix.
- Added an optional Windows tray notifier service. The packaged desktop entrypoint starts it, transfer completion/failure emits non-blocking balloon notifications, and preview/tests remain safe when the shell is unavailable.
- Fresh IAB smoke verified onboarding, Drive navigation, Transfers navigation, queue controls, and responsive layout after the notifier change. The 54-test backend matrix, Python compilation, TypeScript, Vite, PyInstaller, and Inno Setup all pass.
- About now exposes a retryable updater recovery surface with safe “current version unchanged” messaging and expandable technical details; IAB verified the retry path and no overflow.
- Final updater-enabled desktop and installer artifacts were rebuilt successfully after the 54-test / TypeScript / Vite verification matrix.
- The updater retry surface is included in the latest packaged artifacts; `npm run package:desktop` and `npm run package:installer` both completed successfully.
- Appearance now has persisted Light/Dark/System theme selection, system preference tracking, dark design tokens and component overrides, and IAB verification for dark/system rendering without overflow.
- Theme-enabled release artifacts were rebuilt successfully after the 54-test / TypeScript / Vite verification matrix.
- Final post-API-correction matrix passes again: TypeScript, 49 backend tests, PyInstaller desktop packaging, and Inno Setup installer compilation.
- Final artifact inventory: `packaging/cirava.ico`, `packaging/output/Cirava.exe`, and `packaging/output/Cirava-Setup-0.1.0.exe` all present; final TypeScript, Vite, and 46-test backend matrix passes.

## Remaining implementation passes

1. Finish live-shell hydration: expose richer backend error details in structured cards and complete the visible updater failure/retry UX.
2. Complete desktop background ergonomics: polish updater restart/failure UX; native tray presence, completion/failure notifications, and tray-click window restore are implemented.
3. Add full real-account E2E coverage with a user-supplied test Google account, including upload, restart/interruption resume, segmented download, Workspace export, and rate-limit/error handling.

Shared Drive selection, all-drives listing, capability-aware rows, Workspace export format routing, adaptive upload concurrency, visible Manual upload controls, queue priority/reorder, and lifecycle recovery are implemented in the current release slice.

Visual refinement pass: the supplied Cirava logo and cursor artwork are packaged and used in branding/login; Home now has a larger liquid-glass plus stage with animated orbit/cloud accents and separate Upload to Drive / Download from Drive actions; login now has pointer-reactive floating depth, animated cloud/rain ambience, bounded cursor rain trails, reduced-motion support, and the revised transfer-focused copy. Fresh IAB smoke verified onboarding, login, Home, and the plus menu. The latest desktop executable and installer were rebuilt after this cursor pass.

Desktop ergonomics pass: Windows tray activation now restores, shows, and brings the pywebview window forward when the tray icon is clicked, while remaining safe before the desktop shell starts. Backend regression suite is now 55 tests.

Live-shell recovery pass: bridge/offline error toasts now expose a Retry connection action that rechecks the backend and dismisses the error only after a successful response. TypeScript, Vite, 55 backend tests, IAB shell smoke, PyInstaller, and Inno Setup passed after the change.

Real-account E2E pass: added an explicit opt-in `backend/scripts/real_google_e2e.py` runner and documented the safe local OAuth-client-ID workflow in `TESTING.md`. It performs interactive OAuth, creates an isolated Drive E2E folder, pauses each transfer, reopens the persistent database through a fresh API instance, resumes, downloads with segmented workers, and verifies SHA-256; it refuses to run unless explicitly enabled. The account-dependent run remains pending until a dedicated test client ID is configured locally.

E2E handoff pass: added the same opt-in variables to `.env.example`; the runner still refuses execution without `CIRAVA_RUN_REAL_E2E=1`. TypeScript and 55 backend tests remain green.

OAuth/E2E correction pass: Google’s real response exposed a required `client_secret`; OAuth token exchange and refresh now include a locally supplied secret, the E2E runner supports `CIRAVA_E2E_CLIENT_SECRET`, and the setup screen injects a visible credential checklist. The upload pause/restart race was fixed by honoring stop state before worker preparation/transfer. Desktop and installer artifacts were rebuilt after the fix.

Guided-credentials pass: the setup checklist now includes a client-secret field, sends it only to the local pywebview bridge, stores it through protected desktop credential storage, and reuses it for future token refreshes. IAB verified the field at setup step 3. The pause/restart fix and OAuth changes are included in the latest desktop and installer builds.

Upload-completion identity pass: the final 200/201 resumable-upload response is now parsed for the Google Drive file ID and persisted on the completed transfer. Added protocol coverage for this response so the real-account runner can continue into segmented download instead of falsely reporting a completed upload as failed.

E2E timing pass: the real-account runner now handles very fast uploads/downloads that complete before a pause request, while still exercising pause/restart whenever the transfer remains active. This removes the remaining `preparing` restart race from the test harness.

Planner fidelity pass: native file/folder selections are summarized by the backend without reading file contents, and the upload planner now shows the selected item name, file/folder counts, byte total, and a size-derived estimate instead of a hard-coded demo payload.

Google setup capture pass: inspected the current Google Cloud Console project selector, New Project screen, project-gated API Library error state, and APIs & Services navigation. Added a privacy-safe live walkthrough that maps Cirava's five setup states to the exact project, Drive API, OAuth test-user, Desktop client, and validation actions without storing account-bearing screenshots.

Transfer quiescence pass: added an active-worker barrier and made the real Google E2E runner wait for paused workers to release I/O before creating a fresh API instance. Each E2E run now uses a unique download path so stale `.part` and range files cannot collide with a later segmented writer.

Settings completion pass: added a visible “Run setup guide again” action to the connected-account settings surface, preserving stored OAuth tokens while allowing the user to revisit or correct Google Cloud configuration. Added press feedback and an explicit reduced-motion override for the remaining animated UI.

Real-account verification pass: host-context E2E reused the protected local OAuth session and passed a real Drive upload, segmented download, checksum verification, and persistent pause/resume across API instances. The runner now skips redundant browser OAuth when a valid local session exists, and terminal fast-transfer resume is idempotent. Workspace export and rate-limit handling remain separately gated by account-specific fixtures.

Workspace export gate pass: the real-account runner now accepts an explicit local `CIRAVA_E2E_WORKSPACE_FILE_ID`, export MIME type, and output path. It verifies a user-supplied native Workspace fixture without creating cloud documents or printing the file ID; the gate remains intentionally unrun until such a fixture is supplied.

Telemetry fidelity pass: the workspace header speed pill and transfer badge now derive from live queued/preparing/transferring/network-waiting/rate-limited records instead of showing a hard-coded demo speed when the desktop bridge is idle. TypeScript, Vite, 58 backend tests, PyInstaller, and Inno Setup passed after the change; the rebuilt executable remains responsive after launch.

Native shell launch pass: launched the rebuilt packaged executable from the host and confirmed the Cirava process remains responsive. The final executable and installer were rebuilt after the real-account fix.

Workspace export audit: the authenticated test Drive exposed folders only at the inspected levels, with no native Docs/Sheets/Slides fixture to export. The Drive export endpoint remains covered by protocol tests; no cloud document was created merely to manufacture a fixture. A fresh IAB preview attempt still hit the environment's CDP focus timeout, while the local preview HTTP endpoint returned 200.

Five-step onboarding verification: IAB advanced through Project, Drive API, Test users, and Desktop OAuth client; the refreshed setup screen displayed `01 / 05`, a visible guide video, the client ID field, and exactly one client-secret field after removing the duplicate injected secret control.

First-run composition pass: removed the duplicated injected OAuth checklist, kept the setup guidance in one sequence-aware panel, and added a rendered light guide poster so the embedded video has a deliberate first frame before playback. IAB screenshot review confirmed the cleaner composition; desktop and installer artifacts were rebuilt.

OAuth cache recovery pass: an unreadable Windows-protected token cache now falls back to signed-out state instead of crashing `boot_state()`; regression coverage raises the backend matrix to 59 tests.

OAuth live-account gate: the opt-in E2E runner was completed through the authenticated Google account-selection page; Google returned `403 access_denied` because the selected account is not currently approved as a test user for this OAuth client. No credentials were exposed and no Google Cloud permissions were changed by Cirava.

OAuth live-account verification pass: after approving the selected Google test account and granting Cirava the minimum `drive.file` scope, the network-enabled E2E runner completed real OAuth token exchange, created an isolated Drive test folder, uploaded a 1 MiB fixture, exercised pause/resume across a fresh API process, downloaded it through four segmented workers, and verified the SHA-256 checksum. Workspace export remains opt-in because no native Docs/Sheets/Slides fixture was supplied; rate-limit behavior remains covered by protocol tests rather than induced against the account.

Release artifact verification pass: rebuilt the Windows desktop executable and Inno Setup installer after the live-account verification; both completed successfully and the packaged app includes the current liquid-glass UI, onboarding guide, OAuth recovery, transfer controls, tray support, and motion styling.
