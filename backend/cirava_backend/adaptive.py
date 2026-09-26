from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AdaptiveController:
    chunk_size: int = 16 * 1024 * 1024
    min_chunk: int = 8 * 1024 * 1024
    max_chunk: int = 256 * 1024 * 1024
    stable_observations: int = 0
    cooldown: int = 0

    def observe(self, *, throughput_bps: int, latency_ms: float, error_rate: float, rate_limited: bool) -> int:
        unhealthy = rate_limited or error_rate >= 0.12 or latency_ms >= 700
        if unhealthy:
            self.chunk_size = max(self.min_chunk, self.chunk_size // 2)
            self.stable_observations = 0
            self.cooldown = 3
            return self.chunk_size
        if self.cooldown:
            self.cooldown -= 1
            return self.chunk_size
        if throughput_bps > 0 and latency_ms <= 250 and error_rate <= 0.03:
            self.stable_observations += 1
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
    max_workers: int = 16
    stable_observations: int = 0
    cooldown: int = 0

    def __post_init__(self) -> None:
        self.workers = max(self.min_workers, min(self.max_workers, self.workers))

    def observe(self, *, latency_ms: float, error: bool = False, rate_limited: bool = False) -> int:
        if error or rate_limited or latency_ms >= 900:
            self.workers = max(self.min_workers, self.workers - 1)
            self.stable_observations = 0
            self.cooldown = 2
            return self.workers
        if self.cooldown:
            self.cooldown -= 1
            return self.workers
        if latency_ms <= 250:
            self.stable_observations += 1
        else:
            self.stable_observations = 0
        if self.stable_observations >= 4:
            self.workers = min(self.max_workers, self.workers + 1)
            self.stable_observations = 0
            self.cooldown = 2
        return self.workers


@dataclass
class AdaptiveUploadConcurrencyController:
    """Hill-climb cross-file upload concurrency between safe batches."""

    workers: int = 4
    min_workers: int = 1
    max_workers: int = 8
    last_throughput_bps: int = 0
    stable_observations: int = 0
    cooldown: int = 0

    def __post_init__(self) -> None:
        self.workers = max(self.min_workers, min(self.max_workers, self.workers))

    def observe(self, *, aggregate_throughput_bps: int, error: bool = False, rate_limited: bool = False) -> int:
        if error or rate_limited:
            self.workers = max(self.min_workers, self.workers - 1)
            self.stable_observations = 0
            self.cooldown = 2
            self.last_throughput_bps = max(self.last_throughput_bps, aggregate_throughput_bps)
            return self.workers
        if self.last_throughput_bps and aggregate_throughput_bps < int(self.last_throughput_bps * 0.92):
            self.workers = max(self.min_workers, self.workers - 1)
            self.stable_observations = 0
            self.cooldown = 2
        elif not self.cooldown and aggregate_throughput_bps >= int(max(1, self.last_throughput_bps) * 1.08):
            self.stable_observations += 1
            if self.stable_observations >= 2:
                self.workers = min(self.max_workers, self.workers + 1)
                self.stable_observations = 0
                self.cooldown = 2
        else:
            self.stable_observations = 0
        self.cooldown = max(0, self.cooldown - 1)
        self.last_throughput_bps = max(self.last_throughput_bps, aggregate_throughput_bps)
        return self.workers
