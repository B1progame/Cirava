import base64
import io
import tempfile
import unittest
import urllib.error
from unittest.mock import patch
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from cirava_backend.drive_api import DriveApiClient, content_range, is_retryable_status
from cirava_backend.oauth import OAuthConfig, OAuthSession, TokenManager, TokenStore


class GoogleProtocolTests(unittest.TestCase):
    def test_desktop_oauth_uses_os_selected_loopback_port(self):
        session = OAuthSession(OAuthConfig(client_id="desktop-client"), opener=lambda _: None)
        self.assertEqual(session.config.redirect_port, 0)

    def test_desktop_authorization_uses_pkce_and_minimum_drive_scope(self):
        session = OAuthSession(OAuthConfig(client_id="desktop-client", redirect_host="127.0.0.1"), opener=lambda _: None)
        url = session.authorization_url()
        query = parse_qs(urlparse(url).query)
        self.assertEqual(query["client_id"], ["desktop-client"])
        self.assertEqual(query["access_type"], ["offline"])
        self.assertEqual(query["scope"], ["https://www.googleapis.com/auth/drive.file"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertTrue(query["code_challenge"][0])
        self.assertTrue(query["state"][0])

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

        def fake_urlopen(request, timeout):
            captured.append((request, timeout))
            raise urllib.error.HTTPError(request.full_url, 308, "Resume incomplete", {"Range": "bytes=0-255"}, io.BytesIO())

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            offset = DriveApiClient("token").query_upload_offset("https://upload.example/session", 1024)

        self.assertEqual(offset, 256)
        request, timeout = captured[0]
        self.assertEqual(timeout, 60)
        self.assertEqual(request.get_header("Content-range"), "bytes */1024")
        self.assertEqual(request.get_header("Content-length"), "0")

    def test_final_resumable_response_keeps_created_drive_file_id(self):
        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"id":"drive-file-123","name":"fixture.bin"}'

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            client = DriveApiClient("token")
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

    def test_shared_drive_listing_uses_all_drives_parameters(self):
        client = DriveApiClient("token")
        captured = []
        client._request = lambda url, **kwargs: captured.append(url) or (200, {}, b'{"files":[]}')
        client.list_files(parent_id="shared-root", shared_drive_id="drive-123")
        query = parse_qs(urlparse(captured[0]).query)
        self.assertEqual(query["corpora"], ["drive"])
        self.assertEqual(query["driveId"], ["drive-123"])
        self.assertEqual(query["includeItemsFromAllDrives"], ["true"])

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
