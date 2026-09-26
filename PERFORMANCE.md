# Cirava performance model

## Uploads

Large files use Drive resumable sessions and read bounded chunks from disk. Chunk sizes are Drive-aligned to 256 KiB and are selected by Auto/Eco/Fast/Max/Manual modes. A single file remains an ordered byte stream; parallelism is across files, with a bounded scheduler to prevent request storms.

The adaptive upload controller observes throughput, latency, and errors. Stable observations allow larger chunks; high latency, errors, or rate limiting reduce the next chunk size with hysteresis.

## Downloads

Binary downloads use HTTP range requests. A preallocated `.part` file receives each range at its final offset, while a JSON range map records completed segments. Workers claim small logical ranges from a shared queue so slow ranges do not hold up the entire file. Worker count adapts within safe bounds and is lowered when latency/errors/disk pressure rise.

## Backpressure and limits

The upload scheduler bounds concurrent files. A shared token bucket enforces an optional bandwidth ceiling for both directions without long fixed sleeps. Pause/cancel checks occur between safe chunks/ranges, and SQLite progress writes preserve acknowledged state.

## Bottlenecks

Telemetry records current, average, and peak throughput, disk-write speed, retry count, remaining bytes, and ETA. The UI labels bottleneck conclusions as inferred: network/Drive when disk is not limiting, or local disk when observed write throughput trails download speed.

## Memory

The engine never loads a whole file into memory. Memory is bounded by the active upload chunk/range buffers and worker count. The final chunk may be smaller than the configured aligned size.

## Integrity

Downloads verify the Drive MD5 checksum when metadata exposes one. A transfer is not marked complete until all expected bytes are written and verification passes.
