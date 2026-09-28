import base64
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from io import BytesIO
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from cirava_backend.updater import UpdateManifest, Updater, build_windows_update_script, is_newer_version, requires_major_installer


class UpdaterTests(unittest.TestCase):
    def test_windows_apply_script_logs_failures_bounds_wait_and_verifies_replacement(self):
        script = build_windows_update_script(
            4321,
            r"C:\Users\tester\AppData\Roaming\Cirava\updates\it's.exe",
            r"C:\Users\tester\AppData\Local\Programs\Cirava\Cirava.exe",
            r"C:\Users\tester\AppData\Roaming\Cirava\updates\update-apply.log",
            "a" * 64,
        )
        self.assertIn("update-apply.log", script)
        self.assertIn("AddSeconds(120)", script)
        self.assertIn("[IO.File]::Replace($replacement,$target,$backup,$true)", script)
        self.assertIn("ComputeHash($stream)", script)
        self.assertIn("--cirava-update-ready-file", script)
        self.assertIn("startup confirmation", script)
        self.assertIn("AddSeconds(45)", script)
        self.assertIn("Stop-Process -Id $started.Id", script)
        self.assertIn("Previous executable restored and restarted.", script)
        self.assertIn("catch", script)
        self.assertIn("4321", script)
        self.assertIn("it''s.exe", script)

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell integration test")
    def test_windows_apply_script_rolls_back_if_updated_binary_exits_during_startup(self):
        powershell = Path(os.environ["WINDIR"]) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        system_app = Path(os.environ["WINDIR"]) / "System32" / "whoami.exe"
        previous_app = Path(os.environ["WINDIR"]) / "System32" / "where.exe"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            update_dir = root / "updates"
            install_dir = root / "install"
            update_dir.mkdir()
            install_dir.mkdir()
            source = update_dir / "cirava-update.exe"
            target = install_dir / "Cirava.exe"
            shutil.copy2(system_app, source)
            shutil.copy2(previous_app, target)
            expected = hashlib.sha256(source.read_bytes()).hexdigest()
            previous = hashlib.sha256(target.read_bytes()).hexdigest()
            log = update_dir / "update-apply.log"
            script = build_windows_update_script(99999999, str(source), str(target), str(log), expected)
            encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
            result = subprocess.run(
                [str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), previous)
            self.assertTrue(source.exists())
            log_text = log.read_text(encoding="utf-8-sig")
            self.assertIn("exited before startup confirmation", log_text)
            self.assertIn("Previous executable restored and restarted.", log_text)
            time.sleep(1)

    def test_beta_feed_uses_manifest_from_latest_github_prerelease(self):
        api_payload = json.dumps([
            {"draft": False, "prerelease": True, "body": "## Beta notes\n\n- **Resumable** transfers", "assets": [{"name": "update-manifest.json", "browser_download_url": "https://github.com/acme/cirava/releases/download/v1.2.0-beta.2/update-manifest.json"}]},
            {"draft": False, "prerelease": False, "assets": []},
            {"draft": True, "prerelease": True, "assets": []},
        ]).encode()
        manifest_payload = json.dumps({"version": "1.2.0-beta.2", "url": "https://github.com/acme/cirava/releases/download/v1.2.0-beta.2/Cirava-Setup.exe", "sha256": "a" * 64, "releaseNotes": ["Beta improvements"]}).encode()

        class Response(BytesIO):
            headers = {}
            def geturl(self):
                return "https://api.github.com/repos/acme/cirava/releases?per_page=100" if self.getvalue() == api_payload else "https://github.com/acme/cirava/releases/download/v1.2.0-beta.2/update-manifest.json"

        with patch("cirava_backend.updater.urllib.request.urlopen", side_effect=[Response(api_payload), Response(manifest_payload)]):
            manifest = Updater(Path(tempfile.gettempdir())).fetch_manifest("https://api.github.com/repos/acme/cirava/releases?per_page=100")
        self.assertEqual(manifest.version, "1.2.0-beta.2")
        self.assertEqual(manifest.release_notes, ("Beta improvements",))
        self.assertEqual(manifest.release_notes_markdown, "## Beta notes\n\n- **Resumable** transfers")

    def test_beta_feed_rejects_github_release_without_manifest_asset(self):
        api_payload = json.dumps([{"draft": False, "prerelease": True, "assets": []}]).encode()
        class Response(BytesIO):
            headers = {}
            def geturl(self):
                return "https://api.github.com/repos/acme/cirava/releases?per_page=100"
        with patch("cirava_backend.updater.urllib.request.urlopen", return_value=Response(api_payload)):
            with self.assertRaisesRegex(ValueError, "prerelease"):
                Updater(Path(tempfile.gettempdir())).fetch_manifest("https://api.github.com/repos/acme/cirava/releases?per_page=100")

    def test_semver_comparison_ignores_build_metadata(self):
        self.assertTrue(is_newer_version("1.2.0", "1.1.9"))
        self.assertFalse(is_newer_version("1.2.0", "1.2.0"))
        self.assertFalse(is_newer_version("1.1.9", "1.2.0"))

    def test_only_new_major_versions_require_the_installer(self):
        self.assertFalse(requires_major_installer("1.10.1", "1.0.0"))
        self.assertFalse(requires_major_installer("1.11.6", "1.10.0"))
        self.assertTrue(requires_major_installer("2.0.0", "1.10.1"))
        self.assertFalse(requires_major_installer("1.0.0", "1.10.1"))

    def test_manifest_can_publish_app_update_asset(self):
        manifest = UpdateManifest.from_json(json.dumps({
            "version": "1.10.1",
            "url": "https://example.com/setup.exe",
            "sha256": "a" * 64,
            "appUrl": "https://example.com/Cirava.exe",
            "appSha256": "b" * 64,
        }))
        self.assertEqual(manifest.app_url, "https://example.com/Cirava.exe")
        self.assertEqual(manifest.app_sha256, "b" * 64)

    def test_manifest_preserves_release_markdown_for_the_update_screen(self):
        markdown = "## Highlights\n\n- Added **pause** and `resume`.\n"
        manifest = UpdateManifest.from_json(json.dumps({
            "version": "1.10.1", "url": "https://example.com/setup.exe", "sha256": "a" * 64,
            "releaseNotesMarkdown": markdown,
        }))
        self.assertEqual(manifest.release_notes_markdown, markdown)

    def test_manifest_rejects_malformed_or_oversized_markdown_notes(self):
        for notes in ([], "x" * (64 * 1024 + 1)):
            payload = {"version": "1.2.0", "url": "https://example.com/setup.exe", "sha256": "a" * 64, "releaseNotesMarkdown": notes}
            with self.subTest(notes_type=type(notes).__name__), self.assertRaisesRegex(ValueError, "Markdown"):
                UpdateManifest.from_json(json.dumps(payload))

    def test_app_update_download_uses_app_asset_checksum(self):
        payload = b"standalone-app"
        manifest = UpdateManifest(version="1.10.1", url="https://example.invalid/setup.exe", sha256="a" * 64,
                                 app_url="https://example.invalid/Cirava.exe", app_sha256=hashlib.sha256(payload).hexdigest())

        class Response(BytesIO):
            headers = {}
            def geturl(self):
                return "https://example.invalid/Cirava.exe"

        with tempfile.TemporaryDirectory() as directory, patch("cirava_backend.updater.urllib.request.urlopen", return_value=Response(payload)):
            staged = Updater(Path(directory)).download_app_and_stage(manifest)
            self.assertEqual(staged.read_bytes(), payload)

    def test_stable_release_is_newer_than_same_version_prerelease(self):
        self.assertTrue(is_newer_version("1.0.0", "1.0.0-beta.2"))
        self.assertTrue(is_newer_version("1.0.0-beta.3", "1.0.0-beta.2"))
        self.assertFalse(is_newer_version("1.0.0-beta.2", "1.0.0-beta.10"))

    def test_manifest_fetch_requires_https_before_network_access(self):
        with tempfile.TemporaryDirectory() as directory, patch("cirava_backend.updater.urllib.request.urlopen") as open_url:
            updater = Updater(Path(directory))
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                updater.fetch_manifest("http://example.com/update.json")
            open_url.assert_not_called()

    def test_signed_manifest_requires_a_pinned_trusted_key(self):
        payload = b"cirava-installer"
        digest = hashlib.sha256(payload).hexdigest()
        private = Ed25519PrivateKey.generate()
        public = private.public_key().public_bytes_raw()
        signature = base64.b64encode(private.sign(f"1.2.0|https://example.invalid/cirava.exe|{digest}".encode())).decode()
        manifest = UpdateManifest(version="1.2.0", url="https://example.invalid/cirava.exe", sha256=digest, signature=signature, public_key=base64.b64encode(public).decode())
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "trusted"):
                Updater(Path(directory)).verify_and_stage(payload, manifest)
            self.assertTrue(Updater(Path(directory), trusted_public_key=base64.b64encode(public).decode()).verify_and_stage(payload, manifest).exists())

    def test_download_streams_installer_to_disk_and_verifies_checksum(self):
        payload = b"installer-payload" * 4
        digest = hashlib.sha256(payload).hexdigest()
        manifest = UpdateManifest(version="1.2.0", url="https://example.invalid/cirava.exe", sha256=digest)

        class Response(BytesIO):
            headers = {}
            def geturl(self):
                return "https://example.invalid/cirava.exe"
            def read(self, size=-1):
                if size < 0:
                    raise AssertionError("installer download must be streamed in bounded chunks")
                return super().read(size)

        with tempfile.TemporaryDirectory() as directory, patch("cirava_backend.updater.urllib.request.urlopen", return_value=Response(payload)):
            staged = Updater(Path(directory)).download_and_stage(manifest)
            self.assertEqual(staged.read_bytes(), payload)

    def test_download_rejects_insecure_redirect_target(self):
        payload = b"installer-payload"
        manifest = UpdateManifest(version="1.2.0", url="https://example.invalid/cirava.exe", sha256=hashlib.sha256(payload).hexdigest())

        class Response(BytesIO):
            headers = {}
            def geturl(self):
                return "http://example.invalid/cirava.exe"

        with tempfile.TemporaryDirectory() as directory, patch("cirava_backend.updater.urllib.request.urlopen", return_value=Response(payload)):
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                Updater(Path(directory)).download_and_stage(manifest)

    def test_manifest_checksum_is_required_for_download(self):
        payload = b"cirava-installer"
        manifest = UpdateManifest(version="1.2.0", url="https://example.invalid/cirava.exe", sha256=hashlib.sha256(payload).hexdigest())
        with tempfile.TemporaryDirectory() as directory:
            updater = Updater(Path(directory))
            target = updater.verify_and_stage(payload, manifest)
            self.assertEqual(target.read_bytes(), payload)
            with self.assertRaises(ValueError):
                updater.verify_and_stage(b"tampered", manifest)

    def test_manifest_json_rejects_missing_integrity_fields(self):
        with self.assertRaises(ValueError):
                UpdateManifest.from_json(json.dumps({"version": "1.2.0", "url": "https://example.invalid/cirava.exe"}))

    def test_manifest_rejects_insecure_urls_and_malformed_checksums(self):
        for payload in (
            {"version": "1.2.0", "url": "http://example.com/setup.exe", "sha256": "a" * 64},
            {"version": "1.2.0", "url": "https://example.com/setup.exe", "sha256": "z" * 64},
            {"version": "1.2.0", "url": "file:///setup.exe", "sha256": "a" * 64},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                UpdateManifest.from_json(json.dumps(payload))

    def test_release_notes_must_be_a_list_of_strings(self):
        with self.assertRaises(ValueError):
            UpdateManifest.from_json(json.dumps({
                "version": "1.2.0",
                "url": "https://example.com/setup.exe",
                "sha256": "a" * 64,
                "releaseNotes": "untrusted HTML",
            }))

    def test_signed_manifest_can_be_verified_before_staging(self):
        payload = b"cirava-installer"
        digest = hashlib.sha256(payload).hexdigest()
        private = Ed25519PrivateKey.generate()
        public = private.public_key().public_bytes_raw()
        signed = f"1.2.0|https://example.invalid/cirava.exe|{digest}".encode()
        manifest = UpdateManifest(version="1.2.0", url="https://example.invalid/cirava.exe", sha256=digest, signature=base64.b64encode(private.sign(signed)).decode(), public_key=base64.b64encode(public).decode())
        with tempfile.TemporaryDirectory() as directory:
            trusted_key = base64.b64encode(public).decode()
            self.assertTrue(Updater(Path(directory), trusted_public_key=trusted_key).verify_and_stage(payload, manifest).exists())


if __name__ == "__main__":
    unittest.main()
