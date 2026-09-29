# Connect Cirava to Google Drive and Google Photos

Cirava uses a Google OAuth **Desktop app** client. Set it up in Google Cloud Console, then paste its client ID into the installed Windows app. The process does not require your Google password, an API key, or a service account.

## Quick setup

1. In [Google Cloud Console](https://console.cloud.google.com/), create or select a project.
2. Open **APIs & Services → Library**. Enable **Google Drive API**, **Google Photos Library API**, and **Google Photos Picker API** in this same project. The Picker API is a separate service from the Library API.
3. Open **Google Auth Platform** (or **OAuth consent screen**), set the app name and support contact, then choose the audience. If an External app is in Testing, add the Google account you will use under **Audience → Test users**.
4. Open **Data Access** and add both scopes:

   ```text
   https://www.googleapis.com/auth/drive
   https://www.googleapis.com/auth/photoslibrary.appendonly
   https://www.googleapis.com/auth/photospicker.mediaitems.readonly
   ```

5. Open **Google Auth Platform → Clients** (or **APIs & Services → Credentials → Create credentials → OAuth client ID**). Create a client with application type **Desktop app** and copy its full client ID.
6. In Cirava, paste the ID into first-run setup or **Settings → Google account**. If Google provided a client secret and Cirava shows a secret field, enter it locally. Run **Test configuration**, then select **Continue with Google** and approve the requested Drive and Photos access in your browser. Existing installations must reconnect after this change so Google can grant the Photos Picker permission.

The configuration test only checks the client ID format and network reachability. It does not validate the consent screen or sign you in. For example, an External app in Testing must list the account under Test users.

## Read before approving

The `drive` scope allows access to all Drive files. Cirava needs it to browse existing items, show the complete Trash, restore items, empty Trash, and read storage usage. Google classifies it as restricted. External apps left in Testing are limited to listed test users, and refresh tokens for this scope expire after seven days. Google requires applicable verification and policy compliance before public distribution.

The `photoslibrary.appendonly` scope lets Cirava add media uploads to your Google Photos library. `photospicker.mediaitems.readonly` lets Cirava receive only the photos and videos that you choose in Google's separate Photos Picker window. Google does not let this app silently enumerate your whole Photos library; to see items here, choose them in the Picker. Picker thumbnail links are temporary and are refreshed by selecting again. The Photos Library API accepts images up to 200 MB and videos up to 20 GB. Uploads are stored at original quality, and Google Account storage limits may apply.

The Photos page also searches files across My Drive and accessible shared drives. Drive results are paginated so a large account does not have to be loaded into memory all at once. Select regular files to download through Cirava's transfer queue. Google Docs, Sheets, and Slides are listed but need export conversion, so they are not included in this gallery's download action.

Shared-drive uploads require your Google account to be a member of the shared drive and permitted to add content. You can choose a drive listed for your account or paste a shared-drive/folder URL in the upload planner. Cirava uses the selected destination only for those queued uploads; it does not change the destination of existing queue items.

Existing users must reconnect and approve the Photos and Photos Picker permissions before browsing selections or uploading to Google Photos. Never share OAuth codes, tokens, client secrets, or unredacted screenshots.

For the full step-by-step walkthrough, troubleshooting, and official Google references, see the [Google OAuth setup wiki](https://github.com/B1progame/Cirava/wiki/Google-OAuth-Setup). You can also open the [Cirava wiki](https://github.com/B1progame/Cirava/wiki).
