from __future__ import annotations

import os
import sys
import threading
import traceback
import ctypes
from pathlib import Path
from typing import Any, Callable


class _NotifyIconData(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint32),
        ("hWnd", ctypes.c_void_p),
        ("uID", ctypes.c_uint32),
        ("uFlags", ctypes.c_uint32),
        ("uCallbackMessage", ctypes.c_uint32),
        ("hIcon", ctypes.c_void_p),
        ("szTip", ctypes.c_wchar * 128),
        ("dwState", ctypes.c_uint32),
        ("dwStateMask", ctypes.c_uint32),
        ("szInfo", ctypes.c_wchar * 256),
        ("uVersion", ctypes.c_uint32),
        ("szInfoTitle", ctypes.c_wchar * 64),
        ("dwInfoFlags", ctypes.c_uint32),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", ctypes.c_void_p),
    ]


def _shell_notify(action: int, data: _NotifyIconData) -> bool:
    return bool(ctypes.windll.shell32.Shell_NotifyIconW(action, ctypes.byref(data)))


class TrayNotifier:
    """Best-effort Windows tray balloon notifications for the desktop shell."""

    def __init__(self, title: str = "Cirava", on_activate: Callable[[], None] | None = None, on_quit: Callable[[], None] | None = None):
        self.title = title
        self._on_activate = on_activate
        self._on_quit = on_quit
        self._lock = threading.Lock()
        self._hwnd: int | None = None
        self._hicon: Any = None
        self._win32gui: Any = None
        self._win32con: Any = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._error: str | None = None
        self._uid = max(1, os.getpid() & 0x7FFF)
        self._notify_data: _NotifyIconData | None = None
        self._tray_tuple: tuple[object, ...] | None = None

    def set_activate_callback(self, callback: Callable[[], None] | None) -> None:
        self._on_activate = callback

    def set_quit_callback(self, callback: Callable[[], None] | None) -> None:
        self._on_quit = callback

    @property
    def available(self) -> bool:
        return os.name == "nt"

    @property
    def registered(self) -> bool:
        """Whether Windows accepted the icon and the tray thread is live."""
        with self._lock:
            return self._hwnd is not None and self._tray_tuple is not None

    def start(self) -> None:
        if not self.available or self._thread and self._thread.is_alive():
            return
        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run, name="cirava-tray", daemon=True)
        self._thread.start()
        # Wait briefly so a broken tray registration is detected during startup
        # instead of silently leaving the app without its system-tray entry.
        self._ready.wait(timeout=3)

    def notify(self, heading: str, message: str) -> None:
        with self._lock:
            if self._hwnd is None or self._win32gui is None or self._win32con is None:
                return
            try:
                data = self._notify_data
                if data is None:
                    return
                data.uFlags = self._win32gui.NIF_INFO
                data.szInfo = str(message)[:255]
                data.szInfoTitle = str(heading)[:63]
                data.dwInfoFlags = self._win32gui.NIIF_INFO
                _shell_notify(1, data)
            except Exception:
                return

    def stop(self) -> None:
        with self._lock:
            if self._hwnd is not None and self._win32gui and self._win32con:
                try:
                    # Use pywin32 for registration removal as well as add.
                    # It owns the Windows NOTIFYICONDATAW packing and avoids
                    # the size/alignment rejection seen with ctypes on some
                    # Windows builds.
                    if self._tray_tuple is not None:
                        self._win32gui.Shell_NotifyIcon(self._win32gui.NIM_DELETE, self._tray_tuple)
                    else:
                        data = self._notify_data
                        if data is not None:
                            _shell_notify(2, data)
                    # DestroyWindow is thread-affine; ask the tray thread to
                    # perform it so PumpMessages can exit cleanly.
                    self._win32gui.PostMessage(self._hwnd, self._win32con.WM_CLOSE, 0, 0)
                except Exception:
                    pass
                self._hwnd = None
                self._tray_tuple = None

    def _run(self) -> None:
        try:
            import win32api
            import win32con
            import win32gui

            self._win32gui, self._win32con = win32gui, win32con
            instance = win32api.GetModuleHandle(None)
            # A process-specific class avoids stale registrations after an
            # update/restart while the shell is still removing the old icon.
            class_name = f"CiravaTrayWindow_{os.getpid()}"

            def wnd_proc(hwnd: int, message: int, _wparam: int, _lparam: int) -> int:
                if message == win32con.WM_USER + 20 and _lparam in {win32con.WM_LBUTTONUP, win32con.WM_LBUTTONDBLCLK}:
                    callback = self._on_activate
                    if callback:
                        try:
                            callback()
                        except Exception:
                            pass
                    return 0
                if message == win32con.WM_USER + 20 and _lparam == win32con.WM_RBUTTONUP:
                    menu = win32gui.CreatePopupMenu()
                    win32gui.AppendMenu(menu, win32con.MF_STRING, 1, "Open Cirava")
                    win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, "")
                    win32gui.AppendMenu(menu, win32con.MF_STRING, 2, "Exit Cirava")
                    point = win32gui.GetCursorPos()
                    win32gui.SetForegroundWindow(hwnd)
                    command = win32gui.TrackPopupMenu(menu, win32con.TPM_RETURNCMD | win32con.TPM_NONOTIFY, point[0], point[1], 0, hwnd, None)
                    win32gui.PostMessage(hwnd, win32con.WM_NULL, 0, 0)
                    win32gui.DestroyMenu(menu)
                    if command == 1 and self._on_activate:
                        self._on_activate()
                    elif command == 2 and self._on_quit:
                        self._on_quit()
                    return 0
                if message == win32con.WM_DESTROY:
                    win32gui.PostQuitMessage(0)
                return win32gui.DefWindowProc(hwnd, message, _wparam, _lparam)

            window_class = win32gui.WNDCLASS()
            window_class.hInstance = instance
            window_class.lpszClassName = class_name
            window_class.lpfnWndProc = wnd_proc
            try:
                win32gui.RegisterClass(window_class)
            except win32gui.error:
                pass
            hwnd = win32gui.CreateWindow(class_name, self.title, 0, 0, 0, 0, 0, 0, 0, instance, None)
            if not hwnd:
                raise RuntimeError("Windows did not create the Cirava tray message window")
            icon_candidates = [
                Path(getattr(sys, "_MEIPASS", "")) / "cirava.ico",
                Path(__file__).resolve().parents[2] / "packaging" / "cirava.ico",
            ]
            hicon = None
            for icon_path in icon_candidates:
                if icon_path.is_file():
                    try:
                        hicon = win32gui.LoadImage(0, str(icon_path), win32con.IMAGE_ICON, 0, 0, win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE)
                        break
                    except Exception:
                        continue
            hicon = hicon or win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
            with self._lock:
                self._hwnd, self._hicon = hwnd, hicon
            tray_tuple = (
                hwnd,
                self._uid,
                win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
                win32con.WM_USER + 20,
                hicon,
                self.title[:127],
            )
            # pywin32's wrapper is the supported packing for this structure.
            # The previous ctypes call created the hidden message window but
            # returned FALSE from NIM_ADD, leaving no visible tray icon.
            if not win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, tray_tuple):
                raise RuntimeError("Windows rejected the Cirava tray icon")
            with self._lock:
                self._tray_tuple = tray_tuple

            notify = _NotifyIconData()
            notify.cbSize = ctypes.sizeof(_NotifyIconData)
            notify.hWnd = hwnd
            notify.uID = self._uid
            notify.uFlags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
            notify.uCallbackMessage = win32con.WM_USER + 20
            notify.hIcon = hicon
            notify.szTip = self.title[:127]
            with self._lock:
                self._notify_data = notify
            self._ready.set()
            win32gui.PumpMessages()
        except Exception as error:
            self._error = str(error)
            self._ready.set()
            try:
                log_path = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Cirava" / "tray.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(traceback.format_exc(), encoding="utf-8")
            except Exception:
                pass
            return
