import json
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from cirava_backend.photos_api import GooglePhotosApiClient, GooglePhotosApiError
from cirava_backend.models import TransferRecord
from cirava_backend.storage import TransferStore
from tempfile import TemporaryDirectory
from pathlib import Path


class GooglePhotosApiTests(unittest.TestCase):
    def test_picker_session_and_paginated_selected_media_calls(self):
        client = GooglePhotosApiClient("token")
        calls = []
        responses = [
            (200, {}, b'{"id":"picker-1","pickerUri":"https://photos.google.com/picker/session","pollingConfig":{"pollInterval":"5s"}}'),
            (200, {}, b'{"id":"picker-1","mediaItemsSet":true}'),
            (200, {}, b'{"mediaItems":[{"id":"m1"}],"nextPageToken":"page-2"}'),
            (200, {}, b'{"mediaItems":[{"id":"m2"}]}'),
            (200, {}, b'{}'),
        ]
        client._request = lambda url, **kwargs: calls.append((url, kwargs)) or responses.pop(0)

        session = client.create_picker_session()
        polled = client.get_picker_session(session["id"])
        items = client.list_picker_media_items(session["id"])
        client.delete_picker_session(session["id"])

        self.assertTrue(polled["mediaItemsSet"])
        self.assertEqual([item["id"] for item in items], ["m1", "m2"])
        self.assertEqual(urlparse(calls[0][0]).hostname, "photospicker.googleapis.com")
        self.assertEqual(calls[-1][1]["method"], "DELETE")

    def test_photo_destination_survives_transfer_queue_persistence(self):
        with TemporaryDirectory() as directory:
            store = TransferStore(Path(directory) / "transfers.db")
            record = TransferRecord(id="photo-transfer", direction="upload", filename="image.jpg", local_path="image.jpg", size=10, destination="google_photos", destination_album_id="album-1", destination_album_title="Summer trip", destination_item_token="pending-token", upload_chunk_granularity=262144)

            store.upsert(record)
            restored = store.get(record.id)

            self.assertEqual(restored.destination, "google_photos")
            self.assertEqual(restored.destination_item_token, "pending-token")
            self.assertEqual(restored.upload_chunk_granularity, 262144)
            self.assertEqual(restored.destination_album_id, "album-1")
            self.assertEqual(restored.destination_album_title, "Summer trip")

    def test_upload_session_requests_resumable_protocol_and_uses_server_granularity(self):
        client = GooglePhotosApiClient("token")
        captured = []
        client._request = lambda url, **kwargs: captured.append((url, kwargs)) or (
            200, {"X-Goog-Upload-URL": "https://photos.example/session", "X-Goog-Upload-Chunk-Granularity": "262144"}, b""
        )

        session, granularity = client.create_upload_session("image/jpeg", 700000)

        self.assertEqual(session, "https://photos.example/session")
        self.assertEqual(granularity, 262144)
        headers = captured[0][1]["headers"]
        self.assertEqual(headers["X-Goog-Upload-Protocol"], "resumable")
        self.assertEqual(headers["X-Goog-Upload-Raw-Size"], "700000")

    def test_batch_create_uses_original_names_and_returns_photo_ids(self):
        client = GooglePhotosApiClient("token")
        captured = []
        client._request = lambda url, **kwargs: captured.append((url, kwargs)) or (
            200, {}, b'{"newMediaItemResults":[{"status":{"message":"Success"},"mediaItem":{"id":"photo-1"}}]}'
        )

        result = client.create_media_items([("IMG_0001.JPG", "upload-token")])

        self.assertEqual(result[0]["mediaItem"]["id"], "photo-1")
        body = json.loads(captured[0][1]["body"])
        self.assertEqual(body["newMediaItems"][0]["simpleMediaItem"], {"fileName": "IMG_0001.JPG", "uploadToken": "upload-token"})
        self.assertEqual(urlparse(captured[0][0]).path, "/v1/mediaItems:batchCreate")

    def test_create_album_posts_the_user_title_and_returns_the_album_id(self):
        client = GooglePhotosApiClient("token")
        captured = []
        client._request = lambda url, **kwargs: captured.append((url, kwargs)) or (200, {}, b'{"id":"album-1","title":"Summer trip"}')

        album = client.create_album("Summer trip")

        self.assertEqual(album["id"], "album-1")
        self.assertEqual(json.loads(captured[0][1]["body"]), {"album": {"title": "Summer trip"}})
        self.assertEqual(urlparse(captured[0][0]).path, "/v1/albums")

    def test_batch_create_targets_the_created_album_when_one_is_selected(self):
        client = GooglePhotosApiClient("token")
        captured = []
        client._request = lambda url, **kwargs: captured.append((url, kwargs)) or (
            200, {}, b'{"newMediaItemResults":[{"status":{"message":"Success"},"mediaItem":{"id":"photo-1"}}]}'
        )

        client.create_media_items([("IMG_0001.JPG", "upload-token")], album_id="album-1")

        body = json.loads(captured[0][1]["body"])
        self.assertEqual(body["albumId"], "album-1")
        self.assertEqual(body["newMediaItems"][0]["simpleMediaItem"], {"fileName": "IMG_0001.JPG", "uploadToken": "upload-token"})

    def test_batch_create_retries_temporary_server_errors(self):
        client = GooglePhotosApiClient("token")
        attempts = []
        def request(*_args, **_kwargs):
            attempts.append(1)
            if len(attempts) == 1:
                raise GooglePhotosApiError(503, "busy")
            return 200, {}, b'{"newMediaItemResults":[{"status":{"message":"Success"},"mediaItem":{"id":"photo-1"}}]}'
        client._request = request

        with patch("cirava_backend.photos_api.time.sleep"):
            result = client.create_media_items([("IMG_0001.JPG", "upload-token")])

        self.assertEqual(len(attempts), 2)
        self.assertEqual(result[0]["mediaItem"]["id"], "photo-1")


if __name__ == "__main__":
    unittest.main()
