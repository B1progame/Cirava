from __future__ import annotations

import json
import threading
import time
import urllib.parse
from typing import Callable

import requests


PHOTOS_API = "https://photoslibrary.googleapis.com/v1"
PICKER_API = "https://photospicker.googleapis.com/v1"


class GooglePhotosApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class GooglePhotosApiClient:
    """Google Photos upload-only client with resumable byte uploads."""

    def __init__(self, access_token: str | Callable[[], str]):
        self._access_token = access_token
        self._batch_lock = threading.Lock()
        self._adapter = requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=8, max_retries=0, pool_block=True)
        self._session_local = threading.local()

    def _session(self) -> requests.Session:
        session = getattr(self._session_local, "session", None)
        if session is None:
            session = requests.Session()
            for adapter in session.adapters.values():
                adapter.close()
            session.adapters.clear()
            session.mount("https://", self._adapter)
            self._session_local.session = session
        return session

    def _token(self) -> str:
        return self._access_token() if callable(self._access_token) else self._access_token

    def _request(self, url: str, *, method: str = "POST", body: bytes | None = None,
                 headers: dict[str, str] | None = None, timeout: float = 120) -> tuple[int, dict[str, str], bytes]:
        request_headers = {"Authorization": f"Bearer {self._token()}"}
        request_headers.update(headers or {})
        try:
            response = self._session().request(method, url, data=body, headers=request_headers, timeout=timeout)
        except requests.Timeout as error:
            raise TimeoutError(str(error)) from error
        except requests.ConnectionError as error:
            raise ConnectionError(str(error)) from error
        except requests.RequestException as error:
            raise OSError(str(error)) from error
        try:
            data = response.content
            if response.status_code >= 400:
                raise GooglePhotosApiError(response.status_code, data.decode(errors="replace"))
            return response.status_code, dict(response.headers), data
        finally:
            response.close()

    def create_picker_session(self) -> dict:
        _, _, data = self._request(f"{PICKER_API}/sessions", body=b"{}", headers={"Content-Type": "application/json"})
        return json.loads(data.decode())

    def get_picker_session(self, session_id: str) -> dict:
        if not session_id or "/" in session_id:
            raise ValueError("Invalid Google Photos Picker session")
        _, _, data = self._request(f"{PICKER_API}/sessions/{urllib.parse.quote(session_id, safe='')}", method="GET")
        return json.loads(data.decode())

    def list_picker_media_items(self, session_id: str) -> list[dict]:
        items: list[dict] = []
        page_token = None
        while True:
            params = {"sessionId": session_id, "pageSize": "100"}
            if page_token:
                params["pageToken"] = page_token
            url = f"{PICKER_API}/mediaItems?{urllib.parse.urlencode(params)}"
            _, _, data = self._request(url, method="GET")
            page = json.loads(data.decode())
            items.extend(page.get("mediaItems", []))
            page_token = page.get("nextPageToken")
            if not page_token:
                return items

    def delete_picker_session(self, session_id: str) -> None:
        if session_id:
            self._request(f"{PICKER_API}/sessions/{urllib.parse.quote(session_id, safe='')}", method="DELETE")

    def fetch_picker_thumbnail(self, base_url: str, *, video: bool = False, max_bytes: int = 1_000_000) -> tuple[str, bytes]:
        """Fetch a bounded authenticated Picker thumbnail; never expose the OAuth token to JS."""
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".googleusercontent.com"):
            raise ValueError("Google Photos returned an unexpected media URL")
        suffix = "=w360-h260" if not video else "=w360-h260"
        url = base_url if "=" in parsed.path.rsplit("/", 1)[-1] else base_url + suffix
        try:
            response = self._session().get(url, headers={"Authorization": f"Bearer {self._token()}"}, timeout=30, stream=True)
        except requests.RequestException as error:
            raise OSError(str(error)) from error
        try:
            if response.status_code >= 400:
                raise GooglePhotosApiError(response.status_code, "Could not load the selected Google Photos preview")
            mime_type = response.headers.get("Content-Type", "image/jpeg").split(";", 1)[0].strip().lower()
            if not mime_type.startswith("image/"):
                raise ValueError("Google Photos returned a non-image thumbnail")
            content = bytearray()
            for chunk in response.iter_content(32 * 1024):
                content.extend(chunk)
                if len(content) > max_bytes:
                    raise ValueError("Google Photos thumbnail exceeded the preview size limit")
            return mime_type, bytes(content)
        finally:
            response.close()

    def create_upload_session(self, mime_type: str, size: int) -> tuple[str, int]:
        if size <= 0:
            raise ValueError("Google Photos cannot upload an empty file")
        headers = {
            "Content-Length": "0",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Content-Type": mime_type,
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Raw-Size": str(size),
        }
        _, response_headers, _ = self._request(f"{PHOTOS_API}/uploads", headers=headers)
        session_url = response_headers.get("X-Goog-Upload-URL") or response_headers.get("x-goog-upload-url")
        granularity = response_headers.get("X-Goog-Upload-Chunk-Granularity") or response_headers.get("x-goog-upload-chunk-granularity")
        if not session_url or not granularity:
            raise GooglePhotosApiError(502, "Google Photos did not return a resumable upload session")
        return session_url, int(granularity)

    def upload_chunk(self, session_url: str, content: bytes, offset: int, *, final: bool) -> tuple[int, dict[str, str], bytes]:
        if not content:
            raise ValueError("Upload chunks cannot be empty")
        command = "upload, finalize" if final else "upload"
        return self._request(session_url, body=content, headers={
            "Content-Length": str(len(content)),
            "X-Goog-Upload-Command": command,
            "X-Goog-Upload-Offset": str(offset),
        })

    def query_upload_offset(self, session_url: str) -> int:
        _, response_headers, _ = self._request(session_url, headers={
            "Content-Length": "0", "X-Goog-Upload-Command": "query",
        })
        received = response_headers.get("X-Goog-Upload-Size-Received") or response_headers.get("x-goog-upload-size-received") or "0"
        return int(received)

    def create_album(self, title: str) -> dict:
        clean_title = title.strip()
        if not clean_title:
            raise ValueError("Enter a name for the Google Photos album")
        if len(clean_title) > 500:
            raise ValueError("Google Photos album names must be 500 characters or fewer")
        _, _, data = self._request(
            f"{PHOTOS_API}/albums",
            body=json.dumps({"album": {"title": clean_title}}).encode(),
            headers={"Content-Type": "application/json"},
        )
        album = json.loads(data.decode())
        if not album.get("id"):
            raise GooglePhotosApiError(502, "Google Photos created an album without returning its ID")
        return album

    def create_media_items(self, files: list[tuple[str, str]], *, album_id: str | None = None) -> list[dict]:
        if not files:
            return []
        if len(files) > 50:
            raise ValueError("Google Photos accepts at most 50 items per create request")
        payload = {"newMediaItems": [{"simpleMediaItem": {"fileName": name, "uploadToken": token}} for name, token in files]}
        if album_id:
            payload["albumId"] = album_id
        with self._batch_lock:
            for attempt in range(1, 7):
                try:
                    _, _, data = self._request(
                        f"{PHOTOS_API}/mediaItems:batchCreate",
                        body=json.dumps(payload).encode(),
                        headers={"Content-Type": "application/json"},
                    )
                    break
                except GooglePhotosApiError as error:
                    if error.status not in {408, 429, 500, 502, 503, 504} or attempt == 6:
                        raise
                    time.sleep(max(30 if error.status == 429 else 0, min(60, 2 ** (attempt - 1))))
                except (TimeoutError, ConnectionError, OSError):
                    if attempt == 6:
                        raise
                    time.sleep(min(60, 2 ** (attempt - 1)))
        results = json.loads(data.decode()).get("newMediaItemResults", [])
        failures = [item for item in results if (item.get("status") or {}).get("code", 0)]
        if failures:
            reason = "; ".join(str((item.get("status") or {}).get("message") or "Google Photos rejected an item") for item in failures)
            raise GooglePhotosApiError(207, reason)
        return results
