# Google Drive transfer performance research

Research date: 2026-09-27
Scope: research and recommendations only. No application code or transfer settings were changed for this note.

## Executive summary

A 20% speedup is a measurable target, not something the Drive API can promise. The result depends on the user's upstream/downstream connection, Wi-Fi and disk, Google routing, account/API throttling, and the baseline client. Cirava already uses resumable uploads, adaptive 64–128 MiB chunks, and concurrent ranged downloads. The best code-level opportunity found is the download controller: it calls the full time to fetch a large range “latency” and can shrink concurrency because a healthy 64 MiB transfer took longer than 900 ms. The best upload opportunity is careful tuning and measurement, not parallel chunks within one resumable session.

For the screenshot's displayed 4.8 MB/s, Cirava formats byte units in powers of 1024 (so the displayed value is effectively MiB/s, despite the MB label). A 20% target is 5.76 MiB/s (about 48.3 Mbit/s). On the remaining ~4.3 GiB shown, that would reduce ideal transfer time from roughly 15.4 minutes to 12.8 minutes. These are arithmetic estimates, not a measured promise.

## What Drive supports that matters for speed

- **Resumable upload:** create a session, then `PUT` content to its session URL. For chunked upload, chunks must be multiples of 256 KiB except the final chunk; Google says to keep chunks as large as possible. The server's acknowledged `Range` is authoritative, and 308 means resume incomplete. Google says a single request can perform better when the whole file can safely be sent that way, but it gives up chunk-level progress/pause points and is a poor fit for Cirava's resumable, cancellable large-file workflow. [Google upload guide](https://developers.google.com/workspace/drive/api/guides/manage-uploads)
- **No parallel pieces within one resumable upload:** the resumable protocol advances from the acknowledged offset and asks the client to send the next remaining bytes. Do not send multiple overlapping/out-of-order PUTs to the same session as a speed trick; it is not the documented model. For multiple files, separate sessions can run concurrently.
- **Media is not batchable:** Drive's multipart batch API can reduce connection overhead for metadata operations, but Google explicitly says batch does not support media upload, media download, or export. Batching file bytes is not a route to a 20% gain. [Drive performance guide](https://developers.google.com/workspace/drive/api/guides/performance)
- **Binary downloads support partial byte ranges:** use `files.get` with `alt=media` plus HTTP `Range`. That permits independent ranges to be fetched concurrently and reassembled. Workspace-native Docs/Sheets/Slides require export to a chosen format; partial download is not supported for Workspace document exports. [Google download/export guide](https://developers.google.com/workspace/drive/api/guides/manage-downloads)
- **Retry rather than overload:** 429 and rate-limit 403s, plus transient 5xx errors, should use exponential backoff. A concurrency increase that causes more throttling can make total throughput worse. [Google error guide](https://developers.google.com/workspace/drive/api/guides/handle-errors)
- **Service/account limits:** the current Drive API limits page lists a 750 GB/day upload limit for Workspace users across My Drive and shared drives, and a 5 TB maximum file size (subject to storage/account rules). These are ceilings, not promises of throughput. [Google usage limits](https://developers.google.com/workspace/drive/api/guides/limits)

## What Cirava currently does (source inspection)

- `backend/cirava_backend/drive_api.py`: uses `urllib.request.urlopen` for API operations; upload sends each chunk as a bytes object in a PUT with `Content-Range`; download sends `Range` and returns the complete response body as bytes.
- `backend/cirava_backend/transfer_engine.py`: `ResumableUploader` reads and sends one ordered chunk at a time. `SegmentedDownloader` divides a file into ranges (default 64 MiB), runs a bounded worker pool, checks each range length, writes ranges at offsets, and persists completed ranges for resume.
- `backend/main.py`: uploads default to 64 MiB chunks; `AdaptiveController` can raise them to 128 MiB or reduce them after unhealthy/error observations. Cross-file upload concurrency is adjustable from 1–8 and uses aggregate upload telemetry. Downloads use a latency-based `AdaptiveConcurrencyController`.
- `backend/cirava_backend/adaptive.py`: the download controller grows when observations are at most 250 ms and backs off at 900 ms. Its caller currently supplies the **elapsed time for fetching an entire range**, not just connection/server response latency. With 64 MiB ranges, the transfer duration includes all 64 MiB of payload, so a healthy link can exceed the backoff threshold solely because the range is large. This is the clearest code-level candidate to investigate.
- Bandwidth limiting is optional (`bandwidth_limit_mbps`; unset/zero means no limiter in code). A saved nonzero cap can intentionally throttle both transfer directions. Check it before comparing performance.

## Recommendations, ranked by evidence and risk

### 1. Fix the download concurrency signal (highest-confidence code opportunity)

Do not feed total range-download duration into a threshold named/used as network latency. Track per-range bytes and duration for throughput, plus connection/response timing separately if available. Make concurrency adapt using whole-transfer aggregate throughput over windows (and error/rate-limit backoff), as uploads already attempt to do. Start with conservative worker trials (1 → 2 → 4 → 6 → 8); retain a level only when aggregate throughput improves and error rate stays low. Keep a hard cap and cooldown to avoid oscillation.

Why it may help: if the current latency signal repeatedly collapses workers toward one, multiple TCP flows could fill a high-bandwidth/high-latency path better. It will not help when one stream already saturates the actual download bottleneck, and it could hurt under rate limits or server-side contention.

### 2. Stream range downloads to disk instead of buffering each whole range

Current `get_range()` reads a whole range into `bytes`, then the downloader writes that in-memory object to its target offset. At four concurrent 64 MiB ranges, payload buffering alone can approach 256 MiB, plus copies/runtime overhead. A streaming response written in bounded blocks to the preallocated `.part` file can lower peak memory, reduce copy/GC pressure, and allow safe higher parallelism on constrained machines. Preserve exact byte-count validation, retry cleanup/overwrite of the requested range, pause/cancel checks, and range-map durability.

This is primarily a memory/robustness enabler; benchmark before claiming it increases raw network speed.

### 3. Tune upload chunk size by file size, memory budget, and observed throughput

Cirava already starts with large chunks and grows 64 → 128 MiB after stable observations. Benchmark 32/64/128/256 MiB on large files, not just small synthetic files. Larger chunks reduce request/response turns, but do not increase the network line rate by themselves. They also hold a larger payload in memory per active upload and make pause/cancel take effect only between chunk requests; account for `active_uploads × chunk_size` plus copies when selecting a ceiling. Consider choosing the initial chunk from file size and available memory, then adjusting only at acknowledged boundaries. Keep 256 KiB alignment and server-acknowledged offsets.

### 4. Keep batch uploads concurrent, but tune from aggregate throughput

For many files, independent resumable sessions can run concurrently. Cirava has an aggregate byte-rate sampler and a live adjustable worker gate (1–8). Benchmark a set of small files and a set of medium/large files separately: high worker counts can help latency-bound small files, while large uploads can saturate the uplink with fewer workers. Back off on 429/rate-limit/5xx and judge each worker change by aggregate bytes/sec, not the speed of whichever file finishes first.

### 5. Measure connection reuse before introducing it

The client currently calls `urllib.request.urlopen` independently for requests. Test whether the runtime is reusing TLS connections in practice; if not, compare a maintained per-worker/session-based transport with connection pooling. Reuse may reduce setup/handshake overhead, especially for many small files and small download ranges. For one 64–128 MiB upload chunk, handshake time is likely a small fraction of payload time, so this is unlikely to alone deliver 20% for a large single file. Any replacement must preserve OAuth refresh, HTTPS validation, timeouts, retries, Drive 308 handling, cancellation, and Windows packaging.

### 6. Make measurements representative and expose the real bottleneck

The existing “connection speed” check downloads a short sample from Cloudflare. It measures a download path, **not upload capacity to Google Drive**, and cannot prove Cirava's upload is slow. Add separate diagnostics for upload-to-Drive and download-from-Drive only if their test payloads, quota/storage impact, cleanup, consent, and privacy are made explicit. Report effective bytes/sec, request duration, chunk/range size, worker count, retry/status counts, disk read/write rate, and configured cap. Never silently upload a large test file: Drive's daily upload quota and storage are real.

## Benchmark plan for the 20% goal

1. Define “normal Drive” as the Google Drive web UI on the same computer/account, uploading/downloading the same bytes to/from the same Drive region/account, on the same wired/Wi-Fi connection and with no other heavy traffic. Do not compare Cirava against a different test host or against a download-only speed test.
2. Use a harmless, incompressible binary file large enough to run for several minutes (e.g. 1–4 GiB, subject to available Drive quota/storage); use identical content and verify SHA-256 after download. Use unique names or a controlled test folder; document cleanup and avoid burning the 750 GB/day upload allowance.
3. Run baseline and Cirava trials at least three times each, alternate order to reduce time-of-day bias, and compare median payload throughput (bytes successfully acknowledged / elapsed wall time). Record startup/session time separately from payload time, plus retries and completion/integrity results.
4. Test one large file and multi-file batches separately. For download, vary workers and range sizes; for upload, vary chunk sizes for one large file and worker count for batches. Change one variable per test, retain the best stable configuration, and stop increasing concurrency when throughput plateaus or errors rise.
5. Acceptance: median Cirava throughput ≥ 1.20× Drive web baseline in the same direction/workload, successful checksum/integrity, no missing/duplicated bytes, and no increase in unrecovered errors. If the network/Drive route is already the bottleneck, report the measured ceiling instead of claiming the target.

For the screenshot's 4.8 MiB/s upload, the 20% target is 5.76 MiB/s. At the shown 4.5 GiB total and 192 MiB transferred, that target would mean roughly 12.8 minutes for the remaining bytes, versus about 15.4 minutes at the displayed rate (ignoring setup/finalization and rate variation).

## Sources

1. Google Drive API, [Upload file data](https://developers.google.com/workspace/drive/api/guides/manage-uploads) — resumable/single-request/chunk protocol, alignment, server offsets.
2. Google Drive API, [Download and export files](https://developers.google.com/workspace/drive/api/guides/manage-downloads) — media download, HTTP byte ranges, Workspace exports.
3. Google Drive API, [Improve performance](https://developers.google.com/workspace/drive/api/guides/performance) — partial resources, metadata batching, explicit no-media-batching restriction.
4. Google Drive API, [Resolve errors](https://developers.google.com/workspace/drive/api/guides/handle-errors) — 429/403/5xx and exponential backoff.
5. Google Drive API, [Usage limits](https://developers.google.com/workspace/drive/api/guides/limits) — current quota units, daily upload amount, maximum file size.
