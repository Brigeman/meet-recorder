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
    from meetrec.platform.macos.apps import resolve_bundle_id, resolve_localized_name

    bundle_id = str(front.bundleIdentifier() or "")
    app = (
        resolve_app_for_pid(pid)
        or resolve_bundle_id(bundle_id)
        or resolve_localized_name(app_name)
        or match_title_hint(title)
        or (app_name or None)
    )
    return app, title


def _front_window_title(pid: int) -> str:
    from meetrec.platform.macos.windows import get_on_screen_windows

    best = ""
    best_layer = 10_000
    for window in get_on_screen_windows():
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
