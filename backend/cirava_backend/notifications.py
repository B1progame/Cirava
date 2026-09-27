from __future__ import annotations

import os
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Callable


class TrayNotifier:
    """Windows notification-area icon and balloon notifications for Cirava."""

    def __init__(self, title: str = "Cirava", on_activate: Callable[[], None] | None = None, on_quit: Callable[[], None] | None = None):
        self.title = title
        self._on_activate = on_activate
        self._on_quit = on_quit
        self._on_navigate: Callable[[str], None] | None = None
        self._on_transfer_action: Callable[[str], None] | None = None
        self._get_transfer_summary: Callable[[], dict[str, int]] | None = None
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._stop_requested = threading.Event()
        self._stopped = threading.Event()
        self._notify_icon: Any = None
        self._notify_timer: Any = None
        self._registered = False
        self._error: str | None = None

    def set_activate_callback(self, callback: Callable[[], None] | None) -> None:
        self._on_activate = callback

    def set_quit_callback(self, callback: Callable[[], None] | None) -> None:
        self._on_quit = callback

    def set_navigation_callback(self, callback: Callable[[str], None] | None) -> None:
        self._on_navigate = callback

    def set_transfer_callbacks(
        self,
        action: Callable[[str], None] | None,
        summary: Callable[[], dict[str, int]] | None,
    ) -> None:
        self._on_transfer_action = action
        self._get_transfer_summary = summary

    @property
    def available(self) -> bool:
        return os.name == "nt"

    @property
    def registered(self) -> bool:
        """Whether Windows accepted the icon and the message loop is alive."""
        with self._lock:
            return self._registered and self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if not self.available or self._thread and self._thread.is_alive():
            return
        self._ready.clear()
        self._stopped.clear()
        self._stop_requested.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run, name="cirava-tray", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)

    def notify(self, heading: str, message: str) -> None:
        with self._lock:
            icon = self._notify_icon
        if icon is None:
            return
        try:
            from System.Windows.Forms import ToolTipIcon
            icon.ShowBalloonTip(5000, str(heading)[:63], str(message)[:255], ToolTipIcon.Info)
        except Exception:
            return

    def _register_icon_if_visible(self, icon: Any) -> bool:
        """Publish readiness only after WinForms reports the shell icon visible."""
        try:
            visible = bool(icon.Visible)
        except Exception:
            visible = False
        if not visible:
            return False
        with self._lock:
            self._notify_icon = icon
            self._registered = True
        self._ready.set()
        return True

    def stop(self) -> None:
        self._stop_requested.set()
        thread = self._thread
        if thread is None or not thread.is_alive():
            self._stopped.set()
        elif threading.current_thread() is not thread:
            self._stopped.wait(timeout=2)

    def _run(self) -> None:
        pythoncom = None
        icon = None
        menu = None
        timer = None
        try:
            import pythoncom as com
            pythoncom = com
            # WinForms controls and notification callbacks need an STA thread.
            pythoncom.CoInitialize()
            import clr
            clr.AddReference("System.Windows.Forms")
            clr.AddReference("System.Drawing")
            from System.Drawing import Icon, SystemIcons
            from System.Windows.Forms import (
                Application,
                ContextMenuStrip,
                DialogResult,
                MessageBox,
                MessageBoxButtons,
                MessageBoxIcon,
                NotifyIcon,
                ToolStripSeparator,
                Timer,
                ToolStripMenuItem,
            )

            icon = NotifyIcon()
            icon_path = Path(getattr(sys, "_MEIPASS", "")) / "cirava.ico"
            if not icon_path.is_file():
                icon_path = Path(__file__).resolve().parents[2] / "packaging" / "cirava.ico"
            try:
                icon.Icon = Icon(str(icon_path)) if icon_path.is_file() else SystemIcons.Application
            except Exception:
                icon.Icon = SystemIcons.Application
            icon.Text = self.title[:63]

            menu = ContextMenuStrip()
            open_item = ToolStripMenuItem("Open Cirava")
            pages_item = ToolStripMenuItem("Open page")
            for label, page in (
                ("Home", "home"),
                ("Drive", "drive"),
                ("Transfers", "transfers"),
                ("History", "history"),
                ("Scan && repeat", "scan"),
                ("Diagnostics", "diagnostics"),
                ("Settings", "settings"),
                ("About", "about"),
            ):
                page_item = ToolStripMenuItem(label)

                def navigate(_sender: object, _event: object, target: str = page) -> None:
                    callback = self._on_navigate
                    if callback:
                        try:
                            callback(target)
                        except Exception:
                            pass

                page_item.Click += navigate
                pages_item.DropDownItems.Add(page_item)

            pause_item = ToolStripMenuItem("Pause active transfers")
            resume_item = ToolStripMenuItem("Resume paused transfers")
            cancel_item = ToolStripMenuItem("Stop active transfers…")
            exit_item = ToolStripMenuItem("Exit Cirava")

            def run_transfer_action(action: str) -> None:
                callback = self._on_transfer_action
                if not callback:
                    return

                def invoke() -> None:
                    try:
                        callback(action)
                    except Exception as error:
                        self.notify("Transfer control failed", str(error))

                threading.Thread(target=invoke, name="cirava-tray-transfer-control", daemon=True).start()

            pause_item.Click += lambda _sender, _event: run_transfer_action("pause")
            resume_item.Click += lambda _sender, _event: run_transfer_action("resume")

            def cancel_active(_sender: object, _event: object) -> None:
                summary = self._get_transfer_summary() if self._get_transfer_summary else {"active": 0}
                active = int(summary.get("active", 0))
                if not active:
                    return
                answer = MessageBox.Show(
                    f"Stop {active} active transfer(s)? They will be marked cancelled and can be retried later from Transfers.",
                    "Stop active transfers?",
                    MessageBoxButtons.YesNo,
                    MessageBoxIcon.Warning,
                )
                if answer == DialogResult.Yes:
                    run_transfer_action("cancel")

            cancel_item.Click += cancel_active

            def refresh_transfer_items(_sender: object, _event: object) -> None:
                try:
                    summary = self._get_transfer_summary() if self._get_transfer_summary else {"active": 0, "paused": 0}
                    active, paused = int(summary.get("active", 0)), int(summary.get("paused", 0))
                except Exception:
                    active = paused = 0
                pause_item.Text = f"Pause active transfers ({active})"
                pause_item.Enabled = active > 0
                resume_item.Text = f"Resume paused transfers ({paused})"
                resume_item.Enabled = paused > 0
                cancel_item.Text = f"Stop active transfers ({active})…"
                cancel_item.Enabled = active > 0

            menu.Opening += refresh_transfer_items

            def activate(_sender: object, _event: object) -> None:
                callback = self._on_activate
                if callback:
                    try:
                        callback()
                    except Exception:
                        pass

            def quit(_sender: object, _event: object) -> None:
                callback = self._on_quit
                if callback:
                    try:
                        callback()
                    except Exception:
                        pass
                self._stop_requested.set()

            open_item.Click += activate
            exit_item.Click += quit
            menu.Items.Add(open_item)
            menu.Items.Add(pages_item)
            menu.Items.Add(ToolStripSeparator())
            menu.Items.Add(pause_item)
            menu.Items.Add(resume_item)
            menu.Items.Add(cancel_item)
            menu.Items.Add(ToolStripSeparator())
            menu.Items.Add(exit_item)
            icon.ContextMenuStrip = menu
            icon.Click += activate
            icon.DoubleClick += activate

            timer = Timer()
            timer.Interval = 200
            registration_attempts = 0

            def ensure_icon_registered(_sender: object, _event: object) -> None:
                nonlocal registration_attempts
                if self._registered:
                    return
                registration_attempts += 1
                try:
                    # NotifyIcon creates its shell handle on the WinForms STA
                    # message loop. Checking Visible before Application.Run()
                    # can falsely report a registration failure.
                    icon.Visible = True
                    if self._register_icon_if_visible(icon):
                        return
                except Exception:
                    pass
                if registration_attempts < 20:
                    return
                error = RuntimeError("Windows did not show Cirava's notification-area icon after 20 message-loop retries")
                self._error = str(error)
                try:
                    log_path = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Cirava" / "tray.log"
                    log_path.parent.mkdir(parents=True, exist_ok=True)
                    log_path.write_text(str(error), encoding="utf-8")
                except Exception:
                    pass
                self._ready.set()
                timer.Stop()
                Application.ExitThread()

            def stop_message_loop(_sender: object, _event: object) -> None:
                if not self._stop_requested.is_set():
                    return
                timer.Stop()
                icon.Visible = False
                Application.ExitThread()

            timer.Tick += stop_message_loop
            timer.Tick += ensure_icon_registered
            with self._lock:
                self._notify_timer = timer
            timer.Start()
            Application.Run()
        except Exception as error:
            self._error = str(error)
            self._ready.set()
            try:
                log_path = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Cirava" / "tray.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(traceback.format_exc(), encoding="utf-8")
            except Exception:
                pass
        finally:
            try:
                if timer is not None:
                    timer.Stop()
                    timer.Dispose()
                if icon is not None:
                    icon.Visible = False
                    icon.Dispose()
                if menu is not None:
                    menu.Dispose()
            except Exception:
                pass
            with self._lock:
                self._registered = False
                self._notify_icon = None
                self._notify_timer = None
            if pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
            self._stopped.set()
