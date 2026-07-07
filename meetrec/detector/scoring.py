"""Scoring engine with sustain timing."""

import hashlib
import time
from dataclasses import dataclass, field

from meetrec.detector.titles import match_title_hint as apps_match_title_hint

_BROWSER_APPS = {
    "Google Chrome",
    "Microsoft Edge",
    "Firefox",
    "Brave",
    "Opera",
    "Safari",
}


def _weights() -> dict[str, int]:
    from meetrec.platform import get_scoring_weights

    return get_scoring_weights()


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


def _allow_meeting_audio_signal(
    snapshot: SignalSnapshot,
    streak: float,
    threshold: float,
) -> bool:
    if snapshot.in_call_title_app:
        return True
    return streak >= threshold


def _foreground_is_meeting_app(snapshot: SignalSnapshot) -> bool:
    fg = snapshot.foreground_app
    if not fg:
        return False
    if fg in _BROWSER_APPS:
        return snapshot.browser_meeting or bool(snapshot.title_hint_app) or bool(
            snapshot.in_call_title_app
        )
    return fg in snapshot.apps_running


def _network_counts(snapshot: SignalSnapshot) -> bool:
    """Background Teams/Zoom sockets are common while idle; require call context."""
    if not snapshot.meeting_network_active:
        return False
    return bool(snapshot.mic_active or snapshot.in_call_title_app)


def _browser_meeting_counts(snapshot: SignalSnapshot) -> bool:
    """An open tab title alone is not a call; require mic or strict in-call title."""
    if not snapshot.browser_meeting:
        return False
    return bool(snapshot.mic_active or snapshot.in_call_title_app)


def _loopback_counts(snapshot: SignalSnapshot) -> bool:
    """System audio playing (music/video) is not a meeting signal by itself."""
    if not snapshot.loopback_active:
        return False
    return bool(
        snapshot.mic_active
        or snapshot.in_call_title_app
        or _browser_meeting_counts(snapshot)
        or snapshot.meeting_capture_active
        or snapshot.meeting_render_active
        or _network_counts(snapshot)
    )


def compute_matched(
    snapshot: SignalSnapshot,
    *,
    cap_streak: float = 0.0,
    ren_streak: float = 0.0,
    audio_streak_threshold: float = 8.0,
) -> list[str]:
    matched = []
    if snapshot.mic_active:
        matched.append("mic_active")
    if _loopback_counts(snapshot):
        matched.append("loopback_active")
    if snapshot.meeting_capture_active and _allow_meeting_audio_signal(
        snapshot,
        cap_streak,
        audio_streak_threshold,
    ):
        matched.append("meeting_app_capture_active")
    if snapshot.meeting_render_active and _allow_meeting_audio_signal(
        snapshot,
        ren_streak,
        audio_streak_threshold,
    ):
        matched.append("meeting_app_render_active")
    if _network_counts(snapshot):
        matched.append("meeting_app_network_active")
    if snapshot.apps_running:
        matched.append("known_meeting_app_running")
    if _foreground_is_meeting_app(snapshot):
        matched.append("known_meeting_app_foreground")
    if snapshot.in_call_title_app:
        matched.append("in_call_title")
    elif snapshot.title_hint_app:
        matched.append("title_hint")
    if _browser_meeting_counts(snapshot):
        matched.append("browser_meeting_context")
    return matched


def compute_score(
    snapshot: SignalSnapshot,
    *,
    cap_streak: float = 0.0,
    ren_streak: float = 0.0,
    audio_streak_threshold: float = 8.0,
) -> int:
    weights = _weights()
    score = 0
    if snapshot.mic_active:
        score += weights["mic_active"]
    if _loopback_counts(snapshot):
        score += weights["loopback_active"]
    if snapshot.meeting_capture_active and _allow_meeting_audio_signal(
        snapshot,
        cap_streak,
        audio_streak_threshold,
    ):
        score += weights["meeting_app_capture_active"]
    if snapshot.meeting_render_active and _allow_meeting_audio_signal(
        snapshot,
        ren_streak,
        audio_streak_threshold,
    ):
        score += weights["meeting_app_render_active"]
    if _network_counts(snapshot):
        score += weights["meeting_app_network_active"]
    if snapshot.apps_running:
        score += weights["known_meeting_app_running"]
    if _foreground_is_meeting_app(snapshot):
        score += weights["known_meeting_app_foreground"]
    if snapshot.in_call_title_app:
        score += weights["in_call_title"]
    elif snapshot.title_hint_app:
        score += weights["title_hint"]
    if _browser_meeting_counts(snapshot):
        score += weights["browser_meeting_context"]
    return score


def primary_app(snapshot: SignalSnapshot) -> str:
    if snapshot.in_call_title_app:
        return snapshot.in_call_title_app
    if snapshot.browser_meeting and snapshot.browser_app:
        return snapshot.browser_app
    if snapshot.foreground_app:
        return snapshot.foreground_app
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
class AudioStreakTracker:
    threshold_seconds: float = 8.0
    _capture_since: float | None = None
    _render_since: float | None = None

    def update(self, snapshot: SignalSnapshot) -> tuple[float, float]:
        now = time.time()
        if snapshot.meeting_capture_active:
            if self._capture_since is None:
                self._capture_since = now
        else:
            self._capture_since = None

        if snapshot.meeting_render_active:
            if self._render_since is None:
                self._render_since = now
        else:
            self._render_since = None

        cap_streak = (now - self._capture_since) if self._capture_since is not None else 0.0
        ren_streak = (now - self._render_since) if self._render_since is not None else 0.0
        return cap_streak, ren_streak


@dataclass
class SustainTracker:
    threshold: int = 70
    web_sustain: float = 2.5
    desktop_sustain: float = 7.0
    desktop_strong_sustain: float = 4.0
    _since: float | None = None
    _last_key: str | None = None

    def required_for(self, snapshot: SignalSnapshot) -> float:
        strong_desktop = (
            snapshot.meeting_capture_active
            or _network_counts(snapshot)
            or bool(snapshot.in_call_title_app)
        )
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
