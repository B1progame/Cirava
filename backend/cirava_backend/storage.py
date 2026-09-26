from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .models import TransferRecord, TransferStatus


class TransferStore:
    """Small durable store for resumable transfer metadata."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS transfers (
                    id TEXT PRIMARY KEY, direction TEXT NOT NULL, filename TEXT NOT NULL,
                    local_path TEXT NOT NULL, size INTEGER NOT NULL, status TEXT NOT NULL,
                    drive_file_id TEXT, drive_parent_id TEXT, upload_session_url TEXT, relative_path TEXT, bytes_transferred INTEGER NOT NULL,
                    speed_bps INTEGER NOT NULL, average_speed_bps INTEGER NOT NULL,
                    peak_speed_bps INTEGER NOT NULL, disk_write_bps INTEGER NOT NULL, retry_count INTEGER NOT NULL,
                    rate_limit_events INTEGER NOT NULL DEFAULT 0, last_retry_delay_seconds REAL NOT NULL DEFAULT 0, last_http_status INTEGER,
                    error TEXT, priority TEXT NOT NULL DEFAULT 'normal', queue_order INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL, started_at REAL, completed_at REAL
                )
            """)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(transfers)").fetchall()}
            if "relative_path" not in columns:
                connection.execute("ALTER TABLE transfers ADD COLUMN relative_path TEXT")
            if "upload_session_url" not in columns:
                connection.execute("ALTER TABLE transfers ADD COLUMN upload_session_url TEXT")
            if "disk_write_bps" not in columns:
                connection.execute("ALTER TABLE transfers ADD COLUMN disk_write_bps INTEGER NOT NULL DEFAULT 0")
            if "rate_limit_events" not in columns:
                connection.execute("ALTER TABLE transfers ADD COLUMN rate_limit_events INTEGER NOT NULL DEFAULT 0")
            if "last_retry_delay_seconds" not in columns:
                connection.execute("ALTER TABLE transfers ADD COLUMN last_retry_delay_seconds REAL NOT NULL DEFAULT 0")
            if "last_http_status" not in columns:
                connection.execute("ALTER TABLE transfers ADD COLUMN last_http_status INTEGER")
            if "priority" not in columns:
                connection.execute("ALTER TABLE transfers ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal'")
            if "queue_order" not in columns:
                connection.execute("ALTER TABLE transfers ADD COLUMN queue_order INTEGER NOT NULL DEFAULT 0")
            connection.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")

    def upsert(self, record: TransferRecord) -> None:
        values = (record.id, record.direction, record.filename, record.local_path, record.size, record.status.value,
                  record.drive_file_id, record.drive_parent_id, record.upload_session_url, record.relative_path, record.bytes_transferred, record.speed_bps,
                  record.average_speed_bps, record.peak_speed_bps, record.disk_write_bps, record.retry_count, record.rate_limit_events, record.last_retry_delay_seconds, record.last_http_status, record.error,
                  record.priority, record.queue_order, record.created_at, record.started_at, record.completed_at)
        with self._connect() as connection:
            connection.execute("""
                INSERT INTO transfers (id,direction,filename,local_path,size,status,drive_file_id,drive_parent_id,upload_session_url,relative_path,bytes_transferred,speed_bps,average_speed_bps,peak_speed_bps,disk_write_bps,retry_count,rate_limit_events,last_retry_delay_seconds,last_http_status,error,priority,queue_order,created_at,started_at,completed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  direction=excluded.direction, filename=excluded.filename, local_path=excluded.local_path,
                  size=excluded.size, status=excluded.status, drive_file_id=excluded.drive_file_id,
                  upload_session_url=excluded.upload_session_url,
                  drive_parent_id=excluded.drive_parent_id, relative_path=excluded.relative_path, bytes_transferred=excluded.bytes_transferred,
                  speed_bps=excluded.speed_bps, average_speed_bps=excluded.average_speed_bps,
                  peak_speed_bps=excluded.peak_speed_bps, disk_write_bps=excluded.disk_write_bps, retry_count=excluded.retry_count,
                  rate_limit_events=excluded.rate_limit_events, last_retry_delay_seconds=excluded.last_retry_delay_seconds, last_http_status=excluded.last_http_status,
                  error=excluded.error, priority=excluded.priority, queue_order=excluded.queue_order, created_at=excluded.created_at, started_at=excluded.started_at,
                  completed_at=excluded.completed_at
            """, values)

    def get(self, transfer_id: str) -> TransferRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM transfers WHERE id = ?", (transfer_id,)).fetchone()
        if row is None:
            raise KeyError(transfer_id)
        return self._record(row)

    def list(self) -> list[TransferRecord]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM transfers ORDER BY CASE priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, queue_order ASC, created_at DESC").fetchall()
        return [self._record(row) for row in rows]

    def set_priority(self, transfer_id: str, priority: str) -> None:
        if priority not in {"low", "normal", "high"}:
            raise ValueError("Priority must be low, normal, or high")
        with self._connect() as connection:
            cursor = connection.execute("UPDATE transfers SET priority=? WHERE id=?", (priority, transfer_id))
            if cursor.rowcount == 0:
                raise KeyError(transfer_id)

    def reorder(self, transfer_ids: list[str]) -> None:
        with self._connect() as connection:
            for order, transfer_id in enumerate(transfer_ids):
                connection.execute("UPDATE transfers SET queue_order=? WHERE id=?", (order, transfer_id))

    def update_progress(self, transfer_id: str, *, bytes_transferred: int, speed_bps: int, average_speed_bps: int | None = None, peak_speed_bps: int | None = None, disk_write_bps: int | None = None) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE transfers SET bytes_transferred=?, speed_bps=?, average_speed_bps=COALESCE(?, average_speed_bps), peak_speed_bps=COALESCE(?, peak_speed_bps), disk_write_bps=COALESCE(?, disk_write_bps) WHERE id=?", (bytes_transferred, speed_bps, average_speed_bps, peak_speed_bps, disk_write_bps, transfer_id))

    def clear_finished(self) -> int:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM transfers WHERE status IN ('completed','failed','cancelled')")
            return cursor.rowcount

    def delete_finished(self, transfer_id: str) -> None:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM transfers WHERE id = ? AND status IN ('completed','failed','cancelled')", (transfer_id,))
            if cursor.rowcount == 0:
                raise ValueError("Only finished transfers can be removed")

    @staticmethod
    def _record(row: sqlite3.Row) -> TransferRecord:
        data = dict(row)
        data["status"] = TransferStatus(data["status"])
        return TransferRecord(**data)
