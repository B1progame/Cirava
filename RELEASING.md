# Publishing Cirava releases

This is the maintainer memory for building and publishing Cirava. The GitHub Actions workflow builds the Windows app and Inno Setup installer, runs backend tests, computes the installer SHA-256, writes `update-manifest.json`, and publishes a GitHub Release. Do not upload unsigned hand-built installers or edit the generated manifest by hand.

## How the update path is connected

Graphify's code map traced the release path through `.github/workflows/release.yml`, `src/main.tsx`, `backend/main.py`, and `backend/cirava_backend/updater.py`:

- The tagged workflow builds `Cirava-Setup-<version>.exe`, hashes it, and uploads that installer plus `update-manifest.json` to the GitHub Release.
- `src/main.tsx` exposes Stable and Beta choices. Stable reads the latest stable release; Beta asks the GitHub releases API for the newest published prerelease and follows its manifest asset.
- `CiravaApi.check_for_update` and `stage_update` fetch the selected manifest. `Updater` validates HTTPS, SemVer, installer size, and SHA-256 before the UI can offer restart/install.
- `is_newer_version` compares prereleases correctly. A stable release supersedes a beta with the same base version; increment beta tags rather than reusing them.

The generated graph and its queryable release trace live under `graphify-out/` for future codebase questions.

## Before publishing

1. Finish the change and test it locally. For a beta, test the installer and the update flow on a beta-installed build before declaring it stable.
2. Update `package.json` and any user-facing version literals only when the product version itself needs changing. The release tag is the authoritative version embedded by CI.
3. Commit and push the intended changes to the repository's default branch.
4. Confirm the GitHub Actions workflow is enabled and the release permissions allow Actions to create releases (`contents: write`).

## Publish a beta

Use a SemVer prerelease tag. Increase the prerelease number for every beta build; never reuse an existing tag.

```powershell
git tag -a v1.0.1-beta.1 -m "Cirava 1.0.1 beta 1"
git push origin v1.0.1-beta.1
gh run watch
```

The workflow marks the GitHub Release as a prerelease. In Cirava's About → Check for updates screen, choose **Beta releases**. Cirava asks GitHub for the newest published prerelease, downloads that release's `update-manifest.json`, verifies the installer SHA-256, and only then offers to install it. Keep uploading beta tags (`...beta.2`, `...beta.3`) while testing large transfers.

## Publish stable

Only promote a version after beta validation. Use a stable tag without a suffix:

```powershell
git tag -a v1.0.1 -m "Cirava 1.0.1"
git push origin v1.0.1
gh run watch
```

The stable release becomes GitHub's latest release, and Cirava's **Stable release** channel reads its manifest. Stable users do not receive prereleases. A stable version must sort newer than the installed version; do not publish `v1.0.0` as an update to an already-installed `1.0.0` build.

## Release page content

GitHub Actions generates release notes from the commits and merged pull requests associated with the tag. The release page should read like the example: clear product/version title, a version heading, and short scannable bullets describing user-visible changes. Do not claim fixes that are not in the tagged changes. The installer and manifest appear under **Assets** automatically; do not upload a second copy manually.

If generated notes are empty or too technical, edit the release description on GitHub after the workflow completes. Keep the asset names and manifest unchanged so the updater continues to find and verify the release.

## Confirm the release

After Actions completes, inspect the Release page and check it contains both the versioned `Cirava-Setup-<version>.exe` and `update-manifest.json`. Verify the release is marked prerelease for beta tags and not prerelease for stable tags. Test **Check for updates** from a beta build and a stable build separately. If a release failed, fix the cause and use a new version/tag; do not force-move a published tag.

The repository must have `.github/workflows/release.yml` on the branch before pushing a version tag. `gh auth status` checks CLI authentication; `gh login --status` is not a valid GitHub CLI command. Never put a personal access token in source code or a release asset.
