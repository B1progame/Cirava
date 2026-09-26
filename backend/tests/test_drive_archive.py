import tempfile
import unittest
import zipfile
from pathlib import Path

from cirava_backend.drive_archive import download_folder_zip


class MemoryDrive:
    def __init__(self):
        self.items = {
            "folder": [
                {"id": "nested", "name": "Nested", "mimeType": "application/vnd.google-apps.folder"},
                {"id": "hello", "name": "hello.txt", "mimeType": "text/plain", "size": "5"},
                {"id": "empty", "name": "empty.bin", "mimeType": "application/octet-stream", "size": "0"},
            ],
            "nested": [
                {"id": "world", "name": "world.bin", "mimeType": "application/octet-stream", "size": "6"},
            ],
        }
        self.payloads = {"hello": b"hello", "world": b"world!"}

    def list_all_files(self, *, parent_id):
        return {"files": self.items.get(parent_id, [])}

    def get_range(self, file_id, start, end):
        return self.payloads[file_id][start:end + 1]

    def export_file(self, file_id, mime_type):
        return b"pdf"


class DriveArchiveTests(unittest.TestCase):
    def test_folder_zip_contains_nested_files_and_keeps_empty_files(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "folder.zip"
            result = download_folder_zip(MemoryDrive(), "folder", str(destination), segment_size=256 * 1024, workers=2)
            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["files"], 3)
            with zipfile.ZipFile(destination) as archive:
                self.assertEqual(set(archive.namelist()), {"hello.txt", "empty.bin", "Nested/world.bin"})
                self.assertEqual(archive.read("hello.txt"), b"hello")
                self.assertEqual(archive.read("Nested/world.bin"), b"world!")
                self.assertEqual(archive.read("empty.bin"), b"")

    def test_folder_zip_does_not_overwrite_an_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "folder.zip"
            destination.write_bytes(b"keep")
            with self.assertRaises(FileExistsError):
                download_folder_zip(MemoryDrive(), "folder", str(destination))
            self.assertEqual(destination.read_bytes(), b"keep")

    def test_folder_zip_rejects_missing_folder_id(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                download_folder_zip(MemoryDrive(), "", str(Path(directory) / "folder.zip"))


if __name__ == "__main__":
    unittest.main()
