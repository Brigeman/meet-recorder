import ctypes
from ctypes import wintypes

from meetrec.platform.windows.apps import resolve_app_for_pid
from meetrec.detector.titles import match_title_hint

_user32 = ctypes.windll.user32


def probe_foreground() -> tuple[str | None, str]:
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return None, ""
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    title = _window_title(hwnd)
    app = resolve_app_for_pid(pid.value)
    if not app:
        app = match_title_hint(title)
    return app, title


def _window_title(hwnd) -> str:
    length = _user32.GetWindowTextLengthW(hwnd)
    if not length:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value
