from winrec.detector.scoring import (
    SignalSnapshot,
    SustainTracker,
    compute_score,
    compute_matched,
)


def test_teams_desktop_call_scores_prompt():
    snap = SignalSnapshot(
        mic_active=True,
        loopback_active=True,
        apps_running={"Microsoft Teams"},
        foreground_app="Microsoft Teams",
    )
    assert compute_score(snap) >= 70
    assert "mic_active" in compute_matched(snap)


def test_teams_open_no_call():
    snap = SignalSnapshot(
        apps_running={"Microsoft Teams"},
        foreground_app="Microsoft Teams",
    )
    assert compute_score(snap) < 70


def test_youtube_teams_background():
    snap = SignalSnapshot(loopback_active=True, apps_running={"Microsoft Teams"})
    assert compute_score(snap) < 70


def test_mic_only_no_prompt():
    snap = SignalSnapshot(mic_active=True)
    assert compute_score(snap) < 70


def test_google_meet_web():
    snap = SignalSnapshot(
        browser_meeting=True,
        mic_active=True,
        loopback_active=True,
        browser_app="Google Meet",
    )
    assert compute_score(snap) >= 70


def test_sustain_requires_threshold():
    snap = SignalSnapshot(mic_active=True)
    tr = SustainTracker(threshold=70, web_sustain=2.5, desktop_sustain=7.0)
    ok, _ = tr.update(35, snap)
    assert not ok


def test_sustain_web_threshold_config():
    tr = SustainTracker(threshold=70, web_sustain=2.5, desktop_sustain=7.0)
    snap = SignalSnapshot(browser_meeting=True, mic_active=True, loopback_active=True)
    ok1, _ = tr.update(100, snap)
    assert not ok1
    assert tr.web_sustain == 2.5
