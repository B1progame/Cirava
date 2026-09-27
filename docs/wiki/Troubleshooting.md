# Troubleshooting

## Google will not let me sign in

Check that the Google Drive API is enabled in the same Cloud project as the OAuth client. The client type must be **Desktop app**. If the OAuth audience is External and still in Testing, add the account you are using to **Test users**. Then run **Test configuration** in Cirava and retry sign-in in the browser.

That configuration check only validates the client ID format and network access. It does not test the consent screen. Google also expires some test-user authorizations after seven days. The [Google sign-in setup](Google-OAuth-Setup) page explains the audience and test-user settings.

## Drive is missing folders or actions

Make sure Cirava is connected to the account that can see the item. Current Cirava versions request full Drive access for Trash, restore, and account storage features. If you upgraded from an older version, reconnect Google and approve the expanded access. Shared Drive operations still depend on the signed-in user's permissions. Read [Google sign-in setup](Google-OAuth-Setup#part-1-configure-google-cloud) before changing OAuth settings.

## Upload does not start

Confirm the planner has files or a folder selected, the destination is right, and you held **Start upload** until it confirmed. The empty-folder **Upload files** button opens the same planner; it does not start a transfer by itself.

The optional Cobalt test file is a real 20 GB upload to your Google Drive. It uses Drive storage. If Cirava says test data is disabled, choose local files or enable **Test data** in Settings.

## The transfer shows 0 B/s or does not move

At startup, Cirava may still be creating a Drive session. A paused transfer also reports zero speed. Check the status under the progress panel: **Starting transfer**, **Retrying**, or an error gives more context. If it keeps retrying, check your connection, the account's access to the destination, and available Drive quota. Open **Diagnostics** if the issue continues.

## A download fails

Check that the destination folder has free space and that the signed-in account can download the item. Folder downloads are ZIP archives. Google Docs, Sheets, and Slides need an export format; they are not ordinary binary downloads.

## The app asks me to run the installer for an update

Cirava uses the installer when the major version increases, such as 1.x to 2.x. Updates within the same major version use the in-app app update, such as 1.1.2 to 1.1.3.

## The release-channel menu stays open

The channel menu should be closed until you open **Release channel**. If it does not close after choosing Stable or Beta, restart Cirava and install the current release. Press **Escape** to close the menu, or click elsewhere in the dialog.

## The window closed, but Cirava is still running

Closing the window leaves Cirava in the Windows notification area. Active transfers continue there. Open the tray icon and choose **Open Cirava** to return. Choose **Exit Cirava** when you want to stop the app and its background work.

## Sign-in or transfer keeps failing

Share the Cirava version, Windows version, action you were taking, and the exact error after removing account and file names. Never share OAuth codes, tokens, client secrets, `Authorization` headers, resumable-upload URLs, or an unredacted `transfers.db`. The repository's [security model](https://github.com/B1progame/Cirava/blob/main/SECURITY.md) lists sensitive data to keep out of reports.
