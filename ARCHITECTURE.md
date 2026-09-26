# Cirava architecture

```text
React + TypeScript + Vite
          │ pywebview bridge
Python desktop API
 ├─ OAuth / secure token store
 ├─ Drive API client
 ├─ transfer scheduler
 │   ├─ ordered resumable uploader
 │   └─ segmented range downloader
 ├─ adaptive controllers and token bucket
 ├─ SQLite transfer store
 └─ signed update staging
```

The UI owns presentation state and invokes typed bridge methods. The backend owns all credentials, filesystem access, network requests, and transfer state. Transfer records are durable and include the Drive session URL, acknowledged byte count, range-map progress, telemetry, and terminal error.

Uploads are ordered per file because Drive resumable sessions advance by acknowledged range. Different files may run concurrently through a bounded scheduler. Downloads use many logical ranges, a shared work queue, preallocation, synchronized random-access writes, and persisted completion maps.

The adapter boundary is intentionally Drive-specific today but keeps file listing, folder creation, upload sessions, range reads, and export operations isolated so another storage provider can be added later.
