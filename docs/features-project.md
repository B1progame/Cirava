# Project: High-Performance Google Drive Upload + Download Client

Build a production-quality desktop application for transferring files between the user's computer and Google Drive.

The primary objective is:

> Transfer authorized Google Drive files as fast as technically and legitimately possible while automatically adapting to the user's network, disk, CPU, Google Drive behavior, and API rate limits.

This is NOT a quota-bypass tool, credential brute-forcer, account attacker, rate-limit evasion tool, or scraper.

The application must only access files that the authenticated Google account is authorized to access.

The application should behave more like a professional transfer accelerator than a normal Google Drive web upload/download.

---

# 1. Recommended technology

Use:

* Tauri desktop application
* Rust backend
* React
* TypeScript
* modern async Rust networking
* Tokio
* reqwest or another mature HTTP client
* SQLite for persistent transfer state
* OS secure credential/keychain storage for OAuth credentials/tokens
* Google Drive API v3
* Google OAuth 2.0

Do NOT proxy file contents through an unnecessary Node.js server.

The Rust backend should perform the actual transfers.

Architecture:

```text
React / TypeScript UI
        │
        │ Tauri commands/events
        ▼
Rust transfer engine
        │
        ├── OAuth manager
        ├── Drive API client
        ├── Upload manager
        ├── Download manager
        ├── Transfer scheduler
        ├── Adaptive speed controller
        ├── Resume manager
        ├── Integrity verifier
        ├── Network monitor
        ├── SQLite persistence
        └── Filesystem manager
```

Keep the backend modular enough that Google Drive could later be joined by OneDrive, Dropbox, S3, etc.

---

# 2. Google login

Implement "Sign in with Google".

Never request or store the user's Gmail password.

Use proper Google OAuth 2.0.

For desktop:

* launch authentication in the system browser
* use authorization code flow appropriate for desktop/native apps
* securely receive the OAuth callback
* securely store refresh/access credentials
* automatically refresh expired access tokens
* support logout
* support switching accounts
* show the currently authenticated Google account

Never write access tokens, refresh tokens, authorization headers, or resumable-session URLs into normal application logs.

---

# 3. Permissions

Use the minimum Google Drive scopes necessary for each mode.

Prefer file-specific authorization when possible.

If full Drive browsing is enabled, clearly separate that capability from a restricted Picker/file-selection mode.

Do not silently request access to more Drive content than necessary.

---

# 4. Main application layout

Create a desktop UI similar in information density to:

* Google Drive
* Finder/File Explorer
* professional download managers
* FTP/SFTP clients

Main navigation:

```text
Drive
Transfers
Completed
Local Files
Settings
Diagnostics
```

Drive view:

```text
-------------------------------------------------------
 Google Drive                            Account avatar
-------------------------------------------------------
 ← →  / My Drive / Projects

 [Upload files] [Upload folder] [New folder]

 Name               Size       Modified        Status
 -----------------------------------------------------
 Project.zip         18.4 GB    Today
 Video.mp4           8.1 GB     Yesterday
 Photos/                        Today
 Backup.tar.zst      65.8 GB    Yesterday
```

Support:

* list
* search
* sort
* folders
* breadcrumbs
* refresh
* file size
* modification date
* file type
* Drive folder navigation

---

# 5. Transfer queue

Create a central transfer queue.

Every transfer has:

```text
id
direction
localPath
driveFileId
driveParentId
filename
size
bytesTransferred
status
speed
averageSpeed
peakSpeed
eta
progress
retryCount
createdAt
startedAt
completedAt
error
```

Statuses:

```text
queued
preparing
transferring
paused
waiting-for-network
rate-limited
verifying
completed
failed
cancelled
```

Actions:

* start
* pause
* resume
* cancel
* retry
* reveal local file
* open Drive file
* copy Drive link
* remove completed transfer

---

# 6. UPLOAD ENGINE

This is one of the most important pieces.

Use Google Drive resumable uploads for large files.

Do not read a multi-gigabyte file into RAM.

Stream directly:

```text
disk
 ↓
bounded buffer
 ↓
HTTP connection
 ↓
Google Drive
```

---

# 7. Resumable upload sessions

Initiate the Google Drive resumable session using:

```text
uploadType=resumable
```

Store the returned resumable-session URI securely in the transfer database.

Store enough information to resume after:

* application restart
* computer restart
* network interruption
* Wi-Fi change
* temporary Drive outage
* HTTP timeout

On restart, query Google Drive for the resumable upload's current status before continuing.

Never blindly assume that the last locally attempted chunk was fully received.

Use Google's acknowledged received range to determine the next byte.

---

# 8. Upload chunking

Implement configurable chunked upload.

Requirements:

* chunks obey Google Drive's documented alignment requirements
* final chunk may be smaller
* chunks are streamed from disk
* avoid unnecessary copies
* avoid loading entire files into memory

Start with a sensible large chunk size such as:

```text
8 MiB
16 MiB
32 MiB
64 MiB
128 MiB
256 MiB
```

but DO NOT hardcode one value as universally optimal.

Create an adaptive chunk-size controller.

---

# 9. Adaptive upload optimizer

The app should benchmark the connection while transferring.

Track:

```text
upload throughput
request latency
chunk completion time
HTTP failures
retransmitted bytes
CPU usage
disk read speed
rate-limit responses
timeout rate
```

Gradually test larger chunk sizes when the connection is stable.

Example logic:

```text
start 16 MiB

if:
    connection stable
    AND throughput rising
    AND latency acceptable

then:
    32 MiB
    64 MiB
    128 MiB

if:
    timeout frequency rises
    OR network becomes unstable

then:
    reduce chunk size
```

Avoid changing chunk size constantly.

Use hysteresis.

---

# 10. Single-request upload optimization

For stable high-speed connections, investigate whether sending the remaining portion or entire file through the resumable session in a single large request produces better throughput.

Google's resumable upload documentation indicates that fewer requests can provide better performance.

Therefore choose dynamically between:

```text
resumable-session + large continuous request
```

and

```text
resumable-session + multiple chunks
```

depending on:

* network stability
* file size
* previous transfer history
* retry risk
* memory constraints
* connection quality

The transfer must remain resumable.

---

# 11. Important single-file upload restriction

Do NOT assume a Google Drive resumable upload supports arbitrary simultaneous ranges of the same file.

Google's documented resumable upload process advances according to the range the server confirms it has received.

Therefore:

* maintain one ordered byte stream for a single resumable file
* optimize chunk size and connection behavior
* parallelize DIFFERENT FILE uploads instead

Do not invent an unsupported multi-part protocol.

---

# 12. Parallel upload scheduler

If there are multiple files, allow concurrent uploads.

Example:

```text
File A ───────────────►
File B ───────────────►
File C ───────────────►
File D ───────────────►
```

Start conservatively:

```text
2 concurrent uploads
```

Allow adaptive range roughly:

```text
1–8 simultaneous files
```

depending on observed performance.

Do not assume more parallelism means more speed.

Measure aggregate throughput.

Example:

```text
1 transfer  = 420 Mbps
2 transfers = 760 Mbps
3 transfers = 910 Mbps
4 transfers = 930 Mbps
5 transfers = 925 Mbps
```

Stay near 3–4 instead of continuing to increase concurrency.

---

# 13. DOWNLOAD ENGINE

Downloads should use a different optimization strategy.

For normal binary Drive files:

* obtain metadata first
* verify downloading is allowed
* obtain file size
* preallocate local destination file when practical

Then use HTTP byte-range requests.

Example:

```text
0 GB ───────────── 5 GB
      split into segments

Worker 1: 0–511 MiB
Worker 2: 512–1023 MiB
Worker 3: ...
```

Each worker independently requests its assigned range.

---

# 14. Parallel segmented downloads

Create a download scheduler capable of:

```text
1
2
4
6
8
12
16
```

concurrent ranges.

Do NOT start with 16 automatically.

Example initial state:

```text
streams = 4
segment size = 64 MiB
```

Measure total throughput.

Increase streams only when aggregate throughput improves materially.

Decrease them when:

* throughput decreases
* errors increase
* server throttling appears
* local disk becomes bottlenecked
* network latency explodes

---

# 15. Dynamic range scheduling

Don't permanently divide a 100 GB download into only four giant pieces.

Instead create many smaller logical segments.

Example:

```text
File: 100 GB
Segment: 64 MiB
Workers: 8
```

Workers obtain the next uncompleted segment from a shared scheduler.

This prevents one slow connection from delaying completion.

Architecture:

```text
Segment Queue
   │
   ├── Worker 1
   ├── Worker 2
   ├── Worker 3
   ├── Worker 4
   ├── Worker 5
   ├── Worker 6
   ├── Worker 7
   └── Worker 8
```

---

# 16. Random-access download writing

Do NOT create hundreds of temporary files unless necessary.

Prefer:

1. create `.part` destination
2. preallocate target size
3. download byte ranges
4. write each range directly to its correct file offset

Example:

```text
download range:
134217728–201326591

write offset:
134217728
```

Make writes thread-safe.

Prevent overlapping segments.

---

# 17. Resume downloads

Persist a bitmap or range map:

```text
segment 0 = done
segment 1 = done
segment 2 = missing
segment 3 = done
segment 4 = downloading
```

Example:

```json
{
  "fileId": "...",
  "localPath": "...",
  "size": 68719476736,
  "segmentSize": 67108864,
  "completedSegments": [0, 1, 3, 4, 5]
}
```

If the app crashes:

* reload transfer
* validate local `.part`
* query Drive metadata again
* resume missing segments only

---

# 18. Adaptive connection controller

Build a reusable adaptive controller.

Inputs:

```text
current throughput
rolling average throughput
request latency
error rate
retry rate
429 responses
403 rate-limit responses
disk speed
CPU load
active streams
chunk size
```

Outputs:

```text
download stream count
download segment size
upload concurrency
upload chunk size
backoff duration
```

Use a conservative hill-climbing strategy.

Pseudo logic:

```text
baseline = measure()

increase concurrency slightly

measure again

if throughput improvement > threshold:
    keep change
else:
    revert

wait

test again later
```

Never oscillate settings every second.

---

# 19. Rate limits and throttling

Correctly handle:

```text
429
403 rate-limit related responses
500
502
503
504
network timeout
connection reset
DNS failure
```

Use truncated exponential backoff with jitter.

Concept:

```text
delay =
min(
    maxBackoff,
    exponentialDelay + randomJitter
)
```

Do not try to circumvent Google quotas through:

* fake accounts
* rotating credentials
* proxy farms
* changing projects to evade restrictions
* request flooding
* hidden APIs

Instead intelligently lower concurrency.

---

# 20. Connection saturation goal

The optimizer should try to approach:

```text
maximum safe throughput =
min(
    network capacity,
    Drive serving throughput,
    local storage throughput,
    CPU/TLS capacity,
    API/service limits
)
```

Display which component appears to be limiting speed.

Possible display:

```text
Current bottleneck: Network

Network capacity:   ~940 Mbps
Current transfer:   901 Mbps
Disk capability:    ~3.2 GB/s
CPU:                13%
Drive throttling:   No
```

Do not claim certainty when the bottleneck is only inferred.

---

# 21. Transfer diagnostics

Add a real-time diagnostics panel.

Display:

```text
Current speed
Average speed
Peak speed
Uploaded/downloaded bytes
ETA

Active connections
Chunk/segment size
Retries
Rate-limit events
HTTP errors

Disk read speed
Disk write speed
Network utilization
```

Add a live throughput graph.

Keep approximately:

```text
last 60 seconds
last 5 minutes
whole transfer
```

---

# 22. Speed modes

Create:

### Auto

Recommended.

Adaptive optimizer chooses everything.

### Eco

```text
1–2 connections
lower disk activity
lower CPU use
```

### Fast

```text
aggressive but reasonable optimization
```

### Max

Attempts to use as much available network throughput as possible while respecting Drive responses and limits.

### Manual

Allow advanced users to configure:

```text
upload chunk size
download segment size
max parallel downloads
max parallel uploads
bandwidth limits
retry behavior
```

---

# 23. Bandwidth limiter

Support optional limits independently:

```text
Upload:   unlimited / custom
Download: unlimited / custom
```

Examples:

```text
50 Mbps
250 Mbps
1 Gbps
```

Implement a proper token-bucket or similar bandwidth controller.

Don't approximate it using long blocking sleeps.

---

# 24. Folder transfers

Support:

* upload file
* upload multiple files
* upload entire folder recursively
* download file
* download selected files
* download entire Drive folder recursively

Preserve folder structure.

Example:

```text
MyProject/
├── src/
│   ├── main.rs
│   └── app.rs
├── assets/
└── README.md
```

---

# 25. Drag and drop

Support dragging:

```text
file
multiple files
folder
multiple folders
```

onto the application.

Allow dropping directly onto a Drive folder.

---

# 26. File conflicts

When the destination already exists, support:

```text
Ask
Replace
Skip
Keep both
```

Keep both example:

```text
video.mp4
video (1).mp4
```

For batch transfers allow:

```text
Apply to all
```

---

# 27. Integrity checking

After transfer, verify integrity whenever the Drive API exposes suitable metadata/checksums.

Also maintain transfer-level verification while downloading ranges.

Possible states:

```text
Downloading
Verifying
Complete
```

Never mark a file complete before all expected bytes exist.

If verification fails:

* do not destroy potentially useful partial data immediately
* flag transfer
* retry affected data when possible
* provide clear error diagnostics

---

# 28. Sparse/preallocated files

For large downloads, investigate efficient destination allocation.

Use OS-supported preallocation where appropriate.

Do not fill a 200 GB file by manually writing 200 GB of zero bytes.

---

# 29. Memory management

Large files may be hundreds of GB.

The application's memory consumption must remain approximately bounded.

For example:

```text
8 download workers
64 MiB segments
```

does NOT mean all eight entire segments need to remain simultaneously buffered in RAM.

Use streaming buffers.

Prefer buffer pools.

---

# 30. Zero/low-copy optimization

Investigate safe opportunities to reduce copies between:

```text
filesystem
Rust buffers
TLS layer
HTTP layer
```

Prioritize correctness first.

Benchmark every optimization.

Do not introduce `unsafe` Rust merely because it might theoretically be faster.

---

# 31. Disk bottleneck detection

Benchmark disk throughput carefully.

If:

```text
network = 2.5 Gbps
disk write = 150 MB/s
```

then the app should identify local storage as a likely bottleneck.

Don't continue increasing network workers when disk write queues are already saturated.

---

# 32. HDD-aware behavior

SSD and HDD behavior is different.

For HDD downloads, many simultaneous random writes can reduce performance.

Detect or infer storage behavior and reduce parallel random writes when necessary.

Optionally:

* schedule nearby segments
* buffer limited ranges
* reduce active workers

SSD/NVMe may tolerate higher parallelism.

---

# 33. Small-file optimization

Transferring:

```text
one 100 GB file
```

and

```text
100,000 × 20 KB files
```

require very different strategies.

For huge numbers of tiny files:

* metadata requests become significant
* API request count becomes significant
* concurrency should be controlled separately
* UI updates should be batched
* database writes should be batched

Implement a dedicated small-file scheduler.

---

# 34. Queue prioritization

Support:

```text
Normal
High
Low
```

and manual drag/reorder.

A huge background download should not necessarily block a small high-priority file.

---

# 35. Pause behavior

Pause should be graceful.

When the user presses pause:

* stop scheduling new ranges/chunks
* allow currently safe operations to settle
* persist acknowledged state
* close unnecessary connections

Resume should continue rather than restarting.

---

# 36. Offline detection

Detect network loss.

Change transfer state:

```text
Transferring
    ↓
Waiting for network
```

Automatically resume once connectivity returns.

Avoid hammering Google while offline.

---

# 37. Computer sleep/restart

Persist transfer state regularly.

If computer sleeps:

```text
detect wake
refresh OAuth if required
revalidate sessions
continue transfer
```

If the app restarts:

```text
restore queue
validate unfinished transfers
resume automatically if enabled
```

---

# 38. Resumable-session expiration

Drive resumable sessions are not permanent.

Handle expired upload sessions.

If a session can no longer be resumed:

* report this clearly
* create a new resumable session
* restart that file upload safely

Do not get stuck retrying an expired session forever.

---

# 39. Google Drive metadata

Retrieve only required metadata fields.

Avoid giant generic `fields=*` requests.

Use field masks/selective fields where supported.

Typical required information:

```text
id
name
size
mimeType
modifiedTime
parents
capabilities
checksums when available
```

---

# 40. Google Workspace documents

Differentiate normal binary Drive files from native Google Workspace files.

Native types such as Docs/Sheets/Slides may need export behavior rather than normal binary download.

Do not incorrectly send normal byte-range requests against exports if the API does not support them.

Present export format options where required.

Example:

```text
Google Doc →

PDF
DOCX
TXT
```

---

# 41. Shared Drives

Design the Drive abstraction so Shared Drives can be supported.

Correctly handle:

* shared-drive IDs
* file permissions
* inherited permissions
* files the user can view but not download
* files the user can view but not modify

Never attempt to bypass Drive capability restrictions.

---

# 42. UI transfer card

Example:

```text
Ubuntu-Backup.img
██████████████████░░░░░░░░  72%

48.3 GB / 67.1 GB

Download
843 MB/s
Peak 911 MB/s
ETA 23s

Streams: 8
Segment: 64 MiB
Retries: 0
```

For upload:

```text
ProjectArchive.tar.zst
██████████████░░░░░░░░░░░░  54%

28.4 GB / 52.3 GB

Upload
724 Mbps
Peak 791 Mbps
ETA 4m 18s

Chunk: 128 MiB
Concurrent files: 3
Retries: 1
```

---

# 43. Global dashboard

Show:

```text
↓ Download  816 MB/s
↑ Upload    822 Mbps

Active: 6
Queued: 13
Completed today: 42

Network utilization: 91%
```

Do not confuse:

```text
Mbps
```

with:

```text
MB/s
```

Allow the user to choose units.

---

# 44. System tray

Support background operation.

Tray menu:

```text
Transfers
Pause all
Resume all

↓ 812 Mbps
↑ 144 Mbps

Open
Quit
```

---

# 45. Notifications

Optional OS notifications:

```text
Upload complete
Download complete
Transfer failed
Authentication required
```

Do not send a notification for every tiny file.

Batch appropriately.

---

# 46. Transfer history

Store completed transfer metadata locally.

History:

```text
filename
direction
size
average speed
duration
completion timestamp
Drive ID
local path
```

Allow clearing history independently from actual files.

---

# 47. Performance benchmark

Create a built-in benchmark mode.

Benchmark:

```text
disk sequential read
disk sequential write
network upload behavior
network download behavior
latency
```

Use actual Drive testing only with explicit user action because it transfers data.

Use benchmark results to seed Auto mode.

---

# 48. Intelligent auto-tuning

Persist non-sensitive historical performance information.

Example:

```text
Network fingerprint:
Ethernet

Typical download:
920 Mbps

Best streams:
8

Best segment:
64 MiB

Upload:
890 Mbps

Best upload chunk:
128 MiB
```

Do NOT store Wi-Fi passwords or other secrets.

Use previous measurements only as initial hints.

Re-test when conditions change.

---

# 49. Network-change detection

If the computer switches:

```text
Ethernet → Wi-Fi
Wi-Fi → hotspot
VPN off → VPN on
```

reset or soften previous tuning assumptions.

Re-optimize safely.

---

# 50. Security

Critical requirements:

* OAuth only
* never request Gmail password
* OS keychain/credential manager
* redact tokens from logs
* redact authorization headers
* protect resumable session URLs
* validate callback state
* protect PKCE verifier
* validate filesystem paths
* prevent directory traversal
* sanitize filenames where required
* HTTPS only
* no custom TLS disabling
* no certificate validation bypass

---

# 51. Logs

Use structured logs.

Levels:

```text
ERROR
WARN
INFO
DEBUG
TRACE
```

Default production logging must not expose:

```text
OAuth token
refresh token
Authorization header
resumable-session URL
private file contents
```

Create a "copy diagnostics" feature that automatically redacts sensitive information.

---

# 52. Error messages

Don't show users:

```text
Reqwest error code ...
```

as the only explanation.

Translate common cases.

Examples:

```text
Your internet connection was interrupted.
The transfer will resume automatically.

Google Drive temporarily limited requests.
Transfer speed was reduced and will increase again automatically.

This file cannot be downloaded with your current permissions.

Your Google sign-in expired.
Please sign in again.
```

Keep detailed technical information available under:

```text
Details
```

---

# 53. SQLite database

Use migrations.

Possible tables:

```text
accounts
transfers
upload_sessions
download_segments
transfer_history
settings
performance_profiles
```

Never store raw OAuth secrets unencrypted in the SQLite database.

Use secure OS credential storage.

---

# 54. Crash consistency

Transfer progress must be crash-safe.

Do not write:

```text
segment = completed
```

before data has actually been safely written.

For downloads:

```text
receive bytes
write bytes
flush as appropriate
mark segment complete
```

Balance durability with performance.

Don't `fsync` every few kilobytes.

---

# 55. Cancellation

Cancellation must actually stop I/O.

Don't merely hide the UI entry while an HTTP task continues running.

Use cancellation tokens.

Ensure workers terminate cleanly.

---

# 56. Backpressure

Implement real backpressure between:

```text
network
memory
disk
UI
```

If disk becomes slower than network:

* buffers must remain bounded
* network workers must slow down

Never allow memory usage to grow without limit.

---

# 57. UI event throttling

The transfer backend may produce thousands of progress changes per second.

Do not send all of them to React.

Aggregate progress and update UI roughly:

```text
5–10 times/sec
```

while keeping internal measurements higher resolution.

---

# 58. Tests

Create comprehensive tests.

Unit tests:

```text
segment creation
range parsing
resume calculations
chunk alignment
speed calculations
ETA
retry/backoff
filename conflict resolution
queue priority
```

Integration tests:

```text
network interruption
HTTP 429
HTTP 503
partial range
failed chunk
expired token
expired resumable session
Drive file changed during download
app restart during transfer
disk full
destination permission error
```

---

# 59. Mock Drive server

Build a local mock HTTP server for development.

It should simulate:

```text
Range responses
308 resumable upload responses
429 rate limiting
403 rate limits
500
503
timeouts
slow server
connection resets
partial responses
```

This allows the transfer engine to be tested without repeatedly using real Drive data.

---

# 60. Benchmark tests

Benchmark:

```text
1 vs 2 vs 4 vs 8 vs 16 download workers

16 MiB vs
32 MiB vs
64 MiB vs
128 MiB download segments

8 MiB vs
16 MiB vs
32 MiB vs
64 MiB vs
128 MiB upload chunks
```

Test:

```text
NVMe
SSD
HDD
fast Ethernet
Wi-Fi
high latency
packet loss
```

The optimizer should converge toward a good configuration rather than assuming one universal answer.

---

# 61. No fake performance claims

Do not artificially display inflated speed.

Calculate speed from actual acknowledged/transferred bytes.

Use both:

```text
instantaneous speed
rolling average
whole-transfer average
```

Example rolling speed:

```text
last 3 seconds
last 10 seconds
```

ETA should use a smoothed average.

---

# 62. Accuracy

Do NOT implement features based purely on assumptions about Google Drive.

When implementing an API feature:

1. consult the current official Google Drive API v3 documentation
2. confirm endpoint semantics
3. confirm OAuth scope
4. confirm resumable-upload behavior
5. confirm HTTP status handling
6. implement it
7. test it

Never invent undocumented parameters.

---

# 63. Performance philosophy

Prioritize in this order:

```text
correctness
data integrity
security
resume reliability
performance
UI polish
```

But after correctness is established, aggressively profile the transfer pipeline.

Do not prematurely assume the network is the bottleneck.

Measure:

```text
network
TLS
CPU
disk
Drive response
API overhead
database overhead
UI overhead
```

---

# 64. Development phases

Implement the application incrementally.

## Phase 1

* Tauri project
* React UI
* Rust backend
* settings/database infrastructure

## Phase 2

* Google OAuth
* account state
* Drive file/folder listing

## Phase 3

* basic binary download

## Phase 4

* range downloads
* direct offset writes
* resume support

## Phase 5

* adaptive parallel downloader

## Phase 6

* resumable uploads
* persistent upload sessions

## Phase 7

* upload tuning
* multiple simultaneous file uploads

## Phase 8

* queue
* folder transfers
* pause/resume/cancel

## Phase 9

* integrity verification
* diagnostics
* recovery

## Phase 10

* auto-tuning optimizer

## Phase 11

* performance profiling
* UI polish
* packaging

Do not attempt all optimizations before there is a correct baseline transfer implementation.

---

# 65. Required final project

Produce a complete working repository.

Include:

```text
README.md
ARCHITECTURE.md
SECURITY.md
PERFORMANCE.md
GOOGLE_SETUP.md
TESTING.md
```

README must contain:

```text
installation
development
building
OAuth configuration
Google Cloud project setup
Drive API setup
running
testing
packaging
```

PERFORMANCE.md must document:

```text
how downloads are segmented
how uploads are chunked
why upload and download concurrency differ
how auto tuning works
how backpressure works
how bottlenecks are detected
```

SECURITY.md must explain:

```text
OAuth
token storage
logging redaction
local database security
filesystem safety
```

---

# 66. Most important behavior

The finished application should feel like this:

```text
User selects 80 GB download

        ↓

Application probes transfer

4 streams → 520 Mbps

        ↓

tries 6

720 Mbps

        ↓

tries 8

910 Mbps

        ↓

tries 10

916 Mbps

        ↓

improvement negligible

        ↓

settles near 8 streams
```

For multiple uploads:

```text
1 active file → 420 Mbps
2 active files → 750 Mbps
3 active files → 890 Mbps
4 active files → 895 Mbps

settle around 3
```

For one large upload:

```text
create resumable session
        ↓
choose large efficient request/chunk size
        ↓
stream from disk
        ↓
receive acknowledged progress
        ↓
persist resume point
        ↓
adapt chunk sizing when useful
```

---

# 67. Explicit non-goals

Do NOT implement:

```text
account brute forcing
password guessing
quota bypassing
rate-limit evasion
token theft
cookie theft
credential scraping
proxy rotation to evade limits
multiple Google projects intended to bypass quotas
undocumented private Drive endpoints
permission bypassing
```

The speed comes from good engineering, concurrency where supported, HTTP range requests, resumable transfers, large efficient requests, intelligent scheduling, low-copy streaming, and adaptive tuning.

---

# 68. Completion criteria

Consider the implementation finished only when:

* Google login works reliably
* the user can browse authorized Drive content
* uploads work
* downloads work
* folder transfers work
* large transfers survive application restart
* interrupted transfers resume correctly
* segmented downloads are functional
* concurrent multi-file uploads work
* 429/403/5xx handling works
* Auto mode adjusts transfer settings
* memory remains bounded on huge files
* tokens are stored securely
* diagnostics are useful
* UI remains responsive during very large transfers
* transfer state is crash-resilient
* tests cover important recovery conditions
* release builds are produced

Before declaring completion, run the full test suite, run formatting/linting, build a release version, and perform at least one end-to-end upload/download test using a test Drive account and non-sensitive test data.
