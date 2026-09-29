<div align="center">
  <img src="https://raw.githubusercontent.com/B1progame/Cirava/main/public/cirava-logo.png" alt="Cirava" width="88" height="88">
  <h1>Cirava</h1>
  <p><strong>Your files, in motion.</strong><br>
  A Windows desktop client for moving files through Google Drive and uploading media to Google Photos.</p>
  <p>
    <a href="https://github.com/B1progame/Cirava/releases/latest"><img src="https://img.shields.io/badge/STABLE-v1.3.0-6079ed?style=for-the-badge" alt="Latest stable release: v1.3.0"></a>
    <img src="https://img.shields.io/badge/platform-Windows-2aa995?style=for-the-badge" alt="Windows desktop app">
    <a href="https://github.com/B1progame/Cirava/releases/latest"><img src="https://img.shields.io/badge/download-v1.3.0-28344d?style=for-the-badge" alt="Download Cirava 1.3.0"></a>
  </p>
</div>

<br>

<div align="center">
  <img src="docs/images/cirava-home.png" alt="Cirava Home screen" width="100%">
</div>

## What Cirava does

Cirava connects a Windows desktop app to your Google Drive account. It is built for large transfers and for seeing what the app is doing while they run. Uploads use resumable Drive sessions; downloads can use parallel byte ranges. The transfer center shows progress, speed, retries, and estimated time, with pause, resume, and cancel controls.

You can close the window while work is running. Cirava stays in the Windows notification area and continues active transfers until you reopen it or choose **Exit Cirava**. Drive uploads can target My Drive or a shared drive. The Photos page can browse files across Drive and show media you explicitly select in Google's Photos Picker; you can also upload local photos and videos to your Photos library.

## Download and install

Get the latest build from [GitHub Releases](https://github.com/B1progame/Cirava/releases/latest). The v1.3.0 release includes:

- `Cirava-Setup-1.3.0.exe` for the Windows installer.
- `Cirava.exe` for the standalone app, with no installer.
- `update-manifest.json` for checksum-verified in-app updates.

Cirava now has a dedicated Photos workspace: browse Drive media across locations, choose Photos items through Google's secure Picker, and upload local photos or videos to your library, optionally creating a new album. Shared-drive upload destinations can be selected directly or resolved from a Drive link. The transfer route retains its randomized three-packet animation, and in-app updates preserve Google sign-in data in your Windows profile.

After launching Cirava, connect a Google account using a Desktop OAuth client. This is a one-time setup for the Cloud project and client ID. Follow the [step-by-step Google OAuth setup](GOOGLE_SETUP.md), then use the [wiki](https://github.com/B1progame/Cirava/wiki) for everyday tasks and troubleshooting.

## Everyday tasks

- **Upload:** choose files or a folder, select the Drive destination, review the plan, and hold the start button to begin. The empty-folder upload button opens the same planner.
- **Upload to a shared drive:** choose it from the destination list or paste a shared-drive/folder link. Your account needs permission to add files there. The choice is saved on each upload, not as a global queue setting.
- **Browse cloud media:** open **Google Photos**, then choose **Google Drive** to search files across My Drive and shared drives, or **Google Photos** to select items in Google's secure Picker. Drive downloads can be queued or started immediately. Google-native Docs, Sheets, and Slides appear in search but require export conversion.
- **Upload to Google Photos:** choose **This device**, select media files or a folder, then upload now or add the items to the waiting queue. Photos go to your library at original quality; Google account storage limits may apply.
- **Manage a Google Photos item:** use the Photos Picker to select cloud photos. Cirava opens Google Photos in your default browser for deletion because the Photos API does not expose general deletion; local items can be removed from Cirava's selection without deleting the source file.
- **Download:** hold the item's Download action to confirm, then choose a local destination. Folder downloads are packaged as ZIP files; Google Docs, Sheets, and Slides are exported to a supported format.
- **Control transfers:** open **Transfers** to monitor progress, pause or resume work, cancel it, or inspect recent results.
- **Use Trash:** open **Drive → Trash** to restore items, permanently empty Trash, and see account usage reported by Google.
- **Choose updates:** select Stable or Beta in the update dialog. Updates within the same major version install in-app; a major-version change opens the installer.

The optional 20 GB test upload sends real data to your Drive. It uses your Drive storage and network quota. It is not a local simulation. Optional 7-Zip compression lets you preview actual archive size and savings before adding a compressed upload to the queue.

## Google access and privacy

Cirava uses Google’s installed-app authorization-code flow with PKCE. It never asks for your Google password. OAuth tokens are stored locally and protected with Windows DPAPI for the current Windows user. Do not copy token files to another account or share them in support requests.

Cirava requests `https://www.googleapis.com/auth/drive` to browse Drive items, manage Trash, restore files, and show storage use; `https://www.googleapis.com/auth/photoslibrary.appendonly` to upload media; and `https://www.googleapis.com/auth/photospicker.mediaitems.readonly` to receive only the items you select in Google's Photos Picker. It cannot silently enumerate your complete Google Photos library. In Google Cloud, enable Google Drive API, Google Photos Library API, and Google Photos Picker API, then add all three scopes to OAuth Data Access. The full steps are in [Google OAuth setup](GOOGLE_SETUP.md). Existing users must reconnect to grant the new Photos Picker permission.

See the [security model](SECURITY.md) for local data handling and the [Google OAuth setup guide](GOOGLE_SETUP.md) for the exact Console steps.

## Development

For local development, use Windows 10 or 11, Node.js, and Python 3.12. The installer build also uses PyInstaller and Inno Setup 6.

```powershell
npm.cmd install
npm.cmd run dev -- --host 127.0.0.1 --port 4175
```

To type-check, build, run backend tests, and package the app:

```powershell
npx.cmd tsc --noEmit
npm.cmd run build
$env:PYTHONPATH = 'backend'
python -m unittest discover -s backend/tests -q
npm.cmd run package:desktop
npm.cmd run package:installer
```

See [TESTING.md](TESTING.md), [ARCHITECTURE.md](ARCHITECTURE.md), and [packaging/README.md](packaging/README.md) for the test matrix, component overview, and packaging details. The [wiki](https://github.com/B1progame/Cirava/wiki) includes user guides and technical notes.

## Project links

- [Wiki and user guides](https://github.com/B1progame/Cirava/wiki)
- [Google OAuth setup](https://github.com/B1progame/Cirava/wiki/Google-OAuth-Setup)
- [Release history and downloads](https://github.com/B1progame/Cirava/releases)
- [Report a bug](https://github.com/B1progame/Cirava/issues)

Cirava is an independent project. It is not affiliated with, endorsed by, or sponsored by Google LLC.

## License

Cirava's original code is provided under the [Cirava Personal Use and Modification License](LICENSE.md). You may run and privately modify it for your own non-commercial use. You may not sell, redistribute, or share copies or modified versions without written permission. This is a source-available, custom license—not an OSI-approved open-source license. Third-party components remain under their own licenses; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md), especially for optional 7-Zip integration.

Because this repository is public, GitHub's Terms of Service allow users to view and fork it on GitHub. The custom license cannot remove those GitHub platform rights, so public hosting cannot guarantee that nobody will copy or fork the repository. See [GitHub's Terms of Service](https://docs.github.com/en/site-policy/github-terms/github-terms-of-service) and [LICENSE.md](LICENSE.md).

## Optional 7-Zip compression

In the desktop app, open **Settings → 7-Zip archive compression** and turn it on. Cirava fetches the x64 installer from the official 7-Zip project and checks its SHA-256 against GitHub's release metadata before running setup. It keeps 7-Zip in Cirava's app folder rather than installing it system-wide. In the upload planner, choose **Compress this upload** and **Compress & preview** to see the actual archive size and savings before uploading. When the feature is enabled, downloads of Cirava-created archives are verified by an embedded marker, extracted to a new folder, and opened automatically. Your selected originals are never modified. 7-Zip is independent third-party software, not part of Cirava; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
