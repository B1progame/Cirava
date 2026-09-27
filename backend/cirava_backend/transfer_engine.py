from __future__ import annotations

import os
import random
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable, Iterator

ALIGNMENT = 256 * 1024


class TransferStopped(Exception):
    """Raised when a cooperative pause or cancellation is requested."""


def resolve_conflict(path: Path, policy: str) -> Path | None:
    """Resolve an existing destination without ever overwriting by accident."""
    destination = Path(path)
    if not destination.exists():
        return destination
    if policy == "ask":
        raise FileExistsError(destination)
    if policy == "skip":
        return None
    if policy == "replace":
        return destination
    if policy == "keep-both":
        index = 1
        while True:
            candidate = destination.with_name(f"{destination.stem} ({index}){destination.suffix}")
            if not candidate.exists():
                return candidate
            index += 1
    raise ValueError(f"Unknown conflict policy: {policy}")


def verify_md5(path: Path, expected_hex: str, block_size: int = 1024 * 1024) -> bool:
    digest = hashlib.md5()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest().lower() == expected_hex.lower()


def resumable_chunks(file_size: int, chunk_size: int) -> Iterator[tuple[int, int]]:
    """Yield inclusive byte ranges; all non-final ranges are Drive-aligned."""
    if file_size < 0:
        raise ValueError("file_size must be non-negative")
    if chunk_size < ALIGNMENT or chunk_size % ALIGNMENT:
        raise ValueError("chunk_size must be a multiple of 256 KiB")
    start = 0
    while start < file_size:
        end = min(file_size, start + chunk_size) - 1
        yield start, end
        start = end + 1


class RangeMap:
    def __init__(self, file_size: int, segment_size: int):
        if file_size < 0 or segment_size <= 0:
            raise ValueError("file_size and segment_size must be positive")
        self.file_size = file_size
        self.segment_size = segment_size
        self._completed: set[int] = set()
        self._lock = threading.RLock()

    def mark_complete(self, start: int) -> None:
        with self._lock:
            self._completed.add(start)

    def next_pending(self) -> tuple[int, int] | None:
        with self._lock:
            for start in range(0, self.file_size, self.segment_size):
                if start not in self._completed:
                    return start, min(self.file_size, start + self.segment_size) - 1
        return None

    def all_ranges(self) -> list[tuple[int, int]]:
        return [(start, min(self.file_size, start + self.segment_size) - 1) for start in range(0, self.file_size, self.segment_size)]

    @property
    def completed_starts(self) -> tuple[int, ...]:
        with self._lock:
            return tuple(sorted(self._completed))

    @property
    def completed_bytes(self) -> int:
        with self._lock:
            return sum(min(self.file_size, start + self.segment_size) - start for start in self._completed)

    def save(self, path: Path) -> None:
        path = Path(path)
        with self._lock:
            payload = json.dumps({"file_size": self.file_size, "segment_size": self.segment_size, "completed": sorted(self._completed)})
            temporary = path.with_name(path.name + ".tmp")
            temporary.write_text(payload, encoding="utf-8")
            os.replace(temporary, path)

    @classmethod
    def load(cls, path: Path, *, file_size: int, segment_size: int) -> "RangeMap":
        loaded = cls(file_size, segment_size)
        try:
            metadata = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return loaded
        if not isinstance(metadata, dict):
            return loaded
        if metadata.get("file_size") != file_size or metadata.get("segment_size") != segment_size:
            return loaded
        for start in metadata.get("completed", []):
            if type(start) is int and 0 <= start < file_size and start % segment_size == 0:
                loaded.mark_complete(start)
        return loaded


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 6
    max_backoff_seconds: float = 60.0
    jitter_seconds: float = 0.35

    def delay(self, attempt: int, random_value: float | None = None) -> float:
        jitter = random.random() * self.jitter_seconds if random_value is None else random_value * self.jitter_seconds
        return min(self.max_backoff_seconds, (2 ** max(0, attempt - 1)) + jitter)


class TokenBucket:
    """Non-blocking bandwidth limiter. Callers sleep/yield for the returned duration."""

    def __init__(self, rate_bytes_per_second: int, burst_bytes: int | None = None):
        if rate_bytes_per_second <= 0:
            raise ValueError("rate_bytes_per_second must be positive")
        self.rate = float(rate_bytes_per_second)
        self.capacity = float(burst_bytes or rate_bytes_per_second)
        self.tokens = self.capacity
        self._last = 0.0

    def consume(self, amount: int, *, now: float) -> float:
        if amount < 0:
            raise ValueError("amount must be non-negative")
        elapsed = max(0.0, now - self._last)
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self._last = now
        if self.tokens >= amount:
            self.tokens -= amount
            return 0.0
        deficit = amount - self.tokens
        self.tokens = 0.0
        return deficit / self.rate


class TransferTelemetry:
    """Monotonic throughput measurements for UI diagnostics and persistence."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._started = clock()
        self._last_time = self._started
        self._last_bytes = 0
        self.peak_bps = 0

    def observe(self, bytes_transferred: int) -> tuple[int, int, int]:
        now = self._clock()
        delta_time = max(now - self._last_time, 1e-6)
        delta_bytes = max(0, bytes_transferred - self._last_bytes)
        instant = int(delta_bytes / delta_time)
        elapsed = max(now - self._started, 1e-6)
        average = int(bytes_transferred / elapsed)
        self.peak_bps = max(self.peak_bps, instant)
        self._last_time = now
        self._last_bytes = bytes_transferred
        return instant, average, self.peak_bps


class ResumableUploader:
    """Ordered, bounded-memory uploader for one Drive resumable session."""

    def __init__(self, *, retry_policy: RetryPolicy = RetryPolicy(), sleep: Callable[[float], None] = time.sleep, should_continue: Callable[[], bool] | None = None, retryable_error: Callable[[Exception], bool] | None = None, retry_observed: Callable[[int, float, Exception], None] | None = None):
        self.retry_policy = retry_policy
        self._sleep = sleep
        self._should_continue = should_continue or (lambda: True)
        self._retryable_error = retryable_error or (lambda error: isinstance(error, (OSError, TimeoutError, ConnectionError)))
        self._retry_observed = retry_observed

    def upload(self, file_path: Path, chunk_size: int, put_chunk: Callable[[bytes, int, int, int], int | None], progress: Callable[[int, int, int], None] | None = None, next_chunk_size: Callable[[], int] | None = None, initial_offset: int = 0) -> int:
        total = file_path.stat().st_size
        if initial_offset < 0 or initial_offset > total:
            raise ValueError("initial_offset must be within the file")
        acknowledged = initial_offset
        with file_path.open("rb") as source:
            while acknowledged < total:
                if not self._should_continue():
                    raise TransferStopped()
                start = acknowledged
                active_chunk_size = next_chunk_size() if next_chunk_size else chunk_size
                if active_chunk_size < ALIGNMENT or active_chunk_size % ALIGNMENT:
                    raise ValueError("dynamic chunk size must be a multiple of 256 KiB")
                end = min(total, start + active_chunk_size) - 1
                source.seek(start)
                data = source.read(end - start + 1)
                for attempt in range(1, self.retry_policy.max_attempts + 1):
                    if not self._should_continue():
                        raise TransferStopped()
                    try:
                        server_next = put_chunk(data, start, end, total)
                        acknowledged = (server_next if server_next is not None else end + 1)
                        if progress:
                            progress(acknowledged, total, attempt)
                        break
                    except Exception as error:
                        if attempt == self.retry_policy.max_attempts or not self._retryable_error(error):
                            raise
                        delay = self.retry_policy.delay(attempt)
                        if self._retry_observed:
                            self._retry_observed(attempt, delay, error)
                        self._sleep(delay)
        return acknowledged


class SegmentedFileWriter:
    """Preallocates one .part file and writes byte ranges at their final offsets."""

    def __init__(self, destination: Path, size: int):
        self.destination = Path(destination)
        self.destination.parent.mkdir(parents=True, exist_ok=True)
        if not self.destination.exists() or self.destination.stat().st_size != size:
            with self.destination.open("wb") as target:
                target.truncate(size)
        self._lock = threading.Lock()
        self._handle = self.destination.open("r+b")

    def write(self, start: int, data: bytes | bytearray | memoryview) -> None:
        with self._lock:
            if self._handle is None:
                raise ValueError("Range writer is closed")
            self._handle.seek(start)
            self._handle.write(data)

    def flush(self) -> None:
        with self._lock:
            if self._handle is None:
                raise ValueError("Range writer is closed")
            self._handle.flush()

    def close(self) -> None:
        with self._lock:
            if self._handle is not None:
                self._handle.close()
                self._handle = None

    def finalize(self, final_path: Path) -> None:
        self.close()
        os.replace(self.destination, final_path)


class SegmentedDownloader:
    """Fetches many small ranges concurrently and writes them into one .part file."""

    def __init__(self, destination: Path, *, file_size: int, segment_size: int = 64 * 1024 * 1024, workers: int = 4, should_continue: Callable[[], bool] | None = None, worker_provider: Callable[[], int] | None = None, segment_observed: Callable[[float, bool], None] | None = None, wave_observed: Callable[[int, float, bool, bool], None] | None = None, retry_policy: RetryPolicy = RetryPolicy(), sleep: Callable[[float], None] = time.sleep, retryable_error: Callable[[Exception], bool] | None = None, retry_observed: Callable[[int, float, Exception], None] | None = None):
        self.destination = Path(destination)
        self.progress_path = self.destination.with_name(self.destination.name + ".ranges.json")
        self.range_map = RangeMap.load(self.progress_path, file_size=file_size, segment_size=segment_size) if self.progress_path.exists() else RangeMap(file_size, segment_size)
        self.writer = SegmentedFileWriter(self.destination, file_size)
        self.workers = max(1, min(8, workers))
        self._should_continue = should_continue or (lambda: True)
        self._worker_provider = worker_provider
        self._segment_observed = segment_observed
        self._wave_observed = wave_observed
        self.retry_policy = retry_policy
        self._sleep = sleep
        self._retryable_error = retryable_error or (lambda error: isinstance(error, (OSError, TimeoutError, ConnectionError)))
        self._retry_observed = retry_observed

    def download(self, fetch_range: Callable[[int, int], bytes | bytearray | memoryview | Iterator[bytes]], progress: Callable[[int, int], None] | None = None, disk_progress: Callable[[int, float], None] | None = None) -> int:
        pending = [byte_range for byte_range in self.range_map.all_ranges() if byte_range[0] not in self.range_map.completed_starts]

        completed = 0
        def fetch_and_write(byte_range: tuple[int, int]) -> int:
            if not self._should_continue():
                raise TransferStopped()
            start, end = byte_range
            started = time.monotonic()
            try:
                for attempt in range(1, self.retry_policy.max_attempts + 1):
                    payload = None
                    try:
                        payload = fetch_range(start, end)
                        write_elapsed = 0.0
                        cursor = start
                        if isinstance(payload, (bytes, bytearray, memoryview)):
                            if len(payload) != end - start + 1:
                                raise IOError(f"range {start}-{end} returned {len(payload)} bytes, expected {end - start + 1}")
                            write_started = time.monotonic()
                            self.writer.write(start, payload)
                            write_elapsed += max(time.monotonic() - write_started, 1e-6)
                            cursor = end + 1
                        else:
                            for block in payload:
                                if not block:
                                    continue
                                if cursor + len(block) > end + 1:
                                    raise IOError(f"range {start}-{end} returned more than {end - start + 1} bytes")
                                write_started = time.monotonic()
                                self.writer.write(cursor, block)
                                write_elapsed += max(time.monotonic() - write_started, 1e-6)
                                cursor += len(block)
                            if cursor != end + 1:
                                raise IOError(f"range {start}-{end} returned {cursor - start} bytes, expected {end - start + 1}")
                        flush_started = time.monotonic()
                        self.writer.flush()
                        write_elapsed += max(time.monotonic() - flush_started, 1e-6)
                        break
                    except Exception as error:
                        close_payload = getattr(payload, "close", None)
                        if callable(close_payload):
                            close_payload()
                        if attempt == self.retry_policy.max_attempts or not self._retryable_error(error):
                            raise
                        if not self._should_continue():
                            raise TransferStopped()
                        delay = self.retry_policy.delay(attempt)
                        if self._retry_observed:
                            self._retry_observed(attempt, delay, error)
                        self._sleep(delay)
                    finally:
                        close_payload = getattr(payload, "close", None)
                        if callable(close_payload):
                            close_payload()
            except Exception:
                if self._segment_observed:
                    self._segment_observed((time.monotonic() - started) * 1000, False)
                raise
            if self._segment_observed:
                self._segment_observed((time.monotonic() - started) * 1000, True)
            if disk_progress:
                disk_progress(end - start + 1, write_elapsed)
            self.range_map.mark_complete(start)
            self.range_map.save(self.progress_path)
            return end - start + 1

        pool_size = 8 if self._worker_provider else self.workers
        try:
            with ThreadPoolExecutor(max_workers=pool_size, thread_name_prefix="cirava-download") as executor:
                while pending:
                    if not self._should_continue():
                        raise TransferStopped()
                    active_workers = max(1, min(pool_size, self._worker_provider() if self._worker_provider else self.workers))
                    wave, pending = pending[:active_workers * 2], pending[active_workers * 2:]
                    wave_started = time.monotonic()
                    wave_bytes = 0
                    try:
                        futures = [executor.submit(fetch_and_write, byte_range) for byte_range in wave]
                        for future in as_completed(futures):
                            amount = future.result()
                            wave_bytes += amount
                            completed += amount
                            if progress:
                                progress(completed, self.range_map.file_size)
                    except Exception as error:
                        if self._wave_observed:
                            self._wave_observed(0, max(time.monotonic() - wave_started, 1e-6), True, getattr(error, "status", None) in {403, 429})
                        raise
                    if self._wave_observed:
                        self._wave_observed(wave_bytes, max(time.monotonic() - wave_started, 1e-6), False, False)
        finally:
            self.writer.close()
        return completed

    def finalize(self, final_path: Path) -> None:
        self.writer.finalize(final_path)
        self.progress_path.unlink(missing_ok=True)
