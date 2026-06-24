"""Browser meeting heuristics on macOS."""

from __future__ import annotations

import logging
import re

import psutil

from meetrec.detector.titles import match_title_hint
from meetrec.platform.macos.apps import BROWSER_NAMES, _normalize_name
from meetrec.platform.macos.foreground import probe_foreground

log = logging.getLogger(__name__)

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _prettify_title(raw: str) -> str:
    if not raw:
        return ""
    title = _UNSAFE_CHARS.sub("", raw).strip()
    if len(title) > 60:
        title = title[:60]
    return title.rstrip(". ") or ""


def probe_browser_meeting() -> tuple[bool, str | None, str, int]:
    from meetrec.config import load_config

    cfg = load_config()
    if not cfg.get("supported_apps", {}).get("browser_meetings", True):
        return False, None, "", 0

    fg_app, title = probe_foreground()
    hint = match_title_hint(title)
    if hint:
        pid = _browser_pid_for_title(title)
        return True, hint, _prettify_title(title), pid

    for proc in psutil.process_iter(["name", "pid"]):
        try:
            name = _normalize_name(proc.info.get("name"))
            if name not in BROWSER_NAMES:
                continue
            pid = int(proc.info.get("pid") or 0)
            if not pid:
                continue
            proc_title = title if fg_app and fg_app.endswith("Chrome") else ""
            if proc_title and match_title_hint(proc_title):
                return True, match_title_hint(proc_title), _prettify_title(proc_title), pid
        except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError, ValueError):
            continue
    return False, None, "", 0


def _browser_pid_for_title(title: str) -> int:
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            name = _normalize_name(proc.info.get("name"))
            if name in BROWSER_NAMES:
                return int(proc.info.get("pid") or 0)
        except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError, ValueError):
            continue
    return 0
