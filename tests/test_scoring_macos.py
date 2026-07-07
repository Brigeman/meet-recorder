import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS scoring profile")

from meetrec.detector.scoring import (
    SignalSnapshot,
    SustainTracker,
    compute_matched,
    compute_score,
    primary_app,
)
from meetrec.platform.macos.adapter import get_scoring_weights


def test_mac_teams_desktop_call_scores_prompt():
    snap = SignalSnapshot(
        meeting_network_active=True,
        in_call_title_app="Microsoft Teams",
        apps_running={"Microsoft Teams"},
        foreground_app="Microsoft Teams",
        mic_active=True,
        loopback_active=True,
    )
    assert compute_score(snap) >= 70
    matched = compute_matched(snap)
    assert "known_meeting_app_running" in matched
    assert "in_call_title" in matched


def test_mac_teams_open_no_call():
    snap = SignalSnapshot(
        apps_running={"Microsoft Teams"},
        foreground_app="Microsoft Teams",
    )
    assert compute_score(snap) < 70


def test_mac_google_meet_web():
    snap = SignalSnapshot(
        browser_meeting=True,
        mic_active=True,
        in_call_title_app="Google Meet",
        loopback_active=True,
        browser_app="Google Meet",
        foreground_app="Google Chrome",
    )
    assert compute_score(snap) >= 70


def test_mac_scoring_weights_emphasize_context():
    weights = get_scoring_weights()
    assert weights["meeting_app_capture_active"] == 0
    assert weights["known_meeting_app_foreground"] > 10


def test_foreground_cursor_does_not_inflate_score():
    snap = SignalSnapshot(
        apps_running={"Google Chrome", "Safari"},
        foreground_app="Cursor",
    )
    assert compute_score(snap) == get_scoring_weights()["known_meeting_app_running"]


def test_teams_idle_chat_does_not_score_prompt():
    snap = SignalSnapshot(
        meeting_network_active=True,
        meeting_network_count=6,
        apps_running={"Microsoft Teams", "Google Chrome"},
        foreground_app="Cursor",
    )
    assert compute_score(snap) < 70


def test_mac_browser_title_without_mic_does_not_prompt():
    snap = SignalSnapshot(
        browser_meeting=True,
        loopback_active=True,
        title_hint_app="Google Meet",
        apps_running={"Google Chrome"},
        foreground_app="Cursor",
    )
    assert compute_score(snap) < 70


def test_mac_browser_mic_telemost_scores_prompt():
    snap = SignalSnapshot(
        browser_meeting=True,
        browser_app="Yandex Telemost",
        foreground_app="Google Chrome",
        mic_active=True,
        loopback_active=True,
    )
    assert compute_score(snap) >= 70


def test_mac_telegram_desktop_call_scores_prompt():
    snap = SignalSnapshot(
        in_call_title_app="Telegram",
        apps_running={"Telegram"},
        foreground_app="Telegram",
        mic_active=True,
        loopback_active=True,
    )
    assert compute_score(snap) >= 70


def test_primary_app_prefers_in_call_over_foreground():
    snap = SignalSnapshot(
        in_call_title_app="Microsoft Teams",
        foreground_app="Cursor",
    )
    assert primary_app(snap) == "Microsoft Teams"
