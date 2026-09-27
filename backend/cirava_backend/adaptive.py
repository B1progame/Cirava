from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class AdaptiveController:
    chunk_size: int = 16 * 1024 * 1024
    min_chunk: int = 8 * 1024 * 1024
    max_chunk: int = 256 * 1024 * 1024
    stable_observations: int = 0
    cooldown: int = 0
    last_throughput_bps: int = 0

    def observe(self, *, throughput_bps: int, latency_ms: float, error_rate: float, rate_limited: bool) -> int:
        # Request duration includes transmitting the entire chunk. A multi-
        # second PUT is normal for a large chunk and is not itself a timeout.
        unhealthy = rate_limited or error_rate >= 0.12
        if unhealthy:
            self.chunk_size = max(self.min_chunk, self.chunk_size // 2)
            self.stable_observations = 0
            self.cooldown = 3
            if throughput_bps > 0:
                self.last_throughput_bps = throughput_bps
            return self.chunk_size
        if self.cooldown:
            self.cooldown -= 1
            return self.chunk_size
        if throughput_bps > 0 and error_rate <= 0.03:
            if self.last_throughput_bps and throughput_bps < int(self.last_throughput_bps * 0.7):
                self.chunk_size = max(self.min_chunk, self.chunk_size // 2)
                self.stable_observations = 0
                self.cooldown = 2
                self.last_throughput_bps = throughput_bps
                return self.chunk_size
            self.stable_observations += 1
            self.last_throughput_bps = throughput_bps
        else:
            self.stable_observations = 0
        if self.stable_observations >= 3:
            self.chunk_size = min(self.max_chunk, self.chunk_size * 2)
            self.stable_observations = 0
            self.cooldown = 3
        return self.chunk_size


@dataclass
class AdaptiveConcurrencyController:
    workers: int = 4
    min_workers: int = 1
    max_workers: int = 8
    stable_observations: int = 0
    cooldown: int = 0
    last_throughput_bps: int = 0
    trial_baseline_bps: int = 0
    trial_workers: int = 0
    trial_observations: int = 0

    def __post_init__(self) -> None:
        self.workers = max(self.min_workers, min(self.max_workers, self.workers))

    def observe(self, *, throughput_bps: int = 0, latency_ms: float | None = None, error: bool = False, rate_limited: bool = False) -> int:
        # Whole-range duration is not RTT: a healthy 64 MiB response can take
        # seconds. Only compare aggregate bytes/sec for successful worker trials.
        if error or rate_limited:
            self.workers = max(self.min_workers, self.workers - 1)
            self.stable_observations = 0
            self.cooldown = 2
            self.last_throughput_bps = max(0, int(throughput_bps)) or self.last_throughput_bps
            self.trial_workers = 0
            self.trial_observations = 0
            return self.workers
        throughput_bps = max(0, int(throughput_bps))
        if throughput_bps == 0:
            return self.workers
        if self.trial_workers:
            self.trial_observations += 1
            if throughput_bps >= int(self.trial_baseline_bps * 1.06):
                self.last_throughput_bps = throughput_bps
                self.trial_workers = 0
                self.trial_observations = 0
                self.stable_observations = 0
            elif throughput_bps < int(self.trial_baseline_bps * 0.92) or self.trial_observations >= 2:
                self.workers = max(self.min_workers, self.trial_workers - 1)
                self.last_throughput_bps = self.trial_baseline_bps
                self.trial_workers = 0
                self.trial_observations = 0
                self.stable_observations = 0
                self.cooldown = 2
            return self.workers
        if self.cooldown:
            self.cooldown -= 1
            return self.workers
        if not self.last_throughput_bps:
            self.last_throughput_bps = throughput_bps
            return self.workers
        if throughput_bps < int(self.last_throughput_bps * 0.90):
            self.workers = max(self.min_workers, self.workers - 1)
            self.last_throughput_bps = throughput_bps
            self.stable_observations = 0
            self.cooldown = 2
            return self.workers
        if throughput_bps >= int(self.last_throughput_bps * 0.97):
            self.stable_observations += 1
        else:
            self.stable_observations = 0
        self.last_throughput_bps = max(self.last_throughput_bps, throughput_bps)
        if self.stable_observations >= 4:
            if self.workers < self.max_workers:
                self.workers += 1
                self.trial_workers = self.workers
                self.trial_baseline_bps = self.last_throughput_bps
                self.trial_observations = 0
            self.stable_observations = 0
        return self.workers


@dataclass
class AdaptiveUploadConcurrencyController:
    """Probe cross-file concurrency against whole-batch throughput samples."""

    workers: int = 4
    min_workers: int = 1
    max_workers: int = 8
    last_throughput_bps: int = 0
    stable_observations: int = 0
    cooldown: int = 0
    trial_baseline_bps: int = 0
    trial_workers: int = 0
    trial_observations: int = 0

    def __post_init__(self) -> None:
        self.workers = max(self.min_workers, min(self.max_workers, self.workers))

    def observe(self, *, aggregate_throughput_bps: int, error: bool = False, rate_limited: bool = False) -> int:
        if error or rate_limited:
            self.workers = max(self.min_workers, self.workers - 1)
            self.stable_observations = 0
            self.cooldown = 2
            self.last_throughput_bps = max(0, aggregate_throughput_bps)
            self.trial_workers = 0
            self.trial_observations = 0
            return self.workers

        if aggregate_throughput_bps <= 0:
            return self.workers
        if self.trial_workers:
            self.trial_observations += 1
            if aggregate_throughput_bps >= int(self.trial_baseline_bps * 1.06):
                self.last_throughput_bps = aggregate_throughput_bps
                self.trial_workers = 0
                self.trial_observations = 0
                self.stable_observations = 0
            elif aggregate_throughput_bps < int(self.trial_baseline_bps * 0.92) or self.trial_observations >= 2:
                self.workers = max(self.min_workers, self.trial_workers - 1)
                self.last_throughput_bps = self.trial_baseline_bps
                self.trial_workers = 0
                self.trial_observations = 0
                self.stable_observations = 0
                self.cooldown = 2
            return self.workers

        if self.cooldown:
            self.cooldown -= 1
            return self.workers
        if not self.last_throughput_bps:
            self.last_throughput_bps = aggregate_throughput_bps
            return self.workers
        if aggregate_throughput_bps < int(self.last_throughput_bps * 0.90):
            self.workers = max(self.min_workers, self.workers - 1)
            self.stable_observations = 0
            self.cooldown = 2
            self.last_throughput_bps = aggregate_throughput_bps
        else:
            self.stable_observations += 1
            if aggregate_throughput_bps > self.last_throughput_bps:
                self.last_throughput_bps = aggregate_throughput_bps
            if self.stable_observations >= 3 and self.workers < self.max_workers:
                self.workers += 1
                self.trial_baseline_bps = self.last_throughput_bps
                self.trial_workers = self.workers
                self.trial_observations = 0
                self.stable_observations = 0
        return self.workers


class AggregateUploadThroughput:
    """Sample bytes-per-second from all concurrently active upload files."""

    def __init__(self, *, sample_interval: float = 1.5, clock=time.monotonic):
        self.sample_interval = max(0.1, float(sample_interval))
        self._clock = clock
        self._lock = threading.Lock()
        self._active: dict[str, int] = {}
        self._run_bytes = 0
        self._last_sample_bytes = 0
        self._last_sample_time: float | None = None
        self.last_throughput_bps = 0

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._active)

    def begin(self, transfer_id: str, bytes_transferred: int = 0) -> None:
        with self._lock:
            if not self._active:
                self._run_bytes = 0
                self._last_sample_bytes = 0
                self._last_sample_time = None
                self.last_throughput_bps = 0
            self._active[transfer_id] = max(0, int(bytes_transferred))

    def observe(self, transfer_id: str, bytes_transferred: int) -> int | None:
        now = self._clock()
        value = max(0, int(bytes_transferred))
        with self._lock:
            if transfer_id not in self._active:
                if not self._active:
                    self._run_bytes = 0
                    self._last_sample_bytes = 0
                    self._last_sample_time = None
                    self.last_throughput_bps = 0
                self._active[transfer_id] = value
                if self._last_sample_time is None:
                    self._last_sample_time = now
                    self._last_sample_bytes = self._run_bytes
                return None
            previous = self._active[transfer_id]
            self._active[transfer_id] = value
            self._run_bytes += max(0, value - previous)
            if self._last_sample_time is None:
                self._last_sample_time = now
                self._last_sample_bytes = self._run_bytes
                return None
            elapsed = now - self._last_sample_time
            if elapsed < self.sample_interval:
                return None
            throughput = int(max(0, self._run_bytes - self._last_sample_bytes) / max(elapsed, 1e-6))
            self._last_sample_time = now
            self._last_sample_bytes = self._run_bytes
            self.last_throughput_bps = throughput
            return throughput

    def finish(self, transfer_id: str) -> None:
        with self._lock:
            self._active.pop(transfer_id, None)
            if not self._active:
                self._run_bytes = 0
                self._last_sample_bytes = 0
                self._last_sample_time = None
                self.last_throughput_bps = 0


class AdaptiveWorkerGate:
    """A resizeable upload-slot gate that takes effect without restarting work."""

    def __init__(self, workers: int, *, min_workers: int = 1, max_workers: int = 8):
        self.min_workers = min_workers
        self.max_workers = max_workers
        self._limit = max(min_workers, min(max_workers, int(workers)))
        self._active = 0
        self._condition = threading.Condition()

    @property
    def workers(self) -> int:
        with self._condition:
            return self._limit

    @property
    def active(self) -> int:
        with self._condition:
            return self._active

    def resize(self, workers: int) -> None:
        with self._condition:
            self._limit = max(self.min_workers, min(self.max_workers, int(workers)))
            self._condition.notify_all()

    def acquire(self, should_continue=lambda: True, timeout: float | None = None) -> bool:
        deadline = None if timeout is None else time.monotonic() + max(0, timeout)
        with self._condition:
            while self._active >= self._limit:
                if not should_continue():
                    return False
                if deadline is not None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return False
                    self._condition.wait(min(remaining, 0.25))
                else:
                    self._condition.wait(0.25)
            if not should_continue():
                return False
            self._active += 1
            return True

    def release(self) -> None:
        with self._condition:
            if self._active <= 0:
                raise RuntimeError("upload worker gate released without an active worker")
            self._active -= 1
            self._condition.notify_all()
