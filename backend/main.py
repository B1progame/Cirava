from __future__ import annotations

import ctypes
import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
import urllib.error
import urllib.request
from pathlib import Path

from cirava_backend.drive_api import DriveApiClient, DriveApiError
from cirava_backend.adaptive import AdaptiveConcurrencyController, AdaptiveController, AdaptiveUploadConcurrencyController
from cirava_backend.models import TransferRecord, TransferStatus
from cirava_backend.oauth import OAuthConfig, OAuthSession, TokenManager, TokenStore
from cirava_backend.notifications import TrayNotifier
from cirava_backend.storage import TransferStore
from cirava_backend.transfer_engine import ResumableUploader, SegmentedDownloader, TokenBucket, TransferStopped, TransferTelemetry, resolve_conflict, verify_md5
from cirava_backend.updater import Updater, is_newer_version
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
        self.tokens = TokenStore(self.data_dir / "tokens.bin")
        self.client_credentials = TokenStore(self.data_dir / "client-credentials.bin")
        self.preferences = TokenStore(self.data_dir / "preferences.bin")
        self._oauth_config: OAuthConfig | None = None
        self._oauth_lock = threading.Lock()
        self._control_lock = threading.Lock()
        self._worker_condition = threading.Condition()
        self._active_workers: set[str] = set()
        self._controls: dict[str, dict[str, object]] = {}
        self._worker_specs: dict[str, tuple[str, tuple[object, ...]]] = {}
        # Keep cross-file uploads concurrent enough to saturate fast links without
        # creating an unbounded thread/request storm for large folder batches.
        self._upload_adaptive = AdaptiveUploadConcurrencyController(workers=max(1, min(8, int(self._setting("upload_concurrency") or 4))))
        self._upload_slots = threading.Semaphore(self._upload_adaptive.workers)
        self._bandwidth_lock = threading.Lock()
        self._bandwidth_bucket: TokenBucket | None = None
        self._set_bandwidth_bucket_from_setting()
        self._folder_lock = threading.Lock()
        self._folder_cache: dict[tuple[str, str], str] = {}
        self._notifier = TrayNotifier()

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

    def _notify_transfer(self, record: TransferRecord) -> None:
        if self.load_preferences().get("showTransferNotifications", "true").lower() != "true":
            return
        if record.status == TransferStatus.FAILED:
            heading = "Upload failed" if record.direction == "upload" else "Download failed"
            detail = record.error or "No additional error details were provided."
            self._notifier.notify(heading, f"{record.filename}: {detail[:220]}")
            return
        heading = "Upload complete" if record.direction == "upload" else "Download complete"
        self._notifier.notify(heading, f"{record.filename} completed successfully")

    def boot_state(self) -> dict:
        return {"configured": self._oauth_config is not None or bool(self._setting("client_id")), "authenticated": self.tokens.load() is not None, "transfers": [record.to_dict() for record in self.store.list()]}

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

    def pick_save_path(self, filename: str) -> str | None:
        import webview
        if not webview.windows:
            raise RuntimeError("The Cirava desktop window is not ready yet. Try again in a moment.")
        window = webview.windows[0]
        selected = window.create_file_dialog(webview.SAVE_DIALOG, save_filename=filename) or []
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

    def create_test_upload(self, parent_id: str = "root", chunk_size: int = 64 * 1024 * 1024) -> list[dict]:
        """Create the single supported test payload: a sparse 20 GiB local file."""
        test_dir = self.data_dir / "test-data"
        test_dir.mkdir(parents=True, exist_ok=True)
        test_file = test_dir / "cirava-speed-test-20gb.bin"
        test_size = 20 * 1024 ** 3
        if not test_file.exists() or test_file.stat().st_size != test_size:
            with test_file.open("wb") as handle:
                handle.seek(test_size - 1)
                handle.write(b"\0")
        return self.create_upload_batch([str(test_file)], parent_id, chunk_size)

    def list_drive_files(self, parent_id: str = "root", query: str | None = None) -> dict:
        shared_drive_id = self._setting("shared_drive_id") or None
        return self._drive().list_all_files(parent_id=parent_id, query=query, shared_drive_id=shared_drive_id)

    def list_shared_drives(self) -> dict:
        return self._drive().list_shared_drives()

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

    def create_upload(self, local_path: str, parent_id: str = "root", chunk_size: int = 64 * 1024 * 1024, relative_path: str | None = None) -> dict:
        path = Path(local_path)
        if not path.is_file():
            raise FileNotFoundError(local_path)
        transfer_id = str(uuid.uuid4())
        active_drive = self._setting("shared_drive_id") or None
        effective_parent = active_drive if parent_id == "root" and active_drive else parent_id
        record = TransferRecord(id=transfer_id, direction="upload", filename=path.name, local_path=str(path), size=path.stat().st_size, drive_parent_id=effective_parent, relative_path=relative_path, status=TransferStatus.QUEUED)
        self.store.upsert(record)
        self._worker_specs[record.id] = ("upload", (chunk_size,))
        self._controls[record.id] = {"stop": threading.Event(), "action": "run"}
        if self.start_workers:
            threading.Thread(target=self._upload_worker, args=(record, chunk_size), daemon=True).start()
        return record.to_dict()

    def create_upload_batch(self, local_paths: list[str], parent_id: str = "root", chunk_size: int = 64 * 1024 * 1024) -> list[dict]:
        expanded: list[Path] = []
        relative_paths: dict[Path, str] = {}
        for raw_path in local_paths:
            path = Path(raw_path)
            if path.is_dir():
                for item in path.rglob("*"):
                    if item.is_file():
                        expanded.append(item)
                        relative_paths[item] = str(item.relative_to(path).parent).replace(".", "")
            elif path.is_file():
                expanded.append(path)
        return [self.create_upload(str(path), parent_id, chunk_size, relative_paths.get(path) or None) for path in expanded]

    def create_download(self, drive_file_id: str, local_path: str, size: int, segment_size: int = 64 * 1024 * 1024, workers: int = 4, expected_md5: str | None = None, conflict_policy: str = "ask") -> dict:
        destination = resolve_conflict(Path(local_path), conflict_policy)
        if destination is None:
            return {"status": "cancelled", "local_path": local_path, "error": "Destination exists and conflict policy is skip"}
        transfer_id = str(uuid.uuid4())
        record = TransferRecord(id=transfer_id, direction="download", filename=destination.name, local_path=str(destination), size=size, drive_file_id=drive_file_id, status=TransferStatus.QUEUED)
        self.store.upsert(record)
        self._worker_specs[record.id] = ("download", (segment_size, workers, expected_md5))
        self._controls[record.id] = {"stop": threading.Event(), "action": "run"}
        if self.start_workers:
            threading.Thread(target=self._download_worker, args=(record, segment_size, workers, expected_md5), daemon=True).start()
        return record.to_dict()

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

    def _stop_transfer(self, transfer_id: str, action: str) -> dict:
        record = self.store.get(transfer_id)
        with self._control_lock:
            control = self._controls.setdefault(transfer_id, {"stop": threading.Event(), "action": action})
            control["action"] = action
            control["stop"].set()  # type: ignore[union-attr]
        record.status = TransferStatus.PAUSED if action == "pause" else TransferStatus.CANCELLED
        self.store.upsert(record)
        return record.to_dict()

    def _restart_transfer(self, transfer_id: str, allowed: set[TransferStatus]) -> dict:
        record = self.store.get(transfer_id)
        if record.status not in allowed:
            raise ValueError(f"Cannot restart transfer in state {record.status.value}")
        spec = self._worker_specs.get(transfer_id)
        if not spec:
            spec = ("upload", (64 * 1024 * 1024,)) if record.direction == "upload" else ("download", (64 * 1024 * 1024, 4, None))
            self._worker_specs[transfer_id] = spec
        with self._control_lock:
            self._controls[transfer_id] = {"stop": threading.Event(), "action": "run"}
        record.status = TransferStatus.QUEUED
        record.error = None
        self.store.upsert(record)
        if self.start_workers:
            kind, args = spec
            target = self._upload_worker if kind == "upload" else self._download_worker
            threading.Thread(target=target, args=(record, *args), daemon=True).start()
        return record.to_dict()

    def _should_continue(self, transfer_id: str) -> bool:
        with self._control_lock:
            control = self._controls.get(transfer_id)
            return bool(control and not control["stop"].is_set())  # type: ignore[union-attr]

    def _stop_action(self, transfer_id: str) -> str:
        with self._control_lock:
            return str(self._controls.get(transfer_id, {}).get("action", "cancel"))

    def _ensure_drive_path(self, client: DriveApiClient, parent_id: str, relative_path: str | None) -> str:
        parent = parent_id
        if not relative_path:
            return parent
        with self._folder_lock:
            for folder_name in Path(relative_path).parts:
                if not folder_name or folder_name == ".":
                    continue
                key = (parent, folder_name)
                if key not in self._folder_cache:
                    existing = client.find_folder(folder_name, parent)
                    self._folder_cache[key] = existing or client.create_folder(folder_name, parent)
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
        with self._control_lock:
            self._upload_slots = threading.Semaphore(value)
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
        return {"available": is_newer_version(manifest.version, current), "version": manifest.version, "current_version": current, "release_notes": list(manifest.release_notes)}

    def stage_update(self, manifest_url: str, current_version: str | None = None) -> dict:
        current = current_version or __version__
        manifest = Updater(self.data_dir / "updates").fetch_manifest(manifest_url)
        if not is_newer_version(manifest.version, current):
            raise ValueError(f"Manifest version {manifest.version} is not newer than Cirava {current}")
        staged = Updater(self.data_dir / "updates").download_and_stage(manifest)
        return {"staged": True, "path": str(staged), "version": manifest.version}

    def restart_staged_update(self, staged_path: str) -> dict:
        updates_dir = (self.data_dir / "updates").resolve()
        candidate = Path(staged_path).resolve()
        if candidate.suffix.lower() != ".exe" or updates_dir not in candidate.parents or not candidate.is_file():
            raise ValueError("Staged update path is not a valid Cirava installer")
        subprocess.Popen([str(candidate), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"], cwd=str(candidate.parent))
        return {"started": True, "path": str(candidate)}

    def _upload_worker(self, record: TransferRecord, chunk_size: int) -> None:
        self._worker_started(record.id)
        acquired = False
        try:
            while self._should_continue(record.id):
                acquired = self._upload_slots.acquire(timeout=0.25)
                if acquired:
                    break
            if not acquired:
                record.status = TransferStatus.PAUSED if self._stop_action(record.id) == "pause" else TransferStatus.CANCELLED
                self.store.upsert(record)
                return
            self._upload_worker_impl(record, chunk_size)
        finally:
            if acquired:
                self._upload_slots.release()
            if record.status in {TransferStatus.COMPLETED, TransferStatus.FAILED}:
                next_workers = self._upload_adaptive.observe(aggregate_throughput_bps=record.average_speed_bps, error=record.status == TransferStatus.FAILED, rate_limited=record.rate_limit_events > 0)
                self._set_setting("upload_concurrency", str(next_workers))
            self._worker_finished(record.id)

    def _upload_worker_impl(self, record: TransferRecord, chunk_size: int) -> None:
        try:
            record.status = TransferStatus.PREPARING
            self.store.upsert(record)
            if not self._should_continue(record.id):
                raise TransferStopped()
            client = self._drive()
            parent_id = self._ensure_drive_path(client, record.drive_parent_id or "root", record.relative_path)
            session = record.upload_session_url or client.create_upload_session({"name": record.filename, "mimeType": mimetypes.guess_type(record.filename)[0] or "application/octet-stream"}, record.size, parent_id)
            record.upload_session_url = session
            if record.upload_session_url and record.bytes_transferred and callable(getattr(client, "query_upload_offset", None)):
                record.bytes_transferred = client.query_upload_offset(record.upload_session_url, record.size)
            self.store.upsert(record)
            record.status = TransferStatus.TRANSFERRING
            self.store.upsert(record)
            if not self._should_continue(record.id):
                raise TransferStopped()
            telemetry = TransferTelemetry()
            def retry_observed(attempt: int, delay: float, error: Exception) -> None:
                self._record_retry(record, attempt, delay, error)
            controller = AdaptiveController(chunk_size=chunk_size, min_chunk=min(16 * 1024 * 1024, chunk_size), max_chunk=256 * 1024 * 1024)
            def upload_progress(done: int, _total: int, _attempt: int) -> None:
                record.status = TransferStatus.TRANSFERRING
                speed, average, peak = telemetry.observe(done)
                record.bytes_transferred = done
                record.speed_bps = speed
                record.average_speed_bps = average
                record.peak_speed_bps = peak
                self.store.update_progress(record.id, bytes_transferred=done, speed_bps=speed, average_speed_bps=average, peak_speed_bps=peak)
            chunk_started = time.monotonic()
            def put_chunk(data: bytes, start: int, end: int, total: int) -> int | None:
                nonlocal chunk_started
                self._throttle(len(data))
                result = client.put_upload_chunk(session, data, start, end, total)
                elapsed = max(time.monotonic() - chunk_started, 1e-6)
                controller.observe(throughput_bps=int(len(data) / elapsed), latency_ms=elapsed * 1000, error_rate=0, rate_limited=False)
                chunk_started = time.monotonic()
                return result
            ResumableUploader(should_continue=lambda: self._should_continue(record.id), retryable_error=self._is_retryable_error, retry_observed=retry_observed).upload(Path(record.local_path), chunk_size, put_chunk, upload_progress, next_chunk_size=lambda: controller.chunk_size, initial_offset=record.bytes_transferred)
            record.bytes_transferred = record.size
            uploaded_file_id = getattr(client, "last_uploaded_file_id", None)
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
                segment_observed=lambda latency_ms, success: concurrency.observe(latency_ms=latency_ms, error=not success),
                retryable_error=self._is_retryable_error,
                retry_observed=lambda attempt, delay, error: self._record_retry(record, attempt, delay, error),
            )
            telemetry = TransferTelemetry()
            def download_progress(done: int, _total: int) -> None:
                speed, average, peak = telemetry.observe(done)
                record.bytes_transferred = done
                record.speed_bps = speed
                record.average_speed_bps = average
                record.peak_speed_bps = peak
                self.store.update_progress(record.id, bytes_transferred=done, speed_bps=speed, average_speed_bps=average, peak_speed_bps=peak)
            def disk_progress(amount: int, elapsed: float) -> None:
                current = self.store.get(record.id)
                record.bytes_transferred = current.bytes_transferred
                record.speed_bps = current.speed_bps
                record.disk_write_bps = int(amount / elapsed)
                self.store.update_progress(record.id, bytes_transferred=record.bytes_transferred, speed_bps=record.speed_bps, disk_write_bps=record.disk_write_bps)
            def get_range(start: int, end: int) -> bytes:
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
        return DriveApiClient(TokenManager(self.tokens, client_id=client_id, client_secret=os.environ.get("CIRAVA_GOOGLE_CLIENT_SECRET", "") or self._stored_client_secret()).access_token)

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

    api._notifier.set_quit_callback(quit_app)
    window.events.closing += lambda: _close_to_tray(window, state, api._notifier)
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


def _close_to_tray(window: object, state: dict[str, bool] | None = None, notifier: object | None = None) -> bool:
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
            return False
        except Exception:
            pass
    return True


if __name__ == "__main__":
    run()
