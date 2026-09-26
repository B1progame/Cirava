# Testing Cirava

## Automated checks

Run the TypeScript compiler, Vite production build, Python unit suite, PyInstaller build, and Inno Setup compiler:

```powershell
npx.cmd tsc --noEmit
npm.cmd run build
$env:PYTHONPATH='backend'; python -m unittest discover -s backend/tests -q
npm.cmd run package:desktop
npm.cmd run package:installer
```

The backend suite covers OAuth storage, Drive request construction, upload alignment, adaptive sizing, retry/backoff, resumable-session recovery, segmented range resume, MD5 verification, conflict policies, scheduler cancellation, bandwidth persistence, setup validation, updater signatures, and staged-installer path validation.

The browser startup regression test also covers the first-run walkthrough: it must mount without a renderer crash or a self-triggering DOM observer loop. The HTML boot screen is only a pre-mount fallback; a successful mount removes it, while a render exception is shown through the visible startup error boundary.

The five-step setup guide and its embedded video are validated separately from the desktop shell:

```powershell
cd video-motion\cirava-guide-video
npm.cmd run lint
npm.cmd run build
npx.cmd remotion render CiravaGuide out\cirava-guide.mp4
```

The rendered composition is 1920×1080, 26 seconds, and uses the supplied Cloud Console screenshots as visual references rather than sending any account data anywhere. The setup UI keeps the glass header/progress rail visible, exposes Project → Drive API → Test user → Desktop client → Connection stages, and shows one local-only client-secret field.

## Browser/IAB smoke matrix

Fresh sessions verify setup steps, validation success, login waiting/success, Home, Drive search/sort/breadcrumbs, New folder and Refresh controls, upload/download planners, hold-to-start protection, transfer map, full-screen mode, diagnostics, Settings tabs, bandwidth selection, History, About, and logout. Responsive passes use 1100×700 and the wider desktop viewport with a body-width overflow assertion.

## Real-account release gate

Before a public release, run one upload and one download using a dedicated Google test account and non-sensitive fixtures. Confirm pause/resume, process restart recovery, checksum verification, and Drive-side permissions. Do not use production or sensitive data for this test.

An opt-in runner covers the authenticated upload, segmented download, and checksum portion without storing secrets in the repository. Set the non-secret OAuth Desktop Client ID locally, then run:

```powershell
$env:CIRAVA_RUN_REAL_E2E='1'
$env:CIRAVA_E2E_CLIENT_ID='your-desktop-client-id.apps.googleusercontent.com'
$env:CIRAVA_E2E_DATA_DIR=(Join-Path $PWD '.cirava-e2e-data')
python backend/scripts/real_google_e2e.py
```

The script opens the normal Google OAuth flow; complete sign-in yourself. It pauses each transfer, reopens the persistent transfer database through a fresh API instance, resumes, and then verifies the result. Never put a Google password, access token, refresh token, or test-account secret in chat or in the repository.

To verify Workspace export without creating a cloud fixture, supply the ID of a native Google Docs, Sheets, or Slides file that you intentionally chose for testing. The ID is read locally and is not printed:

```powershell
$env:CIRAVA_E2E_WORKSPACE_FILE_ID='your-native-workspace-file-id'
$env:CIRAVA_E2E_WORKSPACE_MIME_TYPE='application/pdf'
$env:CIRAVA_E2E_WORKSPACE_OUTPUT=(Join-Path $env:CIRAVA_E2E_DATA_DIR 'workspace-export.pdf')
python backend/scripts/real_google_e2e.py
```

Supported export MIME types include PDF, DOCX, TXT, XLSX, and CSV. Leave the variable unset when no safe native Workspace fixture is available. Rate-limit behavior is covered by protocol tests and is not induced against a real account.
