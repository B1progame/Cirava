# Troubleshooting

## Google sign-in does not finish

- Check that the Google Drive API is enabled in the selected Cloud project.
- Check that you created a **Desktop app** OAuth client and entered its client ID, not a web client ID.
- If the consent screen is in testing, add the account you are signing in with to **Test users**.
- Complete sign-in in the browser window Cirava opened. Do not paste a password or token into Cirava's client ID field.

For setup steps, see [Google Drive setup](Google-Drive-setup).

## Drive is empty or an action is unavailable

Confirm that you signed into the intended account and that the account can access the item. Shared Drive items follow the signed-in account's permissions. Some actions can be unavailable when Google reports that the account cannot download or edit an item.

## Upload does not start

Make sure at least one local file or folder is selected, the destination is correct, and you completed the hold on **Start upload**. The optional 20 GB test upload requires test data to be enabled in Settings and consumes real Google Drive storage. If it is disabled, choose local files or enable the test in Settings.

## The transfer shows 0 B/s

During startup, Cirava may be preparing a Drive session. If the transfer is paused, zero speed is expected. If the state remains on Starting transfer or Retrying, check the connection and the transfer's error details. Leave Cirava open while it retries; use pause/resume if the controls are available. If it repeatedly fails, note the error and check Diagnostics.

## A download will not open

Check that the destination folder has enough free space. For a folder, Cirava creates a ZIP archive. For a Google Docs, Sheets, or Slides item, choose an export format supported for that document type.

## Update asks to run setup

Cirava uses the installer for a newer major version. Updates within the same major version use the standalone app update flow. For example, moving from 1.1.1 to 1.1.2 is a minor/patch update; moving from 1.x to 2.x is a major update.

## Cirava is still running after the window closes

That is expected when the app is in the system tray. Open the notification-area menu and choose **Open Cirava** to return. Choose **Exit Cirava** when you want to stop the app and its background work.
