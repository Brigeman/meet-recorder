import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS scoring profile")

from meetrec.detector.scoring import (
    SignalSnapshot,
    SustainTracker,
    compute_matched,
    compute_score,
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
        loopback_active=True,
        browser_app="Google Meet",
        foreground_app="Google Meet",
    )
    assert compute_score(snap) >= 70


def test_mac_scoring_weights_emphasize_context():
    weights = get_scoring_weights()
    assert weights["meeting_app_capture_active"] == 0
    assert weights["known_meeting_app_foreground"] > 10
