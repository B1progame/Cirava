# Connect Cirava to Google Drive

Cirava uses a Google OAuth **Desktop app** client. Set it up in Google Cloud Console, then paste its client ID into the installed Windows app. The process does not require your Google password, an API key, or a service account.

## Quick setup

1. In [Google Cloud Console](https://console.cloud.google.com/), create or select a project.
2. Open **APIs & Services → Library**, find **Google Drive API**, and select **Enable**.
3. Open **Google Auth Platform** (or **OAuth consent screen**), set the app name and support contact, then choose the audience. If an External app is in Testing, add the Google account you will use under **Audience → Test users**.
4. Open **Data Access** and add this exact scope:

   ```text
   https://www.googleapis.com/auth/drive
   ```

5. Open **Google Auth Platform → Clients** (or **APIs & Services → Credentials → Create credentials → OAuth client ID**). Create a client with application type **Desktop app** and copy its full client ID.
6. In Cirava, paste the ID into first-run setup or **Settings → Google account**. If Google provided a client secret and Cirava shows a secret field, enter it locally. Run **Test configuration**, then select **Continue with Google** and approve the requested Drive access in your browser.

The configuration test only checks the client ID format and network reachability. It does not validate the consent screen or sign you in. For example, an External app in Testing must list the account under Test users.

## Read before approving

The `drive` scope allows access to all Drive files. Cirava needs it to browse existing items, show the complete Trash, restore items, empty Trash, and read storage usage. Google classifies it as restricted. External apps left in Testing are limited to listed test users, and refresh tokens for this scope expire after seven days. Google requires applicable verification and policy compliance before public distribution.

Existing users upgrading from `drive.file` must reconnect and approve the expanded access. Never share OAuth codes, tokens, client secrets, or unredacted screenshots.

For the full step-by-step walkthrough, troubleshooting, and official Google references, see the [Google OAuth setup wiki](https://github.com/B1progame/Cirava/wiki/Google-OAuth-Setup). You can also open the [Cirava wiki](https://github.com/B1progame/Cirava/wiki).
