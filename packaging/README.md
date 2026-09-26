# Packaging

1. Build the React bundle with `npm run build`.
2. Install the pinned Python dependencies from `requirements.txt`.
3. Run PyInstaller with `pyinstaller packaging/cirava.spec`.
4. Run `npm run package:installer` to compile Inno Setup. The helper resolves `ISCC.exe` from PATH or the standard Windows installation path.

The desktop packaging command produces `packaging/output/Cirava.exe`; the Inno script consumes that exact artifact. This keeps the executable safe from Vite cleaning `dist/`. Update manifests publish both the setup program (`url`/`sha256`) and the standalone app (`appUrl`/`appSha256`). Updates that remain in the same major version download and verify the app executable, then replace only `Cirava.exe` and reopen it without an installer wizard. A newer major version uses the verified setup program. If the app is installed under Program Files, Windows may request administrator approval for the file replacement. If Ed25519 signatures are used, their public key must be pinned in the application build; a key supplied only by the manifest is deliberately not trusted.

## GitHub Releases updater

`.github/workflows/release.yml` builds a Windows installer, standalone app executable, and update manifest for semantic-version tags (`vMAJOR.MINOR.PATCH`, optionally with a prerelease suffix). It embeds the version and release-feed endpoints from the actual GitHub repository at build time, generates release notes, calculates SHA-256 for both executable assets, and publishes them with the manifest. Stable tags become the latest stable release; prerelease tags do not replace that feed.

To prepare a release, first finish the large-file upload tests, then push a version tag. Do not tag or publish `v1.0.0` while the current 1.0.0 test build is still being tested; the first newer update should use a higher semantic version (for example `v1.0.1`). The workflow is event-driven and does not publish anything until a matching tag is pushed. The generated manifest has the form in `update-manifest.example.json` and is attached beside the installer.

Keep the 1.0.0 build labeled beta while large-file upload testing is in progress. Do not commit signing private keys or embed GitHub credentials in Cirava. The stable manifest feed intentionally excludes prereleases so beta testing cannot silently move stable users.

The installer is intentionally separate from normal startup: production users do not need Node, npm, Python, or pip installed. The Cirava icon is rendered from the supplied rounded `public/cirava-logo.png`, converted to `cirava.ico`, and embedded in the executable, installer, and MSIX assets.

The Inno Setup wizard offers optional desktop and per-user Windows startup shortcuts; uninstall removes those shortcuts with the application.
