from __future__ import annotations

import hashlib
import json
import os
import tempfile
import re
from urllib.parse import urlparse
import urllib.request
import base64
from dataclasses import replace
from dataclasses import dataclass
from pathlib import Path


_VERSION_PATTERN = re.compile(
    r"^[vV]?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


def _version_tuple(value: str) -> tuple[int, int, int, tuple[str, ...] | None]:
    match = _VERSION_PATTERN.fullmatch(value.strip())
    if not match:
        raise ValueError(f"Invalid semantic version: {value}")
    prerelease = tuple(match.group(4).split(".")) if match.group(4) else None
    if prerelease and any(part.isdigit() and len(part) > 1 and part.startswith("0") for part in prerelease):
        raise ValueError(f"Invalid semantic version: {value}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3)), prerelease


def is_newer_version(candidate: str, current: str) -> bool:
    candidate_core = _version_tuple(candidate)
    current_core = _version_tuple(current)
    if candidate_core[:3] != current_core[:3]:
        return candidate_core[:3] > current_core[:3]
    candidate_pre, current_pre = candidate_core[3], current_core[3]
    if candidate_pre is None:
        return current_pre is not None
    if current_pre is None:
        return False
    for candidate_part, current_part in zip(candidate_pre, current_pre):
        if candidate_part == current_part:
            continue
        candidate_numeric = candidate_part.isdigit()
        current_numeric = current_part.isdigit()
        if candidate_numeric and current_numeric:
            return int(candidate_part) > int(current_part)
        if candidate_numeric != current_numeric:
            return not candidate_numeric
        return candidate_part > current_part
    return len(candidate_pre) > len(current_pre)


def requires_major_installer(candidate: str, current: str) -> bool:
    """Use the setup wizard only when moving to a newer major release."""
    return _version_tuple(candidate)[0] > _version_tuple(current)[0]


def _require_https(url: str, label: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"{label} URLs must use HTTPS and must not contain credentials")


def build_windows_update_script(process_id: int, source: str, target: str, log_path: str, expected_sha256: str) -> str:
    """Build a logged, bounded Windows handoff for replacing the running app."""
    if not re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256):
        raise ValueError("A valid SHA-256 checksum is required to apply an update")

    def literal(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    source_literal = literal(source)
    target_literal = literal(target)
    log_literal = literal(log_path)
    digest_literal = literal(expected_sha256.lower())
    return (
        "$ErrorActionPreference='Stop';"
        f"$ciravaPid={int(process_id)};$source={source_literal};$target={target_literal};"
        f"$log={log_literal};$expected={digest_literal};$replacement=$target+'.new';"
        "$backup=$target+'.cirava-backup';$ready=$log+'.startup-ready';$started=$null;"
        "function Write-UpdateLog([string]$message){"
        "[IO.File]::AppendAllText($log,((Get-Date).ToString('o')+' '+$message+[Environment]::NewLine),[Text.Encoding]::UTF8)};"
        "function Get-UpdateHash([string]$path){$stream=[IO.File]::OpenRead($path);$sha=[Security.Cryptography.SHA256]::Create();"
        "try{([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-','').ToLowerInvariant()}"
        "finally{$sha.Dispose();$stream.Dispose()}};"
        "try{Write-UpdateLog 'Handoff started; waiting for Cirava to exit.';"
        "$deadline=(Get-Date).AddSeconds(120);"
        "while(Get-Process -Id $ciravaPid -ErrorAction SilentlyContinue){"
        "if((Get-Date)-gt $deadline){throw 'Cirava did not exit within 120 seconds.'};Start-Sleep -Milliseconds 250};"
        "Write-UpdateLog 'Cirava exited; copying verified update.';"
        "Copy-Item -LiteralPath $source -Destination $replacement -Force;"
        "if((Get-UpdateHash $replacement) -ne $expected){throw 'Staged update changed while it was copied.'};"
        "if(Test-Path -LiteralPath $backup){Remove-Item -LiteralPath $backup -Force};"
        "if(Test-Path -LiteralPath $target){[IO.File]::Replace($replacement,$target,$backup,$true)}"
        "else{[IO.File]::Move($replacement,$target)};"
        "if((Get-UpdateHash $target) -ne $expected){throw 'Replacement executable failed checksum verification.'};"
        "if(Test-Path -LiteralPath $ready){Remove-Item -LiteralPath $ready -Force};"
        "$startInfo=[Diagnostics.ProcessStartInfo]::new();$startInfo.FileName=$target;"
        "$startInfo.WorkingDirectory=(Split-Path -Parent $target);$startInfo.UseShellExecute=$false;"
        "$startInfo.Arguments='--cirava-update-ready-file \"'+$ready+'\"';"
        "$started=[Diagnostics.Process]::Start($startInfo);if(-not $started){throw 'Updated executable could not be started.'};"
        "Write-UpdateLog ('Updated executable launched with PID '+$started.Id+'; waiting for startup confirmation.');"
        "$startupDeadline=(Get-Date).AddSeconds(45);"
        "while(-not (Test-Path -LiteralPath $ready)){"
        "if($started.HasExited){throw ('Updated executable exited before startup confirmation (exit code '+$started.ExitCode+').')};"
        "if((Get-Date)-gt $startupDeadline){throw 'Updated executable did not send startup confirmation within 45 seconds.'};"
        "Start-Sleep -Milliseconds 250};"
        "Write-UpdateLog 'Updated executable confirmed its window loaded.';"
        "Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue;"
        "Remove-Item -LiteralPath $source -Force -ErrorAction SilentlyContinue;"
        "Remove-Item -LiteralPath $ready -Force -ErrorAction SilentlyContinue;"
        "Write-UpdateLog 'Update handoff completed.'"
        "}catch{Write-UpdateLog ('Update handoff failed: '+$_.Exception.Message);if($_.ScriptStackTrace){Write-UpdateLog ('Failure location: '+$_.ScriptStackTrace)};"
        "if($started -and -not $started.HasExited){try{Stop-Process -Id $started.Id -Force -ErrorAction Stop;Write-UpdateLog 'Unconfirmed updated process stopped.'}catch{Write-UpdateLog ('Could not stop unconfirmed updated process: '+$_.Exception.Message)}};"
        "if(Test-Path -LiteralPath $ready){Remove-Item -LiteralPath $ready -Force -ErrorAction SilentlyContinue};"
        "if(Test-Path -LiteralPath $backup){try{"
        "if(Test-Path -LiteralPath $target){Remove-Item -LiteralPath $target -Force};"
        "[IO.File]::Move($backup,$target);"
        "Start-Process -FilePath $target -WorkingDirectory (Split-Path -Parent $target);"
        "Write-UpdateLog 'Previous executable restored and restarted.'"
        "}catch{Write-UpdateLog ('Rollback failed: '+$_.Exception.Message)}};exit 1}"
    )


@dataclass(frozen=True)
class UpdateManifest:
    version: str
    url: str
    sha256: str
    release_notes: tuple[str, ...] = ()
    signature: str | None = None
    public_key: str | None = None
    app_url: str | None = None
    app_sha256: str | None = None
    release_notes_markdown: str = ""

    @classmethod
    def from_json(cls, payload: str | bytes) -> "UpdateManifest":
        data = json.loads(payload)
        version = data.get("version")
        url = data.get("url")
        digest = data.get("sha256", "")
        notes = data.get("releaseNotes", [])
        markdown_notes = data.get("releaseNotesMarkdown", "")
        if not isinstance(version, str) or not version or not isinstance(url, str) or not url or not isinstance(digest, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", digest):
            raise ValueError("Update manifest requires version, url, and a SHA-256 checksum")
        _require_https(url, "Update installer")
        app_url = data.get("appUrl")
        app_sha256 = data.get("appSha256")
        if (app_url is None) != (app_sha256 is None):
            raise ValueError("Update manifest appUrl and appSha256 must be provided together")
        if app_url is not None:
            if not isinstance(app_url, str) or not app_url or not isinstance(app_sha256, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", app_sha256):
                raise ValueError("Update manifest appUrl and appSha256 are invalid")
            _require_https(app_url, "Update app")
        _version_tuple(version)
        if not isinstance(notes, list) or not all(isinstance(note, str) for note in notes):
            raise ValueError("Update release notes must be a list of strings")
        if not isinstance(markdown_notes, str) or len(markdown_notes) > 64 * 1024:
            raise ValueError("Update Markdown release notes must be a string no larger than 64 KiB")
        signature = data.get("signature")
        public_key = data.get("publicKey")
        if (signature is not None and not isinstance(signature, str)) or (public_key is not None and not isinstance(public_key, str)):
            raise ValueError("Update manifest signature fields must be strings")
        return cls(version=version, url=url, sha256=digest.lower(), release_notes=tuple(notes), signature=signature, public_key=public_key, app_url=app_url, app_sha256=app_sha256.lower() if app_sha256 else None, release_notes_markdown=markdown_notes)


class Updater:
    MAX_MANIFEST_BYTES = 1024 * 1024
    MAX_INSTALLER_BYTES = 2 * 1024 * 1024 * 1024
    DOWNLOAD_CHUNK_BYTES = 1024 * 1024

    def __init__(self, staging_dir: Path, trusted_public_key: str | bytes | None = None):
        self.staging_dir = Path(staging_dir)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        self.trusted_public_key = trusted_public_key

    def fetch_manifest(self, url: str) -> UpdateManifest:
        _require_https(url, "Update manifest")
        request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "Cirava-Updater/0.1"})
        with urllib.request.urlopen(request, timeout=20) as response:
            _require_https(response.geturl(), "Update manifest response")
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > self.MAX_MANIFEST_BYTES:
                raise ValueError("Update manifest is too large")
            payload = response.read(self.MAX_MANIFEST_BYTES + 1)
        if len(payload) > self.MAX_MANIFEST_BYTES:
            raise ValueError("Update manifest is too large")
        parsed_url = urlparse(url)
        if parsed_url.hostname == "api.github.com" and re.fullmatch(r"/repos/[^/]+/[^/]+/releases", parsed_url.path):
            releases = json.loads(payload)
            if not isinstance(releases, list):
                raise ValueError("GitHub beta release feed is invalid")
            for release in releases:
                if not isinstance(release, dict) or release.get("draft") or not release.get("prerelease"):
                    continue
                assets = release.get("assets", [])
                asset = next((item for item in assets if isinstance(item, dict) and item.get("name") == "update-manifest.json"), None)
                asset_url = asset.get("browser_download_url") if asset else None
                if not isinstance(asset_url, str):
                    continue
                asset_parsed = urlparse(asset_url)
                if asset_parsed.scheme != "https" or asset_parsed.hostname != "github.com" or "/releases/download/" not in asset_parsed.path:
                    raise ValueError("GitHub beta manifest asset URL is invalid")
                manifest = self.fetch_manifest(asset_url)
                release_body = release.get("body")
                if isinstance(release_body, str) and release_body.strip():
                    return replace(manifest, release_notes_markdown=release_body[:64 * 1024])
                return manifest
            raise ValueError("No published beta prerelease with an update manifest was found")
        return UpdateManifest.from_json(payload)

    def download_and_stage(self, manifest: UpdateManifest) -> Path:
        _require_https(manifest.url, "Update installer")
        handle, temp_name = tempfile.mkstemp(prefix="cirava-update-", suffix=".exe", dir=self.staging_dir)
        os.close(handle)
        staged = Path(temp_name)
        digest = hashlib.sha256()
        total = 0
        try:
            request = urllib.request.Request(manifest.url, headers={"User-Agent": "Cirava-Updater/0.1"})
            with urllib.request.urlopen(request, timeout=120) as response, staged.open("wb") as output:
                _require_https(response.geturl(), "Update installer response")
                content_length = response.headers.get("Content-Length")
                expected_length = int(content_length) if content_length else None
                if expected_length is not None and expected_length > self.MAX_INSTALLER_BYTES:
                    raise ValueError("Update installer exceeds the maximum allowed size")
                while chunk := response.read(self.DOWNLOAD_CHUNK_BYTES):
                    total += len(chunk)
                    if total > self.MAX_INSTALLER_BYTES:
                        raise ValueError("Update installer exceeds the maximum allowed size")
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if expected_length is not None and total != expected_length:
                raise ValueError("Update installer download was incomplete")
            self._verify_integrity(digest.hexdigest(), manifest)
            return staged
        except Exception:
            staged.unlink(missing_ok=True)
            raise

    def download_app_and_stage(self, manifest: UpdateManifest) -> Path:
        if not manifest.app_url or not manifest.app_sha256:
            raise ValueError("This release does not provide an in-place app update; use its installer")
        app_manifest = replace(manifest, url=manifest.app_url, sha256=manifest.app_sha256, signature=None, public_key=None)
        return self.download_and_stage(app_manifest)

    def verify_and_stage(self, payload: bytes, manifest: UpdateManifest) -> Path:
        if len(payload) > self.MAX_INSTALLER_BYTES:
            raise ValueError("Update installer exceeds the maximum allowed size")
        digest = hashlib.sha256(payload).hexdigest().lower()
        self._verify_integrity(digest, manifest)
        handle, temp_name = tempfile.mkstemp(prefix="cirava-update-", suffix=".exe", dir=self.staging_dir)
        os.close(handle)
        staged = Path(temp_name)
        staged.write_bytes(payload)
        return staged

    def _verify_integrity(self, digest: str, manifest: UpdateManifest) -> None:
        if digest != manifest.sha256:
            raise ValueError("Downloaded update failed SHA-256 verification")
        if bool(manifest.signature) != bool(manifest.public_key):
            raise ValueError("Update manifest signature fields must be provided together")
        if manifest.signature and manifest.public_key:
            trusted_key = self.trusted_public_key
            if trusted_key is None:
                raise ValueError("A trusted Ed25519 public key is required to verify signed updates")
            try:
                from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
                trusted_bytes = trusted_key if isinstance(trusted_key, bytes) else base64.b64decode(trusted_key, validate=True)
                manifest_bytes = base64.b64decode(manifest.public_key, validate=True)
                if trusted_bytes != manifest_bytes or len(trusted_bytes) != 32:
                    raise ValueError("Update signing key does not match this Cirava build")
                signature = base64.b64decode(manifest.signature, validate=True)
                Ed25519PublicKey.from_public_bytes(trusted_bytes).verify(signature, f"{manifest.version}|{manifest.url}|{manifest.sha256}".encode())
            except Exception as error:
                raise ValueError("Update manifest signature verification failed") from error
