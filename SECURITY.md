# Cirava security model

## OAuth and permissions

Cirava uses the desktop OAuth authorization-code flow with PKCE and a loopback callback. It does not ask for or store a Google password. The current Drive scope is `drive.file`; a future full-browse mode must be clearly separated and must request broader consent explicitly.

## Token storage

Refresh/access token material is stored by the backend using Windows DPAPI and is never returned to the React UI. Logout clears the protected token store. Token refresh happens inside the OAuth/Drive layer.

## Logging

Logs contain event names and safe diagnostics only. Access tokens, refresh tokens, Authorization headers, OAuth codes, client secrets, and resumable-session URLs must never be logged.

## Database and filesystem

SQLite stores transfer metadata, not credentials. Uploads validate that the local path is a file before queueing. Downloads use explicit user-selected paths and conflict policies; partial files and range maps are retained for safe resume. Finished history removal is restricted to terminal records.

## Update security

Update manifests require a semantic version, HTTPS-delivered payload, SHA-256 verification, and optional paired Ed25519 signature/public-key validation. Restart accepts only an executable staged below Cirava's private update directory.

Cirava does not rotate accounts/projects, flood requests, bypass permissions, scrape cookies, or evade Drive quotas.
