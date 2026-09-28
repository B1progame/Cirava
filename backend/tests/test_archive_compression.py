import unittest
import json
import hashlib

from cirava_backend.archive_compression import (
    archive_savings,
    is_cirava_archive_marker,
    resolve_installer_url,
    validate_archive_listing,
    safe_archive_member,
    validate_compression_level,
)


class ArchiveCompressionTests(unittest.TestCase):
    def test_compression_level_is_limited_to_7zip_supported_range(self):
        self.assertEqual(validate_compression_level(5), 5)
        with self.assertRaises(ValueError):
            validate_compression_level(10)

    def test_preview_reports_real_byte_and_percent_savings(self):
        self.assertEqual(archive_savings(1000, 250), {"saved_bytes": 750, "saved_percent": 75.0})
        self.assertEqual(archive_savings(100, 150)["saved_bytes"], 0)

    def test_only_archive_with_cirava_marker_is_auto_extractable(self):
        marker = b"CIRAVA_ARCHIVE_V1\n" + json.dumps({"format": 1, "created_by": "Cirava"}).encode()
        self.assertTrue(is_cirava_archive_marker(marker))
        self.assertFalse(is_cirava_archive_marker(b"{}"))

    def test_archive_member_validation_rejects_traversal_and_absolute_paths(self):
        self.assertTrue(safe_archive_member("folder/photo.jpg"))
        self.assertFalse(safe_archive_member("../../startup.cmd"))
        self.assertFalse(safe_archive_member("C:/Windows/file"))

    def test_installer_link_only_accepts_official_7zip_or_maintainer_release_hosts(self):
        metadata = {
            "tag_name": "26.03",
            "draft": False,
            "prerelease": False,
            "author": {"login": "ip7z"},
            "assets": [{
                "name": "7z2603-x64.exe",
                "browser_download_url": "https://github.com/ip7z/7zip/releases/download/26.03/7z2603-x64.exe",
                "digest": f"sha256:{hashlib.sha256(b'official release').hexdigest()}",
            }],
        }
        self.assertEqual(resolve_installer_url(json.dumps(metadata)), {
            "url": "https://github.com/ip7z/7zip/releases/download/26.03/7z2603-x64.exe",
            "sha256": hashlib.sha256(b"official release").hexdigest(),
        })
        metadata["assets"][0]["browser_download_url"] = "https://example.com/7z2603-x64.exe"
        with self.assertRaisesRegex(RuntimeError, "official"):
            resolve_installer_url(json.dumps(metadata))

    def test_installer_release_metadata_requires_a_github_published_digest(self):
        metadata = {
            "tag_name": "26.03",
            "draft": False,
            "prerelease": False,
            "author": {"login": "ip7z"},
            "assets": [{
                "name": "7z2603-x64.exe",
                "browser_download_url": "https://github.com/ip7z/7zip/releases/download/26.03/7z2603-x64.exe",
                "digest": None,
            }],
        }
        with self.assertRaisesRegex(RuntimeError, "SHA-256"):
            resolve_installer_url(json.dumps(metadata))

    def test_extraction_listing_rejects_unsafe_paths_symlinks_and_insufficient_space(self):
        listing = "Path = C:/downloads/a.cirava.zip\nType = zip\n\nPath = folder/file.txt\nSize = 100\nAttributes = A\n"
        self.assertEqual(validate_archive_listing(listing, "C:/downloads/a.cirava.zip", 100), {"files": 1, "bytes": 100})
        with self.assertRaisesRegex(RuntimeError, "unsafe file path"):
            validate_archive_listing(listing.replace("folder/file.txt", "../outside"), "C:/downloads/a.cirava.zip", 1000)
        with self.assertRaisesRegex(RuntimeError, "symbolic links"):
            validate_archive_listing(listing.replace("Attributes = A", "Attributes = lrwxrwxrwx"), "C:/downloads/a.cirava.zip", 1000)
        with self.assertRaisesRegex(RuntimeError, "not enough free disk space"):
            validate_archive_listing(listing, "C:/downloads/a.cirava.zip", 99)


if __name__ == "__main__":
    unittest.main()
