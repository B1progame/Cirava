# Set up Google sign-in

This page walks through the Google Cloud Console setup needed to connect Cirava to Drive. There are two parts: first configure a Google Cloud project and create a Desktop OAuth client; then enter that client's ID in Cirava and approve access in Google's sign-in window.

Google occasionally changes Console labels. The page names and settings below are more reliable than the exact layout. If you are already signed in to Cirava, you can skip to [enter the client in Cirava](#enter-the-client-in-cirava).

## Before you start

You will need:

- A Google account that can use Google Drive.
- Access to [Google Cloud Console](https://console.cloud.google.com/).
- The installed Cirava Windows app. The browser preview cannot perform native OAuth or access local files.

You do not need to create a service account, API key, Web application client, or download a `credentials.json` file. Cirava needs an OAuth client whose application type is **Desktop app**. Never send your client secret, sign-in code, token, or screenshot containing credentials to anyone.

## Part 1: Configure Google Cloud

### 1. Select a project

Open [Google Cloud Console](https://console.cloud.google.com/) and use the project selector in the top bar. Select a project you control, or choose **New Project**, give it a name such as `Cirava desktop`, and create it. Confirm the new project is selected before continuing.

You do not need to start a free trial to configure Drive OAuth. Billing prompts may relate to other Google Cloud products; do not enable unrelated services for this setup.

### 2. Enable Google Drive API

In the Console navigation, open **APIs & Services → Library**. Search for **Google Drive API**, open its official result, and select **Enable**. If the page says to choose a project or shows no enabled APIs, check the project selector at the top and select the project you intend to use.

### 3. Configure the OAuth app

Open **Google Auth Platform** from the Console navigation. In some projects, the entry is still called **OAuth consent screen**. Complete the following sections and save each one:

#### Branding

Enter an app name and a support email. Add the developer contact email if requested. Use information you control and recognize; these details may appear during Google sign-in.

#### Audience

- Choose **External** for personal Google accounts or accounts outside your own Google Workspace organization.
- Choose **Internal** only if every user belongs to the Google Workspace organization that owns the Cloud project and the Console offers that option.
- For an External app whose publishing status is **Testing**, open **Audience → Test users**, choose **Add users**, enter each Google account that will sign in, and save. Accounts not on this list cannot authorize while the app remains in Testing.

Testing is suitable while you are setting up your own project. Be aware of its limits: Google restricts access to listed testers and documents that refresh tokens for External apps in Testing expire after seven days when the app requests scopes beyond basic profile, email, and OpenID. Cirava requests full Drive access, so you may need to sign in again during testing. See Google's [audience and publishing status guide](https://support.google.com/cloud/answer/15549945) for the current rules.

#### Data Access

Open **Data Access** (previously called **Scopes**) and add this exact scope:

```text
https://www.googleapis.com/auth/drive
```

This is the full Drive permission. Cirava uses it to list existing Drive items, show the complete Trash, restore items, empty Trash, and read account storage usage. Google classifies it as a **restricted** scope. It grants broader access than `drive.file`; do not substitute a narrower scope, because the complete Drive and Trash features would not have the access they need.

Google requires apps using restricted scopes to follow its applicable verification and user-data policies before public distribution. Depending on how an app handles restricted data, additional review or a security assessment may apply. Review Google's [Drive scope table](https://developers.google.com/workspace/drive/api/guides/api-specific-auth) and [restricted-scope verification guidance](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification). Adding a scope to the Console does not itself complete verification.

### 4. Create the Desktop OAuth client

Open **Google Auth Platform → Clients**. If your Console shows the older route, use **APIs & Services → Credentials → Create credentials → OAuth client ID**.

1. Choose **Desktop app** as the application type. Do not choose Web application.
2. Enter a name you will recognize, such as `Cirava on my PC`, then create the client.
3. Copy the complete **Client ID**. It normally ends in `.apps.googleusercontent.com`.
4. If Google displays a client secret, keep it private and enter it only into Cirava on your own PC. Do not put it in source control, a public issue, or a chat.

Cirava opens the system browser and listens for Google's response on a temporary local `127.0.0.1` callback. The available port is chosen during sign-in. You do not need to add a fixed redirect URI. Google's [desktop OAuth guide](https://developers.google.com/identity/protocols/oauth2/native-app) describes this installed-app flow and PKCE.

## Part 2: Connect Cirava

### Enter the client in Cirava

1. Open the installed Cirava app.
2. On first launch, use the Google setup screen. To change an existing setup, open **Settings → Google account**.
3. Paste the entire Desktop OAuth **Client ID** into the client ID field.
4. If Cirava shows a client secret field and Google provided a secret, enter it directly in that field. Do not paste it into a message or save it in the repository.
5. Select **Test configuration**.

The test checks whether the client ID looks valid and whether the required Google endpoints can be reached. It does not sign you in, check the test-user list, verify the OAuth consent configuration, or prove that Google will grant Drive access. Those checks happen during authorization.

### Approve Google access

1. Select **Continue with Google** in Cirava.
2. Your normal web browser opens. Sign in to an account allowed by the Audience setting. If the app is External and in Testing, use one of the accounts you added under **Test users**.
3. Check the app name and requested Drive permission on Google's consent page. Approve only if you trust the Cloud project and understand that the full Drive scope can manage Drive items, including Trash.
4. When Google says sign-in is complete, return to Cirava. The setup screen should show the connected account.

Cirava handles the authorization code and refresh token in its backend. You do not copy a code from the browser. Tokens are stored locally and protected with Windows DPAPI for the current Windows user.

## Existing users: approve the expanded permission

Cirava previously used narrower `drive.file` access. The complete Drive browser, Trash, restore, empty-Trash, and account-storage features need the full `drive` scope. After upgrading, open **Settings → Google account** and reconnect. Review Google's consent screen and approve the expanded access. Until you do, those features may report that access is missing even though the account appears connected.

If you are developing your own OAuth project, add the `drive` scope in **Data Access** before signing in. If the project is in External Testing, make sure the Google account is also listed as a test user. A production app using this restricted scope must meet Google's current verification and policy requirements.

## Fix common setup problems

### The client ID is rejected

Return to **Google Auth Platform → Clients** (or **APIs & Services → Credentials**) and copy the full ID for the **Desktop app** client. A project number, API key, Web client ID, or downloaded JSON filename is not a replacement.

### Google says the app is unavailable or access is blocked

Check **Audience**. If it is External and the publishing status is Testing, add the exact Google account you are signing in with to **Test users** and save. If your organization manages the account, an administrator may also restrict access to unverified or restricted-scope apps.

### Sign-in works, but Cirava says Drive access is missing

Check that Google Drive API is enabled in the same Cloud project as the OAuth client. Confirm that `https://www.googleapis.com/auth/drive` is listed in **Data Access**, then reconnect in Cirava and approve the permission. A successful **Test configuration** alone does not confirm any of these consent settings.

### Authorization works, then stops working days later

If the OAuth app is External and remains in Testing, Google's refresh-token lifetime for this Drive scope is seven days. Sign in again to continue testing. For broader distribution, review the publishing and verification requirements with Google before changing the app's publishing status.

### You see `invalid_client` or a callback error

Confirm the ID belongs to the selected Cloud project and is a **Desktop app** client. Do not change it to a Web client to add a redirect URL: Cirava's native flow uses a temporary loopback callback. Run **Test configuration** again, then retry sign-in from the installed desktop app rather than the browser preview.

If you still need help, share the exact error text and Cirava version, but remove account addresses, client secrets, OAuth codes, tokens, and private project details first. See [Troubleshooting](Troubleshooting).

## Official Google references

- [OAuth 2.0 for desktop apps](https://developers.google.com/identity/protocols/oauth2/native-app)
- [Google Drive API quickstart](https://developers.google.com/workspace/drive/api/quickstart/python)
- [Choose Google Drive API scopes](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)
- [OAuth audience, testing, and publishing status](https://support.google.com/cloud/answer/15549945)
- [Restricted-scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification)
