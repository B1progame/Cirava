# Authentication Internals

Cirava is a native Windows desktop app with a web-rendered UI. Google OAuth and all tokens stay in the Python backend; the React layer receives only safe status/profile data and calls backend operations through `pywebview`.

## Sign-in sequence

1. The setup UI sends the Desktop OAuth client ID (and optional client secret) to `CiravaApi.save_google_configuration()` in `backend/main.py`. The client ID is format-checked and saved in app settings. An optional secret is placed in the protected credential store.
2. `CiravaApi.begin_google_login()` creates an `OAuthSession` from `backend/cirava_backend/oauth.py` and opens the system browser.
3. `OAuthSession` generates a high-entropy PKCE verifier and a separate unpredictable `state`. It derives the S256 challenge and requests an authorization code with `access_type=offline`, the full `drive` scope, and a loopback redirect URI.
4. Before opening the browser, the app binds an HTTP server to `127.0.0.1` on an available port. The callback path is `/oauth/callback`. This avoids a fixed-port collision and keeps the browser outside the embedded app window.
5. The callback handler accepts Google's code, checks that the returned `state` matches the current login, and rejects OAuth errors or a missing code.
6. The backend exchanges the code at Google's token endpoint using the same redirect URI and PKCE verifier. A client secret is included only when configured.
7. The resulting token response is encrypted by `TokenStore` and saved. The UI is told only that authentication succeeded; it never receives the refresh token.

This is Google's installed-app authorization-code + PKCE pattern. Google recommends PKCE for installed apps; see the official [desktop OAuth guide](https://developers.google.com/identity/protocols/oauth2/native-app).

## Authenticated Drive requests and refresh

`CiravaApi._drive()` loads the token store and builds a `DriveApiClient` with a `TokenManager.access_token()` callback. `DriveApiClient._request()` attaches the resulting value as an HTTP `Authorization: Bearer …` header. When an access token is near expiry, `TokenManager` uses the saved refresh token to request a new access token and persists the updated response before returning it.

If the token is missing, the backend reports that Google is not connected. If a refresh token is absent or rejected, the user must sign in again. Cirava does not ask the user to paste a password, copy a browser cookie, or manually handle an authorization code.

## Local persistence on Windows

The app data root is `%APPDATA%\Cirava` (`app_data_dir()` in `backend/main.py`). Important files include:

| Data | Storage | Notes |
|---|---|---|
| OAuth access/refresh token response | `tokens.bin` via `TokenStore` | Windows DPAPI-protected for the current Windows user. |
| Optional OAuth client secret | `client-credentials.bin` via `TokenStore` | Also DPAPI-protected. The client ID is an identifier, not a password. |
| UI and app preferences | `preferences.bin` and `settings.json` | Preferences are separate from OAuth tokens. `settings.json` contains non-secret settings such as the client ID. |
| Transfer queue/history | `transfers.db` SQLite database | Transfer metadata and resume state; not the OAuth token vault. |

`TokenStore.save()` writes an encrypted temporary file and replaces the previous file. On Windows, `_protect()`/`_unprotect()` call DPAPI. Data protected this way is tied to the Windows user context; copying the blob to another Windows account is not a supported migration method. Signing out clears the token store. Removing Cirava's grant from the Google Account is a separate action in Google account security settings.

## Why the UI cannot read tokens

`CiravaApi.boot_state()` returns booleans such as `configured` and `authenticated`, not token contents. `get_account_profile()` returns the display name/email/photo from Drive's `about` endpoint, not OAuth credentials. The Python API bridge exposes callable operations while keeping authentication/session construction in backend code.

Sensitive values that must never be logged or committed include access tokens, refresh tokens, `Authorization` headers, authorization codes, client secrets, and resumable-upload session URLs. Review [SECURITY.md](https://github.com/B1progame/Cirava/blob/main/SECURITY.md) for the broader security model.

## Source map

- `backend/cirava_backend/oauth.py` — `OAuthConfig`, `OAuthSession`, `TokenStore`, `TokenManager`, DPAPI helpers.
- `backend/main.py` — `save_google_configuration()`, `validate_google_configuration()`, `begin_google_login()`, `sign_out()`, `_drive()`, `get_account_profile()`.
- `backend/cirava_backend/drive_api.py` — bearer-authenticated Drive REST requests.
- `src/bridge.ts` — frontend's typed bridge contract.
- Setup/login components in `src/main.tsx` — collect the client ID and trigger backend auth; no Google token is stored in browser storage.

## Testing and developer-only hooks

The OAuth tests in `backend/tests/test_google.py` cover loopback selection, callback/state behavior, token storage, and token refresh without requiring a real Google account. A separate real-Google E2E harness exists under `backend/scripts/real_google_e2e.py`; it requires developer-provided local environment configuration. Never put E2E client secrets in the repository or public Wiki.
