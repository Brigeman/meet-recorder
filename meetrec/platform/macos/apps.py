"""Known meeting applications on macOS."""

from __future__ import annotations

import psutil

PROCESS_TO_APP: dict[str, str] = {
    "zoom.us": "Zoom",
    "zoom": "Zoom",
    "microsoft teams": "Microsoft Teams",
    "teams": "Microsoft Teams",
    "msteams": "Microsoft Teams",
    "slack": "Slack",
    "discord": "Discord",
    "telegram": "Telegram",
    "whatsapp": "WhatsApp",
    "google chrome": "Google Chrome",
    "google chrome helper": "Google Chrome",
    "microsoft edge": "Microsoft Edge",
    "microsoft edge helper": "Microsoft Edge",
    "firefox": "Firefox",
    "brave browser": "Brave",
    "opera": "Opera",
    "safari": "Safari",
    "safariforwebkitdevelopment": "Safari",
}

BROWSER_NAMES = {
    "google chrome",
    "google chrome helper",
    "microsoft edge",
    "microsoft edge helper",
    "firefox",
    "brave browser",
    "opera",
    "safari",
    "safariforwebkitdevelopment",
}


def _normalize_name(name: str | None) -> str:
    return (name or "").strip().lower()


def resolve_process_name(pid: int) -> str | None:
    try:
        return psutil.Process(pid).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def resolve_app_for_pid(pid: int) -> str | None:
    name = _normalize_name(resolve_process_name(pid))
    if not name:
        return None
    return PROCESS_TO_APP.get(name)


def list_running_meeting_apps() -> set[str]:
    apps: set[str] = set()
    for proc in psutil.process_iter(["name"]):
        try:
            name = _normalize_name(proc.info.get("name"))
            app = PROCESS_TO_APP.get(name)
            if app:
                apps.add(app)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return apps


def list_running_meeting_pids() -> dict[str, list[int]]:
    by_app: dict[str, list[int]] = {}
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            name = _normalize_name(proc.info.get("name"))
            pid = proc.info.get("pid")
            if not pid:
                continue
            app = PROCESS_TO_APP.get(name)
            if app:
                by_app.setdefault(app, []).append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return by_app


def is_browser_process(name: str | None) -> bool:
    return _normalize_name(name) in BROWSER_NAMES
