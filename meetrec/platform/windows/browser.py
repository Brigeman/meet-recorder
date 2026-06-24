"""Browser meeting detection — ported from legacy detector.py."""

import ctypes
import logging
import re
from ctypes import wintypes

import psutil
from comtypes import CLSCTX_ALL, CoCreateInstance
from pycaw.constants import CLSID_MMDeviceEnumerator
from pycaw.pycaw import IAudioSessionControl2, IAudioSessionManager2, IMMDeviceEnumerator

from meetrec.config import load_config
from meetrec.detector.titles import match_title_hint
from meetrec.platform.windows.paths import BROWSER_PROCESSES

log = logging.getLogger(__name__)

_user32 = ctypes.windll.user32
_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

def _get_window_title(pid: int) -> str:
    titles = []

    def _cb(hwnd, _):
        if _user32.IsWindowVisible(hwnd):
            proc_id = wintypes.DWORD()
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
            if proc_id.value == pid:
                length = _user32.GetWindowTextLengthW(hwnd)
                if length:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    _user32.GetWindowTextW(hwnd, buf, length + 1)
                    titles.append(buf.value)
        return True

    _user32.EnumWindows(_WNDENUMPROC(_cb), 0)
    return max(titles, key=len) if titles else ""


def _prettify_title(raw: str) -> str:
    if not raw:
        return ""
    title = _UNSAFE_CHARS.sub("", raw).strip()
    title = title.replace("  ", " ")
    if len(title) > 60:
        title = title[:60]
    return title.rstrip(". ") or ""


def _browser_display_name(exe: str) -> str:
    mapping = {
        "chrome.exe": "Google Chrome",
        "msedge.exe": "Microsoft Edge",
        "firefox.exe": "Firefox",
        "brave.exe": "Brave",
        "opera.exe": "Opera",
    }
    return mapping.get(exe, exe.replace(".exe", "").capitalize())


def get_browser_mic_sessions() -> list[dict]:
    cfg = load_config()
    if not cfg.get("supported_apps", {}).get("browser_meetings", True):
        return []

    try:
        enumerator = CoCreateInstance(
            CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, CLSCTX_ALL
        )
        mic_device = enumerator.GetDefaultAudioEndpoint(1, 0)
        raw = mic_device.Activate(IAudioSessionManager2._iid_, CLSCTX_ALL, None)
        mgr = raw.QueryInterface(IAudioSessionManager2)
        session_enum = mgr.GetSessionEnumerator()
    except Exception as e:
        log.debug("browser mic enum failed: %s", e)
        return []

    active = []
    for i in range(session_enum.GetCount()):
        ctl = session_enum.GetSession(i)
        ctl2 = ctl.QueryInterface(IAudioSessionControl2)
        pid = ctl2.GetProcessId()
        if pid == 0:
            continue
        try:
            name = psutil.Process(pid).name().lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if name not in BROWSER_PROCESSES:
            continue
        if ctl.GetState() != 1:
            continue
        raw_title = _get_window_title(pid)
        if not raw_title:
            try:
                parent = psutil.Process(pid).parent()
                if parent and parent.name().lower() in BROWSER_PROCESSES:
                    raw_title = _get_window_title(parent.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        title = _prettify_title(raw_title)
        # Any active browser mic session counts; title hints only refine the label.
        app_name = match_title_hint(title) or _browser_display_name(name)
        active.append(
            {
                "process": name,
                "pid": pid,
                "tab": title,
                "app": app_name,
            }
        )
    return active


def probe_browser_meeting() -> tuple[bool, str | None, str, int]:
    sessions = get_browser_mic_sessions()
    if not sessions:
        return False, None, "", 0
    s0 = sessions[0]
    return True, s0["app"], s0.get("tab", ""), s0.get("pid", 0)
