import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "packaging" / "remove_google_credentials.ps1"


class UninstallCredentialTests(unittest.TestCase):
    def test_cleanup_removes_oauth_client_id_but_keeps_other_settings_and_history(self):
        powershell = shutil.which("powershell.exe")
        if not powershell:
            self.skipTest("Windows PowerShell is only available on Windows")

        with tempfile.TemporaryDirectory() as directory:
            app_data = Path(directory)
            cirava = app_data / "Cirava"
            cirava.mkdir()
            settings = cirava / "settings.json"
            settings.write_text(json.dumps({
                "client_id": "old.apps.googleusercontent.com",
                "bandwidth_limit_mbps": "750",
                "shared_drive_id": "drive-123",
            }), encoding="utf-8")
            (cirava / "tokens.bin").write_bytes(b"token")
            (cirava / "client-credentials.bin").write_bytes(b"secret")

            environment = os.environ.copy()
            environment["APPDATA"] = str(app_data)
            result = subprocess.run(
                [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT)],
                env=environment,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertEqual(json.loads(settings.read_text(encoding="utf-8")), {
                "bandwidth_limit_mbps": "750",
                "shared_drive_id": "drive-123",
            })
            self.assertFalse((cirava / "tokens.bin").exists())
            self.assertFalse((cirava / "client-credentials.bin").exists())


if __name__ == "__main__":
    unittest.main()
