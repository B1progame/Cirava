import unittest

from main import _close_to_tray


class FakeWindow:
    def __init__(self):
        self.hidden = False

    def hide(self):
        self.hidden = True


class FakeNotifier:
    registered = True

    def __init__(self):
        self.messages = []

    def notify(self, heading, message):
        self.messages.append((heading, message))


class CloseToTrayTests(unittest.TestCase):
    def test_close_hides_window_and_notifies_that_one_transfer_continues(self):
        window, notifier = FakeWindow(), FakeNotifier()
        should_close = _close_to_tray(window, {}, notifier, active_transfer_count=1)
        self.assertFalse(should_close)
        self.assertTrue(window.hidden)
        self.assertEqual(len(notifier.messages), 1)
        self.assertIn("1 transfer is continuing", notifier.messages[0][1])

    def test_close_reports_multiple_background_transfers(self):
        window, notifier = FakeWindow(), FakeNotifier()
        _close_to_tray(window, {}, notifier, active_transfer_count=3)
        self.assertIn("3 transfers are continuing", notifier.messages[0][1])

    def test_unregistered_tray_closes_normally_without_hiding(self):
        window, notifier = FakeWindow(), FakeNotifier()
        notifier.registered = False
        self.assertTrue(_close_to_tray(window, {}, notifier, active_transfer_count=2))
        self.assertFalse(window.hidden)
        self.assertEqual(notifier.messages, [])


if __name__ == "__main__":
    unittest.main()
