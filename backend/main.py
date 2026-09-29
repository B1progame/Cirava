from __future__ import annotations

import ctypes
import base64
import json
import mimetypes
import os
import re
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterator

from cirava_backend.drive_api import DriveApiClient, DriveApiError
from cirava_backend.photos_api import GooglePhotosApiClient, GooglePhotosApiError
from cirava_backend.drive_archive import download_folder_zip
from cirava_backend.archive_compression import SevenZip, validate_compression_level
from cirava_backend.adaptive import AdaptiveConcurrencyController, AdaptiveController, AdaptiveUploadConcurrencyController, AdaptiveWorkerGate, AggregateUploadThroughput
from cirava_backend.models import TransferRecord, TransferStatus
from cirava_backend.oauth import OAuthConfig, OAuthSession, TokenManager, TokenStore
from cirava_backend.notifications import TrayNotifier
from cirava_backend.storage import TransferStore
from cirava_backend.transfer_engine import ResumableUploader, RetryPolicy, SegmentedDownloader, TokenBucket, TransferStopped, TransferTelemetry, resolve_conflict, verify_md5
from cirava_backend.updater import Updater, build_windows_update_script, is_newer_version, requires_major_installer
from cirava_backend import __version__


def app_data_dir() -> Path:
    root = Path(os.environ.get("APPDATA", Path.home() / ".config"))
    return root / "Cirava"


def bundled_frontend_path() -> Path:
    """Resolve the Vite entry point in both source and PyInstaller builds."""
    candidates = [
        Path(getattr(sys, "_MEIPASS", "")) / "dist" / "index.html",
        Path(__file__).resolve().parents[1] / "dist" / "index.html",
        Path.cwd() / "dist" / "index.html",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    searched = ", ".join(str(candidate) for candidate in candidates)
    raise FileNotFoundError(f"Cirava frontend bundle is missing. Searched: {searched}")


class CiravaApi:
    """pywebview bridge; secrets stay in the backend and never enter UI logs."""

    def __init__(self, data_dir: Path | None = None, start_workers: bool = True):
        self.data_dir = data_dir or app_data_dir()
        self.start_workers = start_workers
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.store = TransferStore(self.data_dir / "transfers.db")
        self._recover_interrupted_transfers()
        self.tokens = TokenStore(self.data_dir / "tokens.bin")
        self.client_credentials = TokenStore(self.data_dir / "client-credentials.bin")
        self.preferences = TokenStore(self.data_dir / "preferences.bin")
        self._oauth_config: OAuthConfig | None = None
        self._oauth_lock = threading.Lock()
        self._drive_client_lock = threading.Lock()
        self._drive_client: DriveApiClient | None = None
        self._drive_client_config: tuple[str, str] | None = None
        self._photos_client: GooglePhotosApiClient | None = None
        self._photos_picker_sessions: set[str] = set()
        self._photos_picker_collections: dict[str, tuple[float, list[dict]]] = {}
        self._photos_picker_lock = threading.Lock()
        self._control_lock = threading.Lock()
        self._worker_condition = threading.Condition()
        self._active_workers: set[str] = set()
        self._controls: dict[str, dict[str, object]] = {}
        self._worker_specs: dict[str, tuple[str, tuple[object, ...]]] = {}
        # Keep cross-file uploads concurrent enough to saturate fast links without
        # allowing each finished file's individual average to bias the next run.
        self._upload_adaptive = AdaptiveUploadConcurrencyController(workers=max(1, min(8, int(self._setting("upload_concurrency") or 4))))
        self._upload_adaptive_lock = threading.Lock()
        self._upload_gate = AdaptiveWorkerGate(self._upload_adaptive.workers)
        self._upload_telemetry = AggregateUploadThroughput(sample_interval=1.5)
        self._bandwidth_lock = threading.Lock()
        self._bandwidth_bucket: TokenBucket | None = None
        self._set_bandwidth_bucket_from_setting()
        self._folder_lock = threading.Lock()
        self._folder_cache: dict[tuple[str, str], str] = {}
        self._notifier = TrayNotifier()
        self._quit_callback = None

    _TRAY_ACTIVE_STATUSES = {
        TransferStatus.QUEUED,
        TransferStatus.PREPARING,
        TransferStatus.TRANSFERRING,
        TransferStatus.WAITING_FOR_NETWORK,
        TransferStatus.RATE_LIMITED,
        TransferStatus.VERIFYING,
    }

    def tray_transfer_summary(self) -> dict[str, int]:
        records = self.store.list()
        return {
            "active": sum(record.status in self._TRAY_ACTIVE_STATUSES for record in records),
            "paused": sum(record.status == TransferStatus.PAUSED for record in records),
        }

    def pause_all_transfers(self) -> dict[str, int]:
        records = [record for record in self.store.list() if record.status in self._TRAY_ACTIVE_STATUSES and not record.deferred]
        for record in records:
            self.pause_transfer(record.id)
        return {"paused": len(records)}

    def resume_all_transfers(self) -> dict[str, int]:
        records = [record for record in self.store.list() if record.status == TransferStatus.PAUSED]
        for record in records:
            self.resume_transfer(record.id)
        return {"resumed": len(records)}

    def cancel_all_transfers(self) -> dict[str, int]:
        records = [record for record in self.store.list() if record.status in self._TRAY_ACTIVE_STATUSES]
        for record in records:
            self.cancel_transfer(record.id)
        return {"cancelled": len(records)}

    def _recover_interrupted_transfers(self) -> None:
        """Make transfers left active by a previous process resumable and honest."""
        interrupted = {
            TransferStatus.QUEUED,
            TransferStatus.PREPARING,
            TransferStatus.TRANSFERRING,
            TransferStatus.WAITING_FOR_NETWORK,
            TransferStatus.RATE_LIMITED,
            TransferStatus.VERIFYING,
        }
        for record in self.store.list():
            if record.status not in interrupted:
                continue
            if record.deferred and record.status == TransferStatus.QUEUED:
                continue
            record.status = TransferStatus.PAUSED
            record.speed_bps = 0
            self.store.upsert(record)

    def _worker_started(self, transfer_id: str) -> None:
        with self._worker_condition:
            self._active_workers.add(transfer_id)

    def _worker_finished(self, transfer_id: str) -> None:
        with self._worker_condition:
            self._active_workers.discard(transfer_id)
            self._worker_condition.notify_all()

    def wait_for_transfer_idle(self, transfer_id: str, timeout: float = 30.0) -> bool:
        """Wait until a paused worker has released its I/O before restart."""
        deadline = time.monotonic() + timeout
        with self._worker_condition:
            while transfer_id in self._active_workers:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._worker_condition.wait(timeout=remaining)
        return True

    def start_background_services(self) -> None:
        self._notifier.start()

    def _notify_safely(self, heading: str, message: str) -> None:
        try:
            self._notifier.notify(heading, message)
        except Exception:
            # A tray notification is optional and must never alter transfer state.
            pass

    def _notify_transfer(self, record: TransferRecord) -> None:
        if self.load_preferences().get("showTransferNotifications", "true").lower() != "true":
            return
        if record.status == TransferStatus.FAILED:
            heading = ("Google Photos upload failed" if record.destination == "google_photos" else "Upload failed") if record.direction == "upload" else "Download failed"
            detail = record.error or "No additional error details were provided."
            self._notify_safely(heading, f"{record.filename}: {detail[:220]}")
            return
        heading = ("Google Photos upload complete" if record.destination == "google_photos" else "Upload complete") if record.direction == "upload" else "Download complete"
        self._notify_safely(heading, f"{record.filename} completed successfully")

    def boot_state(self) -> dict:
        tokens = self.tokens.load() or {}
        return {"configured": self._oauth_config is not None or bool(self._setting("client_id")), "authenticated": tokens.get("cirava_scope_version") == 4, "transfers": [record.to_dict() for record in self.store.list()]}

    def save_google_configuration(self, client_id: str, client_secret: str | None = None) -> dict:
        if ".apps.googleusercontent.com" not in client_id or len(client_id) < 30:
            raise ValueError("Enter a valid Google Desktop OAuth client ID")
        self._set_setting("client_id", client_id)
        effective_secret = client_secret or os.environ.get("CIRAVA_GOOGLE_CLIENT_SECRET", "")
        if effective_secret:
            self.client_credentials.save({"client_secret": effective_secret})
        self._oauth_config = OAuthConfig(client_id=client_id, client_secret=effective_secret or self._stored_client_secret())
        return {"ok": True, "configured": True}

    def validate_google_configuration(self, client_id: str) -> dict:
        self.save_google_configuration(client_id)
        if ".apps.googleusercontent.com" not in client_id or len(client_id) < 30:
            raise ValueError("Enter a valid Google Desktop OAuth client ID")
        checks = {"client_configuration": True, "oauth_endpoint": False, "drive_endpoint": False}
        try:
            urllib.request.urlopen("https://accounts.google.com/.well-known/openid-configuration", timeout=5).read(64)
            checks["oauth_endpoint"] = True
        except (OSError, urllib.error.URLError) as error:
            raise RuntimeError(f"Google authorization endpoint is unreachable: {error}") from error
        try:
            urllib.request.urlopen("https://www.googleapis.com/drive/v3/about?fields=user", timeout=5).read(64)
            checks["drive_endpoint"] = True
        except urllib.error.HTTPError as error:
            # 401/403 proves the API endpoint is reachable; credentials are checked during OAuth.
            if error.code in {401, 403}:
                checks["drive_endpoint"] = True
            else:
                raise RuntimeError(f"Google Drive API returned HTTP {error.code}") from error
        except (OSError, urllib.error.URLError) as error:
            raise RuntimeError(f"Google Drive API is unreachable: {error}") from error
        return {"ok": True, "checks": checks}

    def begin_google_login(self) -> dict:
        with self._oauth_lock:
            config = self._oauth_config or OAuthConfig(client_id=self._setting("client_id") or "", client_secret=os.environ.get("CIRAVA_GOOGLE_CLIENT_SECRET", "") or self._stored_client_secret())
            if not config.client_id:
                raise RuntimeError("Google configuration is missing")
            tokens = OAuthSession(config).login()
            tokens["cirava_scope_version"] = 4
            self.tokens.save(tokens)
            return {"ok": True, "authenticated": True}

    def sign_out(self) -> dict:
        self.tokens.clear()
        return {"ok": True, "authenticated": False}

    def get_account_profile(self) -> dict:
        """Load the real Google identity after OAuth without exposing tokens to the UI."""
        return self._drive().about_user()

    def load_preferences(self) -> dict:
        """Return non-secret UI preferences persisted for this Windows profile."""
        stored = self.preferences.load()
        return stored if isinstance(stored, dict) else {}

    def save_preferences(self, values: dict) -> dict:
        """Persist a bounded set of UI preferences without exposing credentials to JS."""
        allowed = {
            "theme", "transferMode", "manualChunkMiB", "manualWorkers", "manualUploadWorkers",
            "bandwidthLimit", "rememberMe", "setupComplete", "sharedDriveName", "showTransferNotifications", "testMode",
        }
        current = self.load_preferences()
        current.update({str(key): str(value) for key, value in values.items() if str(key) in allowed})
        self.preferences.save(current)
        return {"ok": True, "saved": sorted(current)}

    def get_archive_compression_status(self) -> dict:
        enabled = (self._setting("archive_compression_enabled") or "false").lower() == "true"
        seven_zip = SevenZip(self.data_dir)
        return {"enabled": enabled, "installed": seven_zip.installed(), "provider": "7-Zip", "license": "GNU LGPL; third-party software"}

    def set_archive_compression_enabled(self, enabled: bool) -> dict:
        if enabled:
            SevenZip(self.data_dir).ensure_installed()
        self._set_setting("archive_compression_enabled", "true" if enabled else "false")
        return self.get_archive_compression_status()

    def prepare_compressed_upload(self, local_paths: list[str], level: int = 5) -> dict:
        if (self._setting("archive_compression_enabled") or "false").lower() != "true":
            raise RuntimeError("Enable 7-Zip archive tools in Settings before preparing a compressed upload")
        return SevenZip(self.data_dir).create_archive(local_paths, validate_compression_level(level))

    def pick_files(self) -> list[str]:
        import webview
        if not webview.windows:
            raise RuntimeError("The Cirava desktop window is not ready yet. Try again in a moment.")
        window = webview.windows[0]
        selected = window.create_file_dialog(webview.OPEN_DIALOG, allow_multiple=True) or []
        return [str(path) for path in selected]

    def pick_folder(self) -> list[str]:
        import webview
        if not webview.windows:
            raise RuntimeError("The Cirava desktop window is not ready yet. Try again in a moment.")
        window = webview.windows[0]
        selected = window.create_file_dialog(webview.FOLDER_DIALOG) or []
        return [str(path) for path in selected]

    def get_google_photos_local_previews(self, local_paths: list[str], limit: int = 300) -> list[dict]:
        """Return bounded, local-only gallery metadata and small image previews."""
        image_extensions = {".avif", ".bmp", ".gif", ".heic", ".ico", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}
        video_extensions = {".3gp", ".3g2", ".asf", ".avi", ".divx", ".m2t", ".m2ts", ".m4v", ".mkv", ".mmv", ".mod", ".mov", ".mp4", ".mpg", ".mpeg", ".mts", ".tod", ".wmv"}
        supported = image_extensions | video_extensions
        files: list[Path] = []
        for raw_path in local_paths:
            selected = Path(raw_path)
            if selected.is_dir():
                for candidate in selected.rglob("*"):
                    if candidate.is_file() and candidate.suffix.lower() in supported:
                        files.append(candidate)
                        if len(files) >= max(1, min(int(limit), 300)):
                            break
            elif selected.is_file() and selected.suffix.lower() in supported:
                files.append(selected)
            if len(files) >= max(1, min(int(limit), 300)):
                break

        previews = []
        for path in files:
            try:
                stat = path.stat()
                preview = None
                if path.suffix.lower() in image_extensions:
                    try:
                        from PIL import Image, ImageOps
                        from io import BytesIO
                        with Image.open(path) as source:
                            image = ImageOps.exif_transpose(source)
                            image.thumbnail((360, 260))
                            image = image.convert("RGB")
                            output = BytesIO()
                            image.save(output, format="JPEG", quality=76, optimize=True)
                            preview = "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
                    except Exception:
                        # Unsupported/corrupt codecs still get a useful gallery tile.
                        preview = None
                previews.append({"path": str(path), "name": path.name, "size": stat.st_size, "modified": stat.st_mtime, "kind": "video" if path.suffix.lower() in video_extensions else "photo", "preview": preview})
            except OSError:
                continue
        return previews

    def pick_save_path(self, filename: str) -> str | None:
        import webview
        if not webview.windows:
            raise RuntimeError("The Cirava desktop window is not ready yet. Try again in a moment.")
        window = webview.windows[0]
        selected = window.create_file_dialog(webview.SAVE_DIALOG, save_filename=filename) or []
        if isinstance(selected, (str, os.PathLike)):
            return os.fspath(selected)
        return str(selected[0]) if selected else None

    def summarize_local_paths(self, local_paths: list[str]) -> dict:
        """Return bounded metadata for the upload planner without reading file contents."""
        files = 0
        folders = 0
        total_bytes = 0
        for raw_path in local_paths:
            path = Path(raw_path)
            if path.is_file():
                files += 1
                total_bytes += path.stat().st_size
            elif path.is_dir():
                folders += 1
                for item in path.rglob("*"):
                    if item.is_file():
                        files += 1
                        total_bytes += item.stat().st_size
        return {"files": files, "folders": folders, "bytes": total_bytes, "items": len(local_paths)}

    def create_test_upload(self, parent_id: str = "root", chunk_size: int = 64 * 1024 * 1024, start_immediately: bool = True) -> list[dict]:
        """Create the single supported test payload: a sparse 20 GiB local file."""
        test_dir = self.data_dir / "test-data"
        test_dir.mkdir(parents=True, exist_ok=True)
        test_file = test_dir / "cirava-speed-test-20gb.bin"
        test_size = 20 * 1024 ** 3
        if not test_file.exists() or test_file.stat().st_size != test_size:
            with test_file.open("wb") as handle:
                handle.seek(test_size - 1)
                handle.write(b"\0")
        if start_immediately:
            return self.create_upload_batch([str(test_file)], parent_id, chunk_size)
        return self.create_upload_batch([str(test_file)], parent_id, chunk_size, False)

    def list_drive_files(self, parent_id: str = "root", query: str | None = None) -> dict:
        shared_drive_id = self._setting("shared_drive_id") or None
        return self._drive().list_all_files(parent_id=parent_id, query=query, shared_drive_id=shared_drive_id)

    def list_my_drive_files(self, parent_id: str = "root", query: str | None = None) -> dict:
        return self._drive().list_all_files(parent_id=parent_id, query=query)

    def list_drive_gallery_files(self, page_token: str | None = None, query: str | None = None, pictures_only: bool = False, page_size: int = 100) -> dict:
        return self._drive().list_gallery_files(page_token=page_token, query=query, pictures_only=pictures_only, page_size=page_size)

    def start_google_photos_picker(self) -> dict:
        session = self._photos().create_picker_session()
        session_id = str(session.get("id") or "")
        picker_uri = str(session.get("pickerUri") or "")
        parsed = urllib.parse.urlparse(picker_uri)
        if not session_id or parsed.scheme != "https" or parsed.hostname not in {"photos.google.com", "photos.googleusercontent.com"}:
            raise RuntimeError("Google Photos did not return a valid Picker session")
        with self._photos_picker_lock:
            self._photos_picker_sessions.add(session_id)
        if not webbrowser.open_new_tab(picker_uri):
            with self._photos_picker_lock:
                self._photos_picker_sessions.discard(session_id)
            self._photos().delete_picker_session(session_id)
            raise RuntimeError("Could not open the Google Photos Picker in your browser")
        return {"session_id": session_id, "polling_config": session.get("pollingConfig") or {}}

    def open_google_photos(self, item_url: str | None = None) -> dict:
        """Open Google Photos in the user's system browser for manual item actions."""
        url = "https://photos.google.com/"
        if item_url:
            parsed = urllib.parse.urlparse(item_url)
            if parsed.scheme != "https" or parsed.hostname != "photos.google.com" or parsed.username or parsed.password:
                raise ValueError("Only Google Photos links can be opened here")
            url = item_url
        if not webbrowser.open_new_tab(url):
            raise RuntimeError("Could not open Google Photos in your default browser")
        return {"url": url}

    def get_google_photos_picker_selection(self, session_id: str) -> dict:
        with self._photos_picker_lock:
            if session_id not in self._photos_picker_sessions:
                raise ValueError("That Google Photos Picker session is no longer active")
        client = self._photos()
        session = client.get_picker_session(session_id)
        if not session.get("mediaItemsSet"):
            return {"ready": False, "polling_config": session.get("pollingConfig") or {}}
        raw_items = client.list_picker_media_items(session_id)
        collection_id = str(uuid.uuid4())
        with self._photos_picker_lock:
            now = time.monotonic()
            self._photos_picker_collections = {key: value for key, value in self._photos_picker_collections.items() if value[0] > now}
            self._photos_picker_collections[collection_id] = (now + 3600, raw_items)
            self._photos_picker_sessions.discard(session_id)
        try:
            client.delete_picker_session(session_id)
        except Exception:
            pass
        page = self.get_google_photos_picker_page(collection_id, 0, 100)
        page["ready"] = True
        return page

    def get_google_photos_picker_page(self, collection_id: str, offset: int = 0, limit: int = 100) -> dict:
        with self._photos_picker_lock:
            collection = self._photos_picker_collections.get(collection_id)
            if not collection or collection[0] <= time.monotonic():
                self._photos_picker_collections.pop(collection_id, None)
                raise ValueError("That Google Photos selection expired. Select the photos again to refresh it.")
            raw_items = collection[1]
        start = max(0, int(offset))
        page_end = min(len(raw_items), start + max(1, min(int(limit), 100)))
        page_items = raw_items[start:page_end]
        from concurrent.futures import ThreadPoolExecutor
        from io import BytesIO
        from PIL import Image
        previews: list[dict | None] = [None] * len(page_items)

        def make_preview(index: int, item: dict) -> tuple[int, dict]:
            media_file = item.get("mediaFile") or {}
            base_url = str(media_file.get("baseUrl") or "")
            mime_type = str(media_file.get("mimeType") or item.get("mimeType") or "application/octet-stream")
            name = str(media_file.get("filename") or item.get("filename") or f"Google Photos item {start + index + 1}")
            metadata = media_file.get("mediaFileMetadata") or item.get("mediaFileMetadata") or {}
            creation = str(metadata.get("creationTime") or "")
            preview = None
            if base_url:
                try:
                    thumbnail_mime, thumbnail = client.fetch_picker_thumbnail(base_url, video=mime_type.startswith("video/"), max_bytes=350_000)
                    with Image.open(BytesIO(thumbnail)) as image:
                        image.thumbnail((360, 260))
                        output = BytesIO()
                        image.convert("RGB").save(output, format="JPEG", quality=72, optimize=True)
                    preview = "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
                except Exception:
                    preview = None
            try:
                modified = __import__("datetime").datetime.fromisoformat(creation.replace("Z", "+00:00")).timestamp()
            except (ValueError, TypeError):
                modified = time.time()
            return index, {"id": str(item.get("id") or start + index), "name": name, "size": int(media_file.get("size") or 0), "modified": modified, "kind": "video" if mime_type.startswith("video/") else "photo", "preview": preview}

        if previews:
            with ThreadPoolExecutor(max_workers=6) as pool:
                futures = [pool.submit(make_preview, index, item) for index, item in enumerate(page_items)]
                for future in futures:
                    index, result = future.result()
                    previews[index] = result
        next_offset = page_end if page_end < len(raw_items) else None
        if next_offset is None:
            with self._photos_picker_lock:
                self._photos_picker_collections.pop(collection_id, None)
        return {"collection_id": collection_id, "items": [item for item in previews if item], "total": len(raw_items), "next_offset": next_offset}

    def cancel_google_photos_picker(self, session_id: str) -> dict:
        with self._photos_picker_lock:
            existed = session_id in self._photos_picker_sessions
            self._photos_picker_sessions.discard(session_id)
        if existed:
            try:
                self._photos().delete_picker_session(session_id)
            except Exception:
                pass
        return {"cancelled": existed}

    def find_drive_files_by_name(self, name: str) -> dict:
        if not name or not name.strip():
            raise ValueError("Drive file name is required")
        shared_drive_id = self._setting("shared_drive_id") or None
        return {"files": self._drive().find_files_by_name(name, shared_drive_id=shared_drive_id)}

    def list_trashed_drive_files(self) -> dict:
        return self._drive().list_trashed_files()

    def restore_drive_file(self, drive_file_id: str) -> dict:
        if not drive_file_id:
            raise ValueError("Drive file ID is required")
        self._drive().restore_file(drive_file_id)
        return {"id": drive_file_id, "status": "restored"}

    def empty_drive_trash(self) -> dict:
        self._drive().empty_trash()
        return {"status": "emptied"}

    def get_storage_quota(self) -> dict:
        return self._drive().storage_quota()

    def list_shared_drives(self) -> dict:
        return {"drives": self._drive().list_all_shared_drives()}

    def list_shared_drive_files(self, parent_id: str, drive_id: str) -> dict:
        if not drive_id:
            raise ValueError("Choose a shared drive first")
        return self._drive().list_all_files(parent_id=parent_id or drive_id, shared_drive_id=drive_id)

    def resolve_shared_drive_link(self, link: str) -> dict:
        return self._drive().resolve_shared_drive_link(link)

    def select_shared_drive(self, drive_id: str | None = None) -> dict:
        self._set_setting("shared_drive_id", drive_id or "")
        return {"shared_drive_id": drive_id or None}

    def create_drive_folder(self, name: str, parent_id: str = "root") -> dict:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("Folder name cannot be empty")
        shared_drive_id = self._setting("shared_drive_id") or None
        folder_id = self._drive().create_folder(clean_name, parent_id, shared_drive_id=shared_drive_id)
        return {"id": folder_id, "name": clean_name, "parent_id": parent_id}

    def create_drive_file(self, name: str, parent_id: str = "root", mime_type: str = "text/plain", content: str = "") -> dict:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError("File name cannot be empty")
        safe_mime = mime_type.strip() or "application/octet-stream"
        result = self._drive().create_file(clean_name, parent_id, safe_mime, content.encode("utf-8"))
        return {"id": result.get("id"), "name": result.get("name", clean_name), "parent_id": parent_id, "mime_type": safe_mime}

    def trash_drive_file(self, drive_file_id: str) -> dict:
        if not drive_file_id:
            raise ValueError("Drive file ID is required")
        self._drive().trash_file(drive_file_id)
        return {"id": drive_file_id, "status": "trashed"}

    def download_drive_folder_zip(self, drive_folder_id: str, local_path: str) -> dict:
        if not drive_folder_id or not local_path:
            raise ValueError("Drive folder and local ZIP destination are required")
        return download_folder_zip(self._drive(), drive_folder_id, local_path)

    def download_drive_folder_zip_by_name(self, folder_name: str, local_path: str) -> dict:
        clean_name = folder_name.strip()
        if not clean_name or not local_path:
            raise ValueError("Drive folder name and local ZIP destination are required")
        drive = self._drive()
        shared_drive_id = self._setting("shared_drive_id") or None
        matches = [str(item["id"]) for item in drive.find_folders_by_name(clean_name, shared_drive_id=shared_drive_id) if item.get("id")]
        if not matches:
            raise FileNotFoundError(f"Could not find the Drive folder {clean_name!r}")
        if len(matches) > 1:
            raise ValueError(f"More than one Drive folder is named {clean_name!r}; open the folder and try from its unique parent")
        return download_folder_zip(drive, matches[0], local_path)

    def read_drive_file(self, drive_file_id: str, mime_type: str = "text/plain", max_bytes: int = 2_000_000) -> dict:
        if not drive_file_id:
            raise ValueError("Drive file ID is required")
        payload = self._drive().get_file_content(drive_file_id, max_bytes=max(1, min(int(max_bytes), 2_000_000)))
        return {
            "id": drive_file_id,
            "content": payload.decode("utf-8", errors="replace"),
            "bytes": len(payload),
            "mime_type": mime_type or "text/plain",
        }

    def update_drive_file(self, drive_file_id: str, content: str, mime_type: str = "text/plain") -> dict:
        if not drive_file_id:
            raise ValueError("Drive file ID is required")
        safe_mime = mime_type.strip() or "text/plain"
        result = self._drive().update_file_content(drive_file_id, content.encode("utf-8"), safe_mime)
        return {"id": result.get("id", drive_file_id), "status": "saved", "bytes": len(content.encode("utf-8"))}

    def export_drive_file(self, drive_file_id: str, local_path: str, mime_type: str) -> dict:
        if not drive_file_id or not mime_type:
            raise ValueError("Drive file ID and export MIME type are required")
        destination = resolve_conflict(Path(local_path), "ask")
        if destination is None:
            return {"status": "cancelled", "local_path": local_path}
        destination.write_bytes(self._drive().export_file(drive_file_id, mime_type))
        return {"status": "completed", "local_path": str(destination), "bytes": destination.stat().st_size}

    def create_upload(self, local_path: str, parent_id: str = "root", chunk_size: int = 64 * 1024 * 1024, relative_path: str | None = None, start_immediately: bool = True, destination_drive_id: str | None = None) -> dict:
        path = Path(local_path)
        if not path.is_file():
            raise FileNotFoundError(local_path)
        transfer_id = str(uuid.uuid4())
        active_drive = destination_drive_id
        effective_parent = active_drive if parent_id == "root" and active_drive else parent_id
        record = TransferRecord(id=transfer_id, direction="upload", filename=path.name, local_path=str(path), size=path.stat().st_size, drive_parent_id=effective_parent, relative_path=relative_path, destination="google_drive", destination_drive_id=active_drive, status=TransferStatus.QUEUED, deferred=not start_immediately)
        self.store.upsert(record)
        self._worker_specs[record.id] = ("upload", (chunk_size,))
        self._controls[record.id] = {"stop": threading.Event(), "action": "run"}
        if self.start_workers and start_immediately:
            threading.Thread(target=self._upload_worker, args=(record, chunk_size), daemon=True).start()
        return record.to_dict()

    def create_upload_batch(self, local_paths: list[str], parent_id: str = "root", chunk_size: int = 64 * 1024 * 1024, start_immediately: bool = True, destination_drive_id: str | None = None) -> list[dict]:
        expanded: list[Path] = []
        relative_paths: dict[Path, str] = {}
        for raw_path in local_paths:
            path = Path(raw_path)
            if path.is_dir():
                for item in path.rglob("*"):
                    if item.is_file():
                        expanded.append(item)
                        relative_parent = item.relative_to(path).parent
                        relative_paths[item] = "" if relative_parent == Path(".") else relative_parent.as_posix()
            elif path.is_file():
                expanded.append(path)
        return [self.create_upload(str(path), parent_id, chunk_size, relative_paths.get(path) or None, start_immediately, destination_drive_id) for path in expanded]

    def create_google_photos_upload_batch(self, local_paths: list[str], start_immediately: bool = True, album_title: str | None = None) -> list[dict]:
        image_extensions = {".avif", ".bmp", ".gif", ".heic", ".ico", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".dng", ".arw", ".cr2", ".cr3", ".nef", ".nrw", ".orf", ".rw2", ".pef", ".srw"}
        video_extensions = {".3gp", ".3g2", ".asf", ".avi", ".divx", ".m2t", ".m2ts", ".m4v", ".mkv", ".mmv", ".mod", ".mov", ".mp4", ".mpg", ".mpeg", ".mts", ".tod", ".wmv"}
        paths: list[Path] = []
        for raw in local_paths:
            selected = Path(raw)
            candidates = [item for item in selected.rglob("*") if item.is_file()] if selected.is_dir() else [selected]
            paths.extend(item for item in candidates if item.suffix.lower() in image_extensions | video_extensions)
        if not paths:
            raise ValueError("Choose supported photos or videos to upload")
        validated: list[Path] = []
        for path in paths:
            if not path.is_file():
                raise FileNotFoundError(str(path))
            if path.stat().st_size <= 0:
                raise ValueError(f"{path.name} is empty and cannot be uploaded to Google Photos")
            limit = 200 * 1024 * 1024 if path.suffix.lower() in image_extensions else 20 * 1024 * 1024 * 1024
            if path.stat().st_size > limit:
                raise ValueError(f"{path.name} exceeds Google Photos' {limit // (1024 * 1024)} MB upload limit")
            validated.append(path)
        album = self._photos().create_album(album_title) if album_title is not None else None
        records = []
        for path in validated:
            record = TransferRecord(id=str(uuid.uuid4()), direction="upload", filename=path.name, local_path=str(path), size=path.stat().st_size, destination="google_photos", destination_album_id=album.get("id") if album else None, destination_album_title=album.get("title") if album else None, status=TransferStatus.QUEUED, deferred=not start_immediately)
            self.store.upsert(record)
            self._worker_specs[record.id] = ("photos_upload", (64 * 1024 * 1024,))
            self._controls[record.id] = {"stop": threading.Event(), "action": "run"}
            if self.start_workers and start_immediately:
                threading.Thread(target=self._upload_worker, args=(record, 64 * 1024 * 1024), daemon=True).start()
            records.append(record.to_dict())
        return records

    def create_download(self, drive_file_id: str, local_path: str, size: int, segment_size: int = 64 * 1024 * 1024, workers: int = 4, expected_md5: str | None = None, conflict_policy: str = "ask", start_immediately: bool = True) -> dict:
        destination = resolve_conflict(Path(local_path), conflict_policy)
        if destination is None:
            return {"status": "cancelled", "local_path": local_path, "error": "Destination exists and conflict policy is skip"}
        transfer_id = str(uuid.uuid4())
        record = TransferRecord(id=transfer_id, direction="download", filename=destination.name, local_path=str(destination), size=size, drive_file_id=drive_file_id, status=TransferStatus.QUEUED, deferred=not start_immediately)
        self.store.upsert(record)
        self._worker_specs[record.id] = ("download", (segment_size, workers, expected_md5))
        self._controls[record.id] = {"stop": threading.Event(), "action": "run"}
        if self.start_workers and start_immediately:
            threading.Thread(target=self._download_worker, args=(record, segment_size, workers, expected_md5), daemon=True).start()
        return record.to_dict()

    def create_drive_gallery_downloads(self, files: list[dict], local_directory: str, start_immediately: bool = True) -> dict:
        directory = Path(local_directory).expanduser().resolve()
        if not directory.is_dir():
            raise ValueError("Choose an existing folder for the Drive downloads")
        records = []
        skipped = 0
        for item in files:
            file_id = str(item.get("id") or "")
            mime_type = str(item.get("mimeType") or "")
            if not file_id or mime_type.startswith("application/vnd.google-apps.") or mime_type == "application/vnd.google-apps.folder":
                skipped += 1
                continue
            try:
                size = int(item.get("size") or 0)
            except (TypeError, ValueError):
                size = 0
            if size < 0:
                skipped += 1
                continue
            name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(item.get("name") or "drive-file" )).strip(" .") or "drive-file"
            destination = directory / name
            record = self.create_download(file_id, str(destination), size, expected_md5=str(item.get("md5Checksum") or "") or None, conflict_policy="keep-both", start_immediately=start_immediately)
            if record.get("id"):
                records.append(record)
        return {"records": records, "skipped": skipped}

    def pause_transfer(self, transfer_id: str) -> dict:
        return self._stop_transfer(transfer_id, "pause")

    def cancel_transfer(self, transfer_id: str) -> dict:
        return self._stop_transfer(transfer_id, "cancel")

    def resume_transfer(self, transfer_id: str) -> dict:
        record = self.store.get(transfer_id)
        if record.status in {TransferStatus.COMPLETED, TransferStatus.FAILED, TransferStatus.CANCELLED}:
            # A fast worker may reach a terminal state between the pause
            # observation and the restart request. Treat resume as idempotent
            # in that case instead of surfacing a misleading state error.
            return record.to_dict()
        return self._restart_transfer(transfer_id, {TransferStatus.PAUSED})

    def retry_transfer(self, transfer_id: str) -> dict:
        return self._restart_transfer(transfer_id, {TransferStatus.FAILED, TransferStatus.CANCELLED})

    def start_transfer(self, transfer_id: str) -> dict:
        """Start one transfer that the user deliberately left waiting in the queue."""
        with self._control_lock:
            record = self.store.get(transfer_id)
            if record.status != TransferStatus.QUEUED or not record.deferred:
                raise ValueError("This transfer is not waiting in the queue")
            spec = self._worker_specs.get(transfer_id)
            if not spec:
                spec = (("photos_upload" if record.destination == "google_photos" else "upload"), (64 * 1024 * 1024,)) if record.direction == "upload" else ("download", (64 * 1024 * 1024, 4, None))
                self._worker_specs[transfer_id] = spec
            record.deferred = False
            record.error = None
            self._controls[transfer_id] = {"stop": threading.Event(), "action": "run"}
            self.store.upsert(record)
        if self.start_workers:
            kind, args = spec
            target = self._upload_worker if kind in {"upload", "photos_upload"} else self._download_worker
            threading.Thread(target=target, args=(record, *args), daemon=True).start()
        return record.to_dict()

    def start_queued_transfers(self) -> dict:
        """Start every deferred transfer in queue order."""
        started = []
        for record in self.store.list():
            if record.status != TransferStatus.QUEUED or not record.deferred:
                continue
            try:
                started.append(self.start_transfer(record.id)["id"])
            except ValueError:
                continue
        return {"started": len(started), "ids": started}

    def _stop_transfer(self, transfer_id: str, action: str) -> dict:
        record = self.store.get(transfer_id)
        with self._control_lock:
            control = self._controls.setdefault(transfer_id, {"stop": threading.Event(), "action": action})
            control["action"] = action
            control["stop"].set()  # type: ignore[union-attr]
        record.status = TransferStatus.PAUSED if action == "pause" else TransferStatus.CANCELLED
        record.deferred = False
        self.store.upsert(record)
        return record.to_dict()

    def _restart_transfer(self, transfer_id: str, allowed: set[TransferStatus]) -> dict:
        record = self.store.get(transfer_id)
        if record.status not in allowed:
            raise ValueError(f"Cannot restart transfer in state {record.status.value}")
        spec = self._worker_specs.get(transfer_id)
        if not spec:
            spec = (("photos_upload" if record.destination == "google_photos" else "upload"), (64 * 1024 * 1024,)) if record.direction == "upload" else ("download", (64 * 1024 * 1024, 4, None))
            self._worker_specs[transfer_id] = spec
        with self._control_lock:
            self._controls[transfer_id] = {"stop": threading.Event(), "action": "run"}
        record.status = TransferStatus.QUEUED
        record.deferred = False
        record.error = None
        self.store.upsert(record)
        if self.start_workers:
            kind, args = spec
            target = self._upload_worker if kind in {"upload", "photos_upload"} else self._download_worker
            threading.Thread(target=target, args=(record, *args), daemon=True).start()
        return record.to_dict()

    def _should_continue(self, transfer_id: str) -> bool:
        with self._control_lock:
            control = self._controls.get(transfer_id)
            return bool(control and not control["stop"].is_set())  # type: ignore[union-attr]

    def _stop_action(self, transfer_id: str) -> str:
        with self._control_lock:
            return str(self._controls.get(transfer_id, {}).get("action", "cancel"))

    def _ensure_drive_path(self, client: DriveApiClient, parent_id: str, relative_path: str | None, shared_drive_id: str | None = None) -> str:
        parent = parent_id
        if not relative_path:
            return parent
        with self._folder_lock:
            for folder_name in Path(relative_path).parts:
                if not folder_name or folder_name == ".":
                    continue
                key = (parent, folder_name)
                if key not in self._folder_cache:
                    existing = client.find_folder(folder_name, parent, shared_drive_id=shared_drive_id) if shared_drive_id else client.find_folder(folder_name, parent)
                    self._folder_cache[key] = existing or (client.create_folder(folder_name, parent, shared_drive_id=shared_drive_id) if shared_drive_id else client.create_folder(folder_name, parent))
                parent = self._folder_cache[key]
        return parent

    def list_transfers(self) -> list[dict]:
        return [record.to_dict() for record in self.store.list()]

    def set_transfer_priority(self, transfer_id: str, priority: str = "normal") -> dict:
        self.store.set_priority(transfer_id, priority)
        return self.store.get(transfer_id).to_dict()

    def reorder_transfers(self, transfer_ids: list[str]) -> dict:
        self.store.reorder([str(transfer_id) for transfer_id in transfer_ids])
        return {"ok": True, "count": len(transfer_ids)}

    def clear_history(self) -> dict:
        return {"cleared": self.store.clear_finished()}

    def get_transfer_limit(self) -> dict:
        return {"mbps": int(self._setting("bandwidth_limit_mbps") or 0)}

    def set_transfer_limit(self, mbps: int = 0) -> dict:
        value = max(0, min(100000, int(mbps)))
        self._set_setting("bandwidth_limit_mbps", str(value))
        with self._bandwidth_lock:
            self._bandwidth_bucket = TokenBucket(value * 125000) if value else None
        return {"mbps": value}

    def measure_connection_speed(self, sample_bytes: int = 5_000_000) -> dict:
        """Measure a short real download sample without changing transfer state."""
        size = max(1_000_000, min(20_000_000, int(sample_bytes)))
        url = f"https://speed.cloudflare.com/__down?bytes={size}"
        started = time.perf_counter()
        received = 0
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Cirava-Speed-Test/0.1"})
            with urllib.request.urlopen(request, timeout=15) as response:
                while received < size:
                    chunk = response.read(min(256 * 1024, size - received))
                    if not chunk:
                        break
                    received += len(chunk)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise RuntimeError(f"Speed test could not reach the measurement service: {error}") from error
        elapsed = max(time.perf_counter() - started, 0.001)
        bits_per_second = received * 8 / elapsed
        return {"bytes": received, "seconds": round(elapsed, 2), "mbps": round(bits_per_second / 1_000_000, 1), "mib_per_second": round(received / elapsed / (1024 * 1024), 1)}

    def get_upload_concurrency(self) -> dict:
        return {"workers": max(1, min(8, int(self._setting("upload_concurrency") or 4)))}

    def set_upload_concurrency(self, workers: int = 4) -> dict:
        value = max(1, min(8, int(workers)))
        self._set_setting("upload_concurrency", str(value))
        with self._upload_adaptive_lock:
            self._upload_adaptive = AdaptiveUploadConcurrencyController(workers=value)
            self._upload_gate.resize(value)
        return {"workers": value}

    def remove_transfer(self, transfer_id: str) -> dict:
        self.store.delete_finished(transfer_id)
        return {"removed": transfer_id}

    def reveal_local(self, transfer_id: str) -> dict:
        record = self.store.get(transfer_id)
        path = Path(record.local_path)
        if not path.exists():
            raise FileNotFoundError(record.local_path)
        if os.name == "nt":
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
        return {"opened": str(path)}

    def open_drive_file(self, transfer_id: str) -> dict:
        record = self.store.get(transfer_id)
        if not record.drive_file_id:
            raise ValueError("This transfer has no Drive file link yet")
        url = f"https://drive.google.com/open?id={record.drive_file_id}"
        webbrowser.open(url)
        return {"url": url}

    def check_for_update(self, manifest_url: str, current_version: str | None = None) -> dict:
        current = current_version or __version__
        manifest = Updater(self.data_dir / "updates").fetch_manifest(manifest_url)
        installer_required = requires_major_installer(manifest.version, current)
        return {"available": is_newer_version(manifest.version, current), "version": manifest.version, "current_version": current, "release_notes": list(manifest.release_notes), "release_notes_markdown": manifest.release_notes_markdown, "update_type": "installer" if installer_required else "in_place", "in_place_available": bool(manifest.app_url and manifest.app_sha256)}

    def stage_update(self, manifest_url: str, current_version: str | None = None) -> dict:
        current = current_version or __version__
        manifest = Updater(self.data_dir / "updates").fetch_manifest(manifest_url)
        if not is_newer_version(manifest.version, current):
            raise ValueError(f"Manifest version {manifest.version} is not newer than Cirava {current}")
        installer_required = requires_major_installer(manifest.version, current)
        updater = Updater(self.data_dir / "updates")
        if installer_required:
            staged = updater.download_and_stage(manifest)
            update_type = "installer"
        else:
            staged = updater.download_app_and_stage(manifest)
            update_type = "in_place"
        return {"staged": True, "path": str(staged), "version": manifest.version, "update_type": update_type}

    def restart_staged_update(self, staged_path: str, update_type: str = "installer") -> dict:
        updates_dir = (self.data_dir / "updates").resolve()
        candidate = Path(staged_path).resolve()
        if candidate.suffix.lower() != ".exe" or updates_dir not in candidate.parents or not candidate.is_file():
            raise ValueError("Staged update path is not a valid Cirava update executable")
        if update_type == "installer":
            subprocess.Popen([str(candidate), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"], cwd=str(candidate.parent))
            return {"started": True, "path": str(candidate), "update_type": update_type}
        if update_type != "in_place":
            raise ValueError("Unknown update type")
        if not getattr(sys, "frozen", False):
            raise RuntimeError("In-place updates are only available in the installed Cirava app")
        target = Path(sys.executable).resolve()
        if target.name.lower() != "cirava.exe" or target == candidate:
            raise RuntimeError("The current Cirava executable path is not safe to update")
        import base64
        import hashlib
        with candidate.open("rb") as update_file:
            expected_sha256 = hashlib.file_digest(update_file, "sha256").hexdigest()
        script = build_windows_update_script(
            os.getpid(), str(candidate), str(target), str(updates_dir / "update-apply.log"), expected_sha256
        )
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        powershell = str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe")
        args = [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded]
        program_files = (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        if any(str(target).casefold().startswith(str(folder).casefold() + "\\") for folder in program_files if folder):
            subprocess.Popen(["powershell.exe", "-NoProfile", "-Command", "Start-Process", "-FilePath", powershell, "-ArgumentList", "'-NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand " + encoded + "'", "-Verb", "RunAs"], cwd=str(candidate.parent))
        else:
            subprocess.Popen(args, cwd=str(candidate.parent), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return {"started": True, "path": str(candidate), "update_type": update_type}

    def request_quit(self) -> None:
        if callable(self._quit_callback):
            self._quit_callback()

    def _upload_worker(self, record: TransferRecord, chunk_size: int) -> None:
        self._worker_started(record.id)
        acquired = False
        try:
            acquired = self._upload_gate.acquire(should_continue=lambda: self._should_continue(record.id))
            if not acquired:
                record.status = TransferStatus.PAUSED if self._stop_action(record.id) == "pause" else TransferStatus.CANCELLED
                self.store.upsert(record)
                return
            self._upload_telemetry.begin(record.id, record.bytes_transferred)
            self._upload_worker_impl(record, chunk_size)
        finally:
            if acquired and record.status == TransferStatus.FAILED:
                self._adjust_upload_concurrency(error=True, rate_limited=record.rate_limit_events > 0)
            if acquired:
                self._upload_telemetry.finish(record.id)
                self._upload_gate.release()
            self._worker_finished(record.id)

    def _adjust_upload_concurrency(self, *, error: bool = False, rate_limited: bool = False) -> int:
        if self._upload_gate.active < 2 and not error and not rate_limited:
            return self._upload_gate.workers
        aggregate_bps = self._upload_telemetry.last_throughput_bps
        with self._upload_adaptive_lock:
            previous = self._upload_adaptive.workers
            next_workers = self._upload_adaptive.observe(
                aggregate_throughput_bps=aggregate_bps,
                error=error,
                rate_limited=rate_limited,
            )
            if next_workers != previous:
                self._upload_gate.resize(next_workers)
                self._set_setting("upload_concurrency", str(next_workers))
            return next_workers

    def _upload_worker_impl(self, record: TransferRecord, chunk_size: int) -> None:
        try:
            record.mark_started()
            record.status = TransferStatus.PREPARING
            self.store.upsert(record)
            if not self._should_continue(record.id):
                raise TransferStopped()
            if record.destination == "google_photos":
                self._photos_upload_worker_impl(record, chunk_size)
                return
            client = self._drive()
            parent_id = self._ensure_drive_path(client, record.drive_parent_id or "root", record.relative_path, record.destination_drive_id)
            telemetry = TransferTelemetry()
            mime_type = mimetypes.guess_type(record.filename)[0] or "application/octet-stream"
            def retry_observed(attempt: int, delay: float, error: Exception) -> None:
                self._record_retry(record, attempt, delay, error)
                status = getattr(error, "status", None)
                is_rate_limited = status in {429, 403}
                controller.observe(throughput_bps=0, latency_ms=0, error_rate=1, rate_limited=is_rate_limited)
                self._adjust_upload_concurrency(error=True, rate_limited=is_rate_limited)
            controller = AdaptiveController(chunk_size=chunk_size, min_chunk=min(16 * 1024 * 1024, chunk_size), max_chunk=128 * 1024 * 1024)
            def upload_progress(done: int, _total: int, _attempt: int) -> None:
                record.status = TransferStatus.TRANSFERRING
                speed, average, peak = telemetry.observe(done)
                record.bytes_transferred = done
                record.speed_bps = speed
                record.average_speed_bps = average
                record.peak_speed_bps = peak
                aggregate_bps = self._upload_telemetry.observe(record.id, done)
                if aggregate_bps is not None and self._upload_gate.active >= 2:
                    self._adjust_upload_concurrency()
                self.store.update_progress(record.id, bytes_transferred=done, speed_bps=speed, average_speed_bps=average, peak_speed_bps=peak)
            def put_chunk(data: bytes, start: int, end: int, total: int) -> int | None:
                self._throttle(len(data))
                request_started = time.monotonic()
                result = client.put_upload_chunk(session, data, start, end, total)
                elapsed = max(time.monotonic() - request_started, 1e-6)
                controller.observe(throughput_bps=int(len(data) / elapsed), latency_ms=elapsed * 1000, error_rate=0, rate_limited=False)
                return result
            uploaded_file_id = None
            small_file_limit = 5 * 1024 * 1024
            create_small_file = getattr(client, "create_file", None)
            if record.size <= small_file_limit and not record.upload_session_url and record.bytes_transferred == 0 and callable(create_small_file):
                source_path = Path(record.local_path)
                if source_path.stat().st_size != record.size:
                    raise IOError("The selected file changed before upload; select it again to avoid uploading partial data")
                with source_path.open("rb") as source:
                    content = source.read(small_file_limit + 1)
                if len(content) != record.size:
                    raise IOError("The selected file changed while it was being prepared for upload")
                record.status = TransferStatus.TRANSFERRING
                self.store.upsert(record)
                if not self._should_continue(record.id):
                    raise TransferStopped()
                self._throttle(len(content))
                created = create_small_file(record.filename, parent_id, mime_type, content)
                uploaded_file_id = str(created.get("id") or "")
                if not uploaded_file_id:
                    raise RuntimeError("Google Drive did not return the ID for the uploaded file")
                upload_progress(record.size, record.size, 1)
            else:
                session = record.upload_session_url or client.create_upload_session({"name": record.filename, "mimeType": mime_type}, record.size, parent_id)
                record.upload_session_url = session
                if record.upload_session_url and record.bytes_transferred and callable(getattr(client, "query_upload_offset", None)):
                    record.bytes_transferred = client.query_upload_offset(record.upload_session_url, record.size)
                self.store.upsert(record)
                record.status = TransferStatus.TRANSFERRING
                self.store.upsert(record)
                if not self._should_continue(record.id):
                    raise TransferStopped()
                ResumableUploader(should_continue=lambda: self._should_continue(record.id), retryable_error=self._is_retryable_error, retry_observed=retry_observed).upload(Path(record.local_path), chunk_size, put_chunk, upload_progress, next_chunk_size=lambda: controller.chunk_size, initial_offset=record.bytes_transferred)
            record.bytes_transferred = record.size
            uploaded_file_id = uploaded_file_id or getattr(client, "last_uploaded_file_id", None)
            if uploaded_file_id:
                record.drive_file_id = uploaded_file_id
            record.upload_session_url = None
            record.status = TransferStatus.COMPLETED
            self.store.upsert(record)
            self._notify_transfer(record)
        except TransferStopped:
            record.status = TransferStatus.PAUSED if self._stop_action(record.id) == "pause" else TransferStatus.CANCELLED
            self.store.upsert(record)
        except Exception as error:  # surface a safe, human-readable message through state only
            record.status = TransferStatus.FAILED
            if isinstance(error, DriveApiError) and error.status == 404 and record.upload_session_url:
                record.upload_session_url = None
                record.bytes_transferred = 0
                record.error = "Drive resumable session expired; retry to start a fresh session"
            else:
                record.error = str(error)[:500]
            self.store.upsert(record)
            self._notify_transfer(record)

    def _download_worker(self, record: TransferRecord, segment_size: int, workers: int, expected_md5: str | None) -> None:
        self._worker_started(record.id)
        part_path = Path(record.local_path + ".part")
        try:
            if not self._should_continue(record.id):
                record.status = TransferStatus.PAUSED if self._stop_action(record.id) == "pause" else TransferStatus.CANCELLED
                self.store.upsert(record)
                return
            record.mark_started()
            record.status = TransferStatus.TRANSFERRING
            self.store.upsert(record)
            client = self._drive()
            concurrency = AdaptiveConcurrencyController(workers=workers)
            downloader = SegmentedDownloader(
                part_path,
                file_size=record.size,
                segment_size=segment_size,
                workers=workers,
                should_continue=lambda: self._should_continue(record.id),
                worker_provider=lambda: concurrency.workers,
                wave_observed=lambda amount, elapsed, error, rate_limited: concurrency.observe(
                    throughput_bps=int(amount / max(elapsed, 1e-6)),
                    error=error,
                    rate_limited=rate_limited,
                ),
                retryable_error=self._is_retryable_error,
                retry_observed=lambda attempt, delay, error: self._record_retry(record, attempt, delay, error),
            )
            telemetry = TransferTelemetry()
            already_downloaded = downloader.range_map.completed_bytes
            def download_progress(done: int, _total: int) -> None:
                total_done = min(record.size, already_downloaded + done)
                speed, average, peak = telemetry.observe(total_done)
                record.bytes_transferred = total_done
                record.speed_bps = speed
                record.average_speed_bps = average
                record.peak_speed_bps = peak
                self.store.update_progress(record.id, bytes_transferred=total_done, speed_bps=speed, average_speed_bps=average, peak_speed_bps=peak)
            def disk_progress(amount: int, elapsed: float) -> None:
                current = self.store.get(record.id)
                record.bytes_transferred = current.bytes_transferred
                record.speed_bps = current.speed_bps
                record.disk_write_bps = int(amount / elapsed)
                self.store.update_progress(record.id, bytes_transferred=record.bytes_transferred, speed_bps=record.speed_bps, disk_write_bps=record.disk_write_bps)
            def get_range(start: int, end: int) -> bytes | Iterator[bytes]:
                stream_range = getattr(client, "iter_range", None)
                if callable(stream_range):
                    def throttled_chunks():
                        for chunk in stream_range(record.drive_file_id or "", start, end):
                            self._throttle(len(chunk))
                            yield chunk
                    return throttled_chunks()
                self._throttle(end - start + 1)
                return client.get_range(record.drive_file_id or "", start, end)
            downloader.download(get_range, download_progress, disk_progress)
            downloader.finalize(Path(record.local_path))
            record.status = TransferStatus.VERIFYING
            self.store.upsert(record)
            if expected_md5 and not verify_md5(Path(record.local_path), expected_md5):
                raise IOError("Downloaded file failed Drive checksum verification")
            record.bytes_transferred = record.size
            record.status = TransferStatus.COMPLETED
            self.store.upsert(record)
            if (self._setting("archive_compression_enabled") or "false").lower() == "true":
                try:
                    extracted = SevenZip(self.data_dir).extract_cirava_archive(Path(record.local_path))
                    if extracted:
                        self._notify_safely("Cirava archive extracted", f"Opened extracted files at {extracted}")
                except Exception as error:
                    self._notify_safely("Archive downloaded", f"Automatic extraction could not finish: {str(error)[:180]}")
            self._notify_transfer(record)
        except TransferStopped:
            record.status = TransferStatus.PAUSED if self._stop_action(record.id) == "pause" else TransferStatus.CANCELLED
            self.store.upsert(record)
        except Exception as error:
            record.status = TransferStatus.FAILED
            record.error = str(error)[:500]
            self.store.upsert(record)
            self._notify_transfer(record)
        finally:
            self._worker_finished(record.id)

    def _drive(self) -> DriveApiClient:
        tokens = self.tokens.load()
        if not tokens or not tokens.get("access_token"):
            raise RuntimeError("Sign in with Google before starting a transfer")
        client_id = self._setting("client_id") or ""
        client_secret = os.environ.get("CIRAVA_GOOGLE_CLIENT_SECRET", "") or self._stored_client_secret()
        config = (client_id, client_secret)
        with self._drive_client_lock:
            if self._drive_client is None or self._drive_client_config != config:
                token_manager = TokenManager(self.tokens, client_id=client_id, client_secret=client_secret)
                self._drive_client = DriveApiClient(token_manager.access_token)
                self._drive_client_config = config
            return self._drive_client

    def _photos(self) -> GooglePhotosApiClient:
        tokens = self.tokens.load()
        if not tokens or not tokens.get("access_token"):
            raise RuntimeError("Sign in with Google before uploading to Google Photos")
        if self._photos_client is None:
            client_id = self._setting("client_id") or ""
            client_secret = os.environ.get("CIRAVA_GOOGLE_CLIENT_SECRET", "") or self._stored_client_secret()
            manager = TokenManager(self.tokens, client_id=client_id, client_secret=client_secret)
            self._photos_client = GooglePhotosApiClient(manager.access_token)
        return self._photos_client

    def _photos_upload_worker_impl(self, record: TransferRecord, chunk_size: int) -> None:
        client = self._photos()
        source = Path(record.local_path)
        if not source.is_file() or source.stat().st_size != record.size:
            raise IOError("The selected media file changed before upload; select it again to avoid uploading partial data")
        mime_type = mimetypes.guess_type(record.filename)[0] or "application/octet-stream"
        telemetry = TransferTelemetry()
        if not record.destination_item_token:
            def retry_observed(attempt: int, delay: float, error: Exception) -> None:
                self._record_retry(record, attempt, delay, error)

            def progress(done: int, total: int, _attempt: int) -> None:
                record.status = TransferStatus.TRANSFERRING
                record.bytes_transferred = done
                speed, average, peak = telemetry.observe(done)
                record.speed_bps, record.average_speed_bps, record.peak_speed_bps = speed, average, peak
                self.store.update_progress(record.id, bytes_transferred=done, speed_bps=speed, average_speed_bps=average, peak_speed_bps=peak)

            def retry_delay(delay: float) -> None:
                minimum = 30 if record.last_http_status == 429 else 0
                deadline = time.monotonic() + max(delay, minimum)
                while time.monotonic() < deadline:
                    if not self._should_continue(record.id):
                        raise TransferStopped()
                    time.sleep(min(0.25, deadline - time.monotonic()))

            for session_attempt in range(1, 4):
                if not record.upload_session_url:
                    session, granularity = client.create_upload_session(mime_type, record.size)
                    record.upload_session_url = session
                    record.upload_chunk_granularity = granularity
                    record.bytes_transferred = 0
                else:
                    session = record.upload_session_url
                    granularity = record.upload_chunk_granularity or 256 * 1024
                    try:
                        record.bytes_transferred = client.query_upload_offset(session)
                    except GooglePhotosApiError as error:
                        if error.status not in {404, 410}:
                            raise
                        session, granularity = client.create_upload_session(mime_type, record.size)
                        record.upload_session_url = session
                        record.upload_chunk_granularity = granularity
                        record.bytes_transferred = 0
                    if record.bytes_transferred >= record.size:
                        # Google may acknowledge the final bytes even when its
                        # response containing the upload token was lost.
                        session, granularity = client.create_upload_session(mime_type, record.size)
                        record.upload_session_url = session
                        record.upload_chunk_granularity = granularity
                        record.bytes_transferred = 0
                if granularity <= 0:
                    raise GooglePhotosApiError(502, "Google Photos returned an invalid upload chunk size")
                chunk_size = max(granularity, (chunk_size // granularity) * granularity)
                self.store.upsert(record)

                def put_chunk(data: bytes, start: int, end: int, _total: int) -> int:
                    self._throttle(len(data))
                    final = end + 1 == record.size
                    try:
                        _, response_headers, response = client.upload_chunk(session, data, start, final=final)
                        if final:
                            token = response.decode(errors="strict").strip()
                            if not token:
                                raise GooglePhotosApiError(502, "Google Photos finished uploading without returning an upload token")
                            record.destination_item_token = token
                            self.store.upsert(record)
                        received = response_headers.get("X-Goog-Upload-Size-Received") or response_headers.get("x-goog-upload-size-received")
                        return int(received) if received else end + 1
                    except GooglePhotosApiError as error:
                        if error.status not in {408, 429, 500, 502, 503, 504}:
                            raise
                        acknowledged = client.query_upload_offset(session)
                        if acknowledged > start:
                            return acknowledged
                        raise
                    except (OSError, TimeoutError, ConnectionError):
                        acknowledged = client.query_upload_offset(session)
                        if acknowledged > start:
                            return acknowledged
                        raise

                record.status = TransferStatus.TRANSFERRING
                self.store.upsert(record)
                ResumableUploader(
                    retry_policy=RetryPolicy(), sleep=retry_delay,
                    should_continue=lambda: self._should_continue(record.id),
                    retryable_error=lambda error: self._is_retryable_error(error) or isinstance(error, GooglePhotosApiError) and error.status in {408, 429, 500, 502, 503, 504},
                    retry_observed=retry_observed,
                ).upload(source, chunk_size, put_chunk, progress, initial_offset=record.bytes_transferred)
                if record.destination_item_token:
                    break
                if record.bytes_transferred < record.size:
                    raise GooglePhotosApiError(502, "Google Photos stopped before returning an upload token")
                if session_attempt == 3:
                    raise GooglePhotosApiError(502, "Google Photos did not return an upload token after restarting the final chunk")
                # Force the next pass to start a clean session after an
                # acknowledged final chunk whose token response was lost.
                record.upload_session_url = None
                record.upload_chunk_granularity = None
                record.bytes_transferred = 0
                self.store.upsert(record)
        if not self._should_continue(record.id):
            raise TransferStopped()
        result = client.create_media_items([(record.filename, record.destination_item_token)], album_id=record.destination_album_id)
        if not result or not (result[0].get("mediaItem") or {}).get("id"):
            raise GooglePhotosApiError(502, "Google Photos did not confirm this media item")
        record.destination_item_token = None
        record.upload_session_url = None
        record.upload_chunk_granularity = None
        record.bytes_transferred = record.size
        record.status = TransferStatus.COMPLETED
        self.store.upsert(record)
        self._notify_transfer(record)

    def _stored_client_secret(self) -> str:
        try:
            return str((self.client_credentials.load() or {}).get("client_secret", ""))
        except (OSError, ValueError, TypeError):
            return ""

    def _record_retry(self, record: TransferRecord, attempt: int, delay: float, error: Exception) -> None:
        status = getattr(error, "status", None)
        record.retry_count += 1
        record.last_retry_delay_seconds = delay
        record.last_http_status = int(status) if isinstance(status, int) else None
        if status in {429, 403}:
            record.rate_limit_events += 1
            record.status = TransferStatus.RATE_LIMITED
        elif isinstance(error, (OSError, TimeoutError, ConnectionError)):
            record.status = TransferStatus.WAITING_FOR_NETWORK
        record.error = f"Retry {record.retry_count} in {delay:.1f}s"
        self.store.upsert(record)

    @staticmethod
    def _is_retryable_error(error: Exception) -> bool:
        if isinstance(error, (OSError, TimeoutError, ConnectionError)):
            return True
        status = getattr(error, "status", None)
        if status in {429, 500, 502, 503, 504}:
            return True
        return status == 403 and any(token in str(error).lower() for token in ("ratelimit", "rate limit", "userratelimit", "backenderror"))

    def _set_bandwidth_bucket_from_setting(self) -> None:
        value = int(self._setting("bandwidth_limit_mbps") or 0)
        self._bandwidth_bucket = TokenBucket(value * 125000) if value else None

    def _throttle(self, amount: int) -> None:
        with self._bandwidth_lock:
            bucket = self._bandwidth_bucket
            delay = bucket.consume(amount, now=time.monotonic()) if bucket else 0.0
        if delay > 0:
            time.sleep(delay)

    def _setting(self, key: str) -> str | None:
        settings = self.data_dir / "settings.json"
        if not settings.exists():
            return None
        return json.loads(settings.read_text(encoding="utf-8")).get(key)

    def _set_setting(self, key: str, value: str) -> None:
        settings = self.data_dir / "settings.json"
        data = json.loads(settings.read_text(encoding="utf-8")) if settings.exists() else {}
        data[key] = value
        settings.write_text(json.dumps(data), encoding="utf-8")


_single_instance_mutex = None
_SINGLE_INSTANCE_NAME = "Local\\Cirava.Desktop.SingleInstance"


def _claim_single_instance() -> bool:
    """Atomically keep one process and focus it when another launch is attempted."""
    global _single_instance_mutex
    if os.name != "nt":
        return True
    try:
        # Use the Win32 API directly instead of relying on pywin32's thread
        # last-error wrapper. On some packaged builds CreateMutex succeeded but
        # win32api.GetLastError() returned 0, allowing two hidden Cirava shells
        # (and two tray instances) to coexist.
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.GetLastError.restype = ctypes.c_uint32
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        mutex = kernel32.CreateMutexW(None, True, _SINGLE_INSTANCE_NAME)
        if not mutex:
            return False
        if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
            hwnd = win32gui_find_window("Cirava")
            if hwnd:
                import win32con
                import win32gui
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
            try:
                kernel32.CloseHandle(mutex)
            except Exception:
                pass
            return False
        # Keep the handle alive globally for the entire process lifetime;
        # releasing it would allow another copy in.
        _single_instance_mutex = mutex
        return True
    except Exception:
        # A Windows build must fail closed if it cannot claim the mutex. The old
        # behavior returned True here, which allowed duplicate desktop shells.
        return False


def win32gui_find_window(title: str) -> int | None:
    try:
        import win32gui
        return win32gui.FindWindow(None, title)
    except Exception:
        return None

def run() -> None:
    import webview

    if not _claim_single_instance():
        return

    api = CiravaApi()
    frontend = bundled_frontend_path()
    window = webview.create_window("Cirava", str(frontend), js_api=api, width=1320, height=877, min_size=(1100, 700), text_select=False)
    state = {"quitting": False}
    api._notifier.set_activate_callback(lambda: _restore_window(window))

    def quit_app() -> None:
        state["quitting"] = True
        api._notifier.stop()
        destroy = getattr(window, "destroy", None)
        if callable(destroy):
            destroy()

    api._quit_callback = quit_app
    api._notifier.set_quit_callback(quit_app)

    def navigate_from_tray(page: str) -> None:
        _restore_window(window)
        try:
            window.evaluate_js(
                "window.dispatchEvent(new CustomEvent('cirava:tray-navigate', {detail: {page: "
                + json.dumps(str(page))
                + "}}))"
            )
        except Exception:
            pass

    def control_transfers_from_tray(action: str) -> None:
        methods = {
            "pause": (api.pause_all_transfers, "Transfers paused", "paused"),
            "resume": (api.resume_all_transfers, "Transfers resumed", "resumed"),
            "cancel": (api.cancel_all_transfers, "Transfers stopped", "cancelled"),
        }
        method, heading, result_key = methods[action]
        result = method()
        count = int(result.get(result_key, 0))
        api._notifier.notify(heading, f"{count} transfer(s) {result_key}.")

    api._notifier.set_navigation_callback(navigate_from_tray)
    api._notifier.set_transfer_callbacks(control_transfers_from_tray, api.tray_transfer_summary)

    update_ready_file = next(
        (arg.split("=", 1)[1] for arg in sys.argv[1:] if arg.startswith("--cirava-update-ready-file=")),
        None,
    )
    if update_ready_file is None and "--cirava-update-ready-file" in sys.argv[1:]:
        index = sys.argv.index("--cirava-update-ready-file")
        if index + 1 < len(sys.argv):
            update_ready_file = sys.argv[index + 1]
    if update_ready_file:
        def confirm_update_startup(*_args: object) -> None:
            """Tell the handoff process the new executable rendered its window."""
            try:
                ready_path = Path(update_ready_file)
                ready_path.parent.mkdir(parents=True, exist_ok=True)
                ready_path.write_text("ready", encoding="utf-8")
            except OSError:
                # The updater will time out and restore the previous executable.
                pass

        window.events.loaded += confirm_update_startup

    def close_to_tray() -> bool:
        moving_statuses = {TransferStatus.QUEUED, TransferStatus.PREPARING, TransferStatus.TRANSFERRING}
        try:
            active_count = sum(record.status in moving_statuses for record in api.store.list())
        except Exception:
            active_count = 0
        return _close_to_tray(window, state, api._notifier, active_count)

    window.events.closing += close_to_tray
    api.start_background_services()
    webview.start(gui="edgechromium")


def _restore_window(window: object) -> None:
    """Bring the pywebview window forward after a tray click, if supported."""
    for method_name in ("restore", "show", "bring_to_front"):
        method = getattr(window, method_name, None)
        if callable(method):
            try:
                method()
            except Exception:
                continue


def _close_to_tray(window: object, state: dict[str, bool] | None = None, notifier: object | None = None, active_transfer_count: int = 0) -> bool:
    """Hide the desktop window instead of terminating Cirava on close."""
    if state and state.get("quitting"):
        return True
    # Do not leave an invisible process behind when Windows rejected the tray
    # registration. The user must still be able to close the app normally.
    if notifier is not None and not getattr(notifier, "registered", False):
        return True
    hide = getattr(window, "hide", None)
    if callable(hide):
        try:
            hide()
            if notifier is not None:
                if active_transfer_count:
                    noun = "transfer is" if active_transfer_count == 1 else "transfers are"
                    message = f"{active_transfer_count} {noun} continuing in the background. Open Cirava from the system tray to check progress."
                else:
                    message = "Cirava is still running in the system tray. Transfers continue in the background."
                try:
                    notifier.notify("Cirava is still running", message)
                except Exception:
                    pass
            return False
        except Exception:
            pass
    return True


if __name__ == "__main__":
    run()
