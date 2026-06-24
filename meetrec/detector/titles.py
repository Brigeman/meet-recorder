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
