"""Browser meeting heuristics on macOS."""

from __future__ import annotations

import logging
import re

import psutil

from meetrec.detector.titles import match_in_call_title, match_title_hint
from meetrec.platform.macos.apps import BROWSER_NAMES, _normalize_name, resolve_app_for_pid
from meetrec.platform.macos.foreground import probe_foreground

log = logging.getLogger(__name__)

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

_BROWSER_APP_NAMES = {
    "Google Chrome",
    "Microsoft Edge",
    "Firefox",
    "Brave",
    "Opera",
    "Safari",
}


def _prettify_title(raw: str) -> str:
    if not raw:
        return ""
    title = _UNSAFE_CHARS.sub("", raw).strip()
    if len(title) > 60:
        title = title[:60]
    return title.rstrip(". ") or ""


def _browser_pid_for_app(app_name: str | None) -> int:
    if not app_name:
        return 0
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            pid = int(proc.info.get("pid") or 0)
            if not pid:
                continue
            if resolve_app_for_pid(pid) == app_name:
                return pid
        except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError, ValueError):
            continue
    return 0


def _scan_browser_in_call_windows() -> tuple[bool, str | None, str, int]:
    """Find browser windows with strict in-call titles only."""
    from meetrec.platform.macos.windows import get_on_screen_windows

    for window in get_on_screen_windows():
        try:
            title = str(window.get("kCGWindowName", "") or "")
            pid = int(window.get("kCGWindowOwnerPID", -1))
        except (TypeError, ValueError):
            continue
        if pid <= 0 or not title:
            continue
        app = resolve_app_for_pid(pid)
        if app not in _BROWSER_APP_NAMES:
            continue
        in_call_app, in_call = match_in_call_title(title)
        if in_call and in_call_app:
            return True, in_call_app, _prettify_title(title), pid
    return False, None, "", 0


def probe_browser_meeting() -> tuple[bool, str | None, str, int]:
    from meetrec.config import load_config
    from meetrec.platform.macos.audio import is_mic_active

    cfg = load_config()
    if not cfg.get("supported_apps", {}).get("browser_meetings", True):
        return False, None, "", 0

    fg_app, title = probe_foreground()

    if fg_app in _BROWSER_APP_NAMES:
        in_call_app, in_call = match_in_call_title(title)
        if in_call and in_call_app:
            pid = _browser_pid_for_app(fg_app)
            return True, in_call_app, _prettify_title(title), pid

    found, app, tab, pid = _scan_browser_in_call_windows()
    if found:
        return True, app, tab, pid

    # Active mic in a browser — same rule as Windows WASAPI browser sessions.
    if is_mic_active() and fg_app in _BROWSER_APP_NAMES:
        pid = _browser_pid_for_app(fg_app)
        app = match_title_hint(title) or match_in_call_title(title)[0] or fg_app
        return True, app, _prettify_title(title), pid

    return False, None, "", 0
