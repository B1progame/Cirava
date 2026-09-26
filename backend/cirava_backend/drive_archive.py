from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path, PurePosixPath
import tempfile
import uuid
import zipfile


FOLDER_MIME = "application/vnd.google-apps.folder"
EXPORT_MIMES = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx"),
    "application/vnd.google-apps.presentation": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx"),
    "application/vnd.google-apps.drawing": ("application/pdf", ".pdf"),
}


def _safe_name(name: str) -> str:
    cleaned = PurePosixPath(str(name).replace("\\", "/")).name
    return cleaned if cleaned not in {"", ".", ".."} else "unnamed"


def _collect_files(drive, folder_id: str) -> list[dict]:
    pending = [(folder_id, "")]
    files: list[dict] = []
    while pending:
        parent_id, relative_parent = pending.pop()
        for item in drive.list_all_files(parent_id=parent_id).get("files", []):
            name = _safe_name(item.get("name", "unnamed"))
            relative = str(PurePosixPath(relative_parent) / name) if relative_parent else name
            if item.get("mimeType") == FOLDER_MIME:
                pending.append((str(item.get("id", "")), relative))
            elif item.get("id"):
                files.append({**item, "archive_path": relative})
    return files


def _download_file(drive, item: dict, staging_dir: Path, segment_size: int, workers: int) -> Path:
    archive_path = item["archive_path"]
    mime_type = str(item.get("mimeType") or "application/octet-stream")
    if mime_type in EXPORT_MIMES:
        export_mime, extension = EXPORT_MIMES[mime_type]
        output = staging_dir / f"{uuid.uuid4().hex}{extension}"
        output.write_bytes(drive.export_file(str(item["id"]), export_mime))
        return output

    size = max(0, int(item.get("size") or 0))
    output = staging_dir / uuid.uuid4().hex
    output.touch()
    if size == 0:
        return output
    with output.open("r+b") as handle:
        handle.truncate(size)
    ranges = [(start, min(size - 1, start + segment_size - 1)) for start in range(0, size, segment_size)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(drive.get_range, str(item["id"]), start, end): (start, end) for start, end in ranges}
        for future in as_completed(futures):
            start, end = futures[future]
            payload = future.result()
            expected = end - start + 1
            if len(payload) != expected:
                raise IOError(f"Drive returned an incomplete range for {archive_path}")
            with output.open("r+b") as handle:
                handle.seek(start)
                handle.write(payload)
    return output


def download_folder_zip(drive, folder_id: str, local_path: str, *, segment_size: int = 8 * 1024 * 1024, workers: int = 6) -> dict:
    """Build a ZIP from a Drive folder, fetching independent byte ranges concurrently."""
    if not folder_id:
        raise ValueError("Drive folder ID is required")
    destination = Path(local_path)
    if destination.suffix.lower() != ".zip":
        destination = destination.with_suffix(".zip")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError(destination)
    entries = _collect_files(drive, folder_id)
    staging_dir = Path(tempfile.mkdtemp(prefix="cirava-zip-", dir=destination.parent))
    partial = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.part")
    try:
        staged: dict[str, Path] = {}
        with ThreadPoolExecutor(max_workers=max(1, min(4, workers))) as file_pool:
            futures = {
                file_pool.submit(_download_file, drive, item, staging_dir, max(256 * 1024, segment_size), max(1, min(6, workers))): item["archive_path"]
                for item in entries
            }
            for future in as_completed(futures):
                staged[futures[future]] = future.result()
        with zipfile.ZipFile(partial, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
            for item in entries:
                archive.write(staged[item["archive_path"]], arcname=item["archive_path"])
        partial.replace(destination)
        return {"status": "completed", "local_path": str(destination), "files": len(entries), "bytes": destination.stat().st_size}
    finally:
        partial.unlink(missing_ok=True)
        for path in staging_dir.iterdir():
            path.unlink(missing_ok=True)
        staging_dir.rmdir()
