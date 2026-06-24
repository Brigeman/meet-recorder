from meetrec.config import load_config
from meetrec.detector.apps import list_running_meeting_apps

_APP_KEYS = {
    "Microsoft Teams": "teams",
    "Zoom": "zoom",
    "Slack": "slack",
    "Discord": "discord",
    "Telegram": "telegram",
    "WhatsApp": "whatsapp",
    "Google Chrome": "browser_meetings",
    "Microsoft Edge": "browser_meetings",
    "Firefox": "browser_meetings",
    "Brave": "browser_meetings",
    "Opera": "browser_meetings",
    "Safari": "browser_meetings",
}


def probe_running_apps() -> set[str]:
    cfg = load_config()
    supported = cfg.get("supported_apps", {})
    running = list_running_meeting_apps()
    return {app for app in running if _is_enabled(app, supported)}


def _is_enabled(app: str, supported: dict) -> bool:
    key = _APP_KEYS.get(app)
    if not key:
        return True
    return supported.get(key, True)
