import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from cirava_backend.drive_api import DriveApiClient, content_range, is_retryable_status
from cirava_backend.oauth import OAuthConfig, OAuthSession, TokenManager, TokenStore, oauth_completion_page


class GoogleProtocolTests(unittest.TestCase):
    def test_drive_client_reuses_keep_alive_connection_for_metadata_requests(self):
        client_ports = []

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):
                client_ports.append(self.client_address[1])
                payload = b'{"ok":true}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            client = DriveApiClient("test-token")
            url = f"http://127.0.0.1:{server.server_port}/drive-test"
            self.assertEqual(client._request(url)[2], b'{"ok":true}')
            self.assertEqual(client._request(url)[2], b'{"ok":true}')
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2)

        self.assertEqual(len(client_ports), 2)
        self.assertEqual(client_ports[0], client_ports[1])

    def test_drive_media_ranges_stream_bounded_chunks_with_the_requested_byte_range(self):
        payload = bytes(range(256)) * 800
        captured_ranges = []
        accepted_encodings = []

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):
                requested = self.headers.get("Range")
                captured_ranges.append(requested)
                accepted_encodings.append(self.headers.get("Accept-Encoding"))
                start, end = (int(value) for value in requested.removeprefix("bytes=").split("-"))
                body = payload[start:end + 1]
                self.send_response(206)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(payload)}")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            client = DriveApiClient("test-token")
            with patch("cirava_backend.drive_api.DRIVE_API", f"http://127.0.0.1:{server.server_port}/drive/v3"):
                chunks = list(client.iter_range("drive-file", 0, len(payload) - 1, chunk_size=64 * 1024))
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2)

        self.assertEqual(captured_ranges, [f"bytes=0-{len(payload) - 1}"])
        self.assertEqual(accepted_encodings, ["identity"])
        self.assertEqual(b"".join(chunks), payload)
        self.assertLessEqual(max(map(len, chunks)), 64 * 1024)

    def test_drive_media_range_rejects_server_that_ignores_range(self):
        class Response:
            status_code = 200
            headers = {}

            def iter_content(self, chunk_size):
                yield b"full file"

            def close(self):
                pass

        client = DriveApiClient("test-token")
        with patch("cirava_backend.drive_api.requests.Session.get", return_value=Response()):
            with self.assertRaisesRegex(IOError, "ignored the requested byte range"):
                list(client.iter_range("drive-file", 4, 7))

    def test_drive_media_range_rejects_mismatched_content_range(self):
        class Response:
            status_code = 206
            headers = {"Content-Range": "bytes 0-3/8"}

            def iter_content(self, chunk_size):
                yield b"data"

            def close(self):
                pass

        client = DriveApiClient("test-token")
        with patch("cirava_backend.drive_api.requests.Session.get", return_value=Response()):
            with self.assertRaisesRegex(IOError, "unexpected Content-Range"):
                list(client.iter_range("drive-file", 4, 7))

    def test_parallel_upload_workers_keep_their_created_drive_ids_separate(self):
        client = DriveApiClient("test-token")
        both_set = threading.Barrier(2)
        results = {}

        def record_id(worker, file_id):
            client.last_uploaded_file_id = file_id
            both_set.wait(timeout=2)
            results[worker] = client.last_uploaded_file_id

        threads = [
            threading.Thread(target=record_id, args=("first", "drive-file-1")),
            threading.Thread(target=record_id, args=("second", "drive-file-2")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=3)

        self.assertEqual(results, {"first": "drive-file-1", "second": "drive-file-2"})

    def test_oauth_completion_page_has_close_attempt_and_honest_fallback(self):
        page = oauth_completion_page().decode("utf-8")

        self.assertIn("window.close()", page)
        self.assertIn("Return to Cirava to finish sign-in.", page)
        self.assertIn("If this tab is still open, close it here.", page)
        self.assertIn('id="completion-message"', page)

    def test_desktop_oauth_uses_os_selected_loopback_port(self):
        session = OAuthSession(OAuthConfig(client_id="desktop-client"), opener=lambda _: None)
        self.assertEqual(session.config.redirect_port, 0)

    def test_desktop_authorization_uses_pkce_and_full_drive_scope(self):
        session = OAuthSession(OAuthConfig(client_id="desktop-client", redirect_host="127.0.0.1"), opener=lambda _: None)
        url = session.authorization_url()
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query["client_id"], ["desktop-client"])
        self.assertEqual(query["access_type"], ["offline"])
        self.assertEqual(query["scope"], ["https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/photoslibrary.appendonly https://www.googleapis.com/auth/photospicker.mediaitems.readonly"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertTrue(query["code_challenge"][0])
        self.assertTrue(query["state"][0])

    def test_drive_gallery_queries_across_drives_and_supports_pagination(self):
        client = DriveApiClient("token")
        captured = []
        client._request = lambda url, **kwargs: captured.append(url) or (200, {}, b'{"files":[{"id":"image-1"}],"nextPageToken":"next"}')

        client.list_all_shared_drives = lambda: []
        result = client.list_gallery_files(query="holiday", pictures_only=True, page_size=75)

        params = parse_qs(urlparse(captured[0]).query)
        self.assertTrue(result["nextPageToken"].startswith("cirava:"))
        self.assertEqual(params["corpora"], ["user"])
        self.assertEqual(params["supportsAllDrives"], ["true"])
        self.assertEqual(params["includeItemsFromAllDrives"], ["true"])
        self.assertNotIn("pageToken", params)
        self.assertEqual(params["pageSize"], ["75"])
        self.assertIn("mimeType contains 'image/'", params["q"][0])

    def test_drive_gallery_cursor_continues_in_a_specific_shared_drive(self):
        client = DriveApiClient("token")
        client.list_all_shared_drives = lambda: [{"id": "team-1"}]
        calls = []
        pages = [
            b'{"files":[{"id":"my-file"}],"nextPageToken":"my-next"}',
            b'{"files":[{"id":"my-file-2"}]}',
            b'{"files":[{"id":"team-file","driveId":"team-1"}]}',
        ]
        client._request = lambda url, **kwargs: calls.append(parse_qs(urlparse(url).query)) or (200, {}, pages.pop(0))

        first = client.list_gallery_files(page_size=1)
        second = client.list_gallery_files(page_token=first["nextPageToken"], page_size=1)
        third = client.list_gallery_files(page_token=second["nextPageToken"], page_size=1)

        self.assertEqual(first["files"][0]["id"], "my-file")
        self.assertEqual(second["files"][0]["id"], "my-file-2")
        self.assertEqual(third["files"][0]["driveId"], "team-1")
        self.assertEqual(calls[0]["corpora"], ["user"])
        self.assertEqual(calls[1]["pageToken"], ["my-next"])
        self.assertEqual(calls[2]["corpora"], ["drive"])
        self.assertEqual(calls[2]["driveId"], ["team-1"])

    def test_token_store_round_trips_without_exposing_raw_json_api(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TokenStore(Path(directory) / "tokens.bin")
            store.save({"access_token": "secret-access", "refresh_token": "secret-refresh", "expires_at": 123})
            self.assertEqual(store.load()["refresh_token"], "secret-refresh")

    def test_token_store_treats_unreadable_cache_as_signed_out(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tokens.bin"
            path.write_bytes(b"stale-or-foreign-profile-token")
            self.assertIsNone(TokenStore(path).load())

    def test_retryable_google_statuses_are_limited_to_transient_failures(self):
        self.assertTrue(is_retryable_status(429))
        self.assertTrue(is_retryable_status(503))
        self.assertFalse(is_retryable_status(403))
        self.assertEqual(content_range(0, 255, 1000), "bytes 0-255/1000")

    def test_resumable_status_probe_uses_drive_acknowledged_range(self):
        captured = []
        client = DriveApiClient("token")
        client._request = lambda url, **kwargs: captured.append((url, kwargs)) or (308, {"Range": "bytes=0-255"}, b"")
        offset = client.query_upload_offset("https://upload.example/session", 1024)

        self.assertEqual(offset, 256)
        url, options = captured[0]
        self.assertEqual(url, "https://upload.example/session")
        self.assertEqual(options["method"], "PUT")
        self.assertEqual(options["body"], b"")
        self.assertEqual(options["headers"]["Content-Range"], "bytes */1024")
        self.assertEqual(options["headers"]["Content-Length"], "0")

    def test_final_resumable_response_keeps_created_drive_file_id(self):
        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"id":"drive-file-123","name":"fixture.bin"}'

        client = DriveApiClient("token")
        client._request = lambda *args, **kwargs: (200, {}, b'{"id":"drive-file-123","name":"fixture.bin"}')
        offset = client.put_upload_chunk("https://upload.example/session", b"data", 0, 3, 4)

        self.assertEqual(offset, 4)
        self.assertEqual(client.last_uploaded_file_id, "drive-file-123")

    def test_drive_folder_creation_returns_created_id(self):
        client = DriveApiClient("token")
        client._request = lambda *args, **kwargs: (200, {}, b'{"id":"folder-123"}')
        self.assertEqual(client.create_folder("nested", "root"), "folder-123")

    def test_drive_folder_lookup_filters_to_exact_folder_name(self):
        client = DriveApiClient("token")
        client.list_files = lambda **kwargs: {"files": [{"id": "file-1", "name": "nested", "mimeType": "text/plain"}, {"id": "folder-1", "name": "nested", "mimeType": "application/vnd.google-apps.folder"}]}
        self.assertEqual(client.find_folder("nested", "root"), "folder-1")

    def test_drive_listing_follows_next_page_tokens(self):
        client = DriveApiClient("token")
        pages = {
            None: {"files": [{"id": "one"}], "nextPageToken": "page-2"},
            "page-2": {"files": [{"id": "two"}]},
        }
        calls = []
        def page(**kwargs):
            calls.append(kwargs.get("page_token"))
            return pages[kwargs.get("page_token")]
        client.list_files = page
        self.assertEqual(client.list_all_files()["files"], [{"id": "one"}, {"id": "two"}])
        self.assertEqual(calls, [None, "page-2"])

    def test_exact_name_lookup_searches_across_folders_and_pages_results(self):
        client = DriveApiClient("token")
        captured = []
        pages = [b'{"nextPageToken":"next","files":[{"id":"one","name":"dummy.bin"}]}', b'{"files":[{"id":"two","name":"dummy.bin"}]}']
        client._request = lambda url, **kwargs: captured.append(url) or (200, {}, pages[len(captured) - 1])

        self.assertEqual(client.find_files_by_name("dummy.bin"), [
            {"id": "one", "name": "dummy.bin"}, {"id": "two", "name": "dummy.bin"},
        ])
        first = parse_qs(urlparse(captured[0]).query)
        second = parse_qs(urlparse(captured[1]).query)
        self.assertEqual(first["q"], ["name = 'dummy.bin' and trashed = false"])
        self.assertNotIn("parents", first["q"][0])
        self.assertEqual(second["pageToken"], ["next"])

    def test_trash_listing_queries_all_pages_without_parent_filter(self):
        client = DriveApiClient("token")
        captured = []
        pages = [b'{"nextPageToken":"next","files":[{"id":"one"}]}', b'{"files":[{"id":"two"}]}']
        client._request = lambda url, **kwargs: captured.append(url) or (200, {}, pages[len(captured) - 1])

        self.assertEqual(client.list_trashed_files(), {"files": [{"id": "one"}, {"id": "two"}]})
        first = parse_qs(urlparse(captured[0]).query)
        second = parse_qs(urlparse(captured[1]).query)
        self.assertEqual(first["q"], ["trashed = true"])
        self.assertNotIn("parents", first["q"][0])
        self.assertEqual(first["includeItemsFromAllDrives"], ["true"])
        self.assertEqual(second["pageToken"], ["next"])

    def test_restore_file_clears_trashed_flag_and_empty_trash_uses_drive_endpoint(self):
        client = DriveApiClient("token")
        captured = []
        client._request = lambda url, **kwargs: captured.append((url, kwargs)) or (204, {}, b"")

        client.restore_file("trashed-1")
        client.empty_trash()

        self.assertEqual(captured[0][1]["method"], "PATCH")
        self.assertEqual(json.loads(captured[0][1]["body"]), {"trashed": False})
        self.assertIn("/files/trashed-1", captured[0][0])
        self.assertEqual(captured[1][1]["method"], "DELETE")
        self.assertIn("/files/trash", captured[1][0])

    def test_storage_quota_reads_used_and_trash_bytes_from_drive_about(self):
        client = DriveApiClient("token")
        captured = []
        client._request = lambda url, **kwargs: captured.append(url) or (200, {}, b'{"storageQuota":{"limit":"1000","usage":"400","usageInDrive":"350","usageInDriveTrash":"50"}}')

        self.assertEqual(client.storage_quota(), {"limit": "1000", "usage": "400", "usageInDrive": "350", "usageInDriveTrash": "50"})
        self.assertIn("/about?", captured[0])
        self.assertIn("storageQuota", parse_qs(urlparse(captured[0]).query)["fields"][0])

    def test_shared_drive_listing_uses_all_drives_parameters(self):
        client = DriveApiClient("token")
        captured = []
        client._request = lambda url, **kwargs: captured.append(url) or (200, {}, b'{"files":[]}')
        client.list_files(parent_id="shared-root", shared_drive_id="drive-123")
        query = parse_qs(urlparse(captured[0]).query)
        self.assertEqual(query["corpora"], ["drive"])
        self.assertEqual(query["driveId"], ["drive-123"])
        self.assertEqual(query["includeItemsFromAllDrives"], ["true"])

    def test_resumable_upload_session_declares_shared_drive_support(self):
        client = DriveApiClient("token")
        captured = []
        client._request = lambda url, **kwargs: captured.append((url, kwargs)) or (200, {"Location": "https://upload.example/session"}, b"")

        self.assertEqual(client.create_upload_session({"name": "payload.bin"}, 7, "shared-folder-1"), "https://upload.example/session")

        query = parse_qs(urlparse(captured[0][0]).query)
        self.assertEqual(query["supportsAllDrives"], ["true"])
        self.assertEqual(json.loads(captured[0][1]["body"])["parents"], ["shared-folder-1"])

    def test_shared_drive_listing_follows_every_page(self):
        client = DriveApiClient("token")
        captured = []
        pages = [b'{"nextPageToken":"next","drives":[{"id":"drive-1","name":"Team"}]}', b'{"drives":[{"id":"drive-2","name":"Archive"}]}']
        client._request = lambda url, **kwargs: captured.append(url) or (200, {}, pages[len(captured) - 1])

        drives = client.list_all_shared_drives()

        self.assertEqual([item["id"] for item in drives], ["drive-1", "drive-2"])
        self.assertEqual(parse_qs(urlparse(captured[1]).query)["pageToken"], ["next"])

    def test_shared_drive_link_resolves_to_its_drive_and_folder_context(self):
        client = DriveApiClient("token")
        captured = []
        client._request = lambda url, **kwargs: captured.append(url) or (200, {}, b'{"id":"folder-1","name":"Shared folder","mimeType":"application/vnd.google-apps.folder","driveId":"drive-1","parents":["parent-1"]}')

        destination = client.resolve_shared_drive_link("https://drive.google.com/drive/folders/folder-1")

        self.assertEqual(destination, {"drive_id": "drive-1", "parent_id": "folder-1", "name": "Shared folder"})
        query = parse_qs(urlparse(captured[0]).query)
        self.assertEqual(query["supportsAllDrives"], ["true"])

    def test_folder_name_resolution_uses_drive_search_and_pages_results(self):
        client = DriveApiClient("token")
        captured = []
        pages = [b'{"nextPageToken":"next","files":[{"id":"one"}]}', b'{"files":[{"id":"two"}]}']
        client._request = lambda url, **kwargs: captured.append(url) or (200, {}, pages[len(captured) - 1])
        matches = client.find_folders_by_name("O'Brien", shared_drive_id="drive-1")
        self.assertEqual(matches, [{"id": "one"}, {"id": "two"}])
        first = parse_qs(urlparse(captured[0]).query)
        second = parse_qs(urlparse(captured[1]).query)
        self.assertIn("mimeType = 'application/vnd.google-apps.folder'", first["q"][0])
        self.assertIn("O\\'Brien", first["q"][0])
        self.assertEqual(first["driveId"], ["drive-1"])
        self.assertEqual(second["pageToken"], ["next"])

    def test_workspace_export_uses_drive_export_endpoint(self):
        client = DriveApiClient("token")
        captured = []
        client._request = lambda url, **kwargs: captured.append(url) or (200, {}, b"pdf")
        self.assertEqual(client.export_file("doc-1", "application/pdf"), b"pdf")
        self.assertIn("/files/doc-1/export", captured[0])

    def test_expired_access_token_refreshes_using_stored_refresh_token(self):
        with tempfile.TemporaryDirectory() as directory:
            store = TokenStore(Path(directory) / "tokens.bin")
            store.save({"access_token": "expired", "refresh_token": "refresh-secret", "expires_at": 0})
            calls = []
            manager = TokenManager(store, refresh_request=lambda refresh: calls.append(refresh) or {"access_token": "fresh", "expires_in": 3600})
            self.assertEqual(manager.access_token(), "fresh")
            self.assertEqual(calls, ["refresh-secret"])
            self.assertEqual(store.load()["access_token"], "fresh")


if __name__ == "__main__":
    unittest.main()
