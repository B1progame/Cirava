from __future__ import annotations

import json
import hashlib
import hmac
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import urllib.request
import uuid
from urllib.parse import urlparse


MARKER_NAME = "__CIRAVA_ARCHIVE__.json"
MARKER_PREFIX = b"CIRAVA_ARCHIVE_V1\n"
SEVEN_ZIP_RELEASE_API = "https://api.github.com/repos/ip7z/7zip/releases/latest"


def validate_compression_level(level: int | str) -> int:
    try:
        value = int(level)
    except (TypeError, ValueError) as error:
        raise ValueError("Choose a 7-Zip compression level from 1 to 9") from error
    if value < 1 or value > 9:
        raise ValueError("Choose a 7-Zip compression level from 1 to 9")
    return value


def archive_savings(original_bytes: int, archive_bytes: int) -> dict[str, int | float]:
    original = max(0, int(original_bytes))
    archive = max(0, int(archive_bytes))
    saved = max(0, original - archive)
    return {"saved_bytes": saved, "saved_percent": round(saved * 100 / original, 1) if original else 0.0}


def is_cirava_archive_marker(payload: bytes) -> bool:
    if not payload.startswith(MARKER_PREFIX):
        return False
    try:
        metadata = json.loads(payload[len(MARKER_PREFIX):])
        return metadata.get("format") == 1 and metadata.get("created_by") == "Cirava"
    except (ValueError, AttributeError, TypeError):
        return False


def safe_archive_member(name: str) -> bool:
    value = str(name).replace("\\", "/")
    path = PurePosixPath(value)
    return value not in {"", ".", ".."} and "\0" not in value and not path.is_absolute() and not re.match(r"^[A-Za-z]:", value) and ":" not in value and all(part not in {"", ".", ".."} for part in path.parts)


def resolve_installer_url(release_json: str) -> dict[str, str]:
    """Return the official x64 release asset and GitHub-published SHA-256."""
    try:
        release = json.loads(release_json)
    except (TypeError, ValueError) as error:
        raise RuntimeError("Could not read the official 7-Zip release metadata") from error
    if not isinstance(release, dict):
        raise RuntimeError("The latest release metadata is not valid JSON for an official 7-Zip release")
    tag = release.get("tag_name", "")
    author = release.get("author")
    if (
        not isinstance(tag, str)
        or not re.fullmatch(r"\d{2}\.\d{2}", tag)
        or release.get("draft") is not False
        or release.get("prerelease") is not False
        or not isinstance(author, dict)
        or author.get("login") != "ip7z"
    ):
        raise RuntimeError("The latest release metadata is not a stable release from the official 7-Zip project")
    expected_name = f"7z{tag.replace('.', '')}-x64.exe"
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise RuntimeError("The official 7-Zip release has no usable installer assets")
    asset = next((item for item in assets if isinstance(item, dict) and item.get("name") == expected_name), None)
    if not asset:
        raise RuntimeError("The official 7-Zip x64 release asset could not be found")
    url = asset.get("browser_download_url", "")
    expected_path = f"/ip7z/7zip/releases/download/{tag}/{expected_name}"
    if not isinstance(url, str):
        raise RuntimeError("The 7-Zip installer link was not hosted by the official 7-Zip project")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.path != expected_path:
        raise RuntimeError("The 7-Zip installer link was not hosted by the official 7-Zip project")
    digest = asset.get("digest", "")
    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
        raise RuntimeError("GitHub did not provide a valid SHA-256 checksum for the 7-Zip installer")
    return {"url": url, "sha256": digest.split(":", 1)[1].lower()}


def validate_archive_listing(output: str, archive_path: str, free_bytes: int) -> dict[str, int]:
    expected_archive = str(archive_path).replace("\\", "/").casefold()
    files = 0
    total_bytes = 0
    for block in re.split(r"\r?\n\s*\r?\n", output):
        fields = {}
        for line in block.splitlines():
            if " = " in line:
                key, value = line.split(" = ", 1)
                fields[key] = value.strip()
        name = fields.get("Path", "")
        if not name or name.replace("\\", "/").casefold() == expected_archive:
            continue
        if not safe_archive_member(name):
            raise RuntimeError("The archive contains an unsafe file path; extraction was stopped")
        if fields.get("Attributes", "").lower().startswith("l") or fields.get("Symbolic Link"):
            raise RuntimeError("The archive contains symbolic links; extraction was stopped")
        if fields.get("Folder") == "+":
            continue
        try:
            size = max(0, int(fields.get("Size", "0")))
        except ValueError as error:
            raise RuntimeError("The archive has invalid file size metadata") from error
        total_bytes += size
        files += 1
    if files == 0:
        raise RuntimeError("The archive contains no files to extract")
    if total_bytes > max(0, int(free_bytes)):
        raise RuntimeError("There is not enough free disk space to extract this archive")
    return {"files": files, "bytes": total_bytes}


class SevenZip:
    """Per-user 7-Zip installer and archive operations for the optional feature."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.tool_dir = self.data_dir / "tools" / "7zip"
        self.executable = self.tool_dir / "7z.exe"

    def installed(self) -> bool:
        return self.executable.is_file()

    def ensure_installed(self) -> Path:
        if os.name != "nt":
            raise RuntimeError("Cirava's optional 7-Zip integration is currently available on Windows only")
        if self.installed():
            return self.executable
        self.tool_dir.mkdir(parents=True, exist_ok=True)
        installer = self.tool_dir / f"7zip-{uuid.uuid4().hex}.exe"
        try:
            request = urllib.request.Request(SEVEN_ZIP_RELEASE_API, headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "Cirava/1.2",
                "X-GitHub-Api-Version": "2022-11-28",
            })
            with urllib.request.urlopen(request, timeout=20) as response:
                release_json = response.read(1_000_000).decode("utf-8", errors="replace")
            installer_asset = resolve_installer_url(release_json)
            request = urllib.request.Request(installer_asset["url"], headers={"User-Agent": "Cirava/1.2"})
            digest = hashlib.sha256()
            with urllib.request.urlopen(request, timeout=60) as response, installer.open("xb") as output:
                total = 0
                while chunk := response.read(256 * 1024):
                    total += len(chunk)
                    if total > 20 * 1024 * 1024:
                        raise RuntimeError("The 7-Zip installer exceeded the expected size limit")
                    digest.update(chunk)
                    output.write(chunk)
            if not hmac.compare_digest(digest.hexdigest(), installer_asset["sha256"]):
                raise RuntimeError("The downloaded 7-Zip installer did not match GitHub's published SHA-256 checksum")
            result = subprocess.run([str(installer), "/S", f"/D={self.tool_dir}"], capture_output=True, timeout=180, check=False)
            if result.returncode != 0 or not self.installed():
                raise RuntimeError("7-Zip setup did not complete successfully")
            return self.executable
        finally:
            installer.unlink(missing_ok=True)

    def create_archive(self, paths: list[str], level: int = 5) -> dict:
        level = validate_compression_level(level)
        executable = self.ensure_installed()
        selected = [Path(path).resolve(strict=True) for path in paths]
        if not selected:
            raise ValueError("Choose files or folders to compress")
        files: list[Path] = []
        for path in selected:
            if path.is_file():
                files.append(path)
            elif path.is_dir():
                files.extend(item.resolve() for item in path.rglob("*") if item.is_file() and not item.is_symlink())
            else:
                raise ValueError(f"Not a regular file or folder: {path.name}")
        files = list(dict.fromkeys(files))
        if not files:
            raise ValueError("The selected folders contain no files")
        try:
            base = Path(os.path.commonpath([str(path if path.is_dir() else path.parent) for path in selected]))
        except ValueError as error:
            raise ValueError("Choose items on the same drive so their folder structure can be preserved") from error
        archive_dir = self.data_dir / "archive-staging"
        archive_dir.mkdir(parents=True, exist_ok=True)
        stage = archive_dir / uuid.uuid4().hex
        stage.mkdir()
        label = selected[0].stem if selected[0].is_file() and len(selected) == 1 else selected[0].name
        label = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", label).strip(" .") or "Cirava archive"
        archive_path = stage / f"{label}.cirava.zip"
        list_path = stage / "files.lst"
        entries = [path.relative_to(base).as_posix() for path in files]
        for entry in entries:
            if not safe_archive_member(entry):
                raise ValueError("A selected path cannot be represented safely inside the archive")
        total_bytes = sum(path.stat().st_size for path in files)
        marker = MARKER_PREFIX + json.dumps({"format": 1, "created_by": "Cirava", "files": entries}, ensure_ascii=False).encode("utf-8")
        list_path.write_text("\ufeff" + "\n".join(f'"{entry.replace(chr(34), chr(34) * 2)}"' for entry in entries), encoding="utf-8")
        try:
            result = subprocess.run(
                [str(executable), "a", "-tzip", f"-mx={level}", "-mmt=on", "-bso0", "-bsp0", "-y", str(archive_path), f"@{list_path}", f"-si{MARKER_NAME}"],
                cwd=base, input=marker, capture_output=True, timeout=24 * 60 * 60, check=False,
            )
            if result.returncode != 0 or not archive_path.is_file():
                detail = (result.stderr or result.stdout).decode("utf-8", errors="replace")[-500:]
                raise RuntimeError(f"7-Zip could not create the archive: {detail}")
            size = archive_path.stat().st_size
            savings = archive_savings(total_bytes, size)
            return {"archive_path": str(archive_path), "archive_name": archive_path.name, "original_bytes": total_bytes, "archive_bytes": size, **savings, "files": len(files)}
        except Exception:
            archive_path.unlink(missing_ok=True)
            raise
        finally:
            list_path.unlink(missing_ok=True)
            try:
                stage.rmdir()
            except OSError:
                pass

    def extract_cirava_archive(self, archive_path: Path) -> Path | None:
        archive = Path(archive_path)
        if archive.suffix.lower() != ".zip" or not archive.is_file():
            return None
        executable = self.ensure_installed()
        marker = subprocess.run([str(executable), "x", "-so", "-bsp0", str(archive), MARKER_NAME], capture_output=True, timeout=30, check=False)
        if marker.returncode != 0 or not is_cirava_archive_marker(marker.stdout):
            return None
        listing = subprocess.run([str(executable), "l", "-slt", "-bsp0", str(archive)], capture_output=True, timeout=60, check=False)
        if listing.returncode != 0:
            raise RuntimeError("Could not inspect the downloaded archive safely")
        validate_archive_listing(listing.stdout.decode("utf-8", errors="replace"), str(archive), shutil.disk_usage(archive.parent).free)
        folder_name = archive.name[:-len(".cirava.zip")] if archive.name.lower().endswith(".cirava.zip") else archive.stem
        destination = archive.parent / f"{folder_name} (extracted)"
        counter = 2
        while destination.exists():
            destination = archive.parent / f"{folder_name} (extracted {counter})"
            counter += 1
        destination.mkdir()
        try:
            result = subprocess.run([str(executable), "x", "-bso0", "-bsp0", str(archive), f"-o{destination}", "-y"], capture_output=True, timeout=24 * 60 * 60, check=False)
            if result.returncode != 0:
                detail = (result.stderr or result.stdout).decode("utf-8", errors="replace")[-500:]
                raise RuntimeError(f"Could not extract the downloaded Cirava archive: {detail}")
            (destination / MARKER_NAME).unlink(missing_ok=True)
            if os.name == "nt":
                os.startfile(str(destination))
            return destination
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            raise
