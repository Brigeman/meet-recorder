"""Scoring engine with sustain timing."""

import hashlib
import time
from dataclasses import dataclass, field

from winrec.detector.apps import match_title_hint as apps_match_title_hint

WEIGHTS = {
    "mic_active": 25,
    "loopback_active": 20,
    "meeting_app_capture_active": 30,
    "meeting_app_render_active": 20,
    "meeting_app_network_active": 25,
    "in_call_title": 25,
    "known_meeting_app_running": 10,
    "known_meeting_app_foreground": 15,
    "title_hint": 10,
    "browser_meeting_context": 40,
}


@dataclass
class SignalSnapshot:
    mic_active: bool = False
    loopback_active: bool = False
    apps_running: set[str] = field(default_factory=set)
    foreground_app: str | None = None
    title_hint_app: str | None = None
    in_call_title_app: str | None = None
    browser_meeting: bool = False
    browser_app: str | None = None
    browser_tab: str = ""
    browser_pid: int = 0
    window_title: str = ""
    meeting_capture_active: bool = False
    meeting_render_active: bool = False
    meeting_network_active: bool = False
    meeting_network_count: int = 0


def compute_matched(snapshot: SignalSnapshot) -> list[str]:
    matched = []
    if snapshot.mic_active:
        matched.append("mic_active")
    if snapshot.loopback_active:
        matched.append("loopback_active")
    if snapshot.meeting_capture_active:
        matched.append("meeting_app_capture_active")
    if snapshot.meeting_render_active:
        matched.append("meeting_app_render_active")
    if snapshot.meeting_network_active:
        matched.append("meeting_app_network_active")
    if snapshot.apps_running:
        matched.append("known_meeting_app_running")
    if snapshot.foreground_app:
        matched.append("known_meeting_app_foreground")
    if snapshot.in_call_title_app:
        matched.append("in_call_title")
    elif snapshot.title_hint_app:
        matched.append("title_hint")
    if snapshot.browser_meeting:
        matched.append("browser_meeting_context")
    return matched


def compute_score(snapshot: SignalSnapshot) -> int:
    score = 0
    if snapshot.mic_active:
        score += WEIGHTS["mic_active"]
    if snapshot.loopback_active:
        score += WEIGHTS["loopback_active"]
    if snapshot.meeting_capture_active:
        score += WEIGHTS["meeting_app_capture_active"]
    if snapshot.meeting_render_active:
        score += WEIGHTS["meeting_app_render_active"]
    if snapshot.meeting_network_active:
        score += WEIGHTS["meeting_app_network_active"]
    if snapshot.apps_running:
        score += WEIGHTS["known_meeting_app_running"]
    if snapshot.foreground_app:
        score += WEIGHTS["known_meeting_app_foreground"]
    if snapshot.in_call_title_app:
        score += WEIGHTS["in_call_title"]
    elif snapshot.title_hint_app:
        score += WEIGHTS["title_hint"]
    if snapshot.browser_meeting:
        score += WEIGHTS["browser_meeting_context"]
    return score


def primary_app(snapshot: SignalSnapshot) -> str:
    if snapshot.browser_meeting and snapshot.browser_app:
        return snapshot.browser_app
    if snapshot.foreground_app:
        return snapshot.foreground_app
    if snapshot.in_call_title_app:
        return snapshot.in_call_title_app
    if snapshot.title_hint_app:
        return snapshot.title_hint_app
    if snapshot.apps_running:
        return sorted(snapshot.apps_running)[0]
    return "Unknown"


def context_key(snapshot: SignalSnapshot) -> str:
    app = primary_app(snapshot)
    pid = snapshot.browser_pid or 0
    title = snapshot.window_title or snapshot.browser_tab or ""
    h = hashlib.md5(title.encode("utf-8", errors="replace")).hexdigest()[:8]
    return f"{app.lower().replace(' ', '_')}:{pid}:{h}"


def match_title_hint(title: str) -> str | None:
    return apps_match_title_hint(title)


def is_web_context(snapshot: SignalSnapshot) -> bool:
    return snapshot.browser_meeting


@dataclass
class SustainTracker:
    threshold: int = 70
    web_sustain: float = 2.5
    desktop_sustain: float = 7.0
    desktop_strong_sustain: float = 4.0
    _since: float | None = None
    _last_key: str | None = None

    def required_for(self, snapshot: SignalSnapshot) -> float:
        strong_desktop = snapshot.meeting_capture_active or snapshot.meeting_network_active
        if is_web_context(snapshot):
            return self.web_sustain
        if strong_desktop:
            return self.desktop_strong_sustain
        return self.desktop_sustain

    def update(
        self, score: int, snapshot: SignalSnapshot
    ) -> tuple[bool, float]:
        """Return (sustained_ready, sustain_elapsed)."""
        key = context_key(snapshot)
        required = self.required_for(snapshot)
        now = time.time()

        if score < self.threshold:
            self._since = None
            self._last_key = None
            return False, 0.0

        if self._last_key != key:
            self._since = now
            self._last_key = key

        elapsed = now - (self._since or now)
        return elapsed >= required, elapsed
