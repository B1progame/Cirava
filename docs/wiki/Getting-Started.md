# Get started

## Install

Open the [latest release](https://github.com/B1progame/Cirava/releases/latest). Choose `Cirava-Setup-<version>.exe` for the Windows installer, or `Cirava.exe` for the standalone app. Start Cirava from the Windows profile you plan to use; its saved Google credentials are protected for that Windows user.

The current stable release is **Cirava 1.2.2**. The installer is optional; the standalone app is also available on the release page.

Cirava 1.2.2 improves the upload planner's Drive destination picker and the optional 7-Zip setup experience. For the full list of changes, open the [release notes](https://github.com/B1progame/Cirava/releases/tag/v1.2.2).

## Connect Drive

On first launch, Cirava asks for a Google OAuth Desktop client ID. Create one by following [Google sign-in setup](Google-OAuth-Setup), then paste the full ID into Cirava.

Use **Test configuration** to check the ID format and whether Google endpoints are reachable. A successful check does not confirm that the consent screen is correct. Choose **Continue with Google**, finish sign-in in the browser, and return to Cirava. You should see that Drive is connected.

## Upload something

1. Choose **Upload to Drive** on Home or **Upload** on the Drive page.
2. Choose local files or a folder. The Cobalt test file is optional and sends 20 GB to your real Drive, using its storage and network quota.
3. Check the destination folder in the planner.
4. Hold **Start upload** until it confirms. Releasing early cancels the hold.
5. Follow progress on **Transfers**.

If test data is disabled in Cirava Settings, choose local files or enable the test data option before using the Cobalt file.

## Download something

Open Drive, find the item, and hold **Download** until it confirms before choosing where to save it. For a folder, hold **Download as ZIP**. See [Downloads](Downloading) for details.

## Two different testing settings

Google OAuth's **Testing** audience setting controls which Google accounts can sign in. Cirava's **Settings → Test data** option controls whether its sample transfer is available. Changing one does not change the other. For OAuth testing limits and missing Drive folders, see [Google sign-in setup](Google-OAuth-Setup).

For errors, see [Troubleshooting](Troubleshooting). Cirava keeps its local app data under `%APPDATA%\Cirava`; do not copy token files between Windows accounts or post them in an issue.
