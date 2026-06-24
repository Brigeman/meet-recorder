"""Known meeting applications and WebView2 ancestry rules."""

import re

import psutil

PROCESS_TO_APP: dict[str, str] = {
    "ms-teams.exe": "Microsoft Teams",
    "teams.exe": "Microsoft Teams",
    "msteams.exe": "Microsoft Teams",
    "zoom.exe": "Zoom",
    "slack.exe": "Slack",
    "discord.exe": "Discord",
    "telegram.exe": "Telegram",
    "whatsapp.exe": "WhatsApp",
    "chrome.exe": "Google Chrome",
    "msedge.exe": "Microsoft Edge",
    "firefox.exe": "Firefox",
    "brave.exe": "Brave",
    "opera.exe": "Opera",
}

WEBVIEW2 = "msedgewebview2.exe"
WEBVIEW2_VALID_ANCESTORS = {
    "ms-teams.exe",
    "teams.exe",
    "msteams.exe",
    "whatsapp.exe",
}

TITLE_HINTS: list[tuple[str, str]] = [
    (r"Microsoft Teams", "Microsoft Teams"),
    (r"Zoom Meeting", "Zoom"),
    (r"\bSlack\b", "Slack"),
    (r"\bHuddle\b", "Slack"),
    (r"\bDiscord\b", "Discord"),
    (r"\bTelegram\b", "Telegram"),
    (r"\bWhatsApp\b", "WhatsApp"),
    (r"Google Meet", "Google Meet"),
    (r"\bMeet\b", "Google Meet"),
    (r"Teams", "Microsoft Teams"),
]

IN_CALL_TITLE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"(?:\d{1,2}:){1,2}\d{2}\s*\|\s*Microsoft Teams", re.IGNORECASE),
        "Microsoft Teams",
    ),
    (
        re.compile(r"(Calling|Meeting in|In call|Incoming call).*Microsoft Teams", re.IGNORECASE),
        "Microsoft Teams",
    ),
    (re.compile(r"Zoom Meeting", re.IGNORECASE), "Zoom"),
    (re.compile(r"Huddle\b.*Slack", re.IGNORECASE), "Slack"),
    (re.compile(r"\b(Voice connected|Speaking)\b.*Discord", re.IGNORECASE), "Discord"),
]


def resolve_process_name(pid: int) -> str | None:
    try:
        return psutil.Process(pid).name().lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def resolve_app_for_pid(pid: int) -> str | None:
    name = resolve_process_name(pid)
    if not name:
        return None
    if name == WEBVIEW2:
        if webview2_has_valid_ancestor(pid):
            parent_name = _get_parent_process_name(pid)
            return PROCESS_TO_APP.get(parent_name or "", "Microsoft Teams")
        return None
    return PROCESS_TO_APP.get(name)


def match_title_hint(title: str) -> str | None:
    if not title:
        return None
    for pattern, app in TITLE_HINTS:
        if re.search(pattern, title, re.IGNORECASE):
            return app
    return None


def match_in_call_title(title: str) -> tuple[str | None, bool]:
    if not title:
        return None, False
    for pattern, app in IN_CALL_TITLE_PATTERNS:
        if pattern.search(title):
            return app, True
    return None, False


def _get_parent_process_name(pid: int) -> str | None:
    try:
        parent = psutil.Process(pid).parent()
        if parent:
            return parent.name().lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return None


def webview2_has_valid_ancestor(pid: int, depth: int = 8) -> bool:
    current = pid
    for _ in range(depth):
        parent_name = _get_parent_process_name(current)
        if not parent_name:
            return False
        if parent_name in WEBVIEW2_VALID_ANCESTORS:
            return True
        if parent_name in PROCESS_TO_APP and parent_name != WEBVIEW2:
            return parent_name in WEBVIEW2_VALID_ANCESTORS
        try:
            current = psutil.Process(current).ppid()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    return False


def list_running_meeting_apps() -> set[str]:
    apps: set[str] = set()
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            name = (proc.info.get("name") or "").lower()
            pid = proc.info.get("pid")
            if name in PROCESS_TO_APP:
                apps.add(PROCESS_TO_APP[name])
            elif name == WEBVIEW2 and pid and webview2_has_valid_ancestor(pid):
                parent = _get_parent_process_name(pid)
                app = PROCESS_TO_APP.get(parent or "", "Microsoft Teams")
                apps.add(app)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return apps


def list_running_meeting_pids() -> dict[str, list[int]]:
    by_app: dict[str, list[int]] = {}
    for proc in psutil.process_iter(["name", "pid"]):
        try:
            name = (proc.info.get("name") or "").lower()
            pid = proc.info.get("pid")
            if not pid:
                continue
            app: str | None = None
            if name in PROCESS_TO_APP:
                app = PROCESS_TO_APP[name]
            elif name == WEBVIEW2 and webview2_has_valid_ancestor(pid):
                parent = _get_parent_process_name(pid)
                app = PROCESS_TO_APP.get(parent or "", "Microsoft Teams")
            if app:
                by_app.setdefault(app, []).append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return by_app
