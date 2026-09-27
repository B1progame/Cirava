# Architecture and Data Flow

## Component boundary

```text
React + TypeScript + Vite (src/)
              │ pywebview JavaScript API
              ▼
Python desktop bridge (backend/main.py)
    ├── OAuth + DPAPI token store
    ├── Google Drive REST client
    ├── transfer records (SQLite)
    ├── bounded transfer workers
    ├── resumable upload engine
    └── segmented download engine
```

The frontend owns presentation and user interaction. The backend owns OAuth, local file access, HTTP requests, transfer records, and worker controls. The browser inspection preview cannot access native file pickers or real Drive credentials; a successful preview interaction is not proof of a real desktop transfer.

## Upload lifecycle

1. The user picks local paths with the native file/folder picker. A selected Drive folder ID and the paths are passed to `create_upload_batch()`.
2. `create_upload_batch()` expands folders recursively and preserves relative subfolder paths. It creates one durable upload record per file.
3. `create_upload()` validates that each path is a file, records its target Drive parent, and adds worker/control metadata. The queue record is written to SQLite before a worker is started.
4. The upload worker creates or resumes a Drive resumable-upload session. The session URL and acknowledged offset are stored with the transfer record so the transfer can recover after restart or network loss.
5. `ResumableUploader` sends ordered chunks for each file. Each file's resumable session is sequential; separate files may progress concurrently through the bounded adaptive scheduler.
6. The backend persists progress/status and emits safe UI updates. The Transfers page polls/receives transfer records; retries/backoff handle transient network and rate-limit errors.

For a directory upload, Cirava creates the needed Drive subfolders beneath the selected destination and maps the local relative paths into those folders. Nothing is queued merely by opening the planner; the user confirms the selection and destination before the app creates the batch.

## Download lifecycle

1. The UI passes a Drive file ID, chosen local path, size, and optional checksum to the backend.
2. The backend applies the conflict policy and creates a durable download record.
3. `SegmentedDownloader` divides the file into byte ranges. Workers fetch ranges, write at the correct offsets, and persist completed-range state.
4. A resumed transfer requests only missing ranges. When a Drive MD5 checksum is available, the final file is verified before it is marked complete.

Google-native Docs, Sheets, and Slides use Drive export operations rather than ordinary binary range download. Actual capabilities and access are always subject to the signed-in user's Google Drive permissions.

## Drive adapter

`DriveApiClient` isolates the HTTP v3 endpoints used by the app: file/folder listing, folder/file creation, metadata updates, resumable upload sessions, range downloads, and native-document export. It requests a fresh bearer token from `TokenManager` for authenticated calls. Google Drive API errors are converted to typed errors so retry logic can distinguish retryable statuses from permanent failures.

Cirava requests the full `drive` OAuth scope to browse existing items, manage the complete Trash, restore items, and read storage quota. Google classifies this scope as restricted; existing users must reconnect to approve it. See [Google OAuth Setup](https://github.com/B1progame/Cirava/wiki/Google-OAuth-Setup#important-full-drive-scope-and-verification).

## Persistence and recovery

- OAuth credentials: protected token files under `%APPDATA%\Cirava`.
- Transfer queue/history: SQLite (`transfers.db`). Records include direction, source/destination identifiers, status, byte progress, retry telemetry, and resumable state.
- Worker stop/pause/cancel controls: maintained by the Python API and applied cooperatively by transfer workers.
- Preferences: local app settings, separate from the token vault.

The transfer database is operational state, not a backup of source files or a substitute for Drive. Protect the Windows profile and Cirava data directory; do not publish transfer databases or resumable-session URLs.

## Source map and local development

| Area | Main source |
|---|---|
| React application / setup UI | `src/main.tsx` |
| pywebview API contract | `src/bridge.ts` |
| Desktop API, queue, workers | `backend/main.py` |
| OAuth and DPAPI | `backend/cirava_backend/oauth.py` |
| Drive API v3 calls | `backend/cirava_backend/drive_api.py` |
| Resume/retry/chunk engines | `backend/cirava_backend/transfer_engine.py` |
| Adaptive upload workers | `backend/cirava_backend/adaptive.py` |
| SQLite transfer store | `backend/cirava_backend/storage.py` |

Build and test commands are maintained in the repository [README](https://github.com/B1progame/Cirava#build-it-yourself) and [TESTING.md](https://github.com/B1progame/Cirava/blob/main/TESTING.md). Run the backend tests with `PYTHONPATH=backend` (PowerShell: `$env:PYTHONPATH = 'backend'`) so project modules resolve correctly.
