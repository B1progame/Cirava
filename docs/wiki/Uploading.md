# Upload files

## Choose files and a destination

1. Open **Upload to Drive** or choose **Upload** from the Drive page.
2. Add files, or choose a folder when you want to upload its contents.
3. Choose the Drive destination. Check the destination shown in the planner before starting.
4. Review the selected items and destination.
5. Hold **Start upload** until the action completes. The hold prevents an accidental start while you are still choosing files.

The **Upload files** action in an empty Drive folder opens the same planner. It does not start uploading by itself.

## Compress before uploading (optional)

To send an archive instead of the original files, first enable **Settings → 7-Zip archive compression**. Cirava fetches the x64 installer from the official 7-Zip project and checks its SHA-256 against GitHub's release metadata before running setup. It keeps 7-Zip in Cirava's app folder rather than installing it system-wide. In the upload planner, choose **Compress this upload**, select a compression level, and prepare the archive. The preview shows the measured archive size and savings; nothing is uploaded until you confirm the prepared item. Source files are left untouched. Already-compressed formats may not shrink much.

## Follow the upload

The transfer panel reports its stage, total transferred, total size, live speed, queue count, and estimated time remaining. Early in a transfer, speed and ETA may be blank or jump around while Cirava prepares the session. A paused transfer reports zero speed. The estimate is based on recent aggregate speed, so it can move up or down.

Use **Pause uploads** to stop sending temporarily, **Resume uploads** to continue, or **Cancel uploads** to stop the queued upload work. If the connection drops, Cirava retries where possible and keeps resumable progress for recovery.

## About the 20 GB test file

The Cobalt test file is an optional speed test, not a local-only simulation. It sends data to your Google Drive and uses your Drive storage and network quota. If test data is disabled in Settings, choose local files instead. You can also enable test data in Settings before starting the test.
