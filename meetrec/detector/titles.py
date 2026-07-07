"""Shared meeting title patterns (platform-neutral)."""

import re

TITLE_HINTS: list[tuple[str, str]] = [
    (r"Microsoft Teams", "Microsoft Teams"),
    (r"Zoom Meeting", "Zoom"),
    (r"\bSlack\b", "Slack"),
    (r"\bHuddle\b", "Slack"),
    (r"\bDiscord\b", "Discord"),
    (r"\bTelegram\b", "Telegram"),
    (r"\bWhatsApp\b", "WhatsApp"),
    (r"Google Meet", "Google Meet"),
    (r"meet\.google\.com", "Google Meet"),
    (r"Teams", "Microsoft Teams"),
    (r"Телемост", "Yandex Telemost"),
    (r"\bTelemost\b", "Yandex Telemost"),
    (r"Webex", "Webex"),
    (r"webex\.com", "Webex"),
    (r"Jitsi Meet", "Jitsi Meet"),
    (r"\bJitsi\b", "Jitsi Meet"),
    (r"GoTo Meeting", "GoTo Meeting"),
    (r"\bWhereby\b", "Whereby"),
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
    (re.compile(r"\bHuddle\b", re.IGNORECASE), "Slack"),
    (re.compile(r"\b(Voice connected|Speaking)\b.*Discord", re.IGNORECASE), "Discord"),
    (
        re.compile(r"(Voice call|Video call|Calling|Incoming call).*Telegram", re.IGNORECASE),
        "Telegram",
    ),
    (
        re.compile(r"(Voice call|Video call|Calling|Incoming call).*WhatsApp", re.IGNORECASE),
        "WhatsApp",
    ),
    (re.compile(r"meet\.google\.com", re.IGNORECASE), "Google Meet"),
    (re.compile(r"Google Meet\s*[-—|]", re.IGNORECASE), "Google Meet"),
    (re.compile(r"Телемост", re.IGNORECASE), "Yandex Telemost"),
    (re.compile(r"\bTelemost\b", re.IGNORECASE), "Yandex Telemost"),
    (re.compile(r"Webex Meeting", re.IGNORECASE), "Webex"),
]


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
