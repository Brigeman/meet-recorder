"""Known meeting applications on macOS."""

from __future__ import annotations

import logging
import time

import psutil

log = logging.getLogger(__name__)

_SCAN_CACHE_TTL = 3.0
_scan_cache: tuple[float, set[str], dict[str, list[int]]] = (0.0, set(), {})

# Skip full psutil scan for processes whose names cannot be meeting apps.
_MEETING_NAME_MARKERS = (
    "teams",
    "zoom",
    "slack",
    "discord",
    "telegram",
    "whatsapp",
    "chrome",
    "edge",
    "firefox",
    "brave",
    "opera",
    "safari",
    "cpthost",
)

PROCESS_TO_APP: dict[str, str] = {
    "zoom.us": "Zoom",
    "zoom": "Zoom",
    "cpthost": "Zoom",
    "msteams": "Microsoft Teams",
    "microsoft teams": "Microsoft Teams",
    "microsoft teams (work or school)": "Microsoft Teams",
    "microsoft teams (work or school) helper": "Microsoft Teams",
    "com.microsoft.teams2": "Microsoft Teams",
    "com.microsoft.teams": "Microsoft Teams",
    "teams": "Microsoft Teams",
    "msteams": "Microsoft Teams",
    "slack": "Slack",
    "discord": "Discord",
    "telegram": "Telegram",
    "telegram helper": "Telegram",
    "telegram desktop": "Telegram",
    "org.telegram.desktop": "Telegram",
    "whatsapp": "WhatsApp",
    "whatsapp helper": "WhatsApp",
    "whatsapp desktop": "WhatsApp",
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

BUNDLE_ID_TO_APP: dict[str, str] = {
    "us.zoom.xos": "Zoom",
    "com.microsoft.teams2": "Microsoft Teams",
    "com.microsoft.teams": "Microsoft Teams",
    "com.tinyspeck.slackmacgap": "Slack",
    "com.hnc.discord": "Discord",
    "org.telegram.desktop": "Telegram",
    "ru.keepcoder.Telegram": "Telegram",
    "net.whatsapp.WhatsApp": "WhatsApp",
    "com.google.Chrome": "Google Chrome",
    "com.microsoft.edgemac": "Microsoft Edge",
    "org.mozilla.firefox": "Firefox",
    "com.brave.Browser": "Brave",
    "com.operasoftware.Opera": "Opera",
    "com.apple.Safari": "Safari",
}

LOCALIZED_NAME_TO_APP: dict[str, str] = {
    "zoom": "Zoom",
    "zoom workplace": "Zoom",
    "zoom.us": "Zoom",
    "microsoft teams": "Microsoft Teams",
    "microsoft teams (work or school)": "Microsoft Teams",
    "slack": "Slack",
    "discord": "Discord",
    "telegram": "Telegram",
    "whatsapp": "WhatsApp",
    "google chrome": "Google Chrome",
    "microsoft edge": "Microsoft Edge",
    "firefox": "Firefox",
    "brave browser": "Brave",
    "opera": "Opera",
    "safari": "Safari",
}

EXE_HINTS: list[tuple[str, str]] = [
    ("/microsoft teams.app/contents/macos/", "Microsoft Teams"),
    ("/microsoft teams.app/contents/helpers/", "Microsoft Teams"),
    ("/zoom.us.app/contents/macos/", "Zoom"),
    ("/zoom.us.app/contents/frameworks/", "Zoom"),
    ("/slack.app/", "Slack"),
    ("/discord.app/", "Discord"),
    ("/telegram.app/", "Telegram"),
    ("/whatsapp.app/", "WhatsApp"),
]

EXCLUDED_BUNDLE_IDS = {
    "us.zoom.updater",
    "com.microsoft.teams2.agent",
    "com.microsoft.teams2.helper",
    "com.microsoft.teams2.notificationcenter",
    "com.microsoft.teams2.modulehost",
}


def _is_auxiliary_process(*, bundle_id: str = "", exe: str | None = None) -> bool:
    if bundle_id in EXCLUDED_BUNDLE_IDS:
        return True
    lowered = (exe or "").lower()
    if "/launchagents/" in lowered or "/launchdaemons/" in lowered:
        return True
    return False

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

DESKTOP_MEETING_APPS = {
    "Microsoft Teams",
    "Zoom",
    "Slack",
    "Discord",
    "Telegram",
    "WhatsApp",
}


def _normalize_name(name: str | None) -> str:
    return (name or "").strip().lower()


def resolve_localized_name(name: str | None) -> str | None:
    return LOCALIZED_NAME_TO_APP.get(_normalize_name(name))


def resolve_bundle_id(bundle_id: str | None) -> str | None:
    if not bundle_id:
        return None
    return BUNDLE_ID_TO_APP.get(bundle_id)


def _match_process_name(name: str | None) -> str | None:
    normalized = _normalize_name(name)
    if not normalized:
        return None
    direct = PROCESS_TO_APP.get(normalized)
    if direct:
        return direct
    for key, app in PROCESS_TO_APP.items():
        if normalized.startswith(key) or key.startswith(normalized):
            return app
    return None


def _match_exe_path(exe: str | None) -> str | None:
    if not exe or _is_auxiliary_process(exe=exe):
        return None
    lowered = exe.lower()
    for fragment, app in EXE_HINTS:
        if fragment in lowered:
            return app
    return None


def resolve_process_name(pid: int) -> str | None:
    try:
        return psutil.Process(pid).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def resolve_app_for_pid(pid: int) -> str | None:
    try:
        proc = psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None

    name = _normalize_name(proc.name())
    app = _match_process_name(name)
    if app:
        return app

    try:
        app = _match_exe_path(proc.exe())
        if app:
            return app
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
        pass

    try:
        from AppKit import NSRunningApplication, NSWorkspace

        for running in NSWorkspace.sharedWorkspace().runningApplications():
            if int(running.processIdentifier()) != pid:
                continue
            bid = str(running.bundleIdentifier() or "")
            if _is_auxiliary_process(bundle_id=bid, exe=proc.exe() if hasattr(proc, "exe") else None):
                return None
            app = resolve_bundle_id(bid) or resolve_localized_name(
                str(running.localizedName() or "")
            )
            if app:
                return app
            break
    except Exception:
        log.debug("resolve_app_for_pid workspace lookup failed pid=%s", pid, exc_info=True)

    return None


def _might_be_meeting_process(name: str | None) -> bool:
    normalized = _normalize_name(name)
    if not normalized:
        return False
    if _match_process_name(normalized):
        return True
    return any(marker in normalized for marker in _MEETING_NAME_MARKERS)


def _cached_meeting_scan() -> tuple[set[str], dict[str, list[int]]]:
    global _scan_cache
    now = time.time()
    if now - _scan_cache[0] < _SCAN_CACHE_TTL:
        return _scan_cache[1], _scan_cache[2]
    apps, by_app = _scan_meeting_processes()
    _scan_cache = (now, apps, by_app)
    return apps, by_app


def _scan_meeting_processes() -> tuple[set[str], dict[str, list[int]]]:
    apps, by_app = _apps_from_workspace()
    apps = set(apps)
    by_app = {app: list(pids) for app, pids in by_app.items()}

    for proc in psutil.process_iter(["name", "pid"]):
        try:
            name = proc.info.get("name")
            pid = int(proc.info.get("pid") or 0)
            if not pid or not _might_be_meeting_process(name):
                continue
            normalized = _normalize_name(name)
            app = _match_process_name(normalized)
            if not app:
                try:
                    app = _match_exe_path(proc.exe())
                except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                    app = None
            if not app:
                continue
            apps.add(app)
            by_app.setdefault(app, [])
            if pid not in by_app[app]:
                by_app[app].append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError, ValueError):
            continue
    return apps, by_app


def _apps_from_workspace() -> tuple[set[str], dict[str, list[int]]]:
    apps: set[str] = set()
    by_app: dict[str, list[int]] = {}
    try:
        from AppKit import NSWorkspace

        for running in NSWorkspace.sharedWorkspace().runningApplications():
            pid = int(running.processIdentifier())
            if pid <= 0:
                continue
            bid = str(running.bundleIdentifier() or "")
            app = resolve_bundle_id(bid) or resolve_localized_name(
                str(running.localizedName() or "")
            )
            if not app:
                continue
            if _is_auxiliary_process(bundle_id=bid):
                continue
            apps.add(app)
            by_app.setdefault(app, []).append(pid)
    except Exception:
        log.debug("workspace meeting app scan failed", exc_info=True)
    return apps, by_app


def list_running_meeting_apps() -> set[str]:
    apps, _ = _cached_meeting_scan()
    return set(apps)


def list_running_meeting_pids() -> dict[str, list[int]]:
    _, by_app = _cached_meeting_scan()
    return {app: list(pids) for app, pids in by_app.items()}


def is_browser_process(name: str | None) -> bool:
    return _normalize_name(name) in BROWSER_NAMES
