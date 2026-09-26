import tempfile
import unittest
import hashlib
import threading
import sys
from unittest.mock import patch
from pathlib import Path

from main import CiravaApi
from cirava_backend.drive_api import DriveApiError
from cirava_backend.notifications import TrayNotifier


class BridgeTests(unittest.TestCase):
    def test_native_file_and_folder_pickers_return_selected_paths(self):
        class FakeWindow:
            def __init__(self):
                self.calls = []

            def create_file_dialog(self, dialog_type, **kwargs):
                self.calls.append((dialog_type, kwargs))
                return [r"C:\\Users\\tester\\one.txt"] if dialog_type == "open" else [r"C:\\Users\\tester\\workspace"]

        class FakeWebview:
            OPEN_DIALOG = "open"
            FOLDER_DIALOG = "folder"
            SAVE_DIALOG = "save"
            windows = [FakeWindow()]

        api = CiravaApi(Path(tempfile.mkdtemp()), start_workers=False)
        with patch.dict(sys.modules, {"webview": FakeWebview}):
            self.assertEqual(api.pick_files(), [r"C:\\Users\\tester\\one.txt"])
            self.assertEqual(api.pick_folder(), [r"C:\\Users\\tester\\workspace"])
        self.assertEqual(FakeWebview.windows[0].calls, [("open", {"allow_multiple": True}), ("folder", {})])

    def test_native_picker_reports_window_not_ready(self):
        class FakeWebview:
            OPEN_DIALOG = "open"
            windows = []

        api = CiravaApi(Path(tempfile.mkdtemp()), start_workers=False)
        with patch.dict(sys.modules, {"webview": FakeWebview}):
            with self.assertRaisesRegex(RuntimeError, "window is not ready"):
                api.pick_files()

    def test_speed_test_is_one_sparse_20_gib_upload_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory), start_workers=False)
            with patch.object(api, "create_upload_batch", return_value=[{"id": "speed-test"}]) as create_batch:
                result = api.create_test_upload()
            self.assertEqual(result, [{"id": "speed-test"}])
            test_file = Path(directory) / "test-data" / "cirava-speed-test-20gb.bin"
            self.assertEqual(test_file.stat().st_size, 20 * 1024 ** 3)
            create_batch.assert_called_once_with([str(test_file)], "root", 64 * 1024 * 1024)

    def test_tray_notifications_are_safe_before_desktop_shell_starts(self):
        notifier = TrayNotifier()
        notifier.notify("Transfer complete", "example.bin")
        self.assertTrue(notifier.available)

    def test_tray_activation_callback_can_be_set_without_starting_shell(self):
        calls = []
        notifier = TrayNotifier(on_activate=lambda: calls.append("activated"))
        notifier.set_activate_callback(lambda: calls.append("replaced"))
        self.assertEqual(calls, [])
        self.assertIsNotNone(notifier._on_activate)

    def test_new_install_reports_unconfigured_and_unauthenticated(self):
        with tempfile.TemporaryDirectory() as directory:
            state = CiravaApi(Path(directory)).boot_state()
            self.assertFalse(state["configured"])
            self.assertFalse(state["authenticated"])
            self.assertEqual(state["transfers"], [])

    def test_google_configuration_requires_desktop_client_id_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory))
            with self.assertRaises(ValueError):
                api.save_google_configuration("not-a-client-id")
            result = api.save_google_configuration("1234567890-cirava.apps.googleusercontent.com")
            self.assertTrue(result["configured"])

    def test_shared_drive_selection_persists_in_backend_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            self.assertEqual(api.select_shared_drive("drive-123"), {"shared_drive_id": "drive-123"})
            self.assertEqual(api._setting("shared_drive_id"), "drive-123")
            self.assertEqual(api.select_shared_drive(), {"shared_drive_id": None})
            self.assertEqual(api._setting("shared_drive_id"), "")

    def test_upload_concurrency_is_bounded_and_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            self.assertEqual(api.set_upload_concurrency(99), {"workers": 8})
            self.assertEqual(api.get_upload_concurrency(), {"workers": 8})
            self.assertEqual(api.set_upload_concurrency(0), {"workers": 1})

    def test_transfer_priority_and_manual_order_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.bin"
            second = root / "second.bin"
            first.write_bytes(b"1")
            second.write_bytes(b"2")
            api = CiravaApi(root / "app", start_workers=False)
            a = api.create_upload(str(first))
            b = api.create_upload(str(second))
            updated = api.set_transfer_priority(a["id"], "high")
            self.assertEqual(updated["priority"], "high")
            api.reorder_transfers([b["id"], a["id"]])
            restored = CiravaApi(root / "app", start_workers=False)
            rows = restored.list_transfers()
            self.assertEqual(rows[0]["priority"], "high")
            self.assertEqual({row["queue_order"] for row in rows}, {0, 1})
            with self.assertRaises(ValueError):
                restored.set_transfer_priority(a["id"], "urgent")

    def test_upload_batch_expands_nested_folder_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            (root / "nested").mkdir(parents=True)
            (root / "one.txt").write_text("one")
            (root / "nested" / "two.txt").write_text("two")
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            records = api.create_upload_batch([str(root)])
            self.assertEqual(sorted(item["filename"] for item in records), ["one.txt", "two.txt"])
            relative = {item["filename"]: item["relative_path"] for item in records}
            self.assertIsNone(relative["one.txt"])
            self.assertEqual(relative["two.txt"], "nested")

    def test_local_selection_summary_counts_files_and_bytes_without_reading_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            (root / "one.bin").write_bytes(b"1234")
            (root / "two.bin").write_bytes(b"12")
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            summary = api.summarize_local_paths([str(root)])
            self.assertEqual(summary, {"files": 2, "folders": 1, "bytes": 6, "items": 1})

    def test_upload_worker_can_cancel_while_waiting_for_scheduler_slot(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "queued.bin"
            source.write_bytes(b"queued")
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            record = api.create_upload(str(source))
            for _ in range(4):
                self.assertTrue(api._upload_slots.acquire(timeout=0.1))
            worker = threading.Thread(target=api._upload_worker, args=(api.store.get(record["id"]), 256 * 1024))
            worker.start()
            api.cancel_transfer(record["id"])
            worker.join(timeout=1)
            for _ in range(4):
                api._upload_slots.release()
            self.assertFalse(worker.is_alive())
            self.assertEqual(api.store.get(record["id"]).status.value, "cancelled")

    def test_transfer_controls_are_explicit_and_restartable(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "clip.bin"
            source.write_bytes(b"clip")
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            record = api.create_upload(str(source))
            paused = api.pause_transfer(record["id"])
            self.assertEqual(paused["status"], "paused")
            queued = api.resume_transfer(record["id"])
            self.assertEqual(queued["status"], "queued")
            cancelled = api.cancel_transfer(record["id"])
            self.assertEqual(cancelled["status"], "cancelled")
            retry = api.retry_transfer(record["id"])
            self.assertEqual(retry["status"], "queued")

    def test_resume_is_idempotent_when_a_fast_transfer_already_finished(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "fast.bin"
            source.write_bytes(b"fast")
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            record = api.create_upload(str(source))
            stored = api.store.get(record["id"])
            stored.status = type(stored.status).COMPLETED
            api.store.upsert(stored)
            resumed = api.resume_transfer(record["id"])
            self.assertEqual(resumed["status"], "completed")

    def test_finished_transfer_can_be_removed_but_active_transfer_cannot(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "clip.bin"
            source.write_bytes(b"clip")
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            record = api.create_upload(str(source))
            with self.assertRaises(ValueError):
                api.remove_transfer(record["id"])
            stored = api.store.get(record["id"])
            stored.status = type(stored.status).COMPLETED
            api.store.upsert(stored)
            result = api.remove_transfer(record["id"])
            self.assertEqual(result["removed"], record["id"])
            self.assertEqual(api.list_transfers(), [])

    def test_bandwidth_limit_persists_and_zero_disables_it(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "app"
            api = CiravaApi(data_dir, start_workers=False)
            self.assertEqual(api.get_transfer_limit()["mbps"], 0)
            self.assertEqual(api.set_transfer_limit(500)["mbps"], 500)
            self.assertEqual(CiravaApi(data_dir, start_workers=False).get_transfer_limit()["mbps"], 500)
            self.assertEqual(api.set_transfer_limit(0)["mbps"], 0)

    def test_google_configuration_validation_checks_both_public_endpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            with patch("main.urllib.request.urlopen") as open_url:
                open_url.return_value.read.return_value = b"{}"
                result = api.validate_google_configuration("1234567890-cirava.apps.googleusercontent.com")
            self.assertTrue(result["ok"])
            self.assertEqual(open_url.call_count, 2)

    def test_folder_creation_is_deduplicated_within_an_api_batch(self):
        class FakeDrive:
            def __init__(self):
                self.calls = []
            def create_folder(self, name, parent):
                self.calls.append((name, parent))
                return f"{parent}/{name}"
            def find_folder(self, name, parent):
                return None

        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            fake = FakeDrive()
            self.assertEqual(api._ensure_drive_path(fake, "root", "nested/deeper"), "root/nested/deeper")
            self.assertEqual(api._ensure_drive_path(fake, "root", "nested/deeper"), "root/nested/deeper")
            self.assertEqual(fake.calls, [("nested", "root"), ("deeper", "root/nested")])

    def test_paused_transfer_can_be_restarted_after_new_api_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "clip.bin"
            source.write_bytes(b"clip")
            data_dir = root / "app"
            first = CiravaApi(data_dir, start_workers=False)
            record = first.create_upload(str(source))
            first.pause_transfer(record["id"])
            second = CiravaApi(data_dir, start_workers=False)
            resumed = second.resume_transfer(record["id"])
            self.assertEqual(resumed["status"], "queued")

    def test_upload_worker_completes_against_drive_adapter(self):
        class FakeDrive:
            def __init__(self):
                self.payload = bytearray()
            def create_upload_session(self, metadata, size, parent):
                return "session"
            def query_upload_offset(self, session, size):
                return 0
            def put_upload_chunk(self, session, data, start, end, total):
                self.payload.extend(data)
                return end + 1

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "upload.bin"
            source.write_bytes(b"u" * (3 * 256 * 1024))
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            fake = FakeDrive()
            api._drive = lambda: fake
            record = api.create_upload(str(source), chunk_size=256 * 1024)
            api._upload_worker(api.store.get(record["id"]), 256 * 1024)
            loaded = api.store.get(record["id"])
            self.assertEqual(loaded.status.value, "completed")
            self.assertEqual(bytes(fake.payload), source.read_bytes())

    def test_paused_upload_reuses_persisted_drive_session_and_offset(self):
        class FakeDrive:
            def __init__(self):
                self.sessions = 0
                self.calls = []
                self.pause_once = True
            def create_upload_session(self, metadata, size, parent):
                self.sessions += 1
                return "session"
            def query_upload_offset(self, session, size):
                return 256 * 1024
            def put_upload_chunk(self, session, data, start, end, total):
                self.calls.append(start)
                if self.pause_once:
                    self.pause_once = False
                    api.pause_transfer(transfer_id)
                return end + 1

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "resume.bin"
            source.write_bytes(b"r" * (2 * 256 * 1024))
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            fake = FakeDrive()
            api._drive = lambda: fake
            record = api.create_upload(str(source), chunk_size=256 * 1024)
            transfer_id = record["id"]
            api._upload_worker(api.store.get(transfer_id), 256 * 1024)
            paused = api.store.get(transfer_id)
            self.assertEqual(paused.status.value, "paused")
            self.assertEqual(paused.bytes_transferred, 256 * 1024)
            self.assertEqual(paused.upload_session_url, "session")
            api.resume_transfer(transfer_id)
            api._upload_worker(api.store.get(transfer_id), 256 * 1024)
            self.assertEqual(fake.sessions, 1)
            self.assertEqual(fake.calls, [0, 256 * 1024])
            self.assertEqual(api.store.get(transfer_id).status.value, "completed")

    def test_expired_upload_session_is_cleared_for_retry(self):
        class FakeDrive:
            def __init__(self):
                self.sessions = 0
            def create_upload_session(self, metadata, size, parent):
                self.sessions += 1
                return f"session-{self.sessions}"
            def put_upload_chunk(self, session, data, start, end, total):
                if self.sessions == 1:
                    raise DriveApiError(404, "expired")
                return end + 1

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "expired.bin"
            source.write_bytes(b"e" * 256 * 1024)
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            fake = FakeDrive()
            api._drive = lambda: fake
            record = api.create_upload(str(source), chunk_size=256 * 1024)
            api._upload_worker(api.store.get(record["id"]), 256 * 1024)
            failed = api.store.get(record["id"])
            self.assertEqual(failed.status.value, "failed")
            self.assertIsNone(failed.upload_session_url)
            self.assertEqual(failed.bytes_transferred, 0)
            api.retry_transfer(record["id"])
            api._upload_worker(api.store.get(record["id"]), 256 * 1024)
            self.assertEqual(api.store.get(record["id"]).status.value, "completed")
            self.assertEqual(fake.sessions, 2)

    def test_download_worker_completes_and_verifies_checksum(self):
        class FakeDrive:
            def __init__(self, payload):
                self.payload = payload
            def get_range(self, file_id, start, end):
                return self.payload[start:end + 1]

        with tempfile.TemporaryDirectory() as directory:
            payload = bytes(range(256)) * 4096
            destination = Path(directory) / "download.bin"
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            api._drive = lambda: FakeDrive(payload)
            record = api.create_download("drive-id", str(destination), len(payload), segment_size=256 * 1024, workers=2, expected_md5=hashlib.md5(payload).hexdigest(), conflict_policy="replace")
            api._download_worker(api.store.get(record["id"]), 256 * 1024, 2, hashlib.md5(payload).hexdigest())
            loaded = api.store.get(record["id"])
            self.assertEqual(loaded.status.value, "completed")
            self.assertEqual(destination.read_bytes(), payload)

    def test_staged_update_handoff_is_path_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = CiravaApi(root / "app", start_workers=False)
            staged = api.data_dir / "updates" / "cirava-update.exe"
            staged.parent.mkdir(parents=True)
            staged.write_bytes(b"MZ")
            with patch("main.subprocess.Popen") as launch:
                result = api.restart_staged_update(str(staged))
                self.assertTrue(result["started"])
                launch.assert_called_once_with(
                    [result["path"], "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                    cwd=str(Path(result["path"]).parent),
                )
            with self.assertRaises(ValueError):
                api.restart_staged_update(str(root / "outside.exe"))


if __name__ == "__main__":
    unittest.main()
