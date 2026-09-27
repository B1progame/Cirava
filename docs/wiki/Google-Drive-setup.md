# Set up Google Drive access

Cirava uses Google's OAuth sign-in for desktop apps. You create the client ID in your own Google Cloud project; Cirava never needs your Google password or a client secret pasted into the app.

## Create a desktop client

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and select a project, or create one.
2. In **APIs & Services → Library**, find **Google Drive API** and enable it.
3. Open **Google Auth Platform → Audience** or **OAuth consent screen**. Configure the audience and add the Google account you will use under **Test users** if the app is in testing.
4. Open **Credentials**, create an OAuth client ID, and choose **Desktop app**.
5. Copy the client ID into Cirava's setup screen.

Google changes Console labels from time to time. If the menu names differ, use the Console search for OAuth, Audience, Credentials, or Drive API. The project, API, audience, test-user, and Desktop app steps still need to be completed.

## Sign in

Cirava opens the system browser and uses authorization code with PKCE, then returns through a local loopback callback. Sign in with the account you added as a test user. If Google's page says the app is unavailable to this user, check the audience and test-user list first.

Treat the client ID as configuration, but keep any client secret and Google sign-in codes private. Never post credentials, access tokens, refresh tokens, or account screenshots in an issue or chat. See [Privacy and security](Privacy-and-security) for local token handling.
