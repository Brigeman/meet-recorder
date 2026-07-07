"""Cached on-screen window list — CGWindowListCopyWindowInfo is expensive."""

from __future__ import annotations

import time

_CACHE_TTL = 1.0
_cache: tuple[float, list] = (0.0, [])


def get_on_screen_windows() -> list:
    global _cache
    now = time.time()
    if now - _cache[0] < _CACHE_TTL:
        return _cache[1]

    try:
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGNullWindowID,
            kCGWindowListExcludeDesktopElements,
            kCGWindowListOptionOnScreenOnly,
        )
    except ImportError:
        return []

    options = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
    windows = CGWindowListCopyWindowInfo(options, kCGNullWindowID) or []
    _cache = (now, windows)
    return windows
