from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TransferStatus(StrEnum):
    QUEUED = "queued"
    PREPARING = "preparing"
    TRANSFERRING = "transferring"
    PAUSED = "paused"
    WAITING_FOR_NETWORK = "waiting-for-network"
    RATE_LIMITED = "rate-limited"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(eq=True)
class TransferRecord:
    id: str
    direction: str
    filename: str
    local_path: str
    size: int
    status: TransferStatus = TransferStatus.QUEUED
    drive_file_id: str | None = None
    drive_parent_id: str | None = None
    upload_session_url: str | None = None
    relative_path: str | None = None
    bytes_transferred: int = 0
    speed_bps: int = 0
    average_speed_bps: int = 0
    peak_speed_bps: int = 0
    disk_write_bps: int = 0
    retry_count: int = 0
    rate_limit_events: int = 0
    last_retry_delay_seconds: float = 0.0
    last_http_status: int | None = None
    error: str | None = None
    priority: str = "normal"
    queue_order: int = 0
    created_at: float = field(default_factory=lambda: __import__("time").time())
    started_at: float | None = None
    completed_at: float | None = None

    @property
    def progress(self) -> float:
        return 0.0 if self.size <= 0 else min(1.0, self.bytes_transferred / self.size)

    def to_dict(self) -> dict[str, Any]:
        data = self.__dict__.copy()
        data["status"] = self.status.value
        data["progress"] = self.progress
        return data
