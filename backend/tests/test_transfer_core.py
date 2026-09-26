import tempfile
import unittest
import hashlib
import sqlite3
from pathlib import Path

from cirava_backend.adaptive import AdaptiveConcurrencyController, AdaptiveController, AdaptiveUploadConcurrencyController
from cirava_backend.models import TransferRecord, TransferStatus
from cirava_backend.storage import TransferStore
from cirava_backend.transfer_engine import RangeMap, ResumableUploader, RetryPolicy, SegmentedDownloader, TokenBucket, TransferStopped, TransferTelemetry, resolve_conflict, resumable_chunks, verify_md5


class AdaptiveControllerTests(unittest.TestCase):
    def test_stable_throughput_grows_chunk_size_only_after_hysteresis(self):
        controller = AdaptiveController(chunk_size=16 * 1024 * 1024, min_chunk=8 * 1024 * 1024, max_chunk=128 * 1024 * 1024)
        for _ in range(3):
            controller.observe(throughput_bps=120_000_000, latency_ms=80, error_rate=0, rate_limited=False)
        self.assertEqual(controller.chunk_size, 32 * 1024 * 1024)

    def test_timeout_or_rate_limit_reduces_chunk_size(self):
        controller = AdaptiveController(chunk_size=64 * 1024 * 1024, min_chunk=8 * 1024 * 1024, max_chunk=128 * 1024 * 1024)
        controller.observe(throughput_bps=20_000_000, latency_ms=900, error_rate=.3, rate_limited=True)
        self.assertEqual(controller.chunk_size, 32 * 1024 * 1024)

    def test_concurrency_grows_after_stable_ranges_and_backs_off_on_error(self):
        controller = AdaptiveConcurrencyController(workers=3, max_workers=8)
        for _ in range(4):
            controller.observe(latency_ms=80)
        self.assertEqual(controller.workers, 4)
        controller.observe(latency_ms=1200, error=True)
        self.assertEqual(controller.workers, 3)

    def test_upload_concurrency_hill_climber_stays_within_one_to_eight(self):
        controller = AdaptiveUploadConcurrencyController(workers=4)
        for _ in range(6):
            controller.observe(aggregate_throughput_bps=500_000_000)
        self.assertGreaterEqual(controller.workers, 4)
        grown = controller.workers
        controller.observe(aggregate_throughput_bps=100_000_000, error=True)
        self.assertLessEqual(controller.workers, grown)
        self.assertGreaterEqual(controller.workers, 1)
        self.assertLessEqual(controller.workers, 8)


class TransferStoreTests(unittest.TestCase):
    def test_legacy_store_migrates_upload_session_column(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.db"
            connection = sqlite3.connect(path)
            connection.execute("CREATE TABLE transfers (id TEXT PRIMARY KEY, direction TEXT NOT NULL, filename TEXT NOT NULL, local_path TEXT NOT NULL, size INTEGER NOT NULL, status TEXT NOT NULL, drive_file_id TEXT, drive_parent_id TEXT, relative_path TEXT, bytes_transferred INTEGER NOT NULL, speed_bps INTEGER NOT NULL, average_speed_bps INTEGER NOT NULL, peak_speed_bps INTEGER NOT NULL, disk_write_bps INTEGER NOT NULL, retry_count INTEGER NOT NULL, error TEXT, created_at REAL NOT NULL, started_at REAL, completed_at REAL)")
            connection.commit()
            connection.close()
            store = TransferStore(path)
            verification = sqlite3.connect(path)
            columns = {row[1] for row in verification.execute("PRAGMA table_info(transfers)").fetchall()}
            verification.close()
            self.assertIn("upload_session_url", columns)
            record = TransferRecord(id="legacy", direction="upload", filename="x", local_path="x", size=1, upload_session_url="session")
            store.upsert(record)
            self.assertEqual(store.get("legacy").upload_session_url, "session")

    def test_transfer_state_round_trips_through_sqlite(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TransferStore(Path(directory) / "cirava.db")
            original = TransferRecord(id="t-1", direction="upload", filename="movie.mp4", local_path="C:/movie.mp4", size=100, status=TransferStatus.QUEUED)
            store.upsert(original)
            loaded = store.get("t-1")
            self.assertEqual(loaded, original)

    def test_transfer_progress_updates_are_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TransferStore(Path(directory) / "cirava.db")
            record = TransferRecord(id="t-2", direction="download", filename="archive.zip", local_path="C:/archive.zip", size=1000, status=TransferStatus.TRANSFERRING)
            store.upsert(record)
            store.update_progress("t-2", bytes_transferred=512, speed_bps=12_000_000)
            loaded = store.get("t-2")
            self.assertEqual(loaded.bytes_transferred, 512)
            self.assertEqual(loaded.speed_bps, 12_000_000)

    def test_clear_finished_preserves_active_transfers(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TransferStore(Path(directory) / "cirava.db")
            store.upsert(TransferRecord(id="done", direction="upload", filename="done", local_path="done", size=1, status=TransferStatus.COMPLETED))
            store.upsert(TransferRecord(id="active", direction="upload", filename="active", local_path="active", size=1, status=TransferStatus.TRANSFERRING))
            self.assertEqual(store.clear_finished(), 1)
            self.assertEqual([item.id for item in store.list()], ["active"])


class TransferEngineTests(unittest.TestCase):
    def test_upload_chunks_are_aligned_except_for_final_chunk(self):
        chunks = list(resumable_chunks(file_size=700 * 1024, chunk_size=256 * 1024))
        self.assertEqual(chunks, [(0, 262143), (262144, 524287), (524288, 716799)])

    def test_uploader_honors_cooperative_stop_between_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.bin"
            path.write_bytes(b"x" * (2 * 256 * 1024))
            calls = []
            with self.assertRaises(TransferStopped):
                ResumableUploader(should_continue=lambda: len(calls) < 1).upload(path, 256 * 1024, lambda data, start, end, total: calls.append(start) or end + 1)
            self.assertEqual(calls, [0])

    def test_uploader_accepts_adaptive_aligned_chunk_sizes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "adaptive.bin"
            path.write_bytes(b"x" * (3 * 256 * 1024))
            sizes = iter((256 * 1024, 512 * 1024))
            calls = []
            ResumableUploader().upload(path, 256 * 1024, lambda data, start, end, total: calls.append((start, len(data))) or end + 1, next_chunk_size=lambda: next(sizes, 256 * 1024))
            self.assertEqual(calls, [(0, 256 * 1024), (256 * 1024, 512 * 1024)])

    def test_uploader_retries_drive_rate_limits_when_policy_allows_them(self):
        class DriveRateLimitError(Exception):
            status = 429

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "retry.bin"
            path.write_bytes(b"x" * (256 * 1024))
            attempts = []
            sleeps = []
            def put_chunk(data, start, end, total):
                attempts.append(start)
                if len(attempts) == 1:
                    raise DriveRateLimitError("slow down")
                return end + 1
            ResumableUploader(sleep=sleeps.append, retryable_error=lambda error: getattr(error, "status", None) == 429).upload(path, 256 * 1024, put_chunk)
            self.assertEqual(attempts, [0, 0])
            self.assertEqual(len(sleeps), 1)

    def test_retry_callback_reports_attempt_and_backoff(self):
        class TooManyRequests(Exception):
            status = 429

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "retry-callback.bin"
            path.write_bytes(b"x" * (256 * 1024))
            observations = []
            calls = [0]
            def put_chunk(data, start, end, total):
                calls[0] += 1
                if calls[0] == 1:
                    raise TooManyRequests()
                return end + 1
            uploader = ResumableUploader(sleep=lambda _delay: None, retryable_error=lambda error: getattr(error, "status", None) == 429, retry_observed=lambda attempt, delay, error: observations.append((attempt, delay, error.status)))
            uploader.upload(path, 256 * 1024, put_chunk)
            self.assertEqual(observations[0][0], 1)
            self.assertEqual(observations[0][2], 429)
            self.assertGreaterEqual(observations[0][1], 1)

    def test_range_map_returns_only_unfinished_segments(self):
        ranges = RangeMap(file_size=10, segment_size=3)
        ranges.mark_complete(0)
        self.assertEqual(ranges.next_pending(), (3, 5))
        ranges.mark_complete(3)
        self.assertEqual(ranges.next_pending(), (6, 8))

    def test_segmented_downloader_writes_each_range_to_its_final_offset(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "movie.part"
            downloader = SegmentedDownloader(destination, file_size=8, segment_size=2, workers=2)
            downloader.download(lambda start, end: bytes(range(start, end + 1)))
            self.assertEqual(destination.read_bytes(), bytes(range(8)))

    def test_segmented_downloader_persists_completed_ranges_for_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "resume.part"
            calls: list[int] = []

            def interrupted_fetch(start, end):
                calls.append(start)
                if start == 2:
                    raise ConnectionError("simulated disconnect")
                return bytes(range(start, end + 1))

            no_retry = RetryPolicy(max_attempts=1)
            first = SegmentedDownloader(destination, file_size=4, segment_size=2, workers=1, retry_policy=no_retry)
            with self.assertRaises(ConnectionError):
                first.download(interrupted_fetch)
            self.assertEqual(calls, [0, 2])

            resumed_calls: list[int] = []
            resumed = SegmentedDownloader(destination, file_size=4, segment_size=2, workers=1, retry_policy=no_retry)
            resumed.download(lambda start, end: (resumed_calls.append(start) or bytes(range(start, end + 1))))
            self.assertEqual(resumed_calls, [2])
            self.assertEqual(destination.read_bytes(), bytes(range(4)))

    def test_segmented_downloader_retries_transient_range_failures(self):
        class TooManyRequests(Exception):
            status = 429

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "retry.part"
            calls = []
            sleeps = []

            def fetch_range(start, end):
                calls.append((start, end))
                if len(calls) == 1:
                    raise TooManyRequests()
                return b"abcd"

            downloader = SegmentedDownloader(
                destination,
                file_size=4,
                segment_size=4,
                workers=1,
                retry_policy=RetryPolicy(max_attempts=2, max_backoff_seconds=0, jitter_seconds=0),
                sleep=sleeps.append,
                retryable_error=lambda error: getattr(error, "status", None) == 429,
            )
            downloader.download(fetch_range)

            self.assertEqual(len(calls), 2)
            self.assertEqual(sleeps, [0])
            self.assertEqual(destination.read_bytes(), b"abcd")

    def test_token_bucket_returns_wait_time_instead_of_blocking(self):
        bucket = TokenBucket(rate_bytes_per_second=100, burst_bytes=100)
        self.assertEqual(bucket.consume(100, now=0), 0)
        self.assertEqual(bucket.consume(50, now=0), 0.5)
        self.assertEqual(bucket.consume(50, now=0.5), 0)

    def test_transfer_telemetry_reports_average_and_peak(self):
        now = [0.0]
        telemetry = TransferTelemetry(clock=lambda: now[0])
        now[0] = 1.0
        self.assertEqual(telemetry.observe(100), (100, 100, 100))
        now[0] = 2.0
        self.assertEqual(telemetry.observe(300), (200, 150, 200))

    def test_download_integrity_uses_streaming_md5(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "file.bin"
            path.write_bytes(b"cirava" * 1000)
            expected = hashlib.md5(path.read_bytes()).hexdigest()
            self.assertTrue(verify_md5(path, expected))
            self.assertFalse(verify_md5(path, "0" * 32))

    def test_conflict_policy_never_silently_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / "video.mp4"
            existing.write_bytes(b"old")
            with self.assertRaises(FileExistsError):
                resolve_conflict(existing, "ask")
            self.assertIsNone(resolve_conflict(existing, "skip"))
            self.assertEqual(resolve_conflict(existing, "replace"), existing)
            self.assertEqual(resolve_conflict(existing, "keep-both").name, "video (1).mp4")


if __name__ == "__main__":
    unittest.main()
