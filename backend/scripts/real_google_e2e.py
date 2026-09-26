from __future__ import annotations

import hashlib
import os
import sys
import time
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from main import CiravaApi


def wait_for_terminal(api: CiravaApi, transfer_id: str, timeout: float = 240.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = next((item for item in api.list_transfers() if item["id"] == transfer_id), None)
        if row and row["status"] in {"completed", "failed", "cancelled"}:
            return row
        time.sleep(1)
    raise TimeoutError(f"Transfer {transfer_id} did not reach a terminal state in {timeout:.0f}s")


def wait_for_status(api: CiravaApi, transfer_id: str, expected: str, timeout: float = 15.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = next((item for item in api.list_transfers() if item["id"] == transfer_id), None)
        if row and row["status"] == expected:
            return row
        time.sleep(0.1)
    raise TimeoutError(f"Transfer {transfer_id} did not reach {expected!r}")


def pause_if_active(api: CiravaApi, transfer_id: str, timeout: float = 30.0) -> dict:
    """Request a pause, but accept a fast transfer that already finished."""
    deadline = time.monotonic() + timeout
    requested = False
    while time.monotonic() < deadline:
        row = next((item for item in api.list_transfers() if item["id"] == transfer_id), None)
        if row and row["status"] in {"paused", "completed", "failed", "cancelled"}:
            if requested and not api.wait_for_transfer_idle(transfer_id):
                raise TimeoutError(f"Transfer {transfer_id} did not release its worker before restart")
            return row
        if row and not requested:
            api.pause_transfer(transfer_id)
            requested = True
        time.sleep(0.1)
    raise TimeoutError(f"Transfer {transfer_id} did not pause or finish in {timeout:.0f}s")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    if os.environ.get("CIRAVA_RUN_REAL_E2E") != "1":
        print("Refusing to run real Google E2E. Set CIRAVA_RUN_REAL_E2E=1 explicitly.")
        return 2
    client_id = os.environ.get("CIRAVA_E2E_CLIENT_ID", "")
    client_secret = os.environ.get("CIRAVA_E2E_CLIENT_SECRET", "")
    if client_secret:
        os.environ["CIRAVA_GOOGLE_CLIENT_SECRET"] = client_secret
    if not re.fullmatch(r"[0-9]+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com", client_id):
        print("Invalid CIRAVA_E2E_CLIENT_ID. Copy the complete Desktop client ID, including the numeric prefix and hyphen.")
        return 2

    data_dir = Path(os.environ.get("CIRAVA_E2E_DATA_DIR", Path.cwd() / ".cirava-e2e-data"))
    fixture = Path(os.environ.get("CIRAVA_E2E_FIXTURE", data_dir / "cirava-e2e-fixture.bin"))
    fixture.parent.mkdir(parents=True, exist_ok=True)
    if not fixture.exists():
        fixture.write_bytes((b"cirava-e2e\0" * 131072)[:1024 * 1024])
    # Keep every run isolated so a crashed process cannot leave a stale .part or
    # range map that a later segmented writer might accidentally reuse.
    download = fixture.with_name(f"{fixture.stem}-download-{int(time.time())}{fixture.suffix}")

    api = CiravaApi(data_dir=data_dir, start_workers=True)
    api.save_google_configuration(client_id, client_secret or None)
    if api.boot_state().get("authenticated"):
        print("Using the existing protected Cirava OAuth session.")
    else:
        print("Opening Google OAuth. Complete sign-in in the browser, then return here.")
        api.begin_google_login()
    folder = api.create_drive_folder(f"Cirava E2E {int(time.time())}")
    upload = api.create_upload(str(fixture), folder["id"], chunk_size=16 * 1024 * 1024)
    paused_upload = pause_if_active(api, upload["id"])
    restarted_api = CiravaApi(data_dir=data_dir, start_workers=True)
    if paused_upload["status"] == "paused":
        restarted_api.resume_transfer(upload["id"])
    uploaded = wait_for_terminal(restarted_api, upload["id"])
    if uploaded["status"] != "completed" or not uploaded.get("drive_file_id"):
        raise RuntimeError(f"Upload failed: {uploaded.get('error') or uploaded['status']}")

    download_row = restarted_api.create_download(uploaded["drive_file_id"], str(download), fixture.stat().st_size, segment_size=16 * 1024 * 1024, workers=4, conflict_policy="overwrite")
    paused_download = pause_if_active(restarted_api, download_row["id"])
    resumed_api = CiravaApi(data_dir=data_dir, start_workers=True)
    if paused_download["status"] == "paused":
        resumed_api.resume_transfer(download_row["id"])
    downloaded = wait_for_terminal(resumed_api, download_row["id"])
    if downloaded["status"] != "completed":
        raise RuntimeError(f"Download failed: {downloaded.get('error') or downloaded['status']}")
    if sha256(fixture) != sha256(download):
        raise RuntimeError("Downloaded fixture checksum does not match the uploaded fixture")

    workspace_file_id = os.environ.get("CIRAVA_E2E_WORKSPACE_FILE_ID", "").strip()
    workspace_mime_type = os.environ.get("CIRAVA_E2E_WORKSPACE_MIME_TYPE", "application/pdf").strip()
    workspace_output = Path(os.environ.get("CIRAVA_E2E_WORKSPACE_OUTPUT", data_dir / "workspace-export"))
    if workspace_file_id:
        workspace_output.parent.mkdir(parents=True, exist_ok=True)
        exported = resumed_api.export_drive_file(workspace_file_id, str(workspace_output), workspace_mime_type)
        if exported.get("status") != "completed" or not workspace_output.is_file() or workspace_output.stat().st_size == 0:
            raise RuntimeError(f"Workspace export failed: {exported.get('status')}")
        print(f"PASS Workspace export bytes={workspace_output.stat().st_size} mime={workspace_mime_type}")

    print(f"PASS upload={uploaded['drive_file_id']} bytes={fixture.stat().st_size} sha256={sha256(fixture)}")
    print("PASS segmented download and checksum verification")
    print("PASS pause/resume and persistent-database process-restart recovery")
    if not workspace_file_id:
        print("NOTE Workspace export remains opt-in: set CIRAVA_E2E_WORKSPACE_FILE_ID to a native Docs/Sheets/Slides file you own.")
    print("NOTE Rate-limit handling remains covered by protocol tests and is not induced against the account.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
