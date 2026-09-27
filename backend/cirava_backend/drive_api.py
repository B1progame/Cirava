from __future__ import annotations

import json
import threading
import urllib.parse
from typing import Callable, Iterator

import requests
from requests.adapters import HTTPAdapter


DRIVE_API = "https://www.googleapis.com/drive/v3"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"


def content_range(start: int, end: int, total: int) -> str:
    return f"bytes {start}-{end}/{total}"


def is_retryable_status(status: int) -> bool:
    return status in {429, 500, 502, 503, 504}


class DriveApiError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class DriveApiClient:
    def __init__(self, access_token: str | Callable[[], str]):
        self._access_token = access_token
        self._http_adapter = HTTPAdapter(pool_connections=4, pool_maxsize=8, max_retries=0, pool_block=True)
        self._session_local = threading.local()
        # The final resumable response is per upload worker. Keep its ID in
        # thread-local state because one DriveApiClient is shared by transfers.

    @property
    def last_uploaded_file_id(self) -> str | None:
        return getattr(self._session_local, "last_uploaded_file_id", None)

    @last_uploaded_file_id.setter
    def last_uploaded_file_id(self, value: str | None) -> None:
        self._session_local.last_uploaded_file_id = value

    def _token(self) -> str:
        return self._access_token() if callable(self._access_token) else self._access_token

    def _session(self) -> requests.Session:
        session = getattr(self._session_local, "session", None)
        if session is None:
            session = requests.Session()
            # Keep per-thread request state isolated while sharing urllib3's
            # thread-safe connection pools across file and range workers.
            for adapter in session.adapters.values():
                adapter.close()
            session.adapters.clear()
            session.mount("https://", self._http_adapter)
            session.mount("http://", self._http_adapter)
            self._session_local.session = session
        return session

    def _request(self, url: str, *, method: str = "GET", body: bytes | None = None, headers: dict[str, str] | None = None, timeout: float = 60) -> tuple[int, dict[str, str], bytes]:
        request_headers = {"Authorization": f"Bearer {self._token()}"}
        request_headers.update(headers or {})
        try:
            response = self._session().request(method, url, data=body, headers=request_headers, timeout=timeout, allow_redirects=False)
        except requests.Timeout as error:
            raise TimeoutError(str(error)) from error
        except requests.ConnectionError as error:
            raise ConnectionError(str(error)) from error
        except requests.RequestException as error:
            raise OSError(str(error)) from error
        try:
            status = response.status_code
            response_headers = dict(response.headers)
            data = response.content
            if status >= 400:
                raise DriveApiError(status, data.decode(errors="replace"))
            return status, response_headers, data
        finally:
            response.close()

    def list_files(self, *, parent_id: str = "root", query: str | None = None, page_token: str | None = None, shared_drive_id: str | None = None) -> dict:
        clauses = [f"'{parent_id}' in parents", "trashed = false"]
        if query:
            escaped = query.replace("'", "\\'")
            clauses.append(f"name contains '{escaped}'")
        params = {"q": " and ".join(clauses), "fields": "nextPageToken,files(id,name,mimeType,size,modifiedTime,md5Checksum,parents,capabilities(canDownload,canEdit))", "pageSize": "1000", "orderBy": "folder,name", "includeItemsFromAllDrives": "true", "supportsAllDrives": "true"}
        if shared_drive_id:
            params.update({"corpora": "drive", "driveId": shared_drive_id})
        if page_token:
            params["pageToken"] = page_token
        _, _, data = self._request(f"{DRIVE_API}/files?{urllib.parse.urlencode(params)}")
        return json.loads(data.decode())

    def about_user(self) -> dict:
        """Return the signed-in Google profile exposed by Drive's about endpoint."""
        params = urllib.parse.urlencode({"fields": "user(displayName,emailAddress,photoLink)"})
        _, _, data = self._request(f"{DRIVE_API}/about?{params}")
        payload = json.loads(data.decode())
        user = payload.get("user") or {}
        return {
            "name": str(user.get("displayName") or "Google account"),
            "email": str(user.get("emailAddress") or ""),
            "photoUrl": str(user.get("photoLink") or ""),
            "driveName": "Personal Drive",
        }

    def storage_quota(self) -> dict:
        """Return Drive storage usage, including the portion held in Trash."""
        params = urllib.parse.urlencode({"fields": "storageQuota(limit,usage,usageInDrive,usageInDriveTrash)"})
        _, _, data = self._request(f"{DRIVE_API}/about?{params}")
        return json.loads(data.decode()).get("storageQuota") or {}

    def list_trashed_files(self) -> dict:
        """List every trashed item visible in the signed-in user's Drive."""
        params = {
            "q": "trashed = true",
            "fields": "nextPageToken,files(id,name,mimeType,size,modifiedTime,trashedTime,parents,owners(displayName,emailAddress),capabilities(canTrash,canDelete))",
            "pageSize": "1000",
            "includeItemsFromAllDrives": "true",
            "supportsAllDrives": "true",
        }
        files: list[dict] = []
        while True:
            _, _, data = self._request(f"{DRIVE_API}/files?{urllib.parse.urlencode(params)}")
            page = json.loads(data.decode())
            files.extend(page.get("files", []))
            token = page.get("nextPageToken")
            if not token:
                return {"files": files}
            params["pageToken"] = token

    def restore_file(self, file_id: str) -> None:
        """Restore an item by clearing its Drive trashed flag."""
        if not file_id:
            raise ValueError("Drive file ID is required")
        params = urllib.parse.urlencode({"supportsAllDrives": "true"})
        status, _, _ = self._request(
            f"{DRIVE_API}/files/{urllib.parse.quote(file_id)}?{params}",
            method="PATCH",
            body=json.dumps({"trashed": False}).encode(),
            headers={"Content-Type": "application/json"},
        )
        if status not in {200, 204}:
            raise DriveApiError(status, "Google Drive did not restore the file")

    def empty_trash(self) -> None:
        """Permanently delete all items in the signed-in user's Drive trash."""
        status, _, _ = self._request(f"{DRIVE_API}/files/trash", method="DELETE")
        if status not in {200, 204}:
            raise DriveApiError(status, "Google Drive could not empty the trash")

    def list_all_files(self, *, parent_id: str = "root", query: str | None = None, shared_drive_id: str | None = None) -> dict:
        files: list[dict] = []
        page_token: str | None = None
        while True:
            page = self.list_files(parent_id=parent_id, query=query, page_token=page_token, shared_drive_id=shared_drive_id)
            files.extend(page.get("files", []))
            page_token = page.get("nextPageToken")
            if not page_token:
                return {"files": files}

    def find_files_by_name(self, name: str, *, shared_drive_id: str | None = None) -> list[dict]:
        """Find exact-name items across Drive folders, not only the visible root."""
        if not name or not name.strip():
            raise ValueError("Drive file name is required")
        escaped = name.replace("\\", "\\\\").replace("'", "\\'")
        params = {
            "q": f"name = '{escaped}' and trashed = false",
            "fields": "nextPageToken,files(id,name,mimeType,size,modifiedTime,parents,capabilities(canDownload,canEdit))",
            "pageSize": "1000",
            "orderBy": "name",
            "includeItemsFromAllDrives": "true",
            "supportsAllDrives": "true",
        }
        if shared_drive_id:
            params.update({"corpora": "drive", "driveId": shared_drive_id})
        matches: list[dict] = []
        while True:
            _, _, data = self._request(f"{DRIVE_API}/files?{urllib.parse.urlencode(params)}")
            page = json.loads(data.decode())
            matches.extend(file for file in page.get("files", []) if file.get("name") == name)
            token = page.get("nextPageToken")
            if not token:
                return matches
            params["pageToken"] = token

    def find_folders_by_name(self, name: str, *, shared_drive_id: str | None = None) -> list[dict]:
        escaped = name.replace("\\", "\\\\").replace("'", "\\'")
        clauses = [f"name = '{escaped}'", "mimeType = 'application/vnd.google-apps.folder'", "trashed = false"]
        params = {
            "q": " and ".join(clauses),
            "fields": "nextPageToken,files(id,name,mimeType,parents)",
            "pageSize": "1000",
            "includeItemsFromAllDrives": "true",
            "supportsAllDrives": "true",
        }
        if shared_drive_id:
            params.update({"corpora": "drive", "driveId": shared_drive_id})
        matches: list[dict] = []
        while True:
            _, _, data = self._request(f"{DRIVE_API}/files?{urllib.parse.urlencode(params)}")
            page = json.loads(data.decode())
            matches.extend(page.get("files", []))
            token = page.get("nextPageToken")
            if not token:
                return matches
            params["pageToken"] = token

    def create_upload_session(self, metadata: dict, total_size: int, parent_id: str | None = None) -> str:
        payload = dict(metadata)
        if parent_id:
            payload["parents"] = [parent_id]
        headers = {"Content-Type": "application/json; charset=UTF-8", "X-Upload-Content-Type": metadata.get("mimeType", "application/octet-stream"), "X-Upload-Content-Length": str(total_size)}
        status, response_headers, _ = self._request(f"{UPLOAD_API}/files?{urllib.parse.urlencode({'uploadType': 'resumable', 'supportsAllDrives': 'true'})}", method="POST", body=json.dumps(payload).encode(), headers=headers)
        if status not in {200, 201} or "Location" not in response_headers:
            raise DriveApiError(status, "Google Drive did not return a resumable session")
        return response_headers["Location"]

    def query_upload_offset(self, session_url: str, total_size: int) -> int:
        """Ask Drive which bytes a resumable session has acknowledged.

        A restart must not trust the last locally persisted chunk: the process or
        network can have failed after sending bytes but before persisting the
        server response. Drive reports the acknowledged end through a 308
        response to an empty status probe.
        """
        headers = {"Content-Length": "0", "Content-Range": f"bytes */{total_size}", "Content-Type": "application/octet-stream"}
        status, response_headers, _ = self._request(session_url, method="PUT", body=b"", headers=headers)
        if status in {200, 201}:
            return total_size
        range_header = response_headers.get("Range", "")
        return int(range_header.rsplit("-", 1)[1]) + 1 if "-" in range_header else 0

    def list_shared_drives(self, page_token: str | None = None) -> dict:
        params = {"pageSize": "100", "fields": "nextPageToken,drives(id,name,createdTime)"}
        if page_token:
            params["pageToken"] = page_token
        _, _, data = self._request(f"{DRIVE_API}/drives?{urllib.parse.urlencode(params)}")
        return json.loads(data.decode())

    def create_folder(self, name: str, parent_id: str, *, shared_drive_id: str | None = None) -> str:
        payload = {"name": name, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
        params = {"supportsAllDrives": "true"}
        if shared_drive_id:
            params["driveId"] = shared_drive_id
        status, _, data = self._request(f"{DRIVE_API}/files?{urllib.parse.urlencode(params)}", method="POST", body=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        if status not in {200, 201}:
            raise DriveApiError(status, "Google Drive did not create the folder")
        return str(json.loads(data.decode())["id"])

    def create_file(self, name: str, parent_id: str, mime_type: str = "application/octet-stream", content: bytes = b"") -> dict:
        """Create a small Drive file without routing it through the transfer queue."""
        payload = {"name": name, "mimeType": mime_type, "parents": [parent_id]}
        if content:
            boundary = "cirava-drive-file"
            body = (
                f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
                f"{json.dumps(payload)}\r\n--{boundary}\r\nContent-Type: {mime_type}\r\n\r\n"
            ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
            headers = {"Content-Type": f"multipart/related; boundary={boundary}"}
            url = f"{UPLOAD_API}/files?{urllib.parse.urlencode({'uploadType': 'multipart', 'supportsAllDrives': 'true'})}"
        else:
            body = json.dumps(payload).encode()
            headers = {"Content-Type": "application/json"}
            url = f"{DRIVE_API}/files?{urllib.parse.urlencode({'supportsAllDrives': 'true'})}"
        status, _, data = self._request(url, method="POST", body=body, headers=headers)
        if status not in {200, 201}:
            raise DriveApiError(status, "Google Drive did not create the file")
        return json.loads(data.decode())

    def find_folder(self, name: str, parent_id: str) -> str | None:
        result = self.list_files(parent_id=parent_id, query=name)
        for item in result.get("files", []):
            if item.get("name") == name and item.get("mimeType") == "application/vnd.google-apps.folder":
                return str(item["id"])
        return None

    def put_upload_chunk(self, session_url: str, data: bytes, start: int, end: int, total: int) -> int | None:
        headers = {"Content-Length": str(len(data)), "Content-Range": content_range(start, end, total), "Content-Type": "application/octet-stream"}
        status, response_headers, payload = self._request(session_url, method="PUT", body=data, headers=headers, timeout=120)
        if status in {200, 201}:
            if payload:
                try:
                    file_id = json.loads(payload.decode()).get("id")
                except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
                    file_id = None
                if file_id:
                    self.last_uploaded_file_id = str(file_id)
            return total
        if status == 308:
            range_header = response_headers.get("Range", "")
            return int(range_header.rsplit("-", 1)[1]) + 1 if "-" in range_header else start
        return end + 1

    def get_range(self, file_id: str, start: int, end: int) -> bytes:
        params = urllib.parse.urlencode({"alt": "media", "supportsAllDrives": "true"})
        _, _, data = self._request(f"{DRIVE_API}/files/{urllib.parse.quote(file_id)}?{params}", headers={"Range": f"bytes={start}-{end}"})
        return data

    def iter_range(self, file_id: str, start: int, end: int, *, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        """Stream a Drive media range in bounded buffers rather than materializing it."""
        params = urllib.parse.urlencode({"alt": "media", "supportsAllDrives": "true"})
        url = f"{DRIVE_API}/files/{urllib.parse.quote(file_id)}?{params}"
        headers = {"Authorization": f"Bearer {self._token()}", "Range": f"bytes={start}-{end}", "Accept-Encoding": "identity"}
        try:
            response = self._session().get(url, headers=headers, timeout=120, stream=True, allow_redirects=False)
        except requests.Timeout as error:
            raise TimeoutError(str(error)) from error
        except requests.ConnectionError as error:
            raise ConnectionError(str(error)) from error
        except requests.RequestException as error:
            raise OSError(str(error)) from error
        try:
            if response.status_code >= 400:
                raise DriveApiError(response.status_code, response.content.decode(errors="replace"))
            if response.status_code == 200:
                # A server may ignore Range. That is safe only for a download
                # beginning at byte zero; nonzero ranges would otherwise write
                # the start of the file into the wrong position.
                if start != 0:
                    raise IOError("Drive ignored the requested byte range")
            elif response.status_code == 206:
                content_range_header = response.headers.get("Content-Range", "")
                expected_prefix = f"bytes {start}-{end}/"
                if not content_range_header.startswith(expected_prefix):
                    raise IOError(f"Drive returned an unexpected Content-Range: {content_range_header or 'missing'}")
            else:
                raise IOError(f"Drive returned unexpected range response status {response.status_code}")
            for block in response.iter_content(chunk_size=max(64 * 1024, int(chunk_size))):
                if block:
                    yield block
        finally:
            response.close()

    def export_file(self, file_id: str, mime_type: str) -> bytes:
        params = urllib.parse.urlencode({"mimeType": mime_type})
        _, _, data = self._request(f"{DRIVE_API}/files/{urllib.parse.quote(file_id)}/export?{params}")
        return data

    def trash_file(self, file_id: str) -> None:
        """Move a Drive item to the user's trash instead of deleting it forever."""
        if not file_id:
            raise ValueError("Drive file ID is required")
        params = urllib.parse.urlencode({"supportsAllDrives": "true"})
        status, _, _ = self._request(
            f"{DRIVE_API}/files/{urllib.parse.quote(file_id)}?{params}",
            method="PATCH",
            body=json.dumps({"trashed": True}).encode(),
            headers={"Content-Type": "application/json"},
        )
        if status not in {200, 204}:
            raise DriveApiError(status, "Google Drive did not move the file to trash")

    def get_file_content(self, file_id: str, *, max_bytes: int = 2_000_000) -> bytes:
        """Read a bounded Drive file payload for the in-app text editor."""
        if not file_id:
            raise ValueError("Drive file ID is required")
        params = urllib.parse.urlencode({"alt": "media", "supportsAllDrives": "true"})
        _, _, data = self._request(f"{DRIVE_API}/files/{urllib.parse.quote(file_id)}?{params}")
        if len(data) > max_bytes:
            raise ValueError(f"This file is too large to edit in Cirava (limit {max_bytes // 1_000_000} MB)")
        return data

    def update_file_content(self, file_id: str, content: bytes, mime_type: str = "text/plain") -> dict:
        """Replace the media content of an existing Drive file."""
        if not file_id:
            raise ValueError("Drive file ID is required")
        params = urllib.parse.urlencode({"uploadType": "media", "supportsAllDrives": "true"})
        status, _, data = self._request(
            f"{UPLOAD_API}/files/{urllib.parse.quote(file_id)}?{params}",
            method="PATCH",
            body=content,
            headers={"Content-Type": mime_type or "text/plain"},
        )
        if status not in {200, 201}:
            raise DriveApiError(status, "Google Drive did not save the file")
        return json.loads(data.decode()) if data else {"id": file_id}
