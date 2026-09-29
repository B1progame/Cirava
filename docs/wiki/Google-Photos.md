# Google Photos and media

Cirava keeps Google Drive and Google Photos as separate destinations. The **Google Photos** workspace has three sources: files on this device, image and video files in Google Drive, and items you choose through Google's secure Photos Picker.

## Browse and select

- **This device** shows photos and videos from a folder or files you choose. Cirava makes small previews so you can review the selection; it does not upload anything until you start or queue an upload.
- **Google Drive** searches accessible image and video files across My Drive and shared drives. Results are loaded in pages. Select Drive items to download them to this device.
- **Google Photos** opens Google's Picker in your default browser. Choose the photos you want to share with Cirava there, then return to Cirava to review the selection. Cirava only receives items that you chose.

Use right-click or the keyboard context-menu key on an item for its available actions. For an unsent local item, **Remove from selection** only deselects it; the original file stays on this PC. For a Google Photos item, **Delete in Google Photos…** opens that item in your default browser. Review and confirm deletion on Google's site. Cirava does not delete Photos library content through the API.

## Upload to Google Photos

1. In the Google Photos workspace, select **This device** and choose photos or a folder.
2. Review the selected media, then choose upload now or add it to the transfer queue.
3. Optionally select **Create a new album**, enter an album name, and start or queue the upload.
4. Follow progress from **Transfers**.

Uploads use the original files and Google Account storage limits apply. Cirava can create a new album for the upload, but it cannot browse or choose arbitrary existing albums through the Photos API. Share a created album later in Google Photos.

## Google Cloud setup

Enable Google Photos Library API and Google Photos Picker API in the same Cloud project as Cirava's Google Drive setup. Add the `photoslibrary.appendonly` and `photospicker.mediaitems.readonly` scopes to the OAuth consent configuration. Existing accounts must reconnect and approve the added access. Follow [Google sign-in setup](Google-OAuth-Setup) for the complete Console and OAuth steps.

Google controls the Photos API's available operations and limits. Cirava cannot silently index the complete Photos library or permanently delete arbitrary library items. Use Google Photos in the browser for deletion and sharing tasks the API does not expose.
