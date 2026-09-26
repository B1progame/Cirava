# <img src="public/cirava-logo.png" width="42" height="42" alt="Cirava logo" align="center"> Cirava

### Your files, in motion.

Cirava is a Windows desktop client for Google Drive, built for transfers that are fast, resumable, and easy to understand. Choose files locally, watch clear progress, and recover cleanly when a connection drops.

> **Stable · v1.0.0** — Cirava's first stable version. Please keep backups of important files while the initial release is being tested in the wild.

![Cirava home screen](docs/images/cirava-home.png)
<sub>Home-screen preview; the screenshot is from the pre-release inspection build.</sub>

## Why Cirava

| | |
|---|---|
| **Resumable transfers** | Uploads and downloads can recover from interruptions instead of starting over. |
| **Clear progress** | See transfer state, throughput, retries, and what needs attention. |
| **Built around Google Drive** | Use your own Google account through the standard desktop OAuth flow. |
| **Local-first credentials** | OAuth tokens stay on your device and are protected by Windows DPAPI. |
| **A focused desktop app** | A native Windows tray app with a calm, purpose-built interface. |

## Screenshots

The home-screen preview above shows Cirava's upload workspace and navigation.

## Download

Download **[Cirava v1.0.0](https://github.com/B1progame/Cirava/releases/latest)** from GitHub Releases. The Windows installer is named `Cirava-Setup-1.0.0.exe`.

## Getting started

Cirava uses a Google **Desktop OAuth client**. Follow [Google setup](GOOGLE_SETUP.md) to configure the client ID, enable the Drive API, and connect your account. Cirava never asks for your Google password.

## Build from source

Requirements: Windows 10/11, Node.js, Python 3.12, and (for the desktop package) PyInstaller and Inno Setup 6.

```powershell
npm.cmd install
npm.cmd run dev -- --host 127.0.0.1 --port 4175
```

Build and verify the desktop app:

```powershell
npx.cmd tsc --noEmit
npm.cmd run build
$env:PYTHONPATH = 'backend'
python -m unittest discover -s backend/tests -q
npm.cmd run package:desktop
npm.cmd run package:installer
```

For transfer and OAuth checks, see [TESTING.md](TESTING.md). Architecture notes are in [ARCHITECTURE.md](ARCHITECTURE.md), packaging guidance is in [packaging/README.md](packaging/README.md), and the maintainer's release checklist is in [RELEASING.md](RELEASING.md).

## Security and privacy

- OAuth uses authorization code + PKCE and the narrow `drive.file` scope.
- Access and refresh tokens are protected with Windows DPAPI.
- Transfers use resumable upload sessions and segmented, recoverable downloads.
- Updates are delivered over HTTPS and checked against the installer SHA-256 before install.
- Cirava does not bypass Drive permissions, quotas, or rate limits.

Read the full [security model](SECURITY.md) and [performance notes](PERFORMANCE.md).

## Project status

Cirava is an independent project. Public repository visibility does not grant permission to redistribute or modify the software; a license has not yet been selected.

Cirava is not affiliated with, endorsed by, or sponsored by Google LLC.
