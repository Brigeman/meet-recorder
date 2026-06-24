import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows scoring profile")

from meetrec.detector.scoring import SignalSnapshot, compute_score


def test_desktop_teams_in_call_signals_cross_threshold():
    snap = SignalSnapshot(
        meeting_capture_active=True,
        meeting_network_active=True,
        in_call_title_app="Microsoft Teams",
        apps_running={"Microsoft Teams"},
        foreground_app="Microsoft Teams",
    )
    assert compute_score(snap) >= 70


def test_desktop_teams_open_without_call_signals_stays_low():
    snap = SignalSnapshot(
        apps_running={"Microsoft Teams"},
        foreground_app="Microsoft Teams",
        title_hint_app="Microsoft Teams",
    )
    assert compute_score(snap) < 70
