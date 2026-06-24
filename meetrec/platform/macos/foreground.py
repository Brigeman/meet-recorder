"""Foreground window detection on macOS."""

from __future__ import annotations

import logging

from meetrec.detector.titles import match_title_hint
from meetrec.platform.macos.apps import resolve_app_for_pid

log = logging.getLogger(__name__)


def probe_foreground() -> tuple[str | None, str]:
    try:
        from AppKit import NSWorkspace
        from Quartz import (
            kCGNullWindowID,
            kCGWindowListExcludeDesktopElements,
            kCGWindowListOptionOnScreenOnly,
        )
    except ImportError:
        log.debug("pyobjc not available for foreground probe")
        return None, ""

    workspace = NSWorkspace.sharedWorkspace()
    front = workspace.frontmostApplication()
    if front is None:
        return None, ""

    pid = int(front.processIdentifier())
    app_name = str(front.localizedName() or "")
    title = _front_window_title(pid)
    app = resolve_app_for_pid(pid) or match_title_hint(title) or (app_name or None)
    return app, title


def _front_window_title(pid: int) -> str:
    try:
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGNullWindowID,
            kCGWindowListExcludeDesktopElements,
            kCGWindowListOptionOnScreenOnly,
        )
    except ImportError:
        return ""

    options = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
    windows = CGWindowListCopyWindowInfo(options, kCGNullWindowID) or []
    best = ""
    best_layer = 10_000
    for window in windows:
        try:
            owner_pid = int(window.get("kCGWindowOwnerPID", -1))
            if owner_pid != pid:
                continue
            layer = int(window.get("kCGWindowLayer", 0))
            if layer > best_layer:
                continue
            name = str(window.get("kCGWindowName", "") or "")
            if not name:
                continue
            best = name
            best_layer = layer
        except (TypeError, ValueError):
            continue
    return best
