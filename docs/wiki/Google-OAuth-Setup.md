# Google OAuth Setup

This guide configures Cirava to call the Google Drive API using your own Google Cloud project. Google changes Console labels over time; the resource types and settings below are the important part.

## Before you start

- A Google account with Google Drive enabled.
- Access to [Google Cloud Console](https://console.cloud.google.com/).
- The Cirava Windows desktop app. The browser inspection preview cannot perform native OAuth or access local files.

Cirava needs an OAuth **Desktop app** client, not a Web application client, API key, service account, or downloaded `credentials.json` file. Cirava's setup screen takes the OAuth client ID; never upload a secret or token to GitHub.

## Step 1 — Create or select a Cloud project

Open Google Cloud Console and select a project from the project picker, or create one for Cirava. Keep a separate project for development/testing if you also manage a production OAuth app. Google Cloud may ask you to select a billing account or configure billing for unrelated products; Drive OAuth setup itself does not require starting a promotional free trial.

## Step 2 — Enable Google Drive API

In the selected project, open **APIs & Services → Library** (or search the Console for API Library), find **Google Drive API**, open it, and click **Enable**. Confirm the project selector still shows the intended project if the API page appears empty or reports a project-selection problem.

## Step 3 — Configure the OAuth consent / Google Auth Platform

Open **Google Auth Platform** (some projects/Console layouts may still label this **OAuth consent screen**).

### Branding

Set the application name and user-support email. Add developer contact information where prompted and save the changes. Use accurate information for the project owner; Cirava does not need your password.

### Audience

- Choose **External** if you are authorizing personal Google accounts or accounts outside one Google Workspace organization.
- Choose **Internal** only when the app is restricted to users in the owning Google Workspace organization and the Cloud project supports that audience.
- If an External app is in **Testing**, add every Google account that will sign in to the **Test users** list and save. An account not listed there cannot finish authorization while the app is in this state.

Testing is appropriate for your own development project. For External apps in Testing, Google currently limits the test-user list and expires test-user authorizations after seven days for scopes outside the basic profile/email/OpenID set. Because Cirava requests full Drive access, expect to authorize again periodically until the OAuth project is appropriately published. See Google's current [test/publishing status guidance](https://support.google.com/cloud/answer/15549945).

### Data Access / scopes

Cirava's code requests this Drive scope so it can browse Drive, manage the complete Trash, restore items, and read account storage usage:

```text
https://www.googleapis.com/auth/drive
```

Declare only scopes the app needs in the consent configuration. Cirava uses the restricted `drive` scope for its complete Drive and Trash features, so the OAuth project must meet Google's applicable verification and policy requirements before public distribution. Review Google's [Drive API scope table](https://developers.google.com/workspace/drive/api/guides/api-specific-auth) when configuring Data Access.

## Step 4 — Create a Desktop OAuth client

In **Google Auth Platform → Clients** (or **APIs & Services → Credentials**):

1. Select **Create client** / **Create credentials → OAuth client ID**.
2. Set the application type to **Desktop app**.
3. Give the client a recognizable name, such as `Cirava on my PC`, and create it.
4. Copy the entire client ID. It typically ends with `.apps.googleusercontent.com`.
5. Keep any client secret Google displays private and local. Do not paste it into chat, a public issue, a screenshot, or a committed file.

Cirava starts a local HTTP listener on `127.0.0.1` at an available port for each sign-in. The port is selected at runtime, so do not invent a Web-client redirect URI or replace the credential with a Web application client. Google's [native-app OAuth guide](https://developers.google.com/identity/protocols/oauth2/native-app) documents the installed-app loopback flow and PKCE.

## Step 5 — Configure Cirava and authorize

1. Open Cirava's first-run setup or **Settings → Google account**.
2. Paste the full Desktop client ID.
3. If the UI offers a client secret field and your client requires one, enter it directly into Cirava. Desktop OAuth clients are installed clients; do not treat an embedded secret as a server-side secret.
4. Run **Test configuration**. A successful result verifies the ID format and network reachability, not that the consent screen is fully correct.
5. Choose **Continue with Google** and use an account allowed by the Audience setting.
6. Review and approve the Google consent screen. After the local callback reports success, return to Cirava and verify the connected account appears.

The full browser-to-token sequence and local token protection are described in [Authentication Internals](https://github.com/B1progame/Cirava/wiki/Authentication-Internals).

## Important: Full Drive scope and verification

The full `drive` scope lets Cirava browse existing Drive items, show the complete Trash, restore items, empty Trash, and report account storage. This is broader than the previous `drive.file` access, so existing users must reconnect and approve the new permission before these features become available.

Google classifies this as a restricted scope. Review the consent-screen setup, verification requirements, and Google's [Drive API scope table](https://developers.google.com/workspace/drive/api/guides/api-specific-auth) before distributing an OAuth client that requests it. If access is unavailable, check the signed-in account and whether consent was granted to this client. See [Troubleshooting](https://github.com/B1progame/Cirava/wiki/Troubleshooting#drive-is-missing-folders-or-actions).

## Official Google references

- [OAuth 2.0 for desktop apps](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Google Drive API Python quickstart — enable API, consent, Desktop client](https://developers.google.com/workspace/drive/api/quickstart/python)
- [Choose Drive API scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)
- [Manage OAuth app audience and testing users](https://support.google.com/cloud/answer/15549945)
