import base64
import tempfile
import unittest
import hashlib
import threading
import sys
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

from main import CiravaApi
from cirava_backend.drive_api import DriveApiError
from cirava_backend.notifications import TrayNotifier
from cirava_backend.updater import UpdateManifest
from cirava_backend.models import TransferRecord


class BridgeTests(unittest.TestCase):
    def test_open_google_photos_uses_system_browser_and_rejects_non_photos_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            with patch("main.webbrowser.open", return_value=True) as open_browser:
                result = api.open_google_photos("https://photos.google.com/")

            self.assertEqual(result, {"url": "https://photos.google.com/"})
            open_browser.assert_called_once()
            self.assertEqual(open_browser.call_args.args[0], "https://photos.google.com/")
            with self.assertRaisesRegex(ValueError, "Google Photos"):
                api.open_google_photos("https://example.com/")

    def test_google_photos_local_gallery_returns_small_image_preview_and_video_metadata(self):
        from io import BytesIO
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            photo = Path(directory) / "photo.png"
            image = Image.new("RGB", (1200, 800), color=(40, 120, 180))
            image.save(photo)
            video = Path(directory) / "clip.mp4"
            video.write_bytes(b"video")
            api = CiravaApi(Path(directory) / "app", start_workers=False)

            previews = api.get_google_photos_local_previews([str(photo), str(video)])

            self.assertEqual([item["kind"] for item in previews], ["photo", "video"])
            self.assertTrue(previews[0]["preview"].startswith("data:image/jpeg;base64,"))
            self.assertIsNone(previews[1]["preview"])
            data = previews[0]["preview"].split(",", 1)[1]
            with Image.open(BytesIO(base64.b64decode(data))) as thumbnail:
                self.assertLessEqual(max(thumbnail.size), 360)

    def test_drive_gallery_downloads_sanitize_names_and_skip_google_native_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "downloads"
            destination.mkdir()
            api = CiravaApi(Path(directory) / "app", start_workers=False)

            result = api.create_drive_gallery_downloads([
                {"id": "drive-image", "name": "../summer.jpg", "mimeType": "image/jpeg", "size": "12", "md5Checksum": "hash"},
                {"id": "drive-doc", "name": "Notes", "mimeType": "application/vnd.google-apps.document"},
            ], str(destination), start_immediately=False)

            self.assertEqual(len(result["records"]), 1)
            self.assertEqual(result["skipped"], 1)
            record = result["records"][0]
            self.assertEqual(Path(record["local_path"]).parent.resolve(), destination.resolve())
            self.assertNotIn("/", Path(record["local_path"]).name)
            self.assertNotIn("\\", Path(record["local_path"]).name)
            self.assertTrue(record["deferred"])

    def test_google_photos_picker_selection_exposes_all_items_in_bounded_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            api._photos_picker_sessions.add("picker-session")
            media_items = [{"id": f"photo-{index}", "mediaFile": {"filename": f"photo-{index}.jpg", "mimeType": "image/jpeg", "mediaFileMetadata": {"creationTime": "2025-01-01T00:00:00Z"}}} for index in range(201)]

            class Photos:
                def get_picker_session(self, _session_id): return {"mediaItemsSet": True}
                def list_picker_media_items(self, _session_id): return media_items
                def delete_picker_session(self, _session_id): return None
                def fetch_picker_thumbnail(self, *_args, **_kwargs): raise AssertionError("No thumbnail URL was supplied")

            api._photos = lambda: Photos()
            first = api.get_google_photos_picker_selection("picker-session")
            second = api.get_google_photos_picker_page(first["collection_id"], first["next_offset"], 100)
            third = api.get_google_photos_picker_page(first["collection_id"], second["next_offset"], 100)

            self.assertEqual(len(first["items"]), 100)
            self.assertEqual(len(second["items"]), 100)
            self.assertEqual(len(third["items"]), 1)
            self.assertEqual(first["total"], 201)
            self.assertIsNone(third["next_offset"])
            with self.assertRaisesRegex(ValueError, "expired"):
                api.get_google_photos_picker_page(first["collection_id"], 0)

    def test_photo_upload_batch_creates_deferred_records_for_media_files(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "photo.jpg"
            source.write_bytes(b"photo bytes")
            api = CiravaApi(Path(directory) / "app", start_workers=False)

            records = api.create_google_photos_upload_batch([str(source)], start_immediately=False)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["destination"], "google_photos")
            self.assertTrue(records[0]["deferred"])

    def test_photo_album_upload_creates_one_album_and_persists_its_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "photo.jpg"
            source.write_bytes(b"photo bytes")
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            created_titles = []

            class Photos:
                def create_album(self, title):
                    created_titles.append(title)
                    return {"id": "album-shared-later", "title": title}

            api._photos = lambda: Photos()
            records = api.create_google_photos_upload_batch([str(source)], start_immediately=False, album_title="Summer trip")

            self.assertEqual(created_titles, ["Summer trip"])
            self.assertEqual(records[0]["destination_album_id"], "album-shared-later")
            self.assertEqual(records[0]["destination_album_title"], "Summer trip")
            self.assertEqual(api.store.get(records[0]["id"]).destination_album_id, "album-shared-later")

    def test_photo_worker_adds_uploaded_media_to_its_persisted_album(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "photo.jpg"
            source.write_bytes(b"image bytes")
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            album_destinations = []

            class Photos:
                def create_album(self, title): return {"id": "album-worker", "title": title}
                def create_upload_session(self, mime_type, size): return "https://photos.example/session", 256 * 1024
                def upload_chunk(self, session, data, offset, *, final): return 200, {}, b"upload-token"
                def create_media_items(self, items, *, album_id=None):
                    album_destinations.append((items, album_id))
                    return [{"status": {"message": "Success"}, "mediaItem": {"id": "photo-1"}}]

            api._photos = lambda: Photos()
            record = api.create_google_photos_upload_batch([str(source)], start_immediately=False, album_title="Summer trip")[0]
            api.start_transfer(record["id"])
            api._upload_worker(api.store.get(record["id"]), 256 * 1024)

            self.assertEqual(album_destinations, [([("photo.jpg", "upload-token")], "album-worker")])

    def test_photo_upload_batch_rejects_empty_media_files(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "empty.jpg"
            source.write_bytes(b"")
            api = CiravaApi(Path(directory) / "app", start_workers=False)

            with self.assertRaisesRegex(ValueError, "empty"):
                api.create_google_photos_upload_batch([str(source)], start_immediately=False)

    def test_upload_destination_drive_is_persisted_per_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "payload.bin"
            source.write_bytes(b"payload")
            api = CiravaApi(Path(directory) / "app", start_workers=False)

            record = api.create_upload(str(source), destination_drive_id="team-drive-1")

            self.assertEqual(record["destination_drive_id"], "team-drive-1")
            self.assertEqual(record["drive_parent_id"], "team-drive-1")

    def test_upload_batch_preserves_dotted_subfolder_names_for_shared_drive_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "selection"
            nested = root / "release.v1" / "payload.bin"
            nested.parent.mkdir(parents=True)
            nested.write_bytes(b"payload")
            api = CiravaApi(Path(directory) / "app", start_workers=False)

            [record] = api.create_upload_batch([str(root)], destination_drive_id="team-drive-1", start_immediately=False)

            self.assertEqual(record["relative_path"], "release.v1")
            self.assertEqual(record["drive_parent_id"], "team-drive-1")

    def test_photo_worker_completes_media_item_through_resumable_session(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "photo.jpg"
            source.write_bytes(b"image bytes")
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            calls = []

            class Photos:
                def create_upload_session(self, mime_type, size):
                    calls.append(("session", mime_type, size))
                    return "https://photos.example/session", 256 * 1024

                def upload_chunk(self, session, data, offset, *, final):
                    calls.append(("chunk", session, data, offset, final))
                    return 200, {}, b"upload-token"

                def create_media_items(self, items, *, album_id=None):
                    calls.append(("create", items, album_id))
                    return [{"status": {"message": "Success"}, "mediaItem": {"id": "photo-1"}}]

            api._photos = lambda: Photos()
            record = api.create_google_photos_upload_batch([str(source)], start_immediately=False)[0]

            api.start_transfer(record["id"])
            api._upload_worker(api.store.get(record["id"]), 256 * 1024)
            finished = api.store.get(record["id"])

            self.assertEqual(finished.status.value, "completed")
            self.assertEqual(finished.bytes_transferred, source.stat().st_size)
            self.assertEqual(calls[-1], ("create", [("photo.jpg", "upload-token")], None))

    def test_photo_worker_restarts_if_final_chunk_was_accepted_but_token_response_was_lost(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "photo.jpg"
            source.write_bytes(b"image bytes")
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            sessions = []
            created = []

            class Photos:
                def create_upload_session(self, mime_type, size):
                    session = f"https://photos.example/session-{len(sessions) + 1}"
                    sessions.append(session)
                    return session, 256 * 1024

                def upload_chunk(self, session, data, offset, *, final):
                    if session == sessions[0]:
                        raise ConnectionError("final response lost after Google received bytes")
                    return 200, {}, b"recovered-upload-token"

                def query_upload_offset(self, session):
                    return source.stat().st_size

                def create_media_items(self, items, *, album_id=None):
                    created.append((items, album_id))
                    return [{"status": {"message": "Success"}, "mediaItem": {"id": "photo-2"}}]

            api._photos = lambda: Photos()
            record = api.create_google_photos_upload_batch([str(source)], start_immediately=False)[0]
            api.start_transfer(record["id"])
            api._upload_worker(api.store.get(record["id"]), 256 * 1024)

            finished = api.store.get(record["id"])
            self.assertEqual(finished.status.value, "completed")
            self.assertEqual(len(sessions), 2)
            self.assertEqual(created, [([("photo.jpg", "recovered-upload-token")], None)])

    def test_photo_transfer_bridge_data_never_exposes_resumable_capabilities(self):
        record = TransferRecord(
            id="private-photo", direction="upload", filename="private.jpg", local_path="private.jpg", size=12,
            destination="google_photos", upload_session_url="https://photos.example/capability", destination_item_token="private-token",
        )

        public = record.to_dict()

        self.assertNotIn("upload_session_url", public)
        self.assertNotIn("destination_item_token", public)

    def test_drive_client_is_reused_across_transfer_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory), start_workers=False)
            api.tokens.save({"access_token": "test-token", "refresh_token": "refresh-token", "expires_at": 4_000_000_000})
            api._set_setting("client_id", "1234567890-cirava.apps.googleusercontent.com")

            first = api._drive()
            second = api._drive()

            self.assertIs(first, second)

    def test_save_dialog_preserves_a_path_returned_as_a_string(self):
        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory), start_workers=False)
            expected = str(Path(directory) / "download.bin")
            window = SimpleNamespace(create_file_dialog=lambda *_args, **_kwargs: expected)
            webview = SimpleNamespace(windows=[window], SAVE_DIALOG=1)
            with patch.dict(sys.modules, {"webview": webview}):
                self.assertEqual(api.pick_save_path("download.bin"), expected)

    def test_archive_feature_installs_only_when_enabled_and_preserves_toggle_setting(self):
        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory), start_workers=False)
            with patch("main.SevenZip.ensure_installed") as install:
                disabled = api.set_archive_compression_enabled(False)
                self.assertFalse(disabled["enabled"])
                install.assert_not_called()
                install.return_value = Path(directory) / "tools" / "7zip" / "7z.exe"
                enabled = api.set_archive_compression_enabled(True)
            self.assertTrue(enabled["enabled"])
            self.assertEqual(enabled["provider"], "7-Zip")
            install.assert_called_once()

    def test_archive_upload_preparation_requires_user_to_enable_the_optional_tool(self):
        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory), start_workers=False)
            with self.assertRaisesRegex(RuntimeError, "Enable 7-Zip"):
                api.prepare_compressed_upload(["missing.bin"], 5)

    def test_update_check_uses_in_place_for_same_major_and_installer_for_major_bump(self):
        manifests = [
            UpdateManifest(version="1.11.6", url="https://example.invalid/setup.exe", sha256="a" * 64,
                           app_url="https://example.invalid/Cirava.exe", app_sha256="b" * 64,
                           release_notes_markdown="## Highlights\n\n- **Better** updates."),
            UpdateManifest(version="2.0.0", url="https://example.invalid/setup.exe", sha256="a" * 64,
                           app_url="https://example.invalid/Cirava.exe", app_sha256="b" * 64),
        ]
        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory), start_workers=False)
            with patch("main.Updater") as updater:
                updater.return_value.fetch_manifest.side_effect = manifests
                same_major = api.check_for_update("https://example.invalid/feed", "1.10.0")
                major_bump = api.check_for_update("https://example.invalid/feed", "1.11.6")
        self.assertTrue(same_major["available"])
        self.assertEqual(same_major["update_type"], "in_place")
        self.assertTrue(same_major["in_place_available"])
        self.assertEqual(same_major["release_notes_markdown"], "## Highlights\n\n- **Better** updates.")
        self.assertTrue(major_bump["available"])
        self.assertEqual(major_bump["update_type"], "installer")

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

    def test_deferred_upload_waits_until_user_starts_queue_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            payload = Path(directory) / "queued.txt"
            payload.write_text("queued", encoding="utf-8")
            app_dir = Path(directory) / "app"
            api = CiravaApi(app_dir, start_workers=False)
            [queued] = api.create_upload_batch([str(payload)], "root", start_immediately=False)
            self.assertTrue(queued["deferred"])
            self.assertEqual(queued["status"], "queued")

            api = CiravaApi(app_dir, start_workers=False)
            [recovered] = api.list_transfers()
            self.assertTrue(recovered["deferred"])
            self.assertEqual(recovered["status"], "queued")

            result = api.start_queued_transfers()
            self.assertEqual(result["started"], 1)
            [started] = api.list_transfers()
            self.assertFalse(started["deferred"])

    def test_download_can_be_added_to_waiting_queue_without_starting(self):
        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            queued = api.create_download("drive-file-1", str(Path(directory) / "download.bin"), 4096, start_immediately=False)
            self.assertEqual(queued["direction"], "download")
            self.assertEqual(queued["status"], "queued")
            self.assertTrue(queued["deferred"])
            started = api.start_transfer(queued["id"])
            self.assertFalse(started["deferred"])

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

    def test_old_drive_file_session_must_reconnect_for_full_drive_access(self):
        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            api.tokens.save({"access_token": "old-token", "refresh_token": "old-refresh"})
            self.assertFalse(api.boot_state()["authenticated"])
            api.tokens.save({"access_token": "new-token", "refresh_token": "new-refresh", "cirava_scope_version": 4})
            self.assertTrue(api.boot_state()["authenticated"])

    def test_google_reauthorization_saves_full_drive_scope_marker(self):
        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            api.save_google_configuration("1234567890-cirava.apps.googleusercontent.com")
            with patch("main.OAuthSession") as oauth:
                oauth.return_value.login.return_value = {"access_token": "new-token", "refresh_token": "new-refresh"}
                self.assertTrue(api.begin_google_login()["authenticated"])
            self.assertEqual(api.tokens.load()["cirava_scope_version"], 4)

    def test_staging_and_auto_update_keep_google_login_and_client_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "Cirava"
            api = CiravaApi(data_dir, start_workers=False)
            client_id = "1234567890-cirava.apps.googleusercontent.com"
            api.save_google_configuration(client_id)
            api.tokens.save({"access_token": "access", "refresh_token": "refresh", "cirava_scope_version": 4})
            staged = data_dir / "updates" / "verified.exe"
            staged.parent.mkdir(parents=True)
            staged.write_bytes(b"verified app")
            manifest = UpdateManifest(
                version="1.1.3", url="https://example.invalid/setup.exe", sha256="a" * 64,
                app_url="https://example.invalid/Cirava.exe", app_sha256="b" * 64,
                release_notes_markdown="## Notes\n\n- Update",
            )
            with patch("main.Updater") as updater:
                updater.return_value.fetch_manifest.return_value = manifest
                updater.return_value.download_app_and_stage.return_value = staged
                self.assertTrue(api.stage_update("https://example.invalid/update-manifest.json", "1.1.2")["staged"])
            reopened = CiravaApi(data_dir, start_workers=False)
            self.assertTrue(reopened.boot_state()["authenticated"])
            self.assertTrue(reopened.boot_state()["configured"])
            self.assertEqual(reopened.tokens.load()["refresh_token"], "refresh")
            self.assertEqual(reopened._setting("client_id"), client_id)

    def test_trash_and_storage_bridge_methods_forward_to_drive(self):
        class FakeDrive:
            def list_trashed_files(self):
                return {"files": [{"id": "trashed-1"}]}

            def restore_file(self, file_id):
                self.restored = file_id

            def empty_trash(self):
                self.emptied = True

            def storage_quota(self):
                return {"usage": "450", "limit": "1000"}

        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            drive = FakeDrive()
            api._drive = lambda: drive
            self.assertEqual(api.list_trashed_drive_files(), {"files": [{"id": "trashed-1"}]})
            self.assertEqual(api.restore_drive_file("trashed-1"), {"id": "trashed-1", "status": "restored"})
            self.assertEqual(api.empty_drive_trash(), {"status": "emptied"})
            self.assertEqual(api.get_storage_quota(), {"usage": "450", "limit": "1000"})
            self.assertEqual(drive.restored, "trashed-1")
            self.assertTrue(drive.emptied)

    def test_drive_name_lookup_uses_an_exact_global_search(self):
        class FakeDrive:
            def find_files_by_name(self, name, *, shared_drive_id=None):
                self.searched = name
                return [{"id": "nested-file", "name": name}]

        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            drive = FakeDrive()
            api._drive = lambda: drive
            self.assertEqual(api.find_drive_files_by_name("dummy_5120mb.bin"), {"files": [{"id": "nested-file", "name": "dummy_5120mb.bin"}]})
            self.assertEqual(drive.searched, "dummy_5120mb.bin")

    def test_startup_marks_orphaned_transfer_paused_and_preserves_resume_offset(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "app"
            first = CiravaApi(data_dir, start_workers=False)
            from cirava_backend.models import TransferRecord, TransferStatus
            first.store.upsert(TransferRecord(
                id="orphaned", direction="upload", filename="large.bin", local_path="large.bin",
                size=4_000_000_000, bytes_transferred=512_000_000, speed_bps=2_000_000,
                average_speed_bps=1_800_000, peak_speed_bps=3_000_000,
                upload_session_url="session-is-preserved", status=TransferStatus.TRANSFERRING,
            ))

            restored_api = CiravaApi(data_dir, start_workers=False)
            restored = restored_api.store.get("orphaned")

            self.assertEqual(restored.status, TransferStatus.PAUSED)
            self.assertEqual(restored.bytes_transferred, 512_000_000)
            self.assertEqual(restored.speed_bps, 0)
            self.assertEqual(restored.average_speed_bps, 1_800_000)
            self.assertEqual(restored.peak_speed_bps, 3_000_000)
            self.assertEqual(restored.upload_session_url, "session-is-preserved")
            resumed = restored_api.resume_transfer("orphaned")
            self.assertEqual(resumed["status"], "queued")
            self.assertEqual(resumed["bytes_transferred"], 512_000_000)
            self.assertEqual(resumed["upload_session_url"], "session-is-preserved")

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

    def test_single_large_upload_does_not_tune_cross_file_concurrency(self):
        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            self.assertTrue(api._upload_gate.acquire(timeout=0.1))
            api._upload_telemetry.last_throughput_bps = 900_000_000
            for _ in range(5):
                api._adjust_upload_concurrency()
            self.assertEqual(api._upload_gate.workers, 4)
            api._upload_gate.release()

    def test_multi_file_batch_can_adjust_worker_limit_during_the_current_run(self):
        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            self.assertTrue(api._upload_gate.acquire(timeout=0.1))
            self.assertTrue(api._upload_gate.acquire(timeout=0.1))
            api._upload_telemetry.last_throughput_bps = 500_000_000
            for _ in range(4):
                api._adjust_upload_concurrency()
            self.assertEqual(api._upload_gate.workers, 5)
            api._upload_gate.release()
            api._upload_gate.release()

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
            api.set_upload_concurrency(4)
            for _ in range(4):
                self.assertTrue(api._upload_gate.acquire(timeout=0.1))
            worker = threading.Thread(target=api._upload_worker, args=(api.store.get(record["id"]), 256 * 1024))
            worker.start()
            api.cancel_transfer(record["id"])
            worker.join(timeout=1)
            for _ in range(4):
                api._upload_gate.release()
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
            source.write_bytes(b"u" * (6 * 1024 * 1024))
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            fake = FakeDrive()
            api._drive = lambda: fake
            record = api.create_upload(str(source), chunk_size=256 * 1024)
            api._upload_worker(api.store.get(record["id"]), 256 * 1024)
            loaded = api.store.get(record["id"])
            self.assertEqual(loaded.status.value, "completed")
            self.assertEqual(bytes(fake.payload), source.read_bytes())

    def test_uploads_files_at_or_below_five_mib_as_one_multipart_request(self):
        class FakeDrive:
            def __init__(self):
                self.created = None

            def create_file(self, name, parent, mime_type, content):
                self.created = (name, parent, mime_type, content)
                return {"id": "small-drive-file"}

            def create_upload_session(self, *_args):
                raise AssertionError("small files should not make a separate resumable-session request")

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "small.txt"
            payload = b"x" * (5 * 1024 * 1024)
            source.write_bytes(payload)
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            fake = FakeDrive()
            api._drive = lambda: fake
            record = api.create_upload(str(source))

            api._upload_worker(api.store.get(record["id"]), 16 * 1024 * 1024)

            completed = api.store.get(record["id"])
            self.assertEqual(completed.status.value, "completed")
            self.assertEqual(completed.drive_file_id, "small-drive-file")
            self.assertEqual(completed.bytes_transferred, len(payload))
            self.assertEqual(fake.created, ("small.txt", "root", "text/plain", payload))

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

    def test_download_remains_completed_when_windows_notification_fails(self):
        class FakeDrive:
            def get_range(self, file_id, start, end):
                return b"download"

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "download.bin"
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            api._drive = lambda: FakeDrive()

            def fail_notification(*_args):
                raise RuntimeError("module 'win32con' has no attribute 'NIF_INFO'")

            api._notifier.notify = fail_notification
            record = api.create_download("drive-id", str(destination), 8, segment_size=256 * 1024, workers=1)
            api._download_worker(api.store.get(record["id"]), 256 * 1024, 1, None)

            self.assertEqual(api.store.get(record["id"]).status.value, "completed")
            self.assertEqual(destination.read_bytes(), b"download")

    def test_download_auto_extracts_after_download_only_when_optional_feature_is_enabled(self):
        class FakeDrive:
            def get_range(self, file_id, start, end):
                return b"archive"

        with tempfile.TemporaryDirectory() as directory:
            api = CiravaApi(Path(directory) / "app", start_workers=False)
            api._drive = lambda: FakeDrive()
            destination = Path(directory) / "bundle.cirava.zip"
            api._set_setting("archive_compression_enabled", "true")
            def fail_notification(*_args):
                raise RuntimeError("notification unavailable")
            api._notifier.notify = fail_notification
            record = api.create_download("drive-id", str(destination), 7, segment_size=256 * 1024, workers=1, conflict_policy="replace")
            with patch("main.SevenZip.extract_cirava_archive", return_value=Path(directory) / "bundle (extracted)") as extract:
                api._download_worker(api.store.get(record["id"]), 256 * 1024, 1, None)
            self.assertEqual(api.store.get(record["id"]).status.value, "completed")
            extract.assert_called_once_with(destination)

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

    def test_in_place_update_starts_logged_hash_verifying_handoff(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            api = CiravaApi(root / "app", start_workers=False)
            staged = api.data_dir / "updates" / "cirava-update.exe"
            staged.parent.mkdir(parents=True)
            staged.write_bytes(b"verified app payload")
            target = root / "install" / "Cirava.exe"
            target.parent.mkdir()
            target.write_bytes(b"old running app")
            with patch("main.sys.frozen", True, create=True), patch("main.sys.executable", str(target)), patch("main.subprocess.Popen") as launch:
                result = api.restart_staged_update(str(staged), "in_place")
            self.assertTrue(result["started"])
            encoded = launch.call_args.args[0][-1]
            script = base64.b64decode(encoded).decode("utf-16le")
            expected = hashlib.sha256(staged.read_bytes()).hexdigest()
            self.assertIn(expected, script)
            self.assertIn("update-apply.log", script)
            self.assertIn("[IO.File]::Replace", script)


if __name__ == "__main__":
    unittest.main()
