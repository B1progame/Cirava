from __future__ import annotations

import unittest

from cirava_backend.notifications import TrayNotifier


class TrayNotifierTests(unittest.TestCase):
    def test_tray_is_unregistered_until_windows_accepts_it(self):
        notifier = TrayNotifier()
        self.assertFalse(notifier.registered)

    def test_stop_before_start_is_safe_and_marks_shutdown_requested(self):
        notifier = TrayNotifier()
        notifier.stop()
        self.assertTrue(notifier._stop_requested.is_set())
        self.assertTrue(notifier._stopped.is_set())

    def test_callbacks_can_be_replaced_before_tray_starts(self):
        calls = []
        notifier = TrayNotifier(on_activate=lambda: calls.append("old"))
        notifier.set_activate_callback(lambda: calls.append("new"))
        notifier.set_quit_callback(lambda: calls.append("quit"))
        self.assertEqual(calls, [])
        self.assertIsNotNone(notifier._on_activate)
        self.assertIsNotNone(notifier._on_quit)


if __name__ == "__main__":
    unittest.main()
