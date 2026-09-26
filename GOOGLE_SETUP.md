# Google Cloud setup

1. Create or select a Google Cloud project.
2. Enable the Google Drive API.
3. Configure the OAuth consent screen with the appropriate test users.
4. Create an OAuth client of type **Desktop app**.
5. Copy the client ID into Cirava's first-run setup screen.

Cirava validates the client ID shape and public reachability of Google's OAuth discovery and Drive API endpoints before login. The desktop login opens the system browser, uses PKCE, and returns through a loopback callback. The browser preview intentionally uses a deterministic local login simulation and never receives real credentials.

## Current Console flow

The current Google Cloud Console was checked on 2026-09-23. Start with the project selector at the top of the Console: select an existing project or choose **New Project**. Do not start a free trial just to configure Cirava. After a project is selected, open **APIs & Services → Library**, search for the official **Google Drive API**, and choose **Enable**. If the API Library shows a navigation/loading error, select the project first and retry.

Then open **OAuth consent screen** (or **Google Auth Platform → Audience** in the newer Console), configure the app as an external test app when appropriate, and add the Google account you will use under **Test users**. Finally open **Credentials → Create credentials → OAuth client ID**, choose **Desktop app**, and copy the complete client ID into Cirava. The client secret, when Google provides one, stays local and must never be pasted into chat.

Cirava mirrors this exact route in its first-run walkthrough with privacy-safe annotated panels. Account names, project IDs, client secrets, and raw Console screenshots are intentionally not stored in the repository.

Use only accounts and files you are authorized to access. Native Google Docs, Sheets, and Slides require export handling rather than normal binary range downloads; Shared Drive access is also governed by the authenticated user's inherited permissions and Drive capabilities.
