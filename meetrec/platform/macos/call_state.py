"""Desktop meeting call-state heuristics on macOS."""

from __future__ import annotations

import logging

from meetrec.detector.titles import match_in_call_title, match_title_hint
from meetrec.platform.macos.apps import DESKTOP_MEETING_APPS, resolve_app_for_pid

log = logging.getLogger(__name__)


def probe_meeting_window_context() -> tuple[str | None, str, bool]:
    """Scan on-screen windows owned by meeting apps for in-call titles."""
    from meetrec.platform.macos.windows import get_on_screen_windows

    for window in get_on_screen_windows():
        try:
            owner = str(window.get("kCGWindowOwnerName", "") or "")
            title = str(window.get("kCGWindowName", "") or "")
            pid = int(window.get("kCGWindowOwnerPID", -1))
        except (TypeError, ValueError):
            continue
        app = resolve_app_for_pid(pid) if pid > 0 else None
        if not app and owner:
            app = match_title_hint(owner)
        if app and app not in DESKTOP_MEETING_APPS and app not in {
            "Google Chrome",
            "Microsoft Edge",
            "Firefox",
            "Brave",
            "Opera",
            "Safari",
        }:
            continue
        in_call_app, in_call = match_in_call_title(title)
        if in_call and in_call_app:
            return in_call_app, title, True
    return None, "", False


def infer_desktop_call_app(
    *,
    apps_running: set[str],
    meeting_network_active: bool,
    meeting_network_pid: int | None,
    mic_active: bool,
    virtual_audio_app: str | None,
) -> str | None:
    if virtual_audio_app:
        return virtual_audio_app
    if meeting_network_active and meeting_network_pid:
        app = resolve_app_for_pid(meeting_network_pid)
        if app in DESKTOP_MEETING_APPS and app in apps_running and mic_active:
            return app
    return None
