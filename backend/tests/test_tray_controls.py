import tempfile
import unittest
from pathlib import Path

from main import CiravaApi
from cirava_backend.models import TransferRecord, TransferStatus
from cirava_backend.notifications import TrayNotifier


class TrayTransferControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.api = CiravaApi(Path(self.temp.name), start_workers=False)

    def tearDown(self):
        self.temp.cleanup()

    def add_transfer(self, transfer_id, direction, status):
        self.api.store.upsert(TransferRecord(
            id=transfer_id,
            direction=direction,
            filename=f"{transfer_id}.bin",
            local_path=str(Path(self.temp.name) / f"{transfer_id}.bin"),
            size=100,
            status=status,
        ))

    def test_pause_all_stops_active_uploads_and_downloads_but_leaves_finished_items_alone(self):
        self.add_transfer("upload", "upload", TransferStatus.TRANSFERRING)
        self.add_transfer("download", "download", TransferStatus.QUEUED)
        self.add_transfer("done", "upload", TransferStatus.COMPLETED)

        self.assertEqual(self.api.pause_all_transfers(), {"paused": 2})
        self.assertEqual(self.api.store.get("upload").status, TransferStatus.PAUSED)
        self.assertEqual(self.api.store.get("download").status, TransferStatus.PAUSED)
        self.assertEqual(self.api.store.get("done").status, TransferStatus.COMPLETED)

    def test_resume_all_restarts_only_paused_transfers(self):
        self.add_transfer("paused", "upload", TransferStatus.PAUSED)
        self.add_transfer("active", "download", TransferStatus.TRANSFERRING)
        self.add_transfer("done", "upload", TransferStatus.COMPLETED)

        self.assertEqual(self.api.resume_all_transfers(), {"resumed": 1})
        self.assertEqual(self.api.store.get("paused").status, TransferStatus.QUEUED)
        self.assertEqual(self.api.store.get("active").status, TransferStatus.TRANSFERRING)
        self.assertEqual(self.api.store.get("done").status, TransferStatus.COMPLETED)

    def test_tray_summary_counts_active_and_paused_transfers(self):
        self.add_transfer("upload", "upload", TransferStatus.TRANSFERRING)
        self.add_transfer("paused", "download", TransferStatus.PAUSED)
        self.add_transfer("done", "upload", TransferStatus.COMPLETED)

        self.assertEqual(self.api.tray_transfer_summary(), {"active": 1, "paused": 1})

    def test_stop_all_cancels_only_active_transfers(self):
        self.add_transfer("active", "upload", TransferStatus.TRANSFERRING)
        self.add_transfer("paused", "download", TransferStatus.PAUSED)
        self.add_transfer("done", "upload", TransferStatus.COMPLETED)

        self.assertEqual(self.api.cancel_all_transfers(), {"cancelled": 1})
        self.assertEqual(self.api.store.get("active").status, TransferStatus.CANCELLED)
        self.assertEqual(self.api.store.get("paused").status, TransferStatus.PAUSED)
        self.assertEqual(self.api.store.get("done").status, TransferStatus.COMPLETED)

    def test_tray_is_marked_ready_only_after_windows_reports_the_icon_visible(self):
        notifier = TrayNotifier()

        class FakeIcon:
            Visible = False

        icon = FakeIcon()
        self.assertFalse(notifier._register_icon_if_visible(icon))
        self.assertFalse(notifier._registered)
        self.assertFalse(notifier._ready.is_set())

        icon.Visible = True
        self.assertTrue(notifier._register_icon_if_visible(icon))
        self.assertTrue(notifier._registered)
        self.assertTrue(notifier._ready.is_set())


if __name__ == "__main__":
    unittest.main()
